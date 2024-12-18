import os
import logging
from platform import python_version, platform
import roifile
import cv2 as cv
import numpy as np
import igraph as ig
import pandas as pd
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


def convert_mask_and_graph(mask_path, graph_path, output_path, output_basename, output_mask_format=None, output_graph_format=None):
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
        output basename. Output file will be saved as `output_path`/`output_basename`.ome.tif, `output_path`/`output_basename`.graphmlz and `output_path`/`output_basename`.log.
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
    logger.info('Output path: %s', output_path)
    logger.info('Output basename: %s', output_basename)

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

    ###########################
    # save graph
    ###########################
    if output_graph_format:
        if output_graph_format == 'tsv':
            output_file = os.path.join(output_path, output_basename+'.tsv')
            logger.info('Saving cell tracking graph to %s', output_file)
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
            del graph2.es['overlap_fraction_source']
            del graph2.es['overlap_fraction_target']
            del graph2.es['frame_source']
            del graph2.es['frame_target']
            del graph2.es['mask_id_source']
            del graph2.es['mask_id_target']
            graph2.vs['name'] = [str(track)+'_'+str(frame)+'_'+str(mask_id) for track, frame, mask_id in zip(graph.vs['cell_track'], graph.vs['frame'], graph.vs['mask_id'])]

            output_file = os.path.join(output_path, output_basename+'.graphml')
            logger.info('Saving cell tracking graph to %s', output_file)
            graph2.write_graphml(output_file)

    ###########################
    # Save mask
    ###########################
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
