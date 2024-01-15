import os
import logging
import numpy as np
import tifffile
import igraph as ig
import csv
import cv2
import nd2
import napari
from aicsimageio.writers import OmeTiffWriter
import matplotlib.pylab as plt
import pandas as pd
from matplotlib import cm
#from general import general_functions as gf

class Image:
    """
    Class used to read and elaborate images
    Default dimension positions = {'F': 0, 'T': 1, 'C': 2, 'Z': 3, 'Y': 4, 'X': 5}

    Attributes
    ----------
    path : str
        path to the image
    basename : str
        image name with extension
    name : str
        image name without extension
    extension : str
        extension of the image
    sizes : dict
        dictionary with dimesions names and values
        # eg. {'F': 1, 'T': 1, 'C': 3, 'Z': 11, 'Y': 2048, 'X': 2048}
    image : ndarray
        numpy ndarray with the image
    shape : list
        list with image shapes

    Methods
    -------
    imread()
        Read the image from the already setted 'path'
        Attributes image, sizes and shape are populated here
    save()
        Empty
    get_TYXarray()
        Return the 3D image with the dimensions T, Y and X.
        When used the other dimensions F,C,Z MUST be empty (with size = 1)
    zProjection(projection_type, zrange,focus_method)
        Return the z-projection of the image using the selected projection type over the range of z values defined by zrange.
        Possible projection types: max, min, std, avg (or mean), median.
        If zrange is None, use all Z values. If zrange is an integer, use z values in [z_best-zrange,z_best+zrange],
        where z_best is the Z corresponding to best focus. If zrange is a tuple of lenght 2 (zmin,zmax), use z values in [zmin,zmax].
        Possible focus_methods: tenengrad_var, laplacian_var, std.
    """

    def __init__(self, im_path):
        self.path = im_path
        self.basename = os.path.basename(self.path)
        self.name, self.extension = os.path.splitext(self.basename)
        self.sizes = None
        self.image = None
        self.shape = None

    def imread(self):
        def set_6Dimage(image, axes):
            """
            Return a 6D ndarray of the input image
            """
            dimensions = {'F': 0, 'T': 1, 'C': 2, 'Z': 3, 'Y': 4, 'X': 5}
            # Dictionary with image axes order
            axes_order = {}
            for i, char in enumerate(axes):
                axes_order[char] = i
            # Mapping for the desired order of dimensions
            mapping = [axes_order.get(d, None) for d in 'FTCZYX']
            mapping = [i for i in mapping if i is not None]
            # Rearrange the image array based on the desired order
            image = np.transpose(image, axes=mapping)
            # Determine the missing dimensions and reshape the array filling the missing dimensions
            missing_dims = []
            for c in 'FTCZYX':
                if c not in axes:
                    missing_dims.append(c)
            for dim in missing_dims:
                position = dimensions[dim]
                image = np.expand_dims(image, axis=position)
            return image, image.shape

        # axis default order: FTCZYX for 6D - F = FieldofView, T = time, C = channels
        if self.extension == '.nd2':
            reader = nd2.ND2File(self.path)
            axes_order = str(''.join(list(reader.sizes.keys()))).upper() #eg. reader.sizes = {'T': 10, 'C': 2, 'Y': 2048, 'X': 2048}
            image = reader.asarray() #nd2.imread(self.path)
            reader.close()
            self.sizes = {}
            self.image, self.shape = set_6Dimage(image, axes_order)
            for key, value in zip('FTCZYX', self.shape):
                self.sizes[key] = value # eg. {'F': 1, 'T': 10, 'C': 2, 'Z': 1, 'Y': 2048, 'X': 2048}
            return self.image

        elif (self.extension == '.tiff' or self.extension == '.tif'):
            reader = tifffile.TiffFile(self.path)
            axes_order = str(reader.series[0].axes).upper()
            image = reader.asarray()
            reader.close()
            self.sizes = {}
            self.image, self.shape = set_6Dimage(image, axes_order)
            for key, value in zip('FTCZYX', self.shape):
                self.sizes[key] = value
            return self.image
        else:
            logging.getLogger(__name__).error('Image format not supported. Please upload a tiff or nd2 image file.')
            raise TypeError('Image format not supported. Please upload a tiff or nd2 image file.')

    def save(self):
        pass

    def get_TYXarray(self):
        if self.sizes['F'] > 1 or self.sizes['C'] > 1 or self.sizes['Z'] > 1:
            logging.getLogger(__name__).error('Image format not supported. Please upload an image with only TYX dimesions.')
        return self.image[0,:,0,0,:,:]

    def zProjection(self, projection_type, zrange, focus_method="tenengrad_var"):
        """
        Return the z-projection of the image using the selected projection type over the range of z values defined by zrange.

        Parameters
        ----------
        projection_type: str
            the projection type (max, min, std, avg, mean or median)
        zrange: int or (int,int) or None
            the range of z sections to use for projection.
            If zrange is None, use all z sections.
            If zrange is an integer, use all z sections in the interval [z_best-zrange,z_best+zrange]
            where z_best is the Z corresponding to best focus.
            If zrange is tuple (zmin,zmax), use all z sections in the interval [zmin,zmax].
        focus_method: str
            the method used to estimate the Z corresponding to best focus (tenengrad_var, laplacian_var, std)
             tenengrad_var: estimate the sharpness using the variance of sqrt(Gx^2+Gy^2), where Gx and Gy are the gradients in the x and y direction computed using Sobel operators.
             laplacian_var: estimate the sharpness using the variance of the laplacian.
             std: estimate the sharpness using the standard deviation of the image.
        Returns
        -------
        ndarray
            a 6D array with original image size, except for Z axis which has size 1.
        """
        if focus_method not in ['tenengrad_var', 'laplacian_var', 'std']:
            raise TypeError(f"Invalid focus_method {focus_method}")

        if zrange is None:
            logging.getLogger(__name__).info('Z-Projection: projection type=%s, zrange=%s (All Z sections)', projection_type, zrange)
        elif isinstance(zrange, int) and zrange == 0:
            logging.getLogger(__name__).info('Z-Projection: projection type=%s, zrange=%s (Z section with best focus), focus method=%s', projection_type, zrange, focus_method)
        elif isinstance(zrange, int):
            logging.getLogger(__name__).info('Z-Projection: projection type=%s, zrange=%s (Range %s around Z section with best focus), focus method=%s', projection_type, zrange, zrange, focus_method)
        elif isinstance(zrange, tuple) and len(zrange) == 2 and zrange[0] <= zrange[1]:
            logging.getLogger(__name__).info('Z-Projection: projection type=%s, zrange=%s (Fixed range from %s to %s)', projection_type, zrange, zrange[0], zrange[1])
        else:
            logging.getLogger(__name__).info('Z-Projection: invalid zrange')
        projected_image = np.zeros((self.sizes['F'], self.sizes['T'], self.sizes['C'], 1, self.sizes['Y'], self.sizes['X']), dtype=self.image.dtype)
        sharpness = np.zeros(self.sizes['Z'])
        for f in range(self.sizes['F']):
            for t in range(self.sizes['T']):
                for c in range(self.sizes['C']):
                    z_values = None
                    if zrange is None:
                        # use all Z
                        z_values = list(range(self.sizes['Z']))
                        logging.getLogger(__name__).info('Z-Projection (F: %s, T: %s, C: %s): %s over z in %s (all)', f, t, c, projection_type, z_values)
                    elif isinstance(zrange, int):
                        # use zrange around Z with best focus
                        # estimate sharpness
                        if focus_method == 'tenengrad_var':
                            for z in range(self.sizes['Z']):
                                sharpness[z] = cv2.magnitude(cv2.Sobel(self.image[f, t, c, z, :, :].astype("float64"), cv2.CV_64F, 0, 1, ksize=3),
                                                            cv2.Sobel(self.image[f, t, c, z, :, :].astype("float64"), cv2.CV_64F, 1, 0, ksize=3)).var()
                        elif focus_method == 'laplacian_var':
                            for z in range(self.sizes['Z']):
                                sharpness[z] = cv2.Laplacian(self.image[f, t, c, z, :, :].astype("float64"), cv2.CV_64F, ksize=11).var()
                        elif focus_method == 'std':
                            sharpness = self.image[f, t, c, :, :, :].std(axis=(1, 2))

                        # estimate z_best
                        if focus_method == 'std':
                            # choose z_best as z with maximum sharpness
                            z_best = sharpness.argmax()
                        elif focus_method in ['tenengrad_var', 'laplacian_var']:
                            # smooth sharpness with running mean and choose z_best as z with maximum smoothed sharpness
                            smooth_window = 1
                            sharpness_smoothed = sharpness/max(sharpness)
                            # smooth with running mean:
                            sharpness_smoothed = np.hstack((np.full(smooth_window, sharpness_smoothed[0]),
                                                            sharpness_smoothed,
                                                            np.full(smooth_window, sharpness_smoothed[-1])))
                            sharpness_smoothed = np.convolve(sharpness_smoothed,
                                                             np.ones(2*smooth_window+1)/(2*smooth_window+1),
                                                             mode='valid')
                            z_best = sharpness_smoothed.argmax()

                        # if z_best is too close to min or maz 'Z' => shift best_z so as to keep (2*zrange+1) z values (z_values).
                        z_best_tmp = min(max(z_best, zrange), self.sizes['Z']-zrange-1)
                        z_values = [z for z in range(z_best_tmp-zrange, z_best_tmp+zrange+1) if z < self.sizes['Z'] and z >= 0]

                        logging.getLogger(__name__).info('Z-Projection (F: %s, T: %s, C: %s): %s over z in %s (Best z=%s)', f, t, c, projection_type, z_values, z_best)
                    elif isinstance(zrange, tuple) and len(zrange) == 2 and zrange[0] <= zrange[1]:
                        # use fixed range
                        z_values = [z for z in range(zrange[0], zrange[1]+1) if z < self.sizes['Z'] and z >= 0]
                        logging.getLogger(__name__).info('Z-Projection (F: %s, T: %s, C: %s): %s over z in %s (fixed range)', f, t, c, projection_type, z_values)

                    if len(z_values) == 1:
                        projected_image[f, t, c, 0, :, :] = self.image[f, t, c, z_values[0], :, :].copy()
                    elif projection_type == 'max':
                        projected_image[f, t, c, 0, :, :] = np.max(self.image[f, t, c, z_values, :, :], axis=0)
                    elif projection_type == 'min':
                        projected_image[f, t, c, 0, :, :] = np.min(self.image[f, t, c, z_values, :, :], axis=0)
                    elif projection_type == 'std':
                        projected_image[f, t, c, 0, :, :] = np.std(self.image[f, t, c, z_values, :, :], axis=0, ddof=1)
                    elif projection_type == 'avg' or projection_type == 'mean':
                        projected_image[f, t, c, 0, :, :] = np.mean(self.image[f, t, c, z_values, :, :], axis=0)
                    elif projection_type == 'median':
                        projected_image[f, t, c, 0, :, :] = np.median(self.image[f, t, c, z_values, :, :], axis=0)
                    else:
                        logging.getLogger(__name__).error('Projection type not recognized')
                        return None

        return projected_image

def plot_graph(viewer, graph):
    """
    Add two layers (with names 'Edges' and 'Vertices') to the `viewer_graph`
    and plot the cell tracking graph.
    Existing layers  'Edges' and 'Vertices' will be cleared.
    Setup mouse click callbacks to allow vertices selection in `viewer_graph`
    and centering `viewer_images` camera to specific vertex.

    Parameters
    ----------
    viewer_graph: napari.Viewer
        napari viewer in which the graph should be displayed.
    viewer_images: napari.Viewer
        napari viewer with image and mask.
    mask_layer: napari.layer.Labels
        napari layer with segmentation mask.
    graph: igraph.Graph
        cell tracking graph.
    colors: numpy.array
        numpy array with shape (number of colors,4) with one color per
        row (row index i corresponds to to mask id i)
    """
    #graph = ig.Graph().Read_GraphMLz(graph_path)
    # Adjust attibute types
    #graph = adjust_graph_types(graph, 'uint16')

    mask_ids = [v['mask_id'] for v in graph.vs]

    colors = []
    for i, c in enumerate(cm.hsv(np.linspace(0, 1, max(mask_ids)+1))):
        colors.append(c.tolist())
    colors = np.asarray(colors)

    layout_per_component = True
    if layout_per_component:
        # Layout_sugiyama doesn't always properly split connectected components.
        # This is an attempt to overcome this problem.
        # A better option would probably be to use the algorithm used by graphviz (dot) or graphviz.
        components = graph.connected_components(mode='weak')
        layout = [[0.0, 0.0] for v in graph.vs]
        lastx = 0
        for cmp in components:
            g2 = graph.subgraph(cmp)
            layout_tmp = g2.layout_sugiyama(
                layers=[f+min(graph.vs['frame']) for f in g2.vs['frame']], maxiter=1000)
            # Shift x coord by lastx
            minx = min(x for x, y in layout_tmp.coords)
            maxx = max(x for x, y in layout_tmp.coords)
            for i, j in enumerate(cmp):
                x, y = layout_tmp[i]
                layout[j] = [x-minx+lastx, y]
            lastx = lastx-minx+maxx+1  # max([x+lastx for x,y in layout_tmp.coords])+1
    else:
        # Simple layout_sugiyama
        layout = graph.layout_sugiyama(
            layers=[f+min(graph.vs['frame']) for f in graph.vs['frame']], maxiter=1000)

    vertex_size = 0.4
    edge_w_min = 0.01
    edge_w_max = vertex_size*0.8

    # Edges
    if not 'Edges' in viewer.layers:
        edges_layer = viewer.add_shapes(name='Edges', opacity=1)
    else:
        edges_layer = viewer.layers['Edges']
        edges_layer.data = []

    # Note: (x,y) to reverse horizontal order (left to right)
    edges_coords = [[[layout[e.source][0], layout[e.source][1]], [
        layout[e.target][0], layout[e.target][1]]] for e in graph.es]
    edges_layer.add(edges_coords,
                    edge_width=np.minimum(graph.es['overlap_fraction_target'],
                                          graph.es['overlap_fraction_source']) * (edge_w_max - edge_w_min) + edge_w_min,
                    edge_color="lightgrey",
                    shape_type='line')
    edges_layer.editable = False
    edges_layer.refresh()

    # Add vertices
    if not 'Vertices' in viewer.layers:
        vertices_layer = viewer.add_points(name='Vertices', opacity=1)
        vertices_layer.help = "<left-click> to set view, <right-click> to select, <shift>+<right-click> to extend selection"
        vertices_layer_isnew = True
    else:
        vertices_layer = viewer.layers['Vertices']
        vertices_layer.data = []
        vertices_layer_isnew = False

    vertices_layer.add(np.array(layout[:graph.vcount()]))
    vertices_layer.edge_width_is_relative = True
    vertices_layer.edge_width = 0.0
    vertices_layer.symbol = 'square'
    vertices_layer.size = vertex_size
    vertices_layer.face_color = colors[mask_ids]
    vertices_layer.properties = {'frame': graph.vs['frame'],
                                 'mask_id': graph.vs['mask_id'],
                                 'selected': np.repeat(False, graph.vcount())}
    vertices_layer.selected_data = set()
    vertices_layer.editable = False

    vertices_layer.refresh()

    # Note: it would be probably better to use the already existing option to select points in the Points layer instead of using an additional 'selected' property.
    # However I couldn't manage to allow selecting points without allowing to move, add or delete points (moving, adding, deleting points should not be allowed as it would cause trouble later).

    if vertices_layer_isnew:
        # mouse click on viewer_graph
        @vertices_layer.mouse_drag_callbacks.append
        def click_drag(layer, event):
            dragged = False
            yield
            # on move
            while event.type == 'mouse_move':
                dragged = True
                yield
            # on release
            if not dragged:  # i.e. simple click
                if event.button == 1:  # center view (left-click)
                    # center view on corresponding vertex
                    point_id = layer.get_value(event.position)
                elif event.button == 2:  # selection (right-click)
                    # vertices selection (multple mask_ids, same frame range for all)
                    point_id = layer.get_value(event.position)
                    if not point_id is None:
                        if 'Shift' in event.modifiers:
                            # add to selection
                            layer.properties['selected'][point_id] = True
                            # find frame range
                            v_selected = np.where(layer.properties['selected'])[0]
                            frame_min = np.min(layer.properties['frame'][v_selected])
                            frame_max = np.max(layer.properties['frame'][v_selected])
                            # find selected mask_ids
                            mask_ids = layer.properties['mask_id'][v_selected]
                            # erase previous selection
                            layer.properties['selected'] = False
                            # select all vertice with mask_id in mask_ids and within frame_range
                            layer.properties['selected'][(layer.properties['frame'] >= frame_min) & (layer.properties['frame'] <= frame_max) & (np.isin(layer.properties['mask_id'], mask_ids))] = True
                        else:
                            # replace selection
                            layer.properties['selected'][layer.properties['selected']] = False
                            layer.properties['selected'][point_id] = not layer.properties['selected'][point_id]
                    else:
                        if not 'Control' in event.modifiers and not 'Shift' in event.modifiers:
                            # erase selection
                            layer.properties['selected'][layer.properties['selected']] = False
                    # change style
                    layer.edge_color[layer.properties['selected']] = [1.0, 1.0, 1.0, 1.0]  # white
                    layer.edge_width[~layer.properties['selected']] = 0
                    layer.edge_width[layer.properties['selected']] = 0.4
                    layer.refresh()

        viewer.reset_view()

def adjust_graph_types(graph, mask_dtype):
    graph.vs['frame'] = np.array(graph.vs['frame'], dtype='int32')
    graph.vs['mask_id'] = np.array(graph.vs['mask_id'], dtype=mask_dtype)
    graph.vs['area'] = np.array(graph.vs['area'], dtype='int64')
    graph.es['overlap_area'] = np.array(graph.es['overlap_area'], dtype='int64')
    graph.es['frame_source'] = np.array(graph.es['frame_source'], dtype='int32')
    graph.es['frame_target'] = np.array(graph.es['frame_target'], dtype='int32')
    graph.es['mask_id_source'] = np.array(graph.es['mask_id_source'], dtype=mask_dtype)
    graph.es['mask_id_target'] = np.array(graph.es['mask_id_target'], dtype=mask_dtype)
    # Remove useless attribute
    return graph

def evaluate_graph_properties(graph):
    """
    Evaluate the properties of the graph
    
    Parameters
    ---------------------
    graph: igraph.Graph
        cell tracking graph

    Returns
    ---------------------
    cell_tracks
    """
    # Set "stable" subgraph = if source vertex has a unique outgoing edge and target vertex has a unique incoming edge
    graph.es['stable'] = False
    graph.es.select(lambda edge: abs(edge['frame_source']-edge['frame_target']) == 1 and edge['mask_id_source'] == edge['mask_id_target'] and graph.outdegree(edge.source) == 1 and graph.indegree(edge.target) == 1)['stable'] = True
    # Flag edge with low overlap as not stable
    graph.es.select(overlap_fraction_source_lt = 0)['stable'] = False
    graph.es.select(overlap_fraction_target_lt = 0)['stable'] = False
    # Evaluate length of "stable" subgraph and store it as vertex attribute
    subgraph = graph.subgraph_edges(graph.es.select(stable=True), delete_vertices=False)
    components = subgraph.connected_components(mode='weak')
    for i, n in enumerate(components.sizes()):
        graph.vs[components[i]]['stable_component_size'] = n

    # Evaluation cell tracks (i.e. connected components of the cell tracking graph)
    components = graph.connected_components(mode='weak')
    cell_tracks = []
    
    for i, cmp in enumerate(components): # each connected component found is a subgraph
        subgraph = graph.subgraph(cmp) # subgraph = subgraph
        mask_ids = np.unique(subgraph.vs['mask_id'])
        frame_min = np.min(subgraph.vs['frame'])
        frame_max = np.max(subgraph.vs['frame'])
        # Number of missing mask regions (edges spanning more than 1 frame)
        n_missing = np.sum([ e['frame_target'] - e['frame_source'] - 1 for e in subgraph.es])
        # Number fusion events with stable neighborhood
        n_fusions = np.sum([1 if v.indegree() > 1 and min([v2['stable_component_size'] for v2 in v.neighbors()]) >= 1 else 0 for v in subgraph.vs])
        fusions_frames = []
        if n_fusions > 0:
            indegree = subgraph.vs[0].indegree()
            for v in subgraph.vs:
                if v.indegree() > indegree:
                    indegree = v.indegree()
                    fusions_frames.append(v['frame'])
        # Number division events with stable neighborhood
        n_divisions = np.sum([1 if v.outdegree() > 1 and min([v2['stable_component_size'] for v2 in v.neighbors()]) >= 1 else 0 for v in subgraph.vs])
        divisions_frames = []
        if n_divisions > 0:
            outdegree = subgraph.vs[0].outdegree()
            for v in subgraph.vs:
                if v.outdegree() > outdegree:
                    outdegree = v.outdegree()
                    divisions_frames.append(v['frame'])
        min_area = np.min(subgraph.vs['area'])
        max_area = np.max(subgraph.vs['area'])
        # Topology
        cell_tracks.append({'graph_vertices': cmp, 'mask_ids': mask_ids, 'frame_min': frame_min,
                            'frame_max': frame_max, 'n_missing': n_missing, 'n_fusions': n_fusions,
                            'n_divisions': n_divisions, 'min_area': min_area, 'max_area': max_area,
                            'fusions_frames': fusions_frames, 'divisions_frames': divisions_frames})
    return cell_tracks






def fusion_correction(mask, magn_image, graph, tp_before, tp_after, output_path):
    """
    Correct the fusion time of the found mask based on the magnified image
    
    Parameters
    ---------------------
    mask: ndarray 3D TYX
        segmentation mask
    magn_image: ndarray 3D TYX
        magnified image
    graph: igraph.Graph
        cell tracking graph
    output_path: str
        output directory

    Saves
    ---------------------
    corrected_mask
        ndarray with the corrected mask
    corrected_graph
        igraph.Graph with the corrected graph
    """
    # Reduce mask Image obj to normal 3D nparray (TXY)
    #%% FIND FUSION - same code of "event filter" module

    # Initialize the cvs file with results
    with open(output_path+'_fusions_dictionary.csv', "w") as file:
        writer = csv.writer(file)
        writer.writerow(['TP start', 'TP event', 'TP end', 'id(s) before event', 'id(s) after event'])

    # Set predefined parameters
    border_width = 2 # pixels to consider in removing cells on the border
    nmissing = 0 # number of maximum missing cells

    # Evaluate of graph's properties
    selected_cell_tracks = evaluate_graph_properties(graph) #gf.

    # Delete the cells masks on the border
    border_mask_ids = np.unique( np.concatenate([
            np.unique(mask[:, :border_width, :]), np.unique(mask[:, -border_width:, :]),
            np.unique(mask[:, :, :border_width]), np.unique(mask[:, :, -border_width:])]))
    border_mask_ids = border_mask_ids[border_mask_ids > 0]
    selected_cell_tracks = [x for x in selected_cell_tracks if np.isin(x['mask_ids'], border_mask_ids).any() == False]

    # Delete the cells masks with more than nmissing missing detections
    selected_cell_tracks = [x for x in selected_cell_tracks if x['n_missing'] <= nmissing]

    # Initilize final results objects
    n_valid_event = 0
    events_mask = np.zeros(mask.shape)
    events_vertices = []

    # Select masks with at least 1 fusion detected
    selected_cell_tracks = [x for x in selected_cell_tracks if x['n_fusions'] > 0]
    for cell_track in selected_cell_tracks:
        subgraph = graph.subgraph(cell_track['graph_vertices'])
        fusions_frames = cell_track['fusions_frames'][1:] # remove first value because always 1
        for fusion_frame in fusions_frames:
            # Read fusion timepoint and ids
            initial_event_tp = int(fusion_frame)
            ids_before = []
            for vertex in subgraph.vs:
                if vertex['frame'] >= initial_event_tp-1 and vertex['frame'] <= initial_event_tp+1:
                    if vertex['frame'] < initial_event_tp and vertex['mask_id'] not in ids_before:
                        ids_before.append(vertex['mask_id'])
                    if vertex['frame'] > initial_event_tp:
                        id_after = vertex['mask_id']        
            # Recalculate fusion timepoint based on the magnified image
            magn_image = magn_image.astype('uint8')
            stds = []
            for t in range(mask.shape[0]):
                # Create the static mask for the time point t :
                # if before fusion, use the first mask after fusion, otherwise the real one
                static_mask = np.zeros([mask.shape[1], mask.shape[2]], dtype='uint8')
                for cellid in set(ids_before + [id_after]):
                    if t > initial_event_tp:
                        static_mask[mask[t,:,:] == cellid] = cellid
                    else:
                        static_mask[mask[initial_event_tp+1,:,:] == cellid] = cellid
                # Calculate std
                px = magn_image[t, static_mask==id_after]
                stds.append(np.std(px))
            # Calculate difference in between stds (row - previous row)
            fusion_data = {'Timepoint': np.arange(mask.shape[0]), 'Stdev':stds}
            fusion_data_df= pd.DataFrame(fusion_data)
            fusion_data_df['std_diff']=fusion_data_df['Stdev'].diff()
            # Get the time point of the minimum difference
            real_event_tp = fusion_data_df.at [fusion_data_df['std_diff'].idxmin(), 'Timepoint']
            if real_event_tp == initial_event_tp: tp_is_changed = 0 
            elif real_event_tp > initial_event_tp:  tp_is_changed = 1
            else: tp_is_changed = 2
            
            # Range of selected time points
            tp_to_check = np.arange(real_event_tp - tp_before, real_event_tp + tp_after)
            
            if min(tp_to_check) >= 0 and max(tp_to_check) <= mask.shape[0]: # valid if event timepoint ± selected timepoints are in a feasible range
                valid = True
                for t in cell_track['fusions_frames']: # valid if there aren't other events in these timepoints
                    valid = False if t != initial_event_tp and t in tp_to_check else True
                if valid:
                    n_valid_event += 1
                    # If event is valid -> update events_mask
                    for t in tp_to_check:
                        tmask = np.zeros([mask.shape[1], mask.shape[2]])
                        for cellid in set(ids_before + [id_after]):
                            # If fusion timepoint changed, change the mask if in the gap timepoints
                            if tp_is_changed == 1 and t >= initial_event_tp  and t < real_event_tp:
                                ref_tp = initial_event_tp-1
                            elif tp_is_changed == 2 and t >= initial_event_tp  and t < real_event_tp:
                                ref_tp = real_event_tp
                            else:
                                ref_tp = t
                            tmask[mask[ref_tp,:,:] == cellid] = cellid
                        events_mask[t, :, :] += tmask
                    # If event is valid -> list the events' vertices
                    for vertex in subgraph.vs:
                        if vertex['frame'] in tp_to_check:
                            events_vertices.append(vertex)
                    # If event is valid -> add the event in the csv file
                    with open(output_path+'_fusions_dictionary.csv', 'a') as file:
                        writer = csv.writer(file)
                        writer.writerow([min(tp_to_check), real_event_tp, max(tp_to_check), ids_before, id_after])

    # Take the subgraph with the listed vertex
    """subgraph_vs = (graph.vs(id=v['id'])[0].index for v in events_vertices)
    events_graph = graph.subgraph(subgraph_vs)

    print(events_graph)

    viewer = napari.Viewer()
    plot_graph(viewer, events_graph) #gf.
    viewer.show(block=True)
    
    # If fusions timepoits are changed -> update the events' graph
    if tp_is_changed == 1: # add missing vertex
        ids_before.remove(id_after)
        ref_vertex = subgraph.vs.select(frame=initial_event_tp-1, mask_id_lt=ids_before[0])
        print(ref_vertex.attibute)
    if tp_is_changed == 2: # remove verteces
        pass
    events_graph.write_graphmlz(output_path+'_fusions_graph.graphmlz')
    """
    
    # Save the mask with the detected events
    events_mask = events_mask.astype(mask.dtype)
    events_mask = events_mask[:, np.newaxis, : ,:]
    OmeTiffWriter.save(events_mask, output_path+'_fusions_mask.tif', dim_order="TCYX")
    
    print('Found '+str(n_valid_event)+' valid fusions events')


def main(mask_path, graph_path, magn_image_path, tp_before, tp_after, output_path):
    """
    Generate mask and graph with for the specified event and with minimum 
    tp_before and tp_after timepoints free of other events 
    
    Parameters
    ---------------------
    mask_path: str
        input mask path
    graph_path: str
        input graph path
    magn_image_path: str
        input magnified (channel) image path
    output_path: str
        output directory

    Saves
    ---------------------
    mask with the new fusion time
    graph with the new fusion time

    """

    ###########################
    # Setup logging
    ###########################

    if not os.path.isdir(output_path):
        os.makedirs(output_path)
        
    """logger = logging.getLogger(__name__)
    logger.info("FUSION CORRECTION MODULE")
    
    
    logfile = os.path.join(output_path, os.path.splitext(os.path.basename(graph_path))[0]+".log")
    logger.setLevel(logging.DEBUG)
    logger.debug("writing log output to: %s", logfile)
    logfile_handler = logging.FileHandler(logfile, mode='w')
    logfile_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    logfile_handler.setLevel(logging.INFO)
    logger.addHandler(logfile_handler)

    logger.info("Mask path: %s", mask_path)
    logger.info("Graph path: %s", graph_path)
    logger.info("Magnified image path: %s", magn_image_path)
    logger.info("Output path: %s", output_path)"""

    ###########################
    # Load mask and graph
    ###########################

    # Load mask
    ##logger.debug("loading %s", mask_path)
    try:
        mask = Image(mask_path) #gf.
        mask.imread()
    except Exception as e:
        logging.getLogger(__name__).error('Error loading mask '+mask_path+'\n'+str(e))

    # Load image
    ##logger.debug("loading %s", magn_image_path)
    try:
        magn_image = Image(magn_image_path) #gf.
        magn_image.imread()
    except Exception as e:
        logging.getLogger(__name__).error('Error loading magnified image '+magn_image_path+'\n'+str(e))
    
    # Load graph
    ##logger.debug("loading %s", graph_path)
    graph = ig.Graph().Read_GraphMLz(graph_path)
    # Adjust attibute types
    graph = adjust_graph_types(graph, mask.image.dtype) #gf.

    # Output path
    if not output_path.endswith('/'):
        output_path += '/'
    image_name = os.path.basename(mask_path).replace('_mask.tif', '')
    output_path += image_name

    fusion_correction(mask.get_TYXarray(), magn_image.get_TYXarray(), graph, tp_before, tp_after, output_path)
    ##logger.info("Done!\n")
    

# To test  
if __name__ == '__main__':
    
    mask_paths = ['/Users/aravera/Documents/CIG_Aleks/tests/test_newmodule/graph_filtering/smp09_BF_mask.tif',
                  '/Users/aravera/Documents/CIG_Aleks/tests/test_newmodule/graph_filtering/smp10_BF_mask.tif']
    graph_paths = ['/Users/aravera/Documents/CIG_Aleks/tests/test_newmodule/graph_filtering/smp09_BF_graph.graphmlz',
                   '/Users/aravera/Documents/CIG_Aleks/tests/test_newmodule/graph_filtering/smp10_BF_graph.graphmlz']
    magn_image_paths = ['/Users/aravera/Documents/CIG_Aleks/tests/test_newmodule/smp09_WL614_registered.tif',
                        '/Users/aravera/Documents/CIG_Aleks/tests/test_newmodule/smp10_WL614_registered.tif']
    tp_before = 10
    tp_after = 10
    output_path = '/Users/aravera/Documents/CIG_Aleks/tests/test_newmodule/results/'
    for i in range(len(mask_paths)):
        main(mask_paths[i], graph_paths[i], magn_image_paths[i], tp_before, tp_after, output_path)


# %%
