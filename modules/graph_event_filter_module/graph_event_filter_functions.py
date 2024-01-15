import os
import logging
import numpy as np
import tifffile
import igraph as ig
import csv
from general import general_functions as gf
from aicsimageio.writers import OmeTiffWriter



def event_filter(mask, graph, event, tp_before, tp_after, output_path):
    """
    Filter the selected event in the graph and in the mask
    
    Parameters
    ---------------------
    mask: Image object
        segmentation mask
    graph: igraph.Graph
        cell tracking graph
    event: str
        type of event to consider
    tp_before: int
        number of time points before the event to consider
    tp_after: int
        number of time points after the event to consider
    output_path: str
        output directory

    Saves
    ---------------------
    event_mask
        ndarray with the valid events selected
    event_graph
        igraph.Graph with the valid events selected
    event_dictionary
        csv file with the valid events selected
    """

    # Initialize the cvs file with results
    with open(output_path+'_'+event+'s_dictionary.csv', "w") as file:
        writer = csv.writer(file)
        writer.writerow(['TP start', 'TP event', 'TP end', 'id(s) before event', 'id(s) after event'])

    # Set predefined parameters
    border_width = 2 # pixels to consider in removing cells on the border
    nmissing = 0 # number of maximum missing cells

    # Evaluate of graph's properties
    cell_tracks = gf.evaluate_graph_properties(graph)
    selected_cell_tracks = cell_tracks

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
    
    # Take the subgraph with the listed vertex
    subgraph_vs = (graph.vs(id=v['id'])[0].index for v in events_vertices)
    events_graph = graph.subgraph(subgraph_vs)
    
    # Save the graph and the mask with the detected events
    output_path += '_'+event # output_path = chosen_path/imagename_eventname
    events_mask = events_mask.astype(mask.dtype)
    events_mask = events_mask[:, np.newaxis, : ,:]
    OmeTiffWriter.save(events_mask, output_path+'s_mask.tif', dim_order="TCYX")
    events_graph.write_graphmlz(output_path+'s_graph.graphmlz')

    ## TODO: There is a problem with the mask ids not included in the event but included in the subgraph in consideration
    ## See division1 in the test/test_segm/prova_event_filter/ folder
    print('Found '+str(n_valid_event)+' valid '+event+'s events')


def main(mask_path, graph_path, event, tp_before, tp_after, output_path):
    """
    Generate mask and graph with for the specified event and with minimum 
    tp_before and tp_after timepoints free of other events 
    
    Parameters
    ---------------------
    mask_path: str
        input mask path
    graph_path: str
        input graph path
    event: str
        type of event to consider
    tp_before: int
        number of time points before the event to consider
    tp_after: int
        number of time points after the event to consider
    output_path: str
        output directory

    Saves
    ---------------------
    mask with the valid events selected
    graph with the valid events selected

    """

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
        mask = gf.Image(mask_path)
        mask.imread()
    except Exception as e:
        logging.getLogger(__name__).error('Error loading mask '+mask_path+'\n'+str(e))
    
    # Load graph
    logger.debug("loading %s", graph_path)
    graph = ig.Graph().Read_GraphMLz(graph_path)
    # Adjust attibute types
    graph = gf.adjust_graph_types(graph, mask.image.dtype)

    # Output path
    if not output_path.endswith('/'):
        output_path += '/'
    image_name = os.path.basename(mask_path).replace('_mask.tif', '')
    output_path += image_name

    event_filter(mask.get_TYXarray(), graph, event, tp_before, tp_after, output_path)
    logger.info("Done!\n")
    

# To test  
"""
if __name__ == '__main__':
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
