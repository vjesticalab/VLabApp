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
from general import general_functions as gf


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
    selected_cell_tracks = gf.evaluate_graph_properties(graph) #gf.

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
    ids_before = None
    id_after = None

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
            
            if ids_before and id_after:# Recalculate fusion timepoint based on the magnified image
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
        mask = gf.Image(mask_path) #gf.
        mask.imread()
    except Exception as e:
        logging.getLogger(__name__).error('Error loading mask '+mask_path+'\n'+str(e))

    # Load image
    ##logger.debug("loading %s", magn_image_path)
    try:
        magn_image = gf.Image(magn_image_path) #gf.
        magn_image.imread()
    except Exception as e:
        logging.getLogger(__name__).error('Error loading magnified image '+magn_image_path+'\n'+str(e))
    
    # Load graph
    ##logger.debug("loading %s", graph_path)
    graph = gf.load_cell_tracking_graph(graph_path,mask.image.dtype)

    # Output path
    if not output_path.endswith('/'):
        output_path += '/'
    image_name = os.path.basename(mask_path).replace('_mask.tif', '')
    output_path += image_name

    fusion_correction(mask.get_TYXarray(), magn_image.get_TYXarray(), graph, tp_before, tp_after, output_path)
    ##logger.info("Done!\n")
    

# To test  
if __name__ == '__main__':
    
    mask_paths = ['/Users/aravera/Documents/CIG_Aleks/tests/test_newmodule/graph_filtering/smp10_BF_mask.tif']
    graph_paths = ['/Users/aravera/Documents/CIG_Aleks/tests/test_newmodule/graph_filtering/smp10_BF_graph.graphmlz']
    magn_image_paths = ['/Users/aravera/Documents/CIG_Aleks/tests/test_newmodule/smp10_WL614_registered.tif']
    tp_before = 5
    tp_after = 5
    output_path = '/Users/aravera/Documents/CIG_Aleks/tests/test_newmodule/fusion_correction/'
    for i in range(len(mask_paths)):
        main(mask_paths[i], graph_paths[i], magn_image_paths[i], tp_before, tp_after, output_path)
