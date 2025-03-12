import os
import logging
from platform import python_version, platform
import roifile
import cv2 as cv
import numpy as np
import igraph as ig
import pandas as pd
import imageio.v3 as iio
import imageio.config as iio_config
from imageio import __version__ as imageio_version
from imageio_ffmpeg import __version__ as imageioffmpeg_version
from general import general_functions as gf
from version import __version__ as vlabapp_version


def write_ImagejRoi(filename, mask, graph=None):
    """
    Convert a mask to a list of roifile.ImagejRoi (for ImageJ) and save to file as ImageJ ROI set (.zip).

    Note: labeled regions in the mask are assumed to be formed of
    a unique connected component, without holes.
    If a region (pixels with same mask_id) consists in multiple components,
    each component will be saved with the same name (`frame`_`mask_id`), wich
    may generate undefined behavior.
    For regions with holes, holes will simply be ignored.

    Parameters
    ----------
    filename: str
        output filename (should be .zip).
    mask: ndarray
        a 3D (TYX) 16bit unsigned integer (uint16) numpy array.
    graph: igraph.Graph
        the corresponding cell tracking graph, with vertex attribute `cell_track`.
        Used to add cell track to ROI names.

    Returns
    -------
    tuple (holes, multicomponents)
        `holes` and `mutlicomponents` are boolean and will be True if at least one region contains a hole or multiple components respectively (i.e. the saved ImageJ ROI setlist of roifile.ImagejRoi does not correspond to the input mask).
    """

    def expand_point(v, dv1, dv2, P):
        """
        Expand the vertex v to points at distance P.
        Adapted from https://forum.opencv.org/t/findcontours-around-pixels/4702/8

        Parameters
        ----------
        P: np.array (4,2)
            expanding points
        v: np.array (2,)
             single vertex
        dv1: np.array (2,)
             incoming vector (from previous vertex to vertex `v`)
        dv2: np.array (2,)
             outgoing vector (from `v` to next vertex)

        Returns
        -------
        list of np.array (2,)
             expanded points
        """
        j = int(np.arctan2(*dv1) // (np.pi / 2))
        k = -int(-np.arctan2(*dv2) // (np.pi / 2))
        return [v + P[(i + j) % 4] for i in range((k - j) % 4 + 1)]

    def expand_contour(path):
        """
        Expand a contour found by cv2.findContours with distances P.
        Contour with points oriented counter-clockwise (resp. clockwise)
        will be expanded towards the exterior (resp. interior).

        Adapted from https://forum.opencv.org/t/findcontours-around-pixels/4702/8

        Parameters
        ----------
        path: np.array (n,2)
             `n` points forming a single, not-closed contour.

        Returns
        -------
        np.array (m,2)
            `m` points forming the single expanded, not-closed contour.
        """
        P = np.array(((-1, -1), (-1, 1), (1, 1), (1, -1))) / 2  # contour of the pixels
        if path.shape[0] == 1:  # single point
            return path + P
        dV1 = np.diff(np.vstack((path[-1], path)), axis=0)
        dV2 = np.diff(np.vstack((path, path[0])), axis=0)

        return np.array([p for u, dv1, dv2 in zip(path, dV1, dV2) for p in expand_point(u, dv1, dv2, P)])

    logging.getLogger(__name__).info('Converting segmentation mask to ImageJ ROI set')
    if graph:
        # build map from <frame>_<mask_id> to <cell_track>_<frame>_<mask_id>
        map_cell_tracks = {str(frame)+'_'+str(mask_id): str(track)+'_'+str(frame)+'_'+str(mask_id) for track, frame, mask_id in zip(graph.vs['cell_track'], graph.vs['frame'], graph.vs['mask_id'])}

    multicomponents = False
    holes = False
    rois = []
    for t in range(mask.shape[0]):
        logging.getLogger(__name__).debug('Converting frame %s/%s', t, mask.shape[0])
        mask_2D = mask[t, :, :]
        mask_2D_test = np.zeros((mask_2D.shape[0], mask_2D.shape[1]), mask_2D.dtype)
        for n in np.unique(mask_2D):
            if n > 0:
                # search for external contours (i.e. ignore holes)
                contours, _ = cv.findContours(image=(mask_2D==n).astype('uint8'),
                                              mode=cv.RETR_EXTERNAL,
                                              method=cv.CHAIN_APPROX_NONE)

                # In mask_2D_test, fill polygon defined by external contours (to later compare with input mask_2D and detect holes).
                cv.fillPoly(img=mask_2D_test,
                            pts=contours,
                            color=int(n))

                if len(contours) > 1:
                    multicomponents = True

                contours = [expand_contour(np.squeeze(path, axis=1)) for path in contours]

                for i, contour in enumerate(contours):
                    if graph:
                        rois.append(roifile.ImagejRoi.frompoints(contour+0.5, name=map_cell_tracks[str(t)+'_'+str(n)], c=0, z=0, t=t))
                    else:
                        rois.append(roifile.ImagejRoi.frompoints(contour+0.5, name=str(t)+'_'+str(n), c=0, z=0, t=t))

        if not np.array_equal(mask_2D, mask_2D_test):
            holes = True

    logging.getLogger(__name__).info('Saving ImageJ ROI set to %s', filename)
    roifile.roiwrite(filename, rois, mode='w')

    return (holes, multicomponents)


def write_edge_list(filename, graph):
    """
    Save a cell tracking graph as a list of edges in tab-separated values format (.tsv)


    Parameters
    ----------
    filename: str
        output filename (should be .tsv).
    graph: igraph.Graph
        a cell tracking graph, with vertex attribute `cell_track`.

    """
    logging.getLogger(__name__).info('Converting cell tracking graph to list of edges')
    ecount = graph.ecount()
    nrows = ecount + len(graph.vs.select(_degree=0))
    data = np.empty((nrows, 9), dtype=np.uint32)
    for i, e in enumerate(graph.es):
        v1 = graph.vs[e.source]
        v2 = graph.vs[e.target]
        data[i, 0] = v1['frame']
        data[i, 1] = v1['mask_id']
        data[i, 2] = v1['area']
        data[i, 3] = v2['frame']
        data[i, 4] = v2['mask_id']
        data[i, 5] = v2['area']
        data[i, 6] = e['overlap_area']
        data[i, 7] = v1['cell_track']
        data[i, 8] = 0
    # add isolated vertices
    for i, v1 in enumerate(graph.vs.select(_degree=0)):
        data[ecount+i, 0] = v1['frame']
        data[ecount+i, 1] = v1['mask_id']
        data[ecount+i, 2] = v1['area']
        data[ecount+i, 3] = 0
        data[ecount+i, 4] = 0
        data[ecount+i, 5] = 0
        data[ecount+i, 6] = 0
        data[ecount+i, 7] = v1['cell_track']
        data[ecount+i, 8] = 1
    df = pd.DataFrame(data, columns=['frame1', 'mask_id1', 'area1', 'frame2', 'mask_id2', 'area2', 'overlap_area', 'cell_track_id', 'isolated_vertex'])
    # sort
    df = df.sort_values(by=['cell_track_id', 'frame1', 'mask_id1'])
    # convert to str
    df = df.astype(str)
    # add ids
    df['id1'] = df['cell_track_id'] + '_' + df['frame1'] + '_' + df['mask_id1']
    df['id2'] = df['cell_track_id'] + '_' + df['frame2'] + '_' + df['mask_id2']
    # set missing values for isolated vertices:
    df.loc[df['isolated_vertex'] == '1', ['id2', 'frame2', 'mask_id2', 'area2', 'overlap_area']] = None
    # save
    df = df[['id1', 'frame1', 'mask_id1', 'area1', 'id2', 'frame2', 'mask_id2', 'area2', 'overlap_area', 'cell_track_id']]
    logging.getLogger(__name__).info('Saving cell tracking graph to %s', filename)
    df.to_csv(filename, sep='\t', na_rep='nan', index=False)


def write_dot(filename, graph):
    """
    Save a cell tracking graph in graphviz format (.dot).


    Parameters
    ----------
    filename: str
        output filename (should be .dot).
    graph: igraph.Graph
        a cell tracking graph, with vertex attribute `cell_track`.

    """
    logging.getLogger(__name__).info('Saving cell tracking graph to %s', filename)
    with open(filename, 'w') as f:
        f.write('digraph {\n')
        f.write(' rankdir="BT"\n')
        f.write(' nodesep=0.2\n')
        f.write(' outputorder=edgesfirst\n')
        f.write(' node[shape=rect margin="0.05,0.055" height=0.3 color=darkgray fillcolor=grey95 style=filled]\n')
        f.write(' edge[arrowhead=none color=darkgray]\n')
        for v in graph.vs:
            f.write(' ' + str(v.index) + '[\n')
            f.write('  label="' + str(v['cell_track']) + '_' + str(v['frame']) + '_' + str(v['mask_id']) + '"\n')
            f.write('  frame=' + str(v['frame']) + '\n')
            f.write('  mask_id=' + str(v['mask_id']) + '\n')
            f.write('  area=' + str(v['area']) + '\n')
            f.write('  cell_track=' + str(v['cell_track']) + '\n')
            f.write('  ];\n')
        for e in graph.es:
            f.write(' ' + str(e.source) + ' -> ' + str(e.target) + ' [\n')
            f.write('  overlap_area=' + str(e['overlap_area']) + '\n')
            f.write('  ];\n')
        for frame1 in np.sort(np.unique(graph.vs['frame'])):
            # To align vertices with same frame
            f.write(' {rank=same ' + ' '.join([str(v.index) for v in graph.vs.select(frame=frame1)]) + ' }\n')
        f.write('}')


def convert_mask_and_graph(mask_path, graph_path, output_path, output_basename, output_mask_format=None, output_graph_format=None, one_file_per_cell_track=False):
    """
    Load mask (`mask_path`), cell tracking graph (`graph_path`).
    Save the selected mask and cell tracking graph into `output_path` directory.

    Parameters
    ----------
    mask_path: str
        segmentation mask (uint16 tif or ome-tif image with axes T,Y,X).
    graph_path: str
        cell tracking graph (graphmlz format).
    output_path: str
        output directory.
    output_basename: str
        output basename. Output file will be saved as `output_path`/`output_basename`.`extension`, with extension determined by the output format.
    output_mask_format: str
        output format for mask. Possible values for `output_mask_format`:
            None or '': do not save mask.
            'imagejroi': save as ImageJ ROI set format (.zip)
    output_graph_format: str
        output format for graph. Possible values for `output_graph_format`:
            None or '': do not save graph.
            'tsv': save as tab-separated value format (.tsv).
            'dot': save as graphviz dot format (.dot).
            'graphml': save as graphml format (.graphml).
    one_file_per_cell_track: bool
        output one file per cell track if True or one file with all cell tracks otherwise.
    """

    ###########################
    # Setup logging
    ###########################
    logger = logging.getLogger(__name__)
    logger.info('FILe CONVERSION MODULE')
    if not os.path.isdir(output_path):
        logger.debug('creating: %s', output_path)
        os.makedirs(output_path)

    logger.setLevel(logging.DEBUG)

    logger.info('System info:')
    logger.info('- platform: %s', platform())
    logger.info('- python version: %s', python_version())
    logger.info('- VLabApp version: %s', vlabapp_version)
    logger.info('- numpy version: %s', np.__version__)
    logger.info('- opencv version: %s', cv.__version__)
    logger.info('- igraph version: %s', ig.__version__)
    logger.info('- roifile version: %s', roifile.__version__)

    logger.info('Input mask path: %s', mask_path)
    logger.info('Input graph path: %s', graph_path)

    ###########################
    # Load mask and graph
    ###########################

    # Load mask
    logger.debug('loading %s', mask_path)
    try:
        mask = gf.Image(mask_path)
        mask.imread()
        mask = mask.get_TYXarray()
    except Exception:
        logger.exception('Error loading mask %s', mask_path)
        raise

    # Load graph
    logger.debug('loading %s', graph_path)
    graph = gf.load_cell_tracking_graph(graph_path, mask.dtype)

    ###########################
    # Evaluate cell tracks
    ###########################
    logger.debug('finding connected components')
    components = graph.connected_components(mode='weak')
    for i, cmp in enumerate(components):
        graph.vs[cmp]['cell_track'] = i

    if not one_file_per_cell_track:
        ###########################
        # save all
        ###########################
        # save graph
        if output_graph_format:
            if output_graph_format == 'tsv':
                output_file = os.path.join(output_path, output_basename+'.tsv')
                write_edge_list(output_file, graph)
            elif output_graph_format == 'dot':
                output_file = os.path.join(output_path, output_basename+'.dot')
                write_dot(output_file, graph)
            elif output_graph_format == 'graphml':
                # adjust attributes
                graph2 = graph.copy()
                for a in graph2.attributes():
                    if a.startswith('VLabApp:Annotation'):
                        del graph2[a]
                for a in graph2.es.attributes():
                    if a not in ['overlap_area']:
                        del graph2.es[a]
                for a in graph2.vs.attributes():
                    if a not in ['frame', 'mask_id', 'area', 'cell_track']:
                        del graph2.vs[a]
                graph2.vs['name'] = [str(track)+'_'+str(frame)+'_'+str(mask_id) for track, frame, mask_id in zip(graph2.vs['cell_track'], graph2.vs['frame'], graph2.vs['mask_id'])]
                output_file = os.path.join(output_path, output_basename+'.graphml')
                logger.info('Saving cell tracking graph to %s', output_file)
                graph2.write_graphml(output_file)

        # save mask
        error_message = ''
        if output_mask_format:
            output_file = os.path.join(output_path, output_basename+'.zip')
            holes, multicomponents = write_ImagejRoi(output_file, mask, graph)
            if holes:
                error_message += 'Regions in the segmentation mask contain holes, which cannot be exported to ImageJ ROI file format. Only outer boundaries were saved (holes were ignored). '
            if multicomponents:
                error_message += 'Regions in the segmentation mask consist in multiple disconnected components. For each region, all components will be saved with same ROI name, which may generate undefined behavior in ImageJ. '

        if error_message:
            raise ValueError(error_message.strip())

    else:
        ###########################
        # save one file per cell track
        ###########################
        holes = False
        multicomponents = False
        for i, cmp in enumerate(components):
            logger.info('Filtering graph and mask (cell track $s)', i)
            output_basename_ct = f"{output_basename}_{i:04d}"
            # filter graph
            graph_ct = graph.subgraph(cmp)
            # filter mask
            mask_ct = mask.copy()
            for t in range(mask_ct.shape[0]):
                mask_ct[t][np.logical_not(np.isin(mask_ct[t], graph_ct.vs.select(frame=t)['mask_id']))] = 0

            # save graph
            if output_graph_format:
                if output_graph_format == 'tsv':
                    output_file = os.path.join(output_path, output_basename_ct+'.tsv')
                    write_edge_list(output_file, graph_ct)
                elif output_graph_format == 'dot':
                    output_file = os.path.join(output_path, output_basename_ct+'.dot')
                    write_dot(output_file, graph_ct)
                elif output_graph_format == 'graphml':
                    # adjust attributes
                    graph_ct2 = graph_ct.copy()
                    for a in graph_ct2.attributes():
                        if a.startswith('VLabApp:Annotation'):
                            del graph_ct2[a]
                    for a in graph_ct2.es.attributes():
                        if a not in ['overlap_area']:
                            del graph_ct2.es[a]
                    for a in graph_ct2.vs.attributes():
                        if a not in ['frame', 'mask_id', 'area', 'cell_track']:
                            del graph_ct2.vs[a]
                    graph_ct2.vs['name'] = [str(track)+'_'+str(frame)+'_'+str(mask_id) for track, frame, mask_id in zip(graph_ct2.vs['cell_track'], graph_ct2.vs['frame'], graph_ct2.vs['mask_id'])]

                    output_file = os.path.join(output_path, output_basename_ct+'.graphml')
                    logger.info('Saving cell tracking graph to %s', output_file)
                    graph_ct2.write_graphml(output_file)

            # save mask
            if output_mask_format:
                output_file = os.path.join(output_path, output_basename_ct+'.zip')
                h, m = write_ImagejRoi(output_file, mask_ct, graph_ct)
                holes = holes or h
                multicomponents = multicomponents or m

        error_message = ''
        if holes:
            error_message += 'Regions in the segmentation mask contain holes, which cannot be exported to ImageJ ROI file format. Only outer boundaries were saved (holes were ignored). '
        if multicomponents:
            error_message += 'Regions in the segmentation mask consist in multiple disconnected components. For each region, all components will be saved with same ROI name, which may generate undefined behavior in ImageJ. '
        if error_message:
            raise ValueError(error_message.strip())


def convert_image_mask_to_lossy_preview(image_path, output_path, output_basename, output_format, projection_type, projection_zrange, input_is_mask, colors, autocontrast, quality, fps):
    """
    Load image or mask (`image_path`).
    Save as mp4 movie or jpg image into `output_path` directory.

    Parameters
    ----------
    image_path: str
        input image or mask path. Should be ome-tiff or nd2 image.
    output_path: str
        output directory.
    output_basename: str
        output basename. Output file will be saved as `output_path`/`output_basename`.mp4.
    output_format: str
        output format. Possible formats:
            mp4: save all as mp4
            jpg: save all as jpg
            auto: save to mp4 if more than one time frame, save to jpg otherwise.
    projection_type : str
        type of projection to perform if the image is a z-stack
    projection_zrange: int or (int,int) or None
        the range of z sections to use for projection.
        If zrange is None, use all z sections.
        If zrange is an integer, use all z sections in the interval [z_best-zrange,z_best+zrange]
        where z_best is the Z corresponding to best focus.
        If zrange is tuple (zmin,zmax), use all z sections in the interval [zmin,zmax].
    input_is_mask: bool
        consider input as segmentation mask (True), image (False), or try to detect automatically (None)
    colors: list of (r, g, b) tuples
        colors to use when combining channels.
    autocontrast: bool
        rescale image intensities to maximize contrast.
    quality: int
        output quality. Lowest quality is 0, highest is 10.
    fps: int
        output number of frames per seconds.
    """

    ###########################
    # Setup logging
    ###########################
    logger = logging.getLogger(__name__)
    logger.info('FILe CONVERSION MODULE')
    if not os.path.isdir(output_path):
        logger.debug('creating: %s', output_path)
        os.makedirs(output_path)

    logger.setLevel(logging.DEBUG)

    logger.info('System info:')
    logger.info('- platform: %s', platform())
    logger.info('- python version: %s', python_version())
    logger.info('- VLabApp version: %s', vlabapp_version)
    logger.info('- numpy version: %s', np.__version__)
    logger.info('- imageio version: %s', imageio_version)
    logger.info('- imageio-ffmpeg version: %s', imageioffmpeg_version)

    logger.info('Input image/mask path: %s', image_path)

    if 'FFMPEG' not in iio_config.known_plugins:
        logger.error('imageio ffmpeg plugin missing. Install imageio with ffmpeg plugin using `pip install imageio[ffmpeg]`')
        raise RuntimeError('imageio ffmpeg plugin missing. Install imageio with ffmpeg plugin using `pip install imageio[ffmpeg]`')

    ###########################
    # Load image or mask
    ###########################

    # Load mask
    logger.debug('loading %s', image_path)
    try:
        image = gf.Image(image_path)
        image.imread()
    except Exception:
        logger.exception('Error loading %s', image_path)
        raise

    # Check 'F' axis has size 1
    if image.sizes['F'] != 1:
        logger.error('Image %s has a F axis with size > 1', str(image_path))
        # Remove all handlers for this module
        raise TypeError(f"Image {image_path} has a F axis with size > 1")

    if output_format == 'auto':
        logger.debug('Output format auto-detection')
        if image.sizes['T'] > 1:
            output_format = 'mp4'
        else:
            output_format = 'jpg'
        logger.debug('Output format: %s', output_format)

    ###########################
    # Prepare image
    ###########################
    if output_format == 'jpg' and image.sizes['T']>1:
        logger.info('Preparing image: keeping only first frame')
        # keep only first time frame
        image.crop('T', 0, 1)

    # Project Z axis if needed and select channel
    if image.sizes['Z'] > 1:
        logger.info('Preparing image: performing Z-projection')
        image_processed = image.z_projection(projection_type, projection_zrange)
    else:
        image_processed = image.image

    if input_is_mask is None:
        # auto-detect input image type
        logger.debug('Input file type auto-detection')
        if image.sizes['C'] > 1:
            input_is_mask = False
        elif image.dtype.char not in np.typecodes['AllInteger']:
            input_is_mask = False
        elif len(np.unique(image_processed)) > 4096:
            input_is_mask = False
        else:
            input_is_mask = True
            for t in range(image.sizes['T']):
                # estimate fraction of image which is constant
                n_nonzero = np.count_nonzero(cv.Laplacian(image_processed[0, t, 0, 0, :, :], cv.CV_32F, ksize=1))
                fraction_const = 1 - n_nonzero / (image.sizes['X'] * image.sizes['Y'])
                if fraction_const < 0.8:
                    input_is_mask = False
                    break
        if input_is_mask:
            logger.debug('Input file type: segmentation mask')
        else:
            logger.debug('Input file type: image')

    # set output size to next multiple of 16 (will pad with 0)
    mbs = 16
    if output_format == 'mp4':
        size_x = round(np.ceil(image.sizes['X'] / mbs) * mbs)
        size_y = round(np.ceil(image.sizes['Y'] / mbs) * mbs)
    else:
        size_x = image.sizes['X']
        size_y = image.sizes['Y']

    if input_is_mask:
        ncolors = image_processed.max() + 2
        L = int(np.ceil(ncolors**(1/3)))
        colors = np.zeros((L**3, 3), np.uint8)
        for R in range(L):
            for G in range(L):
                for B in range(L):
                    colors[R+G*L+B*L*L] = np.array(((R*255)/(L-1), (G*255)/(L-1), (B*255)/(L-1))).astype(np.uint8)
        # shuffle colors (keep black in first position)
        rng = np.random.default_rng(85246)
        idx = list(range(1, colors.shape[0]))
        rng.shuffle(idx)
        idx.insert(0, 0)
        colors = colors[idx, :]

        image_output = np.zeros((image.sizes['T'], size_y, size_x, 3), dtype='uint8')
        image_output[:, :image.sizes['Y'], :image.sizes['X']] = colors[image_processed[0, :, 0, 0, :, :]]
    else:
        image_output = np.zeros((image.sizes['T'], size_y, size_x, 3), dtype='uint8')
        image_output_frame = np.zeros((size_y, size_x), dtype='uint8')
        max_per_channel = image_processed.max(axis=(0, 1, 3, 4, 5))
        min_per_channel = image_processed.min(axis=(0, 1, 3, 4, 5))
        for t in range(image.sizes['T']):
            logger.debug('Processing frame %s/%s', t, image.sizes['T'])
            image_input_frame = np.round(image_processed[0, t, :, 0, :, :]*(np.iinfo('uint8').max/(np.iinfo(image_processed.dtype).max))).astype('uint8')
            if autocontrast:
                for channel in range(image.sizes['C']):
                    image_input_frame[channel] = np.round((image_processed[0, t, channel, 0, :, :]-min_per_channel[channel])*(np.iinfo('uint8').max/(max_per_channel[channel]-min_per_channel[channel]))).astype('uint8')
            for color in range(3):  # RGB
                image_output_frame.fill(0)
                for channel in range(image.sizes['C']):
                    image_output_frame[:image.sizes['Y'], :image.sizes['X']] = cv.addWeighted(src1=image_output_frame[:image.sizes['Y'], :image.sizes['X']],
                                                                                              alpha=1.0,
                                                                                              src2=image_input_frame[channel],
                                                                                              beta=colors[channel][color]/255.0,
                                                                                              gamma=0)
                image_output[t, :, :, color] = image_output_frame

    if output_format == 'mp4':
        output_name = os.path.join(output_path, output_basename+'.mp4')
        logger.info('Saving movie to %s', output_name)
        iio.imwrite(output_name, image_output, extension='.mp4', fps=fps, quality=quality, macro_block_size=mbs)
    elif output_format == 'jpg':
        output_name = os.path.join(output_path, output_basename+'.jpg')
        logger.info('Saving image to %s', output_name)
        iio.imwrite(output_name, image_output[0])
