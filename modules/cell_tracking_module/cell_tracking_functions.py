import os
import logging
from platform import python_version, platform
from collections import deque
import numpy as np
import napari
import cv2 as cv
import igraph as ig
from scipy.optimize import linear_sum_assignment
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QGridLayout, QWidget, QPushButton, QLabel, QSpinBox, QScrollArea, QGroupBox, QCheckBox, QMessageBox
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCursor, QKeySequence
from general import general_functions as gf
from aicsimageio.writers import OmeTiffWriter
from aicsimageio.types import PhysicalPixelSizes
from ome_types.model import CommentAnnotation
from version import __version__ as vlabapp_version


def remove_all_log_handlers():
    # remove all handlers for this module
    while len(logging.getLogger(__name__).handlers) > 0:
        logging.getLogger(__name__).removeHandler(logging.getLogger(__name__).handlers[0])


def split_regions(mask):
    """
    Split disconnected regions by assigning different mask ids to connected components with same mask id
    Note : 'mask' is modified in-place

    Parameters
    ----------
    mask: ndarray
        a 3D (TYX) 16bit unsigned integer (uint16) numpy array, modified in-place
    """
    logging.getLogger(__name__).debug("Splitting disconnected regions")
    for t in range(mask.shape[0]):
        for n in range(mask[t].max()):
            xmin, ymin, w, h = cv.boundingRect((mask[t] == n+1).astype('uint8'))
            if w > 0 and h > 0:
                nlabels, tmp = cv.connectedComponents((mask[t, (ymin):(ymin+h), (xmin):(xmin+w)] == n+1).astype('uint8'))
                # nlabels: number of labels, including 0 (background)
                if nlabels > 2:
                    logging.getLogger(__name__).debug(" Splitting: frame %s, mask id %s", t, n+1)
                    mask[t, (ymin):(ymin+h), (xmin):(xmin+w)][tmp > 1] = (tmp[tmp > 1]-1)+mask[t].max()


def remove_small_regions(mask, min_area):
    """
    Remove (set to 0) labelled regions with small area.
    Note : 'mask' is modified in-place

    Parameters
    ----------
    mask: ndarray
        a 3D (TYX) 16bit unsigned integer (uint16) numpy array, modified in-place
    min_area: int
        remove labelled regions with area (number of pixels) below `min_area`
    """
    logging.getLogger(__name__).debug("Removing small regions")
    for t in range(mask.shape[0]):
        areas = np.bincount(mask[t].ravel())
        mask_ids_toremove = np.where((areas < min_area) & (areas > 0))[0]
        for mask_id in mask_ids_toremove:
            logging.getLogger(__name__).debug(" Removing: frame %s, mask id %s", t, mask_id)
            mask[t][mask[t] == mask_id] = 0


def interpolate_mask(mask, cell_tracking_graph, mask_ids, frame_start, frame_end, max_delta_frame_interpolation=2, min_area=300):
    """
    Interpolate mask across frames
    Note: modify `mask` and `cell_tracking_graph` in-place

    Parameters
    ----------
    mask: ndarray
        a 3D (TYX) 16bit unsigned integer (uint16) numpy array
    cell_tracking_graph: CellTrackingGraph
        cell tracking graph
    mask_ids: list of int
        mask ids to modify
    frame_start: int
        first frame to modify
    frame_end: int
        end frame to modify (i.e. modify up to frame frame_end-1)
    max_delta_frame_interpolation: int
        number of previous and subsequent frames to consider for mask interpolation
    min_area: int
        remove labelled regions with area (number of pixels) below `min_area`
    """
    logger = logging.getLogger(__name__)
    logger.debug("Interpolating mask")

    frame_start = max(frame_start, 0)
    frame_end = min(frame_end, mask.shape[0])
    # Avoid duplicates in mask_ids
    mask_ids = np.unique(mask_ids).tolist()
    # Frame range extended by max_delta_frame_interpolation
    frame_start2 = max(0, frame_start-max_delta_frame_interpolation)
    frame_end2 = min(mask.shape[0], frame_end+max_delta_frame_interpolation)
    # Check that mask contains at least one of the mask_ids
    if not np.any(np.isin(mask[frame_start2:frame_end2, :, :], mask_ids)):
        return

    # Find bounding box for all mask_ids (region 1)
    ymin1, ymax1 = np.nonzero(np.any(np.isin(mask[frame_start2:frame_end2, :, :], mask_ids), axis=(0, 2)))[0][[0, -1]]
    xmin1, xmax1 = np.nonzero(np.any(np.isin(mask[frame_start2:frame_end2, :, :], mask_ids), axis=(0, 1)))[0][[0, -1]]
    # Crop mask to this bounding box (region 1)
    mask_cropped1 = mask[:, (ymin1):(ymax1+1), (xmin1):(xmax1+1)]
    # Destination distmap and mask (only region 1)
    dest_distmap = np.zeros((frame_end-frame_start, ymax1-ymin1+1, xmax1-xmin1+1), dtype='float32')
    dest_mask = mask_cropped1[frame_start:frame_end].copy()
    # Erase previous version of mask_ids
    dest_mask[np.isin(dest_mask, mask_ids)] = 0

    for mask_id in mask_ids:
        # Find bounding box for mask_id (region 2)
        ymin2, ymax2 = np.nonzero(np.any(mask_cropped1[frame_start2:frame_end2] == mask_id, axis=(0, 2)))[0][[0, -1]]
        xmin2, xmax2 = np.nonzero(np.any(mask_cropped1[frame_start2:frame_end2] == mask_id, axis=(0, 1)))[0][[0, -1]]
        distmaps_deque = deque()
        for frame in range(frame_start2, frame_end2):
            # Eval distance map to mask, with positive distance inside mask and negative distance outside mask (consider only region 2 enclosing mask_id)
            distmap = cv.distanceTransform((mask_cropped1[frame, (ymin2):(ymax2+1), (xmin2):(xmax2+1)] == mask_id).astype('uint8'), distanceType=cv.DIST_L2, maskSize=cv.DIST_MASK_5)
            distmap2 = cv.distanceTransform(1-(mask_cropped1[frame, (ymin2):(ymax2+1), (xmin2):(xmax2+1)] == mask_id).astype('uint8'), distanceType=cv.DIST_L2, maskSize=cv.DIST_MASK_5)
            distmap[distmap < 1e-4] = -distmap2[distmap < 1e-4]+1
            distmaps_deque.append(distmap)
            if len(distmaps_deque) > 2*max_delta_frame_interpolation+1:
                removed = distmaps_deque.popleft()
            if len(distmaps_deque) % 2 == 1:
                frame2 = frame-int((len(distmaps_deque)-1)/2)
                if frame2 >= frame_start and frame2 < frame_end:
                    logger.debug("interpolating mask: frame %s, mask id %s", frame2, mask_id)
                    median_dist = np.median(distmaps_deque, axis=0)
                    # Crop to region 2
                    dest_distmap_cropped2 = dest_distmap[frame2 - frame_start, (ymin2):(ymax2+1), (xmin2):(xmax2+1)]
                    dest_mask_cropped2 = dest_mask[frame2 - frame_start, (ymin2):(ymax2+1), (xmin2):(xmax2+1)]
                    dest_mask_cropped2[(median_dist > 0) & (median_dist > dest_distmap_cropped2)] = mask_id
                    dest_distmap_cropped2[(median_dist > 0) & (median_dist > dest_distmap_cropped2)] = median_dist[(median_dist > dest_distmap_cropped2)]

        frame = frame_end2-1
        while len(distmaps_deque) > 0:
            removed = distmaps_deque.popleft()
            if len(distmaps_deque) % 2 == 1:
                frame2 = frame-int((len(distmaps_deque)-1)/2)
                if frame2 >= frame_start and frame2 < frame_end:
                    logger.debug("interpolating mask: frame %s, mask id %s", frame2, mask_id)
                    median_dist = np.median(distmaps_deque, axis=0)
                    dest_distmap_cropped2 = dest_distmap[frame2 - frame_start, (ymin2):(ymax2+1), (xmin2):(xmax2+1)]
                    dest_mask_cropped2 = dest_mask[frame2 - frame_start, (ymin2):(ymax2+1), (xmin2):(xmax2+1)]
                    dest_mask_cropped2[(median_dist > 0) & (median_dist > dest_distmap_cropped2)] = mask_id
                    dest_distmap_cropped2[(median_dist > 0) & (median_dist > dest_distmap_cropped2)] = median_dist[(median_dist > dest_distmap_cropped2)]

    # Update cell tracking
    cell_tracking_graph.update(mask, dest_mask, [(frame_start, frame_end), (ymin1, ymax1+1), (xmin1, xmax1+1)])

    # Update mask
    mask_cropped1[frame_start:frame_end] = dest_mask

    # Clean
    if min_area is not None:
        toremove = []
        logger.debug("removing small regions")
        for frame in range(frame_start, frame_end):
            areas = np.bincount(mask[frame].ravel())
            mask_ids_toremove = np.where((areas < min_area) & (areas > 0))[0]
            for mask_id in mask_ids_toremove:
                logger.debug("Removing mask: frame %s, mask id %s", frame, mask_id)
                mask[mask == mask_id] = 0
                toremove.append((frame, mask_id))
        if len(toremove) > 0:
            cell_tracking_graph.remove_vertices(toremove)


def clean_mask(mask, cell_tracking_graph, max_delta_frame_interpolation=3, nframes_defect=2, nframes_stable=3, stable_overlap_fraction=0, min_area=300, only_missing=False):
    """
    Search for isolated defects in the cell tracking graph and try to remove them by interpolating
    corresponding mask across neighboring frames
    Note: modify `mask` and `cell_tracking_graph` in-place

    Parameters
    ----------
    mask: ndarray
        a 3D (TYX) 16bit unsigned integer (uint16) numpy array
    cell_tracking_graph: CellTrackingGraph
        cell tracking graph
    max_delta_frame_interpolation: int
        number of previous and subsequent frames to consider for mask interpolation
    nframes_defect: int
        maximum size of the defect (n of frames), should be > than `max_delta_frame_interpolation`
    nframes_stable: int
        minimum number of stable frames before and after the defect, should >= than `max_delta_frame_interpolation`
    stable_overlap_fraction: float
        edges stable = with overlap_fraction_target >= `stable_overlap_fraction`
                        and overlap_fraction_source >= `stable_overlap_fraction`
    min_area: int
        remove labelled regions with area (number of pixels) below `min_area`
    only_missing: bool
        only consider missing vertices type of defect

    Returns
    -------
    list of tuples
        Each each tuple corresponds to a defect (masks_ids,frame_start,frame_end)
        involving a list of mask ids (mask_ids) in the frame interval [frame_start,frame_end)
    """
    logger = logging.getLogger(__name__)
    logger.debug("cleaning mask")
    defects = cell_tracking_graph.get_isolated_defects(nframes_defect, nframes_stable, stable_overlap_fraction, only_missing)

    # Clean
    for mask_ids, frame_start, frame_end in defects:
        interpolate_mask(mask, cell_tracking_graph, mask_ids, frame_start, frame_end, max_delta_frame_interpolation=max_delta_frame_interpolation, min_area=None)  # do not filter on area (too long)

    # Clean
    if min_area is not None:
        toremove = []
        logger.debug("removing small regions")
        for frame in range(mask.shape[0]):
            areas = np.bincount(mask[frame].ravel())
            mask_ids_toremove = np.where((areas < min_area) & (areas > 0))[0]
            for mask_id in mask_ids_toremove:
                logging.getLogger(__name__).debug("Removing mask: frame %s, mask id %s", frame, mask_id)
                mask[mask == mask_id] = 0
                toremove.append((frame, mask_id))
        if len(toremove) > 0:
            cell_tracking_graph.remove_vertices(toremove)

    return defects


def plot_cell_tracking_graph(viewer_graph, viewer_images, mask_layer, graph, colors, selectable=True):
    """
    Add two layers (with names 'Edges' and 'Vertices') to the `viewer_graph` and plot the cell tracking graph,
    existing layers  'Edges' and 'Vertices' will be cleared.
    Setup mouse click callbacks to allow vertices selection in `viewer_graph` and centering `viewer_images`
    camera to specific vertex.

    Parameters
    ----------
    viewer_graph: napari.Viewer
        napari viewer in which the graph should be displayed
    viewer_images: napari.Viewer
        napari viewer with image and mask.
        viewer_image.dims.axis_labels must contain the actual axis labels (must contain at least 'T', 'Y' and 'X']).
    mask_layer: napari.layer.Labels
        napari layer with segmentation mask
    graph: igraph.Graph
        cell tracking graph
    colors: numpy.array
        numpy array with shape (number of colors,4) with one color per row (row index i corresponds to to mask id i)
    selectable: bool
        is it possible to select vertices?
    """

    def get_YX_timeframe(mask, t):
        # a function to return YX images
        T_axis_index = viewer_images.dims.axis_labels.index('T')
        Y_axis_index = viewer_images.dims.axis_labels.index('Y')
        X_axis_index = viewer_images.dims.axis_labels.index('X')
        indYX = list(viewer_images.dims.current_step)
        indYX[T_axis_index] = t
        indYX[Y_axis_index] = slice(0, mask.shape[Y_axis_index])
        indYX[X_axis_index] = slice(0, mask.shape[X_axis_index])
        indYX = tuple(indYX)
        return mask[indYX]

    graph2 = graph.copy()
    graph2.vs['missing'] = False

    # Add missing vertices (i.e. split edges spanning more than 1 frame)
    es_missing = graph2.es.select(lambda edge: edge['frame_target']-edge['frame_source'] > 1)
    if len(es_missing) > 0:
        edges_toremove = []
        edges_new_source = []
        edges_new_target = []
        edges_new_overlap_fraction_source = []
        edges_new_overlap_fraction_target = []
        vertices_new_mask_id = []
        vertices_new_frame = []
        for edge in es_missing:
            vsource = graph2.vs[edge.source]
            vtarget = graph2.vs[edge.target]
            if vsource['mask_id'] == vtarget['mask_id']:
                mask_id = vsource['mask_id']
            elif vsource.outdegree() == 1:
                mask_id = vsource['mask_id']
            elif vtarget.indegree() == 1:
                mask_id = vtarget['mask_id']
            else:
                forbidden_mask_ids = {v['mask_id'] for v in vsource.neighbors(mode='out') if v['mask_id'] != vtarget['mask_id']}
                forbidden_mask_ids = forbidden_mask_ids.union({v['mask_id'] for v in vtarget.neighbors(mode='in') if v['mask_id'] != vsource['mask_id']})
                if vsource['mask_id'] not in forbidden_mask_ids:
                    mask_id = vsource['mask_id']
                elif vtarget['mask_id'] not in forbidden_mask_ids:
                    mask_id = vtarget['mask_id']
                else:
                    mask_id = 0
            edges_toremove.append(edge)
            for frame in range(vsource['frame'], vtarget['frame']):
                if frame == vsource['frame']:
                    vertices_new_mask_id.append(mask_id)
                    vertices_new_frame.append(frame+1)
                    edges_new_source.append(edge.source)
                    edges_new_target.append(graph2.vcount() + len(vertices_new_mask_id) - 1)
                elif frame < vtarget['frame'] - 1:
                    vertices_new_mask_id.append(mask_id)
                    vertices_new_frame.append(frame+1)
                    edges_new_source.append(graph2.vcount() + len(vertices_new_mask_id) - 2)
                    edges_new_target.append(graph2.vcount() + len(vertices_new_mask_id) - 1)
                else:
                    edges_new_source.append(graph2.vcount() + len(vertices_new_mask_id) - 1)
                    edges_new_target.append(edge.target)
                edges_new_overlap_fraction_source.append(edge['overlap_fraction_source'])
                edges_new_overlap_fraction_target.append(edge['overlap_fraction_target'])
        graph2.delete_edges(edges_toremove)
        graph2.add_vertices(len(vertices_new_mask_id),
                            {"frame": vertices_new_frame,
                             "mask_id": vertices_new_mask_id,
                             "missing": np.repeat(True, len(vertices_new_mask_id))})
        graph2.add_edges(zip(edges_new_source, edges_new_target),
                         {"overlap_fraction_source": edges_new_overlap_fraction_source,
                          "overlap_fraction_target": edges_new_overlap_fraction_target})

    layout_per_component = True
    if layout_per_component:
        # Layout_sugiyama doesn't always properly split connectected components
        # This is an attempt to overcome this problem
        # A better option would probably be to use the algorithm used by graphviz (dot) or graphviz
        components = graph2.connected_components(mode='weak')
        layout = [[0.0, 0.0] for v in graph2.vs]
        lastx = 0
        for cmp in components:
            g2 = graph2.subgraph(cmp)
            layout_tmp = g2.layout_sugiyama(
                layers=[f+min(graph2.vs['frame']) for f in g2.vs['frame']], maxiter=1000)
            # Shift x coord by lastx
            minx = min(x for x, y in layout_tmp.coords)
            maxx = max(x for x, y in layout_tmp.coords)
            for i, j in enumerate(cmp):
                x, y = layout_tmp[i]
                layout[j] = [x-minx+lastx, y]
            lastx = lastx-minx+maxx+1  # max([x+lastx for x,y in layout_tmp.coords]) + 1
    else:
        # Simple layout_sugiyama
        layout = graph2.layout_sugiyama(
            layers=[f+min(graph2.vs['frame']) for f in graph2.vs['frame']], maxiter=1000)

    vertex_size = 0.4
    edge_w_min = 0.01
    edge_w_max = vertex_size*0.8

    # Edges
    if 'Edges' not in viewer_graph.layers:
        edges_layer = viewer_graph.add_shapes(name='Edges', opacity=1)
    else:
        edges_layer = viewer_graph.layers['Edges']
        edges_layer.data = []

    # Note: (x,y) to reverse horizontal order (left to right)
    edges_coords = [[[layout[e.source][0], layout[e.source][1]], [
        layout[e.target][0], layout[e.target][1]]] for e in graph2.es]
    edges_layer.add(edges_coords,
                    edge_width=np.minimum(graph2.es['overlap_fraction_target'],
                                          graph2.es['overlap_fraction_source']) * (edge_w_max - edge_w_min) + edge_w_min,
                    edge_color="lightgrey",
                    shape_type='line')
    edges_layer.editable = False

    # Add vertices
    shift_str = QKeySequence(Qt.ShiftModifier).toString().rstrip('+').upper()
    if 'Vertices' not in viewer_graph.layers:
        vertices_layer = viewer_graph.add_points(name='Vertices', opacity=1)
        if selectable:
            vertices_layer.help = "LEFT-CLICK to set view, RIGHT-CLICK to select, "+shift_str+" + RIGHT-CLICK to extend selection"
        else:
            vertices_layer.help = "LEFT-CLICK to set view"
        vertices_layer_isnew = True
    else:
        vertices_layer = viewer_graph.layers['Vertices']
        vertices_layer.data = []
        vertices_layer_isnew = False

    if graph2.vcount() > 0:
        # add only vertices with mask_id == 0
        vs = graph2.vs.select(mask_id_gt=0)
        vertices_layer.add(np.array([layout[v.index] for v in vs]))
        vertices_layer.border_width_is_relative = True
        vertices_layer.border_width = 0.0
        vertices_layer.symbol = 'square'
        vertices_layer.size = vertex_size
        vertices_layer.face_color = colors[vs['mask_id']]
        vertices_layer.face_color[vs['missing']] = 0
        vertices_layer.properties = {'frame': vs['frame'],
                                     'mask_id': vs['mask_id'],
                                     'selected': np.repeat(False, len(vs))}

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
                    if point_id is not None:
                        frame = layer.properties['frame'][point_id]
                        mask_id = layer.properties['mask_id'][point_id]
                        # just in case mask has changed and cell_tracking graph has not been updated yet:
                        if mask_id in get_YX_timeframe(mask_layer.data, frame):
                            viewer_images.dims.set_point(viewer_images.dims.axis_labels.index('T'), frame)
                            y0, x0 = np.mean(
                                np.where(get_YX_timeframe(mask_layer.data, frame) == mask_id), axis=1)
                            viewer_images.camera.center = (0, y0, x0)
                elif event.button == 2 and selectable:  # selection (right-click)
                    # vertices selection (multple mask_ids, same frame range for all)
                    point_id = layer.get_value(event.position)
                    if point_id is not None:
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
                        if 'Control' not in event.modifiers and 'Shift' not in event.modifiers:
                            # erase selection
                            layer.properties['selected'][layer.properties['selected']] = False
                    # change style
                    layer.border_color[layer.properties['selected']] = [1.0, 1.0, 1.0, 1.0]  # white
                    layer.border_width[~layer.properties['selected']] = 0
                    layer.border_width[layer.properties['selected']] = 0.4
                    layer.refresh()

        # mouse click on viewer_image (mask_layer)
        @mask_layer.mouse_drag_callbacks.append
        def click_drag(layer, event):
            T_axis_index = viewer_images.dims.axis_labels.index('T')
            dragged = False
            yield
            # on move
            while event.type == 'mouse_move':
                dragged = True
                yield
            # on release
            if not dragged:  # i.e. simple click
                if layer.mode == 'pan_zoom':
                    if event.button == 1:  # center view (left-click)
                        # center view on corresponding vertex
                        frame = event.position[T_axis_index]
                        mask_id = layer.get_value(event.position)
                        if mask_id is not None and mask_id > 0:
                            idx = np.where((viewer_graph.layers['Vertices'].properties['frame'] == frame) &
                                           (viewer_graph.layers['Vertices'].properties['mask_id'] == mask_id))[0]
                            if len(idx) == 1:
                                pos = viewer_graph.layers['Vertices'].data[idx][0]
                                viewer_graph.camera.center = (
                                    0, pos[0], pos[1])
                    if event.button == 2 and selectable:  # select in viewer_graph
                        frame = event.position[T_axis_index]
                        mask_id = layer.get_value(event.position)
                        point_id = None
                        if mask_id is not None and mask_id > 0:
                            idx = np.where((viewer_graph.layers['Vertices'].properties['frame'] == frame) &
                                           (viewer_graph.layers['Vertices'].properties['mask_id'] == mask_id))[0]
                            if len(idx) == 1:
                                point_id = idx[0]
                        if point_id is not None:
                            if 'Shift' in event.modifiers:
                                # add to selection
                                viewer_graph.layers['Vertices'].properties['selected'][point_id] = True
                                # find frame range
                                v_selected = np.where(
                                    viewer_graph.layers['Vertices'].properties['selected'])[0]
                                frame_min = np.min(
                                    viewer_graph.layers['Vertices'].properties['frame'][v_selected])
                                frame_max = np.max(
                                    viewer_graph.layers['Vertices'].properties['frame'][v_selected])
                                # find selected mask_ids
                                mask_ids = viewer_graph.layers['Vertices'].properties['mask_id'][v_selected]
                                # erase previous selection
                                viewer_graph.layers['Vertices'].properties['selected'] = False
                                # select all vertice with mask_id in mask_ids and within frame_range
                                viewer_graph.layers['Vertices'].properties['selected'][(viewer_graph.layers['Vertices'].properties['frame'] >= frame_min) & (
                                    viewer_graph.layers['Vertices'].properties['frame'] <= frame_max) & (np.isin(viewer_graph.layers['Vertices'].properties['mask_id'], mask_ids))] = True
                            else:
                                # replace selection
                                viewer_graph.layers['Vertices'].properties['selected'][
                                    viewer_graph.layers['Vertices'].properties['selected']] = False
                                viewer_graph.layers['Vertices'].properties['selected'][point_id] = (
                                    not viewer_graph.layers['Vertices'].properties['selected'][point_id])
                        else:
                            if 'Control' not in event.modifiers and 'Shift' not in event.modifiers:
                                # erase selection
                                viewer_graph.layers['Vertices'].properties['selected'][
                                    viewer_graph.layers['Vertices'].properties['selected']] = False
                        # change style
                        viewer_graph.layers['Vertices'].border_color[viewer_graph.layers['Vertices'].properties['selected']] = [1.0, 1.0, 1.0, 1.0]  # white
                        viewer_graph.layers['Vertices'].border_width[~viewer_graph.layers['Vertices'].properties['selected']] = 0
                        viewer_graph.layers['Vertices'].border_width[viewer_graph.layers['Vertices'].properties['selected']] = 0.4
                        viewer_graph.layers['Vertices'].refresh()

        viewer_graph.reset_view()


class CellTrackingGraph:
    def __init__(self, mask, max_delta_frame=5, min_overlap_fraction=0.2, beta=1):
        """
        Create cell tracking graph (`self._graph_full`) from mask

        Parameters
        ----------
        mask: ndarray
            a 3D (TYX) 16bit unsigned integer (uint16) numpy array
        max_delta_frame: int
            number of previous frames to consider when creating the cell tracking graph
        min_overlap_fraction: float
            minimum overlap fraction to consider when filtering the cell tracking graph (`self._graph`)
        beta: float, >= 1
            for cell tracking, the weight of the mask overlap between frames t1 and t2 is 1/beta**(t2-t1-1)
        """
        self.logger = logging.getLogger(__name__)

        self.min_overlap_fraction = min_overlap_fraction
        self.beta = beta
        self._max_delta_frame = max_delta_frame
        # Full graph (only internal)
        self._graph_full = ig.Graph(directed=True)
        # Final cell tracking graph (acces it with self.get_graph())
        self._graph = None
        self._create_graph(mask)

    def reset(self, mask, max_delta_frame=None, min_overlap_fraction=None, beta=None):
        """
        Reset the track

        Parameters
        ----------
        mask: ndarray
            a 3D (TYX) 16bit unsigned integer (uint16) numpy array
        max_delta_frame: int
            number of previous frames to consider when creating the cell tracking graph
        min_overlap_fraction: float
            minimum overlap fraction to consider when filtering the cell tracking graph (`self._graph`).
        beta: float, >= 1
            for cell tracking, the weight of the mask overlap between frames t1 and t2 is 1/beta**(t2-t1-1)
        """
        if min_overlap_fraction is not None:
            self.min_overlap_fraction = min_overlap_fraction
        if beta is not None:
            self.beta = beta
        if max_delta_frame is not None:
            self._max_delta_frame = max_delta_frame

        self._graph_full.clear()
        self._graph = None
        self._create_graph(mask)

    def relabel(self, mask):
        """
        Relabel mask so as to have consistent mask ids in consecutive frames
        Note : modify `mask` and `self._graph_full` in-place

        Parameters
        ----------
        mask: ndarray
            a 3D (TYX) 16bit unsigned integer (uint16) numpy array
        """
        self._relabel(mask)
        # Invalidate self._graph
        self._graph = None

    def update(self, mask, mask_new, region):
        """
        Update cell tracking graph (`self._graph_full`)

        Parameters
        ----------
        mask: ndarray
            a 3D (TYX) 16bit unsigned integer (uint16) numpy array
        mask_new:  numpy.array
            a 3D (TYX) unsigned integer (uint16) numpy array corresponding to a slice of mask
        region: list of tuples
            list of tuples ((frame_start,frame_end),(y_start,y_end),(x_start,x_end))
            specifying the position of `mask_new` within `mask`
            (i.e. mask[frame_start:frame_end,y_start:y_end,x_start:x_end])
        """

        frame_start = region[0][0]
        frame_end = region[0][1]
        mask_cropped = mask[:, region[1][0]:region[1][1], region[2][0]:region[2][1]]

        # Add attribute to keep track of modifications
        self._graph_full.vs['changed'] = False
        self._graph_full.es['changed'] = False

        self.logger.debug("Updating graph")
        # Modify vertex attribute 'area' (mask areas)
        for frame in range(frame_start, frame_end):
            # Evaluate difference of area between old (mask_cropped) and new (mask_new)
            m = max(mask_cropped[frame].max()+1, mask_new[frame-frame_start].max()+1).astype(mask.dtype)
            area_old = cv.calcHist(images=[mask_cropped[frame]], channels=[0], mask=None, histSize=[m], ranges=[0, m]).astype(np.int64).reshape(-1)
            area_new = cv.calcHist(images=[mask_new[frame-frame_start]], channels=[0], mask=None, histSize=[m], ranges=[0, m]).astype(np.int64).reshape(-1)
            area_diff = area_new - area_old

            # Modify 'area' vertex attribute (mask area)
            frame_vs = self._graph_full.vs.select(frame=frame, mask_id_lt=m)
            # Add missing vertices
            mask_ids_new = np.nonzero(area_new)[0]
            mask_ids_missing = np.setdiff1d(mask_ids_new[mask_ids_new > 0], frame_vs['mask_id'])
            if len(mask_ids_missing) > 0:
                self._graph_full.add_vertices(len(mask_ids_missing),
                                              {"frame": np.repeat(frame, len(mask_ids_missing)),
                                               "area": np.repeat(0, len(mask_ids_missing)),
                                               "mask_id": mask_ids_missing.astype(mask.dtype),
                                               "changed": True})
                frame_vs = self._graph_full.vs.select(frame=frame, mask_id_lt=m)
            # Update area
            frame_vs['area'] = frame_vs['area'] + area_diff[frame_vs['mask_id']]
            frame_vs['changed'] = [True if d != 0 else False for d in area_diff[frame_vs['mask_id']]]
            # Consider only modified edges
            frame_vs = self._graph_full.vs.select(frame=frame, mask_id_lt=m, changed=True)
            # Update overlap_fraction_source for outgoing edges
            outgoing_es = self._graph_full.es.select(_source_in=frame_vs)
            outgoing_es['overlap_fraction_source'] = [e['overlap_area']/self._graph_full.vs[e.source]['area'] for e in outgoing_es]
            outgoing_es['changed'] = True
            # Update overlap_fraction_source for incoming edges
            incoming_es = self._graph_full.es.select(_target_in=frame_vs)
            incoming_es['overlap_fraction_target'] = [e['overlap_area']/self._graph_full.vs[e.target]['area'] for e in incoming_es]
            incoming_es['changed'] = True

        # Modify edge attribute 'overlap_area'
        for frame1 in range(frame_start, min(mask.shape[0], frame_end+self._max_delta_frame)):
            frame2_range = range(max(0, frame1-self._max_delta_frame), min(frame_end, frame1))
            for frame2 in frame2_range:
                m = max(mask_cropped[frame1].max()+1, mask_cropped[frame2].max()+1)
                if frame1 in range(frame_start, frame_end):
                    m = max(m, mask_new[frame1-frame_start].max()+1)
                if frame2 in range(frame_start, frame_end):
                    m = max(m, mask_new[frame2-frame_start].max()+1)
                m = m.astype(mask.dtype)
                # Evaluate confusion matrix for old mask (mask_cropped)
                cm_old = cv.calcHist(images=[mask_cropped[frame1], mask_cropped[frame2]], channels=[0, 1], mask=None, histSize=[m, m], ranges=[0, m, 0, m]).astype(np.int64)
                # Evaluate confusion matrix for new mask (mask_cropped)
                if frame1 in range(frame_start, frame_end) and frame2 in range(frame_start, frame_end):
                    cm_new = cv.calcHist(images=[mask_new[frame1-frame_start], mask_new[frame2-frame_start]], channels=[0, 1], mask=None, histSize=[m, m], ranges=[0, m, 0, m]).astype(np.int64)
                elif frame1 in range(frame_start, frame_end) and frame2 not in range(frame_start, frame_end):
                    cm_new = cv.calcHist(images=[mask_new[frame1-frame_start], mask_cropped[frame2]], channels=[0, 1], mask=None, histSize=[m, m], ranges=[0, m, 0, m]).astype(np.int64)
                elif frame1 not in range(frame_start, frame_end) and frame2 in range(frame_start, frame_end):
                    cm_new = cv.calcHist(images=[mask_cropped[frame1], mask_new[frame2-frame_start]], channels=[0, 1], mask=None, histSize=[m, m], ranges=[0, m, 0, m]).astype(np.int64)
                else:
                    cm_new = cv.calcHist(images=[mask_cropped[frame1], mask_cropped[frame2]], channels=[0, 1], mask=None, histSize=[m, m], ranges=[0, m, 0, m]).astype(np.int64)

                cm_diff = cm_new-cm_old

                # Add edges (create if needed)
                # Select vertices from frame1 and frame2 for faster vertex search)
                frame1_vs = self._graph_full.vs.select(frame=frame1)
                frame2_vs = self._graph_full.vs.select(frame=frame2)
                elist = []
                overlap_area = []
                overlap_fraction_source = []
                overlap_fraction_target = []
                mask_id_source = []
                mask_id_target = []
                for id1, id2 in np.argwhere(cm_diff != 0):
                    # Ignore mask==0, i.e. cm_diff[0,:] and cm_diff[:,0]
                    if id1 > 0 and id2 > 0:
                        v2 = frame2_vs.find(mask_id=id2)
                        v1 = frame1_vs.find(mask_id=id1)
                        eid = self._graph_full.get_eid(v2, v1, error=False)
                        if eid < 0:
                            # Edge does not exist => add
                            elist.append((v2, v1))
                            overlap_area.append(cm_new[id1, id2])
                            overlap_fraction_source.append(cm_new[id1, id2]/v2['area'])
                            overlap_fraction_target.append(cm_new[id1, id2]/v1['area'])
                            mask_id_source.append(id2.astype(mask.dtype))
                            mask_id_target.append(id1.astype(mask.dtype))
                        else:
                            # Edge exist => modify
                            self._graph_full.es[eid]['overlap_area'] = self._graph_full.es[eid]['overlap_area']+cm_diff[id1, id2]
                            self._graph_full.es[eid]['overlap_fraction_source'] = self._graph_full.es[eid]['overlap_area']/v2['area']
                            self._graph_full.es[eid]['overlap_fraction_target'] = self._graph_full.es[eid]['overlap_area']/v1['area']
                            self._graph_full.es[eid]['changed'] = True

                if len(elist) > 0:
                    # Add missing edges (it is more efficient than adding one by one)
                    self._graph_full.add_edges(elist,
                                               {"overlap_area": overlap_area,
                                                "overlap_fraction_source": overlap_fraction_source,
                                                "overlap_fraction_target": overlap_fraction_target,
                                                "frame_source": np.repeat(frame2, len(elist)),
                                                "frame_target": np.repeat(frame1, len(elist)),
                                                "mask_id_source": mask_id_source,
                                                "mask_id_target": mask_id_target,
                                                "changed": np.repeat(True, len(elist))})

        # Clean cell tracking graph
        # Remove edges with overlap_area=0
        self._graph_full.delete_edges(self._graph_full.es.select(overlap_area=0))
        # Remove vertices with area=0
        self._graph_full.delete_vertices(self._graph_full.vs.select(area=0))

        # Remove useless attribute
        del self._graph_full.es['changed']
        del self._graph_full.vs['changed']

        # Invalidate self._graph
        self._graph = None

    def remove_vertices(self, vertices):
        """
        Remove vertices from cell tracking graph

        Parameters
        ----------
        vertices: list of tuple
            list of vertices to remove, each vertex is defined by the tuple (frame, mask_id)
        """

        self.logger.debug("Removing %s vertices", len(vertices))
        vs = self._graph_full.vs.select(lambda v: (v['frame'], v['mask_id']) in vertices)
        self._graph_full.delete_vertices(vs)
        # Invalidate self._graph
        self._graph = None

    def get_isolated_defects(self, nframes_defect=2, nframes_stable=3, stable_overlap_fraction=0, only_missing=False):
        """
        Return list of isolated defects in the cell tracking graph

        Parameters
        ----------
        nframes_defect: int
            maximum size of the defect (number of frames)
        nframes_stable: int
            minimum number of stable frames before and after the defect
        stable_overlap_fraction: float
            stable edges = with overlap_fraction_target >= `stable_overlap_fraction`
                             and overlap_fraction_source >= `stable_overlap_fraction`
        only_missing: bool
            only consider missing vertices type of defect

        Returns
        -------
        list of tuples
            Each each tuple corresponds to a defect (masks_ids, frame_start, frame_end)
            involving a list of mask ids (mask_ids) in the frame interval [frame_start, frame_end)
        """

        g = self.get_graph()

        self.logger.debug("Searching for isolated defects")
        # Search for stable portions of the graph (vertices connected only to vertices in consecutive frames with same mask_id)
        # Flag edges as stable if source vertex has a unique outgoing edge and target vertex has a unique incoming edge
        g.es['stable'] = False
        g.es.select(lambda edge: abs(g.vs[edge.source]['frame']-g.vs[edge.target]['frame']) == 1 and g.vs[edge.source]['mask_id'] == g.vs[edge.target]['mask_id'] and g.outdegree(edge.source) == 1 and g.indegree(edge.target) == 1)['stable'] = True
        # Flag edge with low overlap as unstable
        g.es.select(overlap_fraction_source_lt=stable_overlap_fraction)['stable'] = False
        g.es.select(overlap_fraction_target_lt=stable_overlap_fraction)['stable'] = False

        # Evaluate length of "stable edges" regions (size of connected components in the subgraph of "stable edges") and store it as vertex attribute
        g2 = g.subgraph_edges(g.es.select(stable=True), delete_vertices=False)
        components = g2.connected_components(mode='weak')
        for i, n in enumerate(components.sizes()):
            g.vs[components[i]]['stable_component_size'] = n

        # Search for connected components in the subgraph of "no stable edges"
        g2 = g.subgraph_edges(g.es.select(stable=False), delete_vertices=False)
        components = g2.connected_components(mode='weak')

        # Search for punctual defects:
        # - defect should not span more than nframes_defect consecutive frames
        # - the graph must be stable for at least nframes_stable consecutive frames before and after the defect.
        # Defects is a list of tuples (mask_ids,frame_start,frame_end), with mask_ids a list of mask_id
        defects = []
        frame_max = max(g.vs['frame'])
        for cmp in components:
            if only_missing:
                # Check that it contains only two vertices (i.e. missing vertices)
                if len(cmp) != 2:
                    continue
            # Check that it contains more than one vertex
            if not len(cmp) > 1:
                continue
            # Check that it spans not more than nframes_defect+2 frames
            cmp_frames = np.array(g2.vs[cmp]['frame'])
            first_frame = min(cmp_frames)
            last_frame = max(cmp_frames)
            if not last_frame-first_frame+1 <= nframes_defect+2:
                continue
            # Augment with all vertices in g with mask_ids in frame range [first_frame,last_frame]
            cmp_mask_ids = np.array(g2.vs[cmp]['mask_id'])
            vs = g.vs.select(frame_ge=first_frame, frame_le=last_frame, mask_id_in=cmp_mask_ids)
            # Check that it has the same mask_ids in first and last frame
            first_frame_mask_ids = np.sort(vs.select(frame=first_frame)['mask_id'])
            last_frame_mask_ids = np.sort(vs.select(frame=last_frame)['mask_id'])
            if not np.array_equal(first_frame_mask_ids, last_frame_mask_ids):
                continue
            # Check that all vertices in first frames and last frame are connected to at least nframes_stable stable frames
            # TODO: properly recompute number of stable frames BEFORE, and AFTER vertices in vs. Using stable_component_size as a proxy may overestimate the number of stable frames before/after vertices in vs, as it could include vertices in vs.
            first_frame_stable_component_size = min(vs.select(frame=first_frame)['stable_component_size'])
            if not first_frame_stable_component_size >= min(nframes_stable, first_frame+1):
                continue
            last_frame_stable_component_size = min(vs.select(frame=last_frame)['stable_component_size'])
            if not last_frame_stable_component_size >= min(nframes_stable, frame_max+1-last_frame):
                continue

            defects.append((np.unique(cmp_mask_ids).tolist(), first_frame+1, last_frame))

        return defects

    def get_graph(self):
        """
        Generate cell tracking graph (if needed) and return it

        Returns
        -------
        igraph.Graph
            cell tracking graph
        """
        if self._graph is None:
            self.logger.debug("Filtering graph")
            # Simplify graph to keep only edges corresponding to an overlap of at least 20% of cell area in both frames
            self._graph = self._graph_full.subgraph_edges(self._graph_full.es.select(overlap_fraction_source_ge=self.min_overlap_fraction, overlap_fraction_target_ge=self.min_overlap_fraction), delete_vertices=False)

            self.logger.debug("Adding missing edges between vertices with same mask_id")
            self._add_missing_edges()

            self.logger.debug("Removing redundant edges")
            self._remove_redundant_edges()

        return self._graph

    def _create_graph(self, mask):
        """
        Evaluate `self._graph_full` from `mask`

        Parameters
        ----------
        mask: ndarray
            a 3D (TYX) 16bit unsigned integer (uint16) numpy array
        """
        self.logger.debug("Creating cell tracking graph")
        self._graph_full.clear()
        for frame1 in range(mask.shape[0]):
            mask_ids1 = np.sort(np.unique(mask[frame1]))
            areas = np.bincount(mask[frame1].ravel())
            # Add vertices (i.e. cells) in frame i (ignore mask==0, which corresponds to background)
            self._graph_full.add_vertices(len(mask_ids1[mask_ids1 > 0]),
                                          {"frame": np.repeat(frame1, len(mask_ids1[mask_ids1 > 0])),
                                           "mask_id": mask_ids1[mask_ids1 > 0],
                                           "area": areas[mask_ids1[mask_ids1 > 0]]})

            frame2_range = range(max(0, frame1-self._max_delta_frame), frame1)

            for frame2 in frame2_range:
                mask_ids2 = np.sort(np.unique(mask[frame2]))
                mask_ids = np.union1d(mask_ids1, mask_ids2)
                # Evaluate confusion matrix
                cm_tmp = cv.calcHist(images=[mask[frame1], mask[frame2]], channels=[0, 1], mask=None, histSize=[max(mask_ids+1), max(mask_ids+1)], ranges=[0, max(mask_ids+1), 0, max(mask_ids+1)]).astype(np.int64)
                # Alternatives to cv.calcHist (slower):

                # * sklearn.metrics.confusion_matrix:
                #   cm_tmp=confusion_matrix(mask[frame1].ravel(),mask[frame2].ravel(),labels = np.arange(0,max(mask_ids)+1,dtype=mask.dtype))
                # * cm_tmp,xbins,ybins=np.histogram2d(mask[frame1].ravel(),mask[frame2].ravel(),bins=[max(mask_ids+1),max(mask_ids+1)],range=[[0,max(mask_ids+1)],[0,max(mask_ids+1)]])

                # Add edges
                elist = []
                overlap_area = []
                overlap_fraction_source = []
                overlap_fraction_target = []
                # Select vertices from frame1 and frame2 for faster vertex search)
                frame1_vs = self._graph_full.vs.select(frame=frame1)
                frame2_vs = self._graph_full.vs.select(frame=frame2)
                for id1, id2 in np.argwhere(cm_tmp > 0):
                    # Ignore mask==0, i.e. cm_tmp[0,:] and cm_tmp[:,0]
                    if id1 > 0 and id2 > 0:
                        v2 = frame2_vs.find(mask_id=id2)
                        v1 = frame1_vs.find(mask_id=id1)
                        elist.append((v2, v1))
                        overlap_area.append(cm_tmp[id1, id2])
                        overlap_fraction_source.append(cm_tmp[id1, id2]/v2['area'])
                        overlap_fraction_target.append(cm_tmp[id1, id2]/v1['area'])
                self._graph_full.add_edges(elist,
                                           {"overlap_area": overlap_area,
                                            "overlap_fraction_source": overlap_fraction_source,
                                            "overlap_fraction_target": overlap_fraction_target})
        # Add attributes
        self._graph_full.es['frame_source'] = [self._graph_full.vs[e.source]['frame'] for e in self._graph_full.es]
        self._graph_full.es['frame_target'] = [self._graph_full.vs[e.target]['frame'] for e in self._graph_full.es]
        self._graph_full.es['mask_id_source'] = [self._graph_full.vs[e.source]['mask_id'] for e in self._graph_full.es]
        self._graph_full.es['mask_id_target'] = [self._graph_full.vs[e.target]['mask_id'] for e in self._graph_full.es]

    def _relabel(self, mask):
        """
        Using `self._graph_full`, relabel mask (modify `mask` and `self._graph_full`)
        so as to have consistent mask ids in consecutive frames

        Parameters
        ----------
        mask: ndarray
            a 3D (TYX) 16bit unsigned integer (uint16) numpy array
        """
        # Relabel mask and graph (mask_ids)
        n_ids = 1  # Store 1 + highest mask_id assigned so far
        self.logger.debug("Relabelling mask and cell tracking graph")
        for frame1 in range(mask.shape[0]):
            frame1_vs = self._graph_full.vs.select(frame=frame1)
            mask_ids1 = np.sort(np.unique(frame1_vs['mask_id'])).astype(mask.dtype)
            max_mask_ids1 = np.max(mask_ids1) if len(mask_ids1) > 0 else 0
            # Check mask and self._graph_full are consistent:
            if not np.array_equal(mask_ids1, np.sort(np.unique(mask[frame1][mask[frame1] > 0]))):
                raise ValueError("not the same mask_ids in mask and self._graph_full")
            map_id = np.repeat(-1, max_mask_ids1+1)
            if frame1 == 0:
                # Relabel with consecutiv mask_ids
                for mask_id in mask_ids1:
                    if mask_id > 0:
                        map_id[mask_id] = n_ids
                        n_ids += 1
                # Map 0 to 0
                map_id[0] = 0
            else:
                frame2_range = range(max(0, frame1-self._max_delta_frame), frame1)
                mask_ids2 = np.sort(np.unique(self._graph_full.vs.select(frame_in=frame2_range)['mask_id'])).astype(mask.dtype)
                mask_ids = np.union1d(mask_ids1, mask_ids2)
                max_mask_ids = np.max(mask_ids) if len(mask_ids) > 0 else 0
                # Confusion matrix (contain the sum of mask overlap between frame1 and frame2 (with frame2=frame1-1,frame1-2,...frame1-self._max_delta_frame))
                cm = np.zeros((max_mask_ids+1, max_mask_ids+1), dtype=np.int64)
                for frame2 in frame2_range:
                    # Get confusion matrix
                    # e = (v2,v1).overlap_area = cm_tmp[id1,id2]
                    frame12_es = self._graph_full.es.select(frame_source=frame2, frame_target=frame1)
                    cm_tmp = np.zeros((max_mask_ids+1, max_mask_ids+1), dtype=np.int64)
                    cm_tmp[frame12_es['mask_id_target'], frame12_es['mask_id_source']] = frame12_es['overlap_area']
                    if self.beta > 1:
                        cm_tmp /= (self.beta**(frame1-frame2-1))
                    cm += cm_tmp.astype(np.int64)

                # Use Hungarian algorithm (linear_sum_assignment) to solve minimum weight matching in bipartite graphs.
                # ignore mask==0, i.e. cm[0,:] and cm[:,0]
                row_ind, col_ind = linear_sum_assignment(-cm)
                map_id = np.repeat(-1, max_mask_ids1+1)
                for r, c in zip(row_ind, col_ind):
                    if cm[r, c] > 0:
                        map_id[r] = c
                # Add missing
                for mask_id in mask_ids1:
                    if map_id[mask_id] < 0:
                        map_id[mask_id] = n_ids
                        n_ids += 1
                # Map background (0) to itself
                map_id[0] = 0
            # Relabel
            mask[frame1] = map_id[mask[frame1]]
            frame1_vs['mask_id'] = map_id[frame1_vs['mask_id']].astype(mask.dtype)
            frame1_es = self._graph_full.es.select(frame_source=frame1)
            frame1_es['mask_id_source'] = map_id[frame1_es['mask_id_source']].astype(mask.dtype)
            frame1_es = self._graph_full.es.select(frame_target=frame1)
            frame1_es['mask_id_target'] = map_id[frame1_es['mask_id_target']].astype(mask.dtype)

    def _add_missing_edges(self):
        """
        Add missing edges to `self._graph` to connect disconnected vertices with same mask_id
        """
        # Add missing edge to link vertices with same mask_id
        for mask_id in np.unique(self._graph.vs['mask_id']):
            v2 = None
            frame2 = None
            maskid_vs = self._graph.vs.select(mask_id=mask_id)
            for frame1 in np.sort(np.unique(maskid_vs['frame'])):
                frame1_vs = maskid_vs.select(frame=frame1)
                if len(frame1_vs) == 1:
                    v1 = frame1_vs[0]
                    if v2:
                        # Add edge if it does not exist
                        if self._graph.get_eid(v2, v1, error=False) < 0:
                            self._graph.add_edge(v2, v1, overlap_area=np.int64(0), overlap_fraction_source=np.float64(0), overlap_fraction_target=np.float64(0),
                                                 frame_source=frame2, frame_target=frame1,
                                                 mask_id_source=v2['mask_id'], mask_id_target=v1['mask_id'])
                    v2 = v1
                    frame2 = frame1

    def _remove_redundant_edges(self):
        """
        Remove redundant edges in `self._graph` (edge attributes 'redundant')
        Redundant edges are defined as:
            - For a pair of mask_id1 mask_id2, consider all edges connecting mask_id1 to mask_id2.
            - For each edge in this list connecting frame1 to frame2, flag all other edges in this
            list connecting frame1-n to frame2+m (with n,m>=0) as redundant
        """
        mask_id_pairs = [(self._graph.vs[e.source]['mask_id'], self._graph.vs[e.target]['mask_id']) for e in self._graph.es]
        mask_id_pairs = set(mask_id_pairs)
        self._graph.es['redundant'] = False

        for mask_id1, mask_id2 in mask_id_pairs:
            edge_list = self._graph.es.select(mask_id_source=mask_id1, mask_id_target=mask_id2)
            # Order by frame_source
            edge_list = edge_list[np.argsort(edge_list['frame_source'])]
            edge_list2 = edge_list
            for e in edge_list:
                # Keep only edge with frame_source>=e['frame_source'] (edges with frame_source<e['frame_source'] will not be used anymore)
                edge_list2 = edge_list2.select(frame_source_ge=e['frame_source'])
                # Flag e as redundant if more than one edge (itself) is contained in the frame interval [e['frame_source'],e['frame_target']]
                e['redundant'] = (len(edge_list2.select(frame_target_le=e['frame_target'])) > 1)

        # Remove redundant edges
        self._graph.delete_edges(self._graph.es.select(redundant=True))
        # Remove useless attribute
        del self._graph.es['redundant']


class CellTrackingWidget(QWidget):
    """
    A widget to use inside napari
    """

    # TODO: pass the mask as an Image object, instead of using the quick&dirty hack to pass the additional parameters mask_physical_pixel_sizes and mask_channel_names.
    def __init__(self, mask, cell_tracking_graph, viewer_graph, viewer_images, image_path, output_path, output_basename, min_area=300, max_delta_frame=5, min_overlap_fraction=0.2, max_delta_frame_interpolation=3, nframes_defect=2, nframes_stable=3, stable_overlap_fraction=0, mask_physical_pixel_sizes=(None, None, None), mask_channel_names=None, mask_metadata=None):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.logger.debug("CellTrackingWidget.__init__")

        self.mask = mask
        self.mask_physical_pixel_sizes = mask_physical_pixel_sizes
        self.mask_channel_names = mask_channel_names
        self.mask_metadata = mask_metadata
        self.cell_tracking_graph = cell_tracking_graph
        self.viewer_graph = viewer_graph
        self.viewer_images = viewer_images
        self.image_path = image_path
        self.output_path = output_path
        self.output_basename = output_basename

        # True if mask have been modified using napari paint tools (and thus need to call self.relabel()):
        self.mask_need_relabelling = False
        # True if mask have been modified since last save:
        self.mask_modified = True

        layout = QVBoxLayout()

        groupbox = QGroupBox("Help")
        layout2 = QVBoxLayout()

        shift_str = QKeySequence(Qt.ShiftModifier).toString().rstrip('+').upper()
        help_label = QLabel("Image viewer (this viewer):\nLEFT-CLICK on the Cell mask layer to center the view on the corresponding vertex in the cell tracking graph viewer. RIGHT-CLICK to select the corresponding vertex in cell tracking graph and "+shift_str+" + RIGHT-CLICK to extend selection.\nMask can be manually edited using the Cell mask layer controls. Once done, click on the \"Relabel\" button to update the cell tracking tracking graph.\n\nCell tracking graph viewer:\nVertices (squares) correspond to labelled regions (mask id) at a given frame. Edges correspond to overlap between mask. Vertices are ordered by time along the horizontal axis (time increases from left to right).\nLEFT-CLICK on a vertex to center the view on the corresponding mask in this viewer. RIGHT-CLICK to select a vertex and "+shift_str+" + RIGHT-CLICK to extend selection.")
        help_label.setWordWrap(True)
        help_label.setMinimumWidth(10)
        layout2.addWidget(help_label)

        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        groupbox = QGroupBox("Automatic cleaning")
        layout2 = QGridLayout()

        help_label = QLabel("Search for isolated defects in the cell tracking graph and try to remove them by interpolating corresponding mask across neighboring frames.")
        help_label.setWordWrap(True)
        help_label.setMinimumWidth(10)
        layout2.addWidget(help_label, 0, 0, 1, 2)

        self.stable_overlap_fraction = QSpinBox()
        self.stable_overlap_fraction.setMinimum(0)
        self.stable_overlap_fraction.setMaximum(100)
        self.stable_overlap_fraction.setValue(int(100*stable_overlap_fraction))
        self.stable_overlap_fraction.setSuffix('%')
        self.stable_overlap_fraction.setToolTip('Cell tracking graph edges corresponding to an overlap fraction below this value are considered as not stable.')
        layout2.addWidget(QLabel("Stable overlap fraction:"), 1, 0)
        layout2.addWidget(self.stable_overlap_fraction, 1, 1)

        self.nframes_defect = QSpinBox()
        self.nframes_defect.setMinimum(1)
        self.nframes_defect.setMaximum(50)
        self.nframes_defect.setValue(int(nframes_defect))
        self.nframes_defect.setToolTip('Maximum size of the defect (number of frames).')
        self.nframes_defect.valueChanged.connect(self.nframes_defect_changed)
        layout2.addWidget(QLabel("Max defect size (frames):"), 2, 0)
        layout2.addWidget(self.nframes_defect, 2, 1)

        self.max_delta_frame_interpolation = QSpinBox()
        self.max_delta_frame_interpolation.setMinimum(1)
        self.max_delta_frame_interpolation.setMaximum(50)
        self.max_delta_frame_interpolation.setValue(int(max_delta_frame_interpolation))
        self.max_delta_frame_interpolation.setToolTip('Number of previous and subsequent frames to consider for mask interpolation.')
        self.max_delta_frame_interpolation.valueChanged.connect(self.max_delta_frame_interpolation_changed)
        layout2.addWidget(QLabel("Max delta frame (interpolation):"), 3, 0)
        layout2.addWidget(self.max_delta_frame_interpolation, 3, 1)

        self.nframes_stable = QSpinBox()
        self.nframes_stable.setMinimum(1)
        self.nframes_stable.setMaximum(50)
        self.nframes_stable.setValue(int(nframes_stable))
        self.nframes_stable.setToolTip('Minimum number of stable frames before and after the defect.')
        self.nframes_stable.valueChanged.connect(self.nframes_stable_changed)
        layout2.addWidget(QLabel("Min stable size (frames):"), 4, 0)
        layout2.addWidget(self.nframes_stable, 4, 1)

        self.min_area = QSpinBox()
        self.min_area.setMinimum(1)
        self.min_area.setMaximum(10000)
        self.min_area.setValue(int(min_area))
        self.min_area.setToolTip('Remove labelled regions with area (number of pixels) below this value')
        layout2.addWidget(QLabel("Min area:"), 5, 0)
        layout2.addWidget(self.min_area, 5, 1)

        # Create a checkbox to select only missing frames
        self.only_missing = QCheckBox("Clean \"missing\" mask only")
        self.only_missing.setChecked(False)
        layout2.addWidget(self.only_missing, 6, 0, 1, 2, Qt.AlignLeft)

        # Create a checkbox to select only missing frames
        self.show_mask_diff = QCheckBox("Add a layer with mask modifications")
        self.show_mask_diff.setChecked(False)
        layout2.addWidget(self.show_mask_diff, 7, 0, 1, 2, Qt.AlignLeft)

        # Create a button to clean mask
        button = QPushButton("Clean")
        button.setToolTip('Search for isolated defects in the cell tracking graph and try to clean them by interpolating corresponding mask across neighboring frames.')
        button.clicked.connect(self.clean_mask)
        layout2.addWidget(button, 8, 0, 1, 2, Qt.AlignCenter)

        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        groupbox = QGroupBox("Interpolate selection")
        layout2 = QGridLayout()

        help_label = QLabel("Interpolate selected mask across neighboring frames. Use the cell tracking graph viewer to select mask")
        help_label.setWordWrap(True)
        help_label.setMinimumWidth(10)
        layout2.addWidget(help_label, 0, 0, 1, 2)

        self.max_delta_frame_interpolation2 = QSpinBox()
        self.max_delta_frame_interpolation2.setMinimum(1)
        self.max_delta_frame_interpolation2.setMaximum(50)
        self.max_delta_frame_interpolation2.setValue(int(max_delta_frame_interpolation))
        self.max_delta_frame_interpolation2.setToolTip('Number of previous and subsequent frames to consider for mask interpolation.')
        layout2.addWidget(QLabel("Max delta frame (interpolation):"), 1, 0)
        layout2.addWidget(self.max_delta_frame_interpolation2, 1, 1)

        self.min_area2 = QSpinBox()
        self.min_area2.setMinimum(1)
        self.min_area2.setMaximum(10000)
        self.min_area2.setValue(int(min_area))
        self.min_area2.setToolTip('Remove labelled regions with area (number of pixels) below this value')
        layout2.addWidget(QLabel("Min area:"), 2, 0)
        layout2.addWidget(self.min_area2, 2, 1)

        self.show_mask_diff2 = QCheckBox("Add a layer with mask modifications")
        self.show_mask_diff2.setChecked(False)
        layout2.addWidget(self.show_mask_diff2, 3, 0, 1, 2, Qt.AlignLeft)

        # Create a button to clean mask
        button = QPushButton("Interpolate selection")
        button.setToolTip('Interpolated selected labelled regions across neighboring frames.')
        button.clicked.connect(self.interpolate_mask)
        layout2.addWidget(button, 4, 0, 1, 2, Qt.AlignCenter)

        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        groupbox = QGroupBox("Relabel mask and graph")
        layout2 = QGridLayout()

        help_label = QLabel("Split disconnected labelled regions, remove small labelled regions, recompute cell tracking graph and relabel labelled regions so as to have consistent mask ids in consecutive frames. Should be done if the mask are manually edited to synchronize cell tracking. It is also advised to do it before saving, to make sure to split disconnected labelled regions.")
        help_label.setWordWrap(True)
        help_label.setMinimumWidth(10)
        layout2.addWidget(help_label, 0, 0, 1, 2)

        self.max_delta_frame = QSpinBox()
        self.max_delta_frame.setMinimum(1)
        self.max_delta_frame.setMaximum(50)
        self.max_delta_frame.setValue(int(max_delta_frame))
        self.max_delta_frame.setToolTip('Number of previous frames to consider when creating the cell tracking graph.')
        layout2.addWidget(QLabel("Max delta frame:"), 1, 0)
        layout2.addWidget(self.max_delta_frame, 1, 1)

        self.min_area3 = QSpinBox()
        self.min_area3.setMinimum(1)
        self.min_area3.setMaximum(10000)
        self.min_area3.setValue(int(min_area))
        self.min_area3.setToolTip('Remove labelled regions with area (number of pixels) below this value.')
        layout2.addWidget(QLabel("Min area:"), 2, 0)
        layout2.addWidget(self.min_area3, 2, 1)

        self.min_overlap_fraction = QSpinBox()
        self.min_overlap_fraction.setMinimum(0)
        self.min_overlap_fraction.setMaximum(100)
        self.min_overlap_fraction.setValue(int(100*min_overlap_fraction))
        self.min_overlap_fraction.setSuffix('%')
        self.min_overlap_fraction.setToolTip('minimum overlap fraction (w.r.t mask area) to consider when creating edges in the cell tracking graph.')
        layout2.addWidget(QLabel("Min overlap fraction:"), 3, 0)
        layout2.addWidget(self.min_overlap_fraction, 3, 1)

        self.show_mask_diff3 = QCheckBox("Add a layer with mask modifications")
        self.show_mask_diff3.setChecked(False)
        layout2.addWidget(self.show_mask_diff3, 4, 0, 1, 2, Qt.AlignLeft)

        # Create a button to relabel mask
        button = QPushButton("Relabel")
        button.setToolTip('Split disconnected labelled regions, recompute cell tracking graph and relabel mask (slow).')
        button.clicked.connect(self.relabel)
        layout2.addWidget(button, 5, 0, 1, 2, Qt.AlignCenter)

        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        groupbox = QGroupBox("Save && quit")
        layout2 = QVBoxLayout()
        layout3 = QHBoxLayout()

        # Save button
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.save)
        layout3.addWidget(self.save_button)

        # Create a button to quit
        button = QPushButton("Quit")
        button.clicked.connect(self.quit)
        layout3.addWidget(button)
        layout2.addLayout(layout3)

        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        # Add spacer (to avoid filling whole space when the widget is inside a QScrollArea)
        layout.addStretch(1)
        self.setLayout(layout)

        if self.mask_modified:
            self.save_button.setStyleSheet("background: darkred;")
        if self.mask_need_relabelling:
            self.save_button.setText("Relabel && Save")

        # To detect image modifications
        self.viewer_images.layers['Cell mask'].events.paint.connect(self.paint_callback)

        # To allow saving image & mask before closing (__del__ is called too late)
        # TODO: replace by proper napari close event once implemented (https://forum.image.sc/t/handle-of-close-event-in-napari/61039)
        self.viewer_images.window._qt_window.destroyed.connect(self.on_viewer_images_close)

        # Add a handler to output messages to napari status bar
        handler = gf.NapariStatusBarHandler(self.viewer_images)
        handler.setFormatter(logging.Formatter('%(message)s'))
        handler.setLevel(logging.DEBUG)
        self.logger.addHandler(handler)

        self.logger.debug("Ready")

    def paint_callback(self, event):
        self.logger.info("Manually editing mask")
        self.mask_need_relabelling = True
        self.save_button.setText("Relabel && Save")
        self.mask_modified = True
        self.save_button.setStyleSheet("background: darkred;")

    def nframes_defect_changed(self, value):
        # Set nframes_defect<=max_delta_frame_interpolation<=nframes_stable
        if self.nframes_stable.value() < value:
            self.nframes_stable.setValue(int(value))
        if self.max_delta_frame_interpolation.value() < value:
            self.max_delta_frame_interpolation.setValue(int(value))

    def max_delta_frame_interpolation_changed(self, value):
        # Set nframes_defect<=max_delta_frame_interpolation<=nframes_stable
        if self.nframes_stable.value() < value:
            self.nframes_stable.setValue(int(value))
        if self.nframes_defect.value() > value:
            self.nframes_defect.setValue(int(value))

    def nframes_stable_changed(self, value):
        # Set nframes_defect<=max_delta_frame_interpolation<=nframes_stable
        if self.nframes_defect.value() > value:
            self.nframes_defect.setValue(int(value))
        if self.max_delta_frame_interpolation.value() > value:
            self.max_delta_frame_interpolation.setValue(int(value))

    def clean_mask(self):
        # Set cursor to BusyCursor
        napari.qt.get_qapp().setOverrideCursor(QCursor(Qt.BusyCursor))
        napari.qt.get_qapp().processEvents()

        if self.show_mask_diff.isChecked():
            mask_original = self.mask.copy()

        self.logger.info("Automatic cleaning: max delta frame=%s, max defect size=%s, min stable size=%s, stable overlap fraction=%s%%, min area=%s, clean missing mask only=%s",
                         self.max_delta_frame_interpolation.value(),
                         self.nframes_defect.value(),
                         self.nframes_stable.value(),
                         self.stable_overlap_fraction.value(),
                         self.min_area.value(),
                         self.only_missing.isChecked())
        clean_mask(self.mask,
                   self.cell_tracking_graph,
                   max_delta_frame_interpolation=self.max_delta_frame_interpolation.value(),
                   nframes_defect=self.nframes_defect.value(),
                   nframes_stable=self.nframes_stable.value(),
                   stable_overlap_fraction=self.stable_overlap_fraction.value()/100,
                   min_area=self.min_area.value(),
                   only_missing=self.only_missing.isChecked())

        if self.show_mask_diff.isChecked():
            mask_diff = np.zeros(self.mask.shape, dtype='uint8')
            mask_diff[self.mask == mask_original] = 0
            mask_diff[(self.mask != mask_original) & (self.mask == 0)] = 1  # removed
            mask_diff[(self.mask != mask_original) & (self.mask != 0) & (mask_original != 0)] = 2  # modified
            mask_diff[(self.mask != mask_original) & (mask_original == 0)] = 3  # added
            del mask_original
            # broadcast TYX mask_diff to FTZYX with F and Z axis containing shallow copies (C axis is used as channel_axis):
            sizeF = self.viewer_images.layers['Cell mask'].data.shape[0]
            sizeZ = self.viewer_images.layers['Cell mask'].data.shape[2]
            mask_diff_FTZYX = np.broadcast_to(mask_diff[np.newaxis, :, np.newaxis, :, :], (sizeF, mask_diff.shape[0], sizeZ, mask_diff.shape[1], mask_diff.shape[2]))
            layer = self.viewer_images.add_image(mask_diff_FTZYX, name="Cell mask modifications (1: removed, 2: modified, 3: added)", opacity=0.8,
                                                 colormap=napari.utils.Colormap([[0, 0, 0, 0],
                                                                                 [0.77, 0.27, 0.29, 1],
                                                                                 [0.16, 0.36, 0.62, 1],
                                                                                 [0.30, 0.51, 0.15, 1]]),
                                                 contrast_limits=[0, 3], visible=False)
            layer.editable = False
            self.viewer_images.layers.selection.active = self.viewer_images.layers['Cell mask']

        self.viewer_images.layers['Cell mask'].refresh()

        self.logger.debug("Plotting cell tracking graph")
        # make sure all labels are visible to avoid problems with get_color
        self.viewer_images.layers['Cell mask'].show_selected_label = False
        plot_cell_tracking_graph(self.viewer_graph,
                                 self.viewer_images,
                                 self.viewer_images.layers['Cell mask'],
                                 self.cell_tracking_graph.get_graph(),
                                 self.viewer_images.layers['Cell mask'].get_color(range(self.mask.max()+1)))

        self.mask_modified = True
        self.save_button.setStyleSheet("background: darkred;")
        self.mask_need_relabelling = True
        self.save_button.setText("Relabel && Save")

        self.logger.debug("Done")
        # Restore cursor
        napari.qt.get_qapp().restoreOverrideCursor()

    def interpolate_mask(self):
        # Set cursor to BusyCursor
        napari.qt.get_qapp().setOverrideCursor(QCursor(Qt.BusyCursor))
        napari.qt.get_qapp().processEvents()

        if self.show_mask_diff2.isChecked():
            mask_original = self.mask.copy()

        if any(self.viewer_graph.layers['Vertices'].properties['selected']):
            mask_ids = np.unique(self.viewer_graph.layers['Vertices'].properties['mask_id'][self.viewer_graph.layers['Vertices'].properties['selected']])
            frames = self.viewer_graph.layers['Vertices'].properties['frame'][self.viewer_graph.layers['Vertices'].properties['selected']]
            frame_start = frames.min()
            frame_end = frames.max()+1
            self.logger.info("Interpolating selected mask: max delta frame=%s, min area=%s, selected frames [%s,%s], selected mask ids (%s)",
                             self.max_delta_frame_interpolation2.value(),
                             self.min_area2.value(),
                             frame_start,
                             frame_end-1,
                             ",".join([str(x) for x in mask_ids]))
            interpolate_mask(self.mask,
                             self.cell_tracking_graph,
                             mask_ids,
                             frame_start,
                             frame_end,
                             max_delta_frame_interpolation=self.max_delta_frame_interpolation2.value(),
                             min_area=self.min_area2.value())

        if self.show_mask_diff2.isChecked():
            mask_diff = np.zeros(self.mask.shape, dtype='uint8')
            mask_diff[self.mask == mask_original] = 0
            mask_diff[(self.mask != mask_original) & (self.mask == 0)] = 1  # removed
            mask_diff[(self.mask != mask_original) & (self.mask != 0) & (mask_original != 0)] = 2  # modified
            mask_diff[(self.mask != mask_original) & (mask_original == 0)] = 3  # added
            del mask_original
            # broadcast TYX mask_diff to FTZYX with F and Z axis containing shallow copies (C axis is used as channel_axis):
            sizeF = self.viewer_images.layers['Cell mask'].data.shape[0]
            sizeZ = self.viewer_images.layers['Cell mask'].data.shape[2]
            mask_diff_FTZYX = np.broadcast_to(mask_diff[np.newaxis, :, np.newaxis, :, :], (sizeF, mask_diff.shape[0], sizeZ, mask_diff.shape[1], mask_diff.shape[2]))
            layer = self.viewer_images.add_image(mask_diff_FTZYX, name="Cell mask modifications (1: removed, 2: modified, 3: added)", opacity=0.8,
                                                 colormap=napari.utils.Colormap([[0, 0, 0, 0],
                                                                                 [0.77, 0.27, 0.29, 1],
                                                                                 [0.16, 0.36, 0.62, 1],
                                                                                 [0.30, 0.51, 0.15, 1]]),
                                                 contrast_limits=[0, 3], visible=False)
            layer.editable = False
            self.viewer_images.layers.selection.active = self.viewer_images.layers['Cell mask']

        self.viewer_images.layers['Cell mask'].refresh()

        self.logger.debug("Plotting cell tracking graph")
        # make sure all labels are visible to avoid problems with get_color
        self.viewer_images.layers['Cell mask'].show_selected_label = False
        plot_cell_tracking_graph(self.viewer_graph,
                                 self.viewer_images,
                                 self.viewer_images.layers['Cell mask'],
                                 self.cell_tracking_graph.get_graph(),
                                 self.viewer_images.layers['Cell mask'].get_color(range(self.mask.max()+1)))

        self.mask_modified = True
        self.save_button.setStyleSheet("background: darkred;")
        self.mask_need_relabelling = True
        self.save_button.setText("Relabel && Save")

        self.logger.debug("Done")
        # Restore cursor
        napari.qt.get_qapp().restoreOverrideCursor()

    def relabel(self, closing=False):
        # Set cursor to BusyCursor
        napari.qt.get_qapp().setOverrideCursor(QCursor(Qt.BusyCursor))
        napari.qt.get_qapp().processEvents()

        if self.show_mask_diff3.isChecked():
            mask_original = self.mask.copy()

        self.logger.info("Creating cell tracking graph and relabelling mask: max delta frame=%s, min overlap fraction=%s%%, min area=%s",
                         self.max_delta_frame.value(),
                         self.min_overlap_fraction.value(),
                         self.min_area3.value())
        split_regions(self.mask)
        remove_small_regions(self.mask, self.min_area3.value())
        self.cell_tracking_graph.reset(self.mask,
                                       max_delta_frame=int(self.max_delta_frame.value()),
                                       min_overlap_fraction=self.min_overlap_fraction.value()/100)
        self.cell_tracking_graph.relabel(self.mask)

        if self.show_mask_diff3.isChecked() and not closing:
            mask_diff = np.zeros(self.mask.shape, dtype='uint8')
            mask_diff[self.mask == mask_original] = 0
            mask_diff[(self.mask != mask_original) & (self.mask == 0)] = 1  # removed
            mask_diff[(self.mask != mask_original) & (self.mask != 0) & (mask_original != 0)] = 2  # modified
            mask_diff[(self.mask != mask_original) & (mask_original == 0)] = 3  # added
            del mask_original
            # broadcast TYX mask_diff to FTZYX with F and Z axis containing shallow copies (C axis is used as channel_axis):
            sizeF = self.viewer_images.layers['Cell mask'].data.shape[0]
            sizeZ = self.viewer_images.layers['Cell mask'].data.shape[2]
            mask_diff_FTZYX = np.broadcast_to(mask_diff[np.newaxis, :, np.newaxis, :, :], (sizeF, mask_diff.shape[0], sizeZ, mask_diff.shape[1], mask_diff.shape[2]))
            layer = self.viewer_images.add_image(mask_diff_FTZYX, name="Cell mask modifications (1: removed, 2: modified, 3: added)", opacity=0.8,
                                                 colormap=napari.utils.Colormap([[0, 0, 0, 0],
                                                                                 [0.77, 0.27, 0.29, 1],
                                                                                 [0.16, 0.36, 0.62, 1],
                                                                                 [0.30, 0.51, 0.15, 1]]),
                                                 contrast_limits=[0, 3], visible=False)
            layer.editable = False
            self.viewer_images.layers.selection.active = self.viewer_images.layers['Cell mask']

        if not closing:
            self.viewer_images.layers['Cell mask'].refresh()

            self.logger.debug("Plotting cell tracking graph")
            # make sure all labels are visible to avoid problems with get_color
            self.viewer_images.layers['Cell mask'].show_selected_label = False
            plot_cell_tracking_graph(self.viewer_graph,
                                     self.viewer_images,
                                     self.viewer_images.layers['Cell mask'],
                                     self.cell_tracking_graph.get_graph(),
                                     self.viewer_images.layers['Cell mask'].get_color(range(self.mask.max()+1)))

            self.save_button.setStyleSheet("background: darkred;")
            self.save_button.setText("Save")
        self.mask_modified = True
        self.mask_need_relabelling = False

        self.logger.debug("Done")
        # Restore cursor
        napari.qt.get_qapp().restoreOverrideCursor()

    def save(self, closing=False):
        # Set cursor to BusyCursor
        napari.qt.get_qapp().setOverrideCursor(QCursor(Qt.BusyCursor))
        napari.qt.get_qapp().processEvents()

        if self.mask_need_relabelling:
            self.relabel(closing)

        # TODO: adapt metadata to more generic input files (other axes)
        output_file1 = os.path.join(self.output_path, self.output_basename+".ome.tif")
        self.logger.info("Saving segmentation mask to %s", output_file1)
        ome_metadata = OmeTiffWriter.build_ome(data_shapes=[self.mask.shape],
                                               data_types=[self.mask.dtype],
                                               dimension_order=["TYX"],
                                               channel_names=[self.mask_channel_names],
                                               physical_pixel_sizes=[PhysicalPixelSizes(X=self.mask_physical_pixel_sizes[0], Y=self.mask_physical_pixel_sizes[1], Z=self.mask_physical_pixel_sizes[2])])
        ome_metadata.structured_annotations.append(CommentAnnotation(value=buffered_handler.get_messages(), namespace="VLabApp"))
        for x in self.mask_metadata:
            ome_metadata.structured_annotations.append(CommentAnnotation(value=x, namespace="VLabApp"))
        OmeTiffWriter.save(self.mask, output_file1, ome_xml=ome_metadata)

        output_file3 = os.path.join(self.output_path, self.output_basename+".graphmlz")
        self.logger.info("Saving cell tracking graph to %s", output_file3)
        g = self.cell_tracking_graph.get_graph()
        # add metadata
        g['VLabApp:Annotation:1'] = buffered_handler.get_messages()
        for i, x in enumerate(self.mask_metadata):
            g['VLabApp:Annotation:'+str(i+2)] = x
        g.write_graphmlz(output_file3)

        if not closing:
            self.mask_modified = False
            self.save_button.setStyleSheet("")

        self.logger.debug("Done")
        # Restore cursor
        napari.qt.get_qapp().restoreOverrideCursor()

        QMessageBox.information(self, 'Files saved', 'Mask and graph saved to\n' + output_file1 + "\n" + output_file3)

    def quit(self):
        # TODO: currently, all napari viewers are closed (including viewers opened by other modules). Find a way to close only viewer_graph and viewer_images (avoid errors if one of the viewers is already closed).
        while napari.current_viewer() is not None:
            napari.current_viewer().close()

    def on_viewer_images_close(self):
        # Restore cursor
        napari.qt.get_qapp().restoreOverrideCursor()
        if self.mask_modified:
            if self.mask_need_relabelling:
                save = QMessageBox.question(self, 'Save changes', "Relabel and save changes before closing?", QMessageBox.Yes | QMessageBox.No)
            else:
                save = QMessageBox.question(self, 'Save changes', "Save changes before closing?", QMessageBox.Yes | QMessageBox.No)
            if save == QMessageBox.Yes:
                self.save(closing=True)

    def __del__(self):
        # Remove all handlers for this module
        remove_all_log_handlers()


def main(image_path, mask_path, output_path, output_basename, min_area=300, max_delta_frame=5, min_overlap_fraction=0.2, clean=False, max_delta_frame_interpolation=3, nframes_defect=2, nframes_stable=3, stable_overlap_fraction=0, display_results=True):
    """
    Load mask from `mask_path`, evaluate cell tracking graph, relabel mask,
    save the resulting mask and cell tracking graph into `output_path` directory

    Parameters
    ----------
    image_path: str
        input image path (tif, ome-tif or nd2 3D image TYX) to be shown in napari
        Use empty string to ignore
    mask_path: str
        segmentation mask (uint16 tif or ome-tif 3D image TYX)
    output_path: str
        output directory
    output_basename: str
        output basename. Output file will be saved as `output_path`/`output_basename`.ome.tif, `output_path`/`output_basename`.graphmlz and `output_path`/`output_basename`.log.
    min_area: int
        remove labelled regions with area (number of pixels) below `min_area`
    max_delta_frame: int
        number of previous frames to consider when creating the cell tracking graph
    min_overlap_fraction: float
        minimum overlap fraction (w.r.t mask area) to consider when creating edges in the cell tracking graph
    clean: bool
        search for isolated defects in the cell tracking graph and try to remove them by interpolating
        corresponding mask across neighboring frames
    max_delta_frame_interpolation: int
        number of previous and subsequent frames to consider for mask interpolation
        Only used with `clean`=True
    nframes_defect: int
        maximum size of the defect (number of frames), < than max_delta_frame_interpolation
        Only used with `clean`=True
    nframes_stable: int
        minimum number of stable frames before and after the defect, >= than max_delta_frame_interpolation.
        Only used with `clean`=True
    stable_overlap_fraction: float
        stable edges = with overlap_fraction_target >= `stable_overlap_fraction`
                        and overlap_fraction_source >= `stable_overlap_fraction`
        Only used with `clean`=True
    display_results: bool
        display image, mask and results in napari
    """

    # This is a temporary workaround to avoid having multiple conflicting
    # logging to metadata and log file, which could happen when a napari
    # window is already opened.
    # TODO: find a better solution.
    if napari.current_viewer():
        raise RuntimeError('To avoid potential log file corruption, close all napari windows and try again.')

    try:
        ###########################
        # Setup logging
        ###########################
        logger = logging.getLogger(__name__)
        logger.info("CELL TRACKING MODULE")
        if not os.path.isdir(output_path):
            logger.debug("creating: %s", output_path)
            os.makedirs(output_path)

        logfile = os.path.join(output_path, output_basename+".log")
        logger.setLevel(logging.DEBUG)
        logger.debug("writing log output to: %s", logfile)
        logfile_handler = logging.FileHandler(logfile, mode='w')
        logfile_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
        logfile_handler.setLevel(logging.INFO)
        logfile_handler.addFilter(gf.IgnoreDuplicate("Manually editing mask"))
        logger.addHandler(logfile_handler)

        # Log to memory
        global buffered_handler
        buffered_handler = gf.BufferedHandler()
        buffered_handler.setFormatter(logging.Formatter('%(asctime)s (VLabApp - cell tracking module) [%(levelname)s] %(message)s'))
        buffered_handler.setLevel(logging.INFO)
        buffered_handler.addFilter(gf.IgnoreDuplicate("Manually editing mask"))
        logger.addHandler(buffered_handler)

        logger.info("System info:")
        logger.info("- platform: %s", platform())
        logger.info("- python version: %s", python_version())
        logger.info("- VLabApp version: %s", vlabapp_version)
        logger.info("- numpy version: %s", np.__version__)
        logger.info("- opencv version: %s", cv.__version__)
        logger.info("- igraph version: %s", ig.__version__)
        if display_results:
            logger.info("- napari version: %s", napari.__version__)

        if image_path:
            logger.info("Input image path: %s", image_path)
        logger.info("Input mask path: %s", mask_path)
        logger.debug("min area: %s", min_area)
        logger.debug("max delta frame: %s", max_delta_frame)
        logger.debug("min overlap fraction: %s%%", min_overlap_fraction*100)

        ###########################
        # Load image and mask
        ###########################

        # Load image
        if image_path != '':
            logger.debug("loading %s", image_path)
            try:
                image = gf.Image(image_path)
                image.imread()
            except Exception:
                logging.getLogger(__name__).exception('Error loading image %s', image_path)
                # Remove all handlers for this module
                remove_all_log_handlers()
                raise

        # Load mask
        logger.debug("loading %s", mask_path)
        try:
            mask_image = gf.Image(mask_path)
            mask_image.imread()
            mask = mask_image.get_TYXarray()
        except Exception:
            logging.getLogger(__name__).exception('Error loading mask %s', mask_path)
            # Remove all handlers for this module
            remove_all_log_handlers()
            raise

        # load mask metadata
        mask_metadata = []
        if mask_image.ome_metadata:
            for x in mask_image.ome_metadata.structured_annotations:
                if isinstance(x, CommentAnnotation) and x.namespace == "VLabApp":
                    if len(mask_metadata) == 0:
                        mask_metadata.append("Metadata for "+mask_image.path+":\n"+x.value)
                    else:
                        mask_metadata.append(x.value)

        if mask.max() == 0:
            logger.warning("Input mask is empty")
            if display_results:
                QMessageBox.warning(None, 'Warning', 'Input mask is empty. Aborting.')
            else:
                logger.info("Creating cell tracking graph and relabelling mask: max delta frame=%s, min overlap fraction=%s%%, min area=%s", max_delta_frame, min_overlap_fraction*100, min_area)
                output_file = os.path.join(output_path, output_basename+".ome.tif")
                logger.info("Saving segmentation mask to %s", output_file)
                ome_metadata = OmeTiffWriter.build_ome(data_shapes=[mask.shape],
                                                       data_types=[mask.dtype],
                                                       dimension_order=["TYX"],
                                                       channel_names=[mask_image.channel_names],
                                                       physical_pixel_sizes=[PhysicalPixelSizes(X=mask_image.physical_pixel_sizes[0], Y=mask_image.physical_pixel_sizes[1], Z=mask_image.physical_pixel_sizes[2])])
                ome_metadata.structured_annotations.append(CommentAnnotation(value=buffered_handler.get_messages(), namespace="VLabApp"))
                for x in mask_metadata:
                    ome_metadata.structured_annotations.append(CommentAnnotation(value=x, namespace="VLabApp"))
                OmeTiffWriter.save(mask, output_file, ome_xml=ome_metadata)

                output_file = os.path.join(output_path, output_basename+".graphmlz")
                logger.info("Saving cell tracking graph to %s", output_file)
                # create empty graph
                g = ig.Graph(directed=True)
                # add attributes
                g.vs['frame'] = []
                g.vs['mask_id'] = []
                g.vs['area'] = []
                g.es['overlap_area'] = []
                g.es['overlap_fraction_source'] = []
                g.es['overlap_fraction_target'] = []
                g.es['frame_source'] = []
                g.es['frame_target'] = []
                g.es['mask_id_source'] = []
                g.es['mask_id_target'] = []
                # add metadata
                g['VLabApp:Annotation:1'] = buffered_handler.get_messages()
                for i, x in enumerate(mask_metadata):
                    g['VLabApp:Annotation:'+str(i+2)] = x
                g.write_graphmlz(output_file)

            # Remove all handlers for this module
            remove_all_log_handlers()
            return

        ###########################
        # Cell tracking
        ###########################

        logger.info("Creating cell tracking graph and relabelling mask: max delta frame=%s, min overlap fraction=%s%%, min area=%s", max_delta_frame, min_overlap_fraction*100, min_area)
        split_regions(mask)
        remove_small_regions(mask, min_area)
        cell_tracking_graph = CellTrackingGraph(mask, max_delta_frame=max_delta_frame, min_overlap_fraction=min_overlap_fraction)
        cell_tracking_graph.relabel(mask)

        ###########################
        # Automatic cleaning
        ###########################

        if clean:
            logger.info("Automatic cleaning: max delta frame=%s, max defect size=%s, min stable size=%s, stable overlap fraction=%s%%, min area=%s, clean missing mask only=%s", max_delta_frame_interpolation, nframes_defect, nframes_stable, stable_overlap_fraction*100, min_area, False)
            clean_mask(mask, cell_tracking_graph, max_delta_frame_interpolation=max_delta_frame_interpolation,
                       nframes_defect=nframes_defect, nframes_stable=nframes_stable,
                       stable_overlap_fraction=stable_overlap_fraction, min_area=min_area, only_missing=False)

            # relabel (to avoid problem with splitted labelled regions)
            logger.info("Relabelling mask and graph: max delta frame=%s, min area=%s, min overlap fraction=%s%%", max_delta_frame, min_area, min_overlap_fraction*100)
            split_regions(mask)
            remove_small_regions(mask, min_area)
            cell_tracking_graph.reset(mask, max_delta_frame=max_delta_frame, min_overlap_fraction=min_overlap_fraction)
            cell_tracking_graph.relabel(mask)

        ###########################
        # Napari
        ###########################
        if display_results:
            logger.debug("displaying image and mask")
            viewer_images = napari.Viewer(title=mask_path)
            if image_path != '':
                layers = viewer_images.add_image(image.image, channel_axis=2, name=['Image [' + x + ']' for x in image.channel_names] if image.channel_names else 'Image')
                for layer in layers:
                    layer.editable = False
                # channel axis is already used as channel_axis (layers) => it is not in viewer.dims:
                viewer_images.dims.axis_labels = ('F', 'T', 'Z', 'Y', 'X')
            # broadcast TYX mask to FTZYX with F and Z axis containing shallow copies (C axis is used as channel_axis):
            sizeF = image.image.shape[0] if image_path != '' else 1
            sizeZ = image.image.shape[3] if image_path != '' else 1
            mask_FTZYX = np.broadcast_to(mask[np.newaxis, :, np.newaxis, :, :], (sizeF, mask.shape[0], sizeZ, mask.shape[1], mask.shape[2]))
            # the resulting mask_FTZYX is read only. To make it writeable:
            mask_FTZYX.flags['WRITEABLE'] = True
            mask_layer = viewer_images.add_labels(mask_FTZYX, name="Cell mask")
            # channel axis is already used as channel_axis (layers) => it is not in viewer.dims:
            viewer_images.dims.axis_labels = ('F', 'T', 'Z', 'Y', 'X')

            logger.debug("displaying cell tracking graph")
            viewer_graph = napari.Viewer(title='Cell tracking graph')
            # Hide "layer controls" and "layer list" docks
            viewer_graph.window._qt_viewer.dockLayerControls.toggleViewAction().trigger()
            viewer_graph.window._qt_viewer.dockLayerList.toggleViewAction().trigger()
            logger.debug("Plotting cell tracking graph")
            # make sure all labels are visible to avoid problems with get_color
            mask_layer.show_selected_label = False
            plot_cell_tracking_graph(viewer_graph, viewer_images, mask_layer, cell_tracking_graph.get_graph(), mask_layer.get_color(range(mask.max()+1)))

            # Add CellTrackingWidget to napari
            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setWidget(CellTrackingWidget(mask, cell_tracking_graph, viewer_graph, viewer_images, image_path, output_path, output_basename,
                                                     min_area=min_area, max_delta_frame=max_delta_frame,
                                                     min_overlap_fraction=min_overlap_fraction, max_delta_frame_interpolation=max_delta_frame_interpolation,
                                                     nframes_defect=nframes_defect, nframes_stable=nframes_stable,
                                                     stable_overlap_fraction=stable_overlap_fraction,
                                                     mask_physical_pixel_sizes=mask_image.physical_pixel_sizes,
                                                     mask_channel_names=mask_image.channel_names,
                                                     mask_metadata=mask_metadata))
            viewer_images.window.add_dock_widget(scroll_area, area='right', name="Cell tracking")

        else:
            output_file = os.path.join(output_path, output_basename+".ome.tif")
            logger.info("Saving segmentation mask to %s", output_file)
            ome_metadata = OmeTiffWriter.build_ome(data_shapes=[mask.shape],
                                                   data_types=[mask.dtype],
                                                   dimension_order=["TYX"],
                                                   channel_names=[mask_image.channel_names],
                                                   physical_pixel_sizes=[PhysicalPixelSizes(X=mask_image.physical_pixel_sizes[0], Y=mask_image.physical_pixel_sizes[1], Z=mask_image.physical_pixel_sizes[2])])
            ome_metadata.structured_annotations.append(CommentAnnotation(value=buffered_handler.get_messages(), namespace="VLabApp"))
            for x in mask_metadata:
                ome_metadata.structured_annotations.append(CommentAnnotation(value=x, namespace="VLabApp"))
            OmeTiffWriter.save(mask, output_file, ome_xml=ome_metadata)

            output_file = os.path.join(output_path, output_basename+".graphmlz")
            logger.info("Saving cell tracking graph to %s", output_file)
            g = cell_tracking_graph.get_graph()
            # add metadata
            g['VLabApp:Annotation:1'] = buffered_handler.get_messages()
            for i, x in enumerate(mask_metadata):
                g['VLabApp:Annotation:'+str(i+2)] = x
            g.write_graphmlz(output_file)
            # Remove all handlers for this module
            remove_all_log_handlers()

    except Exception:
        # Remove all handlers for this module
        remove_all_log_handlers()
        remove_all_log_handlers()
        if display_results:
            # Restore cursor
            napari.qt.get_qapp().restoreOverrideCursor()
            try:
                # close napari window
                viewer_images.close()
                viewer_graph.close()
            except:
                pass
        raise
