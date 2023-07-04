import os
import logging
from platform import python_version, platform
import numpy as np
import tifffile
import igraph as ig
import nd2
import napari
import csv
import matplotlib.pyplot as plt
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QGridLayout, QWidget, QPushButton, QLabel, QSpinBox, QScrollArea, QGroupBox, QCheckBox, QMessageBox, QSizePolicy
from PyQt5.QtCore import Qt, QPoint, QPointF
from PyQt5.QtGui import QCursor, QPixmap, QPainter, QPen, QIcon, QPolygonF
from general import general_functions as gf


def adjust_types(graph, mask_dtype):
    graph.vs['frame'] = np.array(graph.vs['frame'], dtype='int32')
    graph.vs['mask_id'] = np.array(graph.vs['mask_id'], dtype=mask_dtype)
    graph.vs['area'] = np.array(graph.vs['area'], dtype='int64')
    graph.es['overlap_area'] = np.array(graph.es['overlap_area'], dtype='int64')
    graph.es['frame_source'] = np.array(graph.es['frame_source'], dtype='int32')
    graph.es['frame_target'] = np.array(graph.es['frame_target'], dtype='int32')
    graph.es['mask_id_source'] = np.array(graph.es['mask_id_source'], dtype=mask_dtype)
    graph.es['mask_id_target'] = np.array(graph.es['mask_id_target'], dtype=mask_dtype)
    # Remove useless attribute
    del graph.vs['id']
    return graph


def save(subgraph, subgraph_masks, output_path, event_type):
        output_path += '_'+event_type # output_path = chosen_path/imagename_eventname
        tifffile.imwrite(output_path+'s_mask.tif', subgraph_masks, metadata={'axes': 'TYX'}, imagej=True, compression='zlib')
        subgraph.write_graphmlz(output_path+'s_graph.graphmlz')


def evaluate_graph_properties(graph):
    # Set "stable" subgraph = if source vertex has a unique outgoing edge and target vertex has a unique incoming edge
    graph.es['stable'] = False
    graph.es.select(lambda edge: abs(edge['frame_source']-edge['frame_target']) == 1 and edge['mask_id_source'] == edge['mask_id_target'] and graph.outdegree(edge.source) == 1 and graph.indegree(edge.target) == 1)['stable'] = True
    # Flag edge with low overlap as not stable
    graph.es.select(overlap_fraction_source_lt = 0)['stable'] = False
    graph.es.select(overlap_fraction_target_lt = 0)['stable'] = False
    # Evaluate length of "stable" subgraph and store it as vertex attribute
    g2 = graph.subgraph_edges(graph.es.select(stable=True), delete_vertices=False)
    components = g2.connected_components(mode='weak')
    for i, n in enumerate(components.sizes()):
        graph.vs[components[i]]['stable_component_size'] = n

    # Eval cell tracks (i.e. connected components of the cell tracking graph)
    components = graph.connected_components(mode='weak')
    cell_tracks = []
    
    for i, cmp in enumerate(components): # each connected component found is a subgraph
        g2 = graph.subgraph(cmp) # g2 = subgraph
        mask_ids = np.unique(g2.vs['mask_id'])
        frame_min = np.min(g2.vs['frame'])
        frame_max = np.max(g2.vs['frame'])
        # Number of missing mask regions (edges spanning more than 1 frame)
        n_missing = np.sum([ e['frame_target'] - e['frame_source'] - 1 for e in g2.es])
        # Number fusion events with stable neighborhood
        n_fusions = np.sum([1 if v.indegree() > 1 and min([v2['stable_component_size'] for v2 in v.neighbors()]) >= 1 else 0 for v in g2.vs])
        fusions_frames = []
        if n_fusions > 0:
            indegree = g2.vs[0].indegree()
            for v in g2.vs:
                if v.indegree() > indegree:
                    indegree = v.indegree()
                    fusions_frames.append(v['frame'])
        # Number division events with stable neighborhood
        n_divisions = np.sum([1 if v.outdegree() > 1 and min([v2['stable_component_size'] for v2 in v.neighbors()]) >= 1 else 0 for v in g2.vs])
        divisions_frames = []
        if n_divisions > 0:
            outdegree = g2.vs[0].outdegree()
            for v in g2.vs:
                if v.outdegree() > outdegree:
                    outdegree = v.outdegree()
                    divisions_frames.append(v['frame'])
        min_area = np.min(g2.vs['area'])
        max_area = np.max(g2.vs['area'])
        # Topology
        cell_tracks.append({'graph_vertices': cmp, 'mask_ids': mask_ids, 'frame_min': frame_min,
                            'frame_max': frame_max, 'n_missing': n_missing, 'n_fusions': n_fusions,
                            'n_divisions': n_divisions, 'min_area': min_area, 'max_area': max_area,
                            'fusions_frames': fusions_frames, 'divisions_frames': divisions_frames})
    return cell_tracks


def event_filter(mask, graph, event, tp_before, tp_after, output_path):
    # Initialize the cvs file with results
    with open(output_path+'_'+event+'s_dictionary.csv', "w") as file:
        writer = csv.writer(file)
        writer.writerow(['TP start', 'TP event', 'TP end', 'id(s) before event', 'id(s) after event'])

    # Set predefined parameters
    border_width = 2 # pixels to consider in removing cells on the border
    nmissing = 0 # number of maximum missing cells

    # Evaluate of graph's properties
    cell_tracks = evaluate_graph_properties(graph)
    selected_cell_tracks = cell_tracks

    # Delete the cells masks on the border
    border_mask_ids = np.unique( np.concatenate([
            np.unique(mask[:, :border_width, :]), np.unique(mask[:, -border_width:, :]),
            np.unique(mask[:, :, :border_width]), np.unique(mask[:, :, -border_width:])]))
    border_mask_ids = border_mask_ids[border_mask_ids > 0]
    selected_cell_tracks = [x for x in selected_cell_tracks if np.isin(x['mask_ids'], border_mask_ids).any() == False]

    # Delete the cells masks with more than nmissing detections
    selected_cell_tracks = [x for x in selected_cell_tracks if x['n_missing'] <= nmissing]

    # Initilize final results objects
    n_valid_event = 0
    events_mask = np.zeros(mask.shape)
    events_vertices = []
    
    # Set the different paramenters for each event
    if event == 'fusion':
        n_event = 'n_fusions'
        event_frames = 'fusions_frames'
        otherevent_frames = 'divisions_frames'
        n = 1
    elif event == 'division':
        n_event = 'n_divisions'
        event_frames = 'divisions_frames'
        otherevent_frames = 'fusions_frames'
        n = 0

    # Delete the masks with less than 1 of the selected event
    selected_cell_tracks = [x for x in selected_cell_tracks if x[n_event] >= 1]
    for cell_track in selected_cell_tracks:
        g2 = graph.subgraph(cell_track['graph_vertices'])
        ## TODO change ==1 because we have to consider also a secondary event in the same subgraph if is valid
        if cell_track[n_event] == 1:
            subgraph_mask = np.zeros(mask.shape)
            event_tp = int(cell_track[event_frames][n])
            # Range of selected time points
            tp_to_check = np.arange(event_tp - tp_before, event_tp + tp_after)
            # Continue if event timepoint ± selected timepoints are in a feasible range
            if min(tp_to_check) >= 0 and max(tp_to_check) <= mask.shape[0]:
                # Continue if in tp_to_check there are no other events
                valid = True
                for t in cell_track[event_frames]:
                    valid = False if t != event_tp and t in tp_to_check else True
                for t in cell_track[otherevent_frames]:
                    valid = False if t in tp_to_check else True

                if valid:
                    # Create the event graph and the corresponding mask
                    ids_before = []
                    ids_after = []
                    for vertex in g2.vs:
                        # Check if the frame is in the range of selected time points
                        if vertex['frame'] >= min(tp_to_check) and vertex['frame'] <= max(tp_to_check):
                            mask_copy = mask.copy()
                            mask_copy[mask_copy != vertex['mask_id']] = 0

                            if vertex['frame'] < event_tp and vertex['mask_id'] not in ids_before:
                                ids_before.append(vertex['mask_id'])
                            if vertex['frame'] > event_tp and vertex['mask_id'] not in ids_after:
                                ids_after.append(vertex['mask_id'])
                            # Add the vertex to the final vertices list
                            events_vertices.append(vertex)
                            # Create the event mask
                            subgraph_mask[vertex['frame'],:,:] += mask_copy[vertex['frame'],:,:]
                    
                    n_valid_event += 1
                    # Add the event mask to the final mask
                    events_mask += subgraph_mask.astype(mask.dtype)
                    # Add the event in the csv file
                    with open(output_path+'_'+event+'s_dictionary.csv', 'a') as file:
                        writer = csv.writer(file)
                        writer.writerow([min(tp_to_check), event_tp, max(tp_to_check), ids_before, ids_after])
    # Delete duplicates in the events_vertices list
    events_vertices_set = []
    for v in events_vertices:
        if v.index not in [vs.index for vs in events_vertices_set]:
            events_vertices_set.append(v)
    # Take the subgrapth with the listed vertex       
    events_graph = graph.subgraph(events_vertices_set)
    # Save the graph and the mask with the detected events
    save(events_graph, events_mask.astype(mask.dtype), output_path, event)

    ## TODO: There is still a problem with the mask ids not included in the event but included in the subgraph in consideration
    ## See division1 in the test/test_segm/prova_event_filter/ folder
    print('Found '+str(n_valid_event)+' valid '+event+'s events')


def main(mask_path, graph_path, event, tp_before, tp_after, output_path):
    tp_before = int(tp_before)
    tp_after = int(tp_after)
    if not output_path.endswith('/'):
        output_path += '/'
    image_name = mask_path.replace('_mask.tif', '')
    output_path += image_name
    

    ###########################
    # Setup logging
    ###########################
    logger = logging.getLogger(__name__)
    logger.info("GRAPH EVENT FILTER MODULE")
    if not os.path.isdir(output_path):
        logger.debug("creating: %s", output_path)
        os.makedirs(output_path)
    
    logfile = os.path.join(output_path, os.path.splitext(os.path.basename(graph_path))[0]+".log")
    logger.setLevel(logging.DEBUG)
    logger.debug("writing log output to: %s", logfile)
    logfile_handler = logging.FileHandler(logfile, mode='w')
    logfile_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    logfile_handler.setLevel(logging.INFO)
    logger.addHandler(logfile_handler)

    logger.info("Mask path: %s", mask_path)
    logger.info("Graph path: %s", graph_path)
    logger.info("Output path: %s", output_path)
    logger.info("Event: %s - with %d timepoints before and %d after", event, tp_before, tp_after)

    ###########################
    # Load mask and graph
    ###########################

    # Load mask
    logger.debug("loading %s", mask_path)
    try:
        mask = gf.Image(mask_path)#gf.Image(mask_path)
    except Exception as e:
        logger.error(e)
    mask.imread()

    # Load graph
    logger.debug("loading %s", graph_path)
    graph = ig.Graph().Read_GraphMLz(graph_path)
    # Adjust attibute types
    graph = adjust_types(graph, mask.image.dtype)

    event_filter(mask.get_TYXarray(), graph, event, tp_before, tp_after, output_path)
    logger.info("Done!\n")
    
    
"""if __name__ == '__main__':
    mask = '/Users/aravera/Documents/CIG_Aleks/Application/test/test_segm/cell_tracking/smp00_BF_registered_mask.tif'
    graph = '/Users/aravera/Documents/CIG_Aleks/Application/test/test_segm/cell_tracking/smp00_BF_registered_graph.graphmlz'
    event = 'fusion'
    tp_before = 10
    tp_after = 10
    output_path = '/Users/aravera/Documents/CIG_Aleks/Application/test/test_segm/prova_event_filter/'
    main(mask, graph, event, tp_before, tp_after, output_path)
    
    mask = Image(mask)#gf.Image(mask_path)
    mask.imread()

    graph2_path = '/Users/aravera/Documents/CIG_Aleks/Application/test/test_segm/graph_filtering/smp00_BF_registered_graph.graphmlz'
    graph2 = ig.Graph().Read_GraphMLz(graph2_path)
    # Adjust attibute types
    graph2.vs['frame'] = np.array(graph2.vs['frame'], dtype='int32')
    graph2.vs['mask_id'] = np.array(graph2.vs['mask_id'], dtype=mask.image.dtype)
    graph2.vs['area'] = np.array(graph2.vs['area'], dtype='int64')
    graph2.es['overlap_area'] = np.array(graph2.es['overlap_area'], dtype='int64')
    graph2.es['frame_source'] = np.array(graph2.es['frame_source'], dtype='int32')
    graph2.es['frame_target'] = np.array(graph2.es['frame_target'], dtype='int32')
    graph2.es['mask_id_source'] = np.array(graph2.es['mask_id_source'], dtype=mask.image.dtype)
    graph2.es['mask_id_target'] = np.array(graph2.es['mask_id_target'], dtype=mask.image.dtype)
    # Remove useless attribute
    del graph2.vs['id']
    components = graph2.connected_components(mode='weak')
"""
"""
fig, ax = plt.subplots()
ig.plot(g, target=ax)
plt.show()
"""