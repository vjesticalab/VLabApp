import os
import logging
from platform import python_version, platform
import numpy as np
import pandas as pd
import igraph as ig
import csv
from general import general_functions as gf
from aicsimageio.writers import OmeTiffWriter
from aicsimageio.types import PhysicalPixelSizes
from ome_types.model import CommentAnnotation
from version import __version__ as vlabapp_version


def remove_all_log_handlers():
    # remove all handlers for this module
    while len(logging.getLogger(__name__).handlers) > 0:
        logging.getLogger(__name__).removeHandler(logging.getLogger(__name__).handlers[0])

def event_filter(mask, graph, event, timecorrection, magn_image, tp_before, tp_after, output_path, output_basename):
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
    output_basename: str
        output basename. Output file will be saved as `output_path`/`output_basename`.csv, `output_path`/`output_basename`.graphmlz and `output_path`/`output_basename`.log.

    Saves
    ---------------------
    corrected_mask
        ndarray with the corrected mask
    corrected_graph
        igraph.Graph with the corrected graph
    """
    # Reduce mask Image obj to normal 3D nparray (TXY)
    # FIND FUSION - same code of "event filter" module

    # Initialize the cvs file with results
    with open(os.path.join(output_path, output_basename+'.csv'), "w") as file:
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
    ids_after = None
    events_list = []
    
    # Set the different paramenters for each event
    if event == 'fusion':
        n_event = 'n_fusions'
        event_frames = 'fusions_frames'
    elif event == 'division':
        n_event = 'n_divisions'
        event_frames = 'divisions_frames'

    # Select masks with at least 1 "event" detected
    selected_cell_tracks = [x for x in selected_cell_tracks if x[n_event] > 0]
    for cell_track in selected_cell_tracks:
        subgraph = graph.subgraph(cell_track['graph_vertices'])

        list_event_frames = cell_track[event_frames] if event=='division' else cell_track[event_frames][1:] # if fusion: remove first value because always 1
        
        for event_frame in list_event_frames:
            # Read fusion timepoint and ids
            initial_event_tp = int(event_frame)
            ids_before = []
            ids_after= []

            for vertex in subgraph.vs:
                if vertex['frame'] >= initial_event_tp-1 and vertex['frame'] <= initial_event_tp+1:
                    if vertex['frame'] < initial_event_tp and vertex['mask_id'] not in ids_before:
                        ids_before.append(vertex['mask_id'])
                    if vertex['frame'] > initial_event_tp:
                        ids_after.append(vertex['mask_id'])

            # If required, recalculate fusion timepoint based on the magnified image
            if timecorrection:
                magn_image = magn_image.astype('uint8')
                stds = []
                for t in range(mask.shape[0]):
                    # Create the static mask for the time point t :
                    # if before fusion, use the first mask after fusion, otherwise the real one
                    static_mask = np.zeros([mask.shape[1], mask.shape[2]], dtype='uint8')
                    for cellid in set(ids_before + ids_after):
                        if t > initial_event_tp:
                            static_mask[mask[t,:,:] == cellid] = cellid
                        else:
                            static_mask[mask[initial_event_tp+1,:,:] == cellid] = cellid
                    # Calculate std
                    px = magn_image[t, static_mask==ids_after[0]]
                    if len(px) > 0:
                        stds.append(np.std(px))
                    else:
                        stds.append(None)
                # Calculate difference in between stds (row - previous row)
                fusion_data = {'Timepoint': np.arange(mask.shape[0]), 'Stdev':stds}
                fusion_data_df= pd.DataFrame(fusion_data)
                fusion_data_df['std_diff']=fusion_data_df['Stdev'].diff()
                # Get the time point of the minimum difference
                real_event_tp = fusion_data_df.at [fusion_data_df['std_diff'].idxmin(), 'Timepoint']
                if real_event_tp == initial_event_tp:
                    tp_is_changed = 0 
                elif real_event_tp > initial_event_tp:
                    tp_is_changed = 1
                else: tp_is_changed = 2
            
            else:
                real_event_tp = initial_event_tp
                tp_is_changed = 0
                
            # Range of selected time points
            tp_to_check = np.arange(max(0,real_event_tp - tp_before), min(real_event_tp + tp_after, mask.shape[0]))
            
            valid = True
            for t in cell_track[event_frames]: # valid if there aren't other events in these timepoints
                valid = False if t != initial_event_tp and t in tp_to_check else True
            if valid:
                n_valid_event += 1
                # If event is valid -> update events_mask
                for t in tp_to_check:
                    tmask = np.zeros([mask.shape[1], mask.shape[2]])
                    for cellid in set(ids_before + ids_after):
                        # If event timepoint changed, change the mask if in the gap timepoints
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
                with open(os.path.join(output_path, output_basename+'.csv'), 'a') as file:
                    writer = csv.writer(file)
                    writer.writerow([min(tp_to_check), real_event_tp, max(tp_to_check), ids_before, ids_after])
                    events_list.append((min(tp_to_check), real_event_tp, max(tp_to_check), ids_before, ids_after))

    
    subgraph_vs = (graph.vs(id=v['id'])[0].index for v in events_vertices)
    events_graph = graph.subgraph(subgraph_vs)
    ## TODO : MODIFY THIS GRAPH WITH THE NEW TIMEPOINTS
    
    # Save the mask with the detected events
    events_mask = events_mask.astype(mask.dtype)
    events_mask = events_mask[:, np.newaxis, : ,:]

    return events_mask, events_graph, events_list


def save_cropped_events(events_list, n_tp, total_events_mask, marker_image, chcropimage_path, BFimage_path, crop_output_path, crop_output_basename, mask_physical_pixel_sizes=(None, None, None), mask_channel_names=None, metadata=None):
    """
    marker_image, chcropimage_path, BFimage_path : can be None
    """
    metadata = metadata if metadata is not None else []
    for n, event in enumerate(events_list):
        # event = (min(tp_to_check), event_tp, max(tp_to_check), ids_before, id_after)
        ids = list(event[3])
        if str(event[4]).isnumeric():
            ids.append(event[4])
        else:
            ids.append(event[4][0])
        ids = list(set(ids))
        ymin, ymax = np.nonzero(np.any(np.isin(total_events_mask[int(event[0]):int(event[2]+1), 0, :, :], ids), axis=(0,2)))[0][[0, -1]]
        xmin, xmax = np.nonzero(np.any(np.isin(total_events_mask[int(event[0]):int(event[2]+1), 0, :, :], ids), axis=(0,1)))[0][[0, -1]]

        valid_images = [x for x in [marker_image, chcropimage_path, BFimage_path] if x is not None]
        
        # Initialize result
        cropped_mask = np.zeros((n_tp, len(valid_images)+1, ymax-ymin, xmax-xmin))
        
        # In position ch=0 save the mask with only the interested ids
        new_cropped = np.zeros((n_tp, ymax-ymin, xmax-xmin))
        for cell_id in ids:
            new_cropped[total_events_mask[:, 0, ymin:ymax, xmin:xmax] == cell_id] = cell_id
        cropped_mask[:,0,:,:] = new_cropped #TCYX

        # Then, save the other valid_images
        for i, valid_im in enumerate(valid_images):
            # n+1 because position 0 is already filled
            if isinstance(valid_im, str): # chcropimage_path or BFimage_path -> to be uploaded
                try:
                    img = gf.Image(valid_im) #gf.
                    img.imread()
                    img = img.get_TYXarray()
                except Exception as e:
                    logging.getLogger(__name__).exception('Error loading image to crop %s',valid_im)
                    remove_all_log_handlers()
                    raise
                cropped_mask[:,i+1,:,:] = img[:, ymin:ymax, xmin:xmax] #TYX
            else: # marker_image -> already into the variable
                cropped_mask[:,i+1,:,:] = valid_im[:, ymin:ymax, xmin:xmax] #TYX

        # Save
        output_name=os.path.join(crop_output_path, crop_output_basename+'-'+str(n)+'.ome.tif')
        logging.getLogger(__name__).info("Saving cropped mask %d to %s",n, output_name)
        ome_metadata=OmeTiffWriter.build_ome(data_shapes=[cropped_mask.shape],
                                             data_types=[cropped_mask.dtype],
                                             dimension_order=["TCYX"],
                                             channel_names=[mask_channel_names],
                                             physical_pixel_sizes=[PhysicalPixelSizes(X=mask_physical_pixel_sizes[0], Y=mask_physical_pixel_sizes[1], Z=mask_physical_pixel_sizes[2])])
        ome_metadata.structured_annotations.append(CommentAnnotation(value=buffered_handler.get_messages(),namespace="VLabApp"))
        for x in metadata:
            ome_metadata.structured_annotations.append(CommentAnnotation(value=x,namespace="VLabApp"))
        OmeTiffWriter.save(cropped_mask, output_name, ome_xml=ome_metadata)


def main(mask_path, graph_path, event, timecorrection, magn_image_path, tp_before, tp_after, cropsave, chcropimage_path, BFimage_path, output_path, output_basename):
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
    timecorrection: bool
        correct the time or not
    tp_before: int
        number of time points before the event to consider
    tp_after: int
        number of time points after the event to consider
    output_path: str
        output directory.
    output_basename: str
        output basename. Output file will be saved as `output_path`/`output_basename`.ome.tif, `output_path`/`output_basename`.graphmlz, `output_path`/`output_basename`.csv and `output_path`/`output_basename`.log.

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

    logfile = os.path.join(output_path, output_basename+'.log')
    logger.setLevel(logging.DEBUG)
    logger.debug("writing log output to: %s", logfile)
    logfile_handler = logging.FileHandler(logfile, mode='w')
    logfile_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    logfile_handler.setLevel(logging.INFO)
    logger.addHandler(logfile_handler)

    # Log to memory
    global buffered_handler
    buffered_handler = gf.BufferedHandler()
    buffered_handler.setFormatter(logging.Formatter('%(asctime)s (VLabApp - events filter module) [%(levelname)s] %(message)s'))
    buffered_handler.setLevel(logging.INFO)
    logger.addHandler(buffered_handler)

    logger.info("System info:")
    logger.info("- platform: %s", platform())
    logger.info("- python version: %s", python_version())
    logger.info("- VLabApp version: %s", vlabapp_version)
    logger.info("- numpy version: %s", np.__version__)
    logger.info("- igraph version: %s", ig.__version__)

    logger.info("Input mask path: %s", mask_path)
    logger.info("Input graph path: %s", graph_path)
    logger.info("Output path: %s", output_path)
    logger.info("Output basename: %s", output_basename)
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
        logging.getLogger(__name__).exception('Error loading mask %s',mask_path)
        remove_all_log_handlers()
        raise

    #load mask metadata
    mask_metadata = []
    if mask.ome_metadata:
        for i,x in enumerate(mask.ome_metadata.structured_annotations):
            if isinstance(x, CommentAnnotation) and x.namespace == "VLabApp":
                if len(mask_metadata) == 0:
                    mask_metadata.append("Metadata for "+mask.path+":\n"+x.value)
                else:
                    mask_metadata.append(x.value)

    # Load graph
    logger.debug("loading %s", graph_path)
    graph = gf.load_cell_tracking_graph(graph_path,mask.image.dtype)

    #graph metadata
    graph_metadata = []
    for a in graph.attributes():
        if a.startswith('VLabApp:Annotation'):
            if len(graph_metadata) == 0:
                graph_metadata.append("Metadata for "+graph_path+":\n"+graph[a])
            else:
                graph_metadata.append(graph[a])

    if event == 'fusion' and timecorrection: 
        try:
            magn_image = gf.Image(magn_image_path) #
            magn_image.imread()
            # load magn_image metdata
            magn_image_metadata = []
            if magn_image.ome_metadata:
                for i,x in enumerate(magn_image.ome_metadata.structured_annotations):
                    if isinstance(x, CommentAnnotation) and x.namespace == "VLabApp":
                        if len(magn_image_metadata) == 0:
                            magn_image_metadata.append("Metadata for "+magn_image.path+":\n"+x.value)
                        else:
                            magn_image_metadata.append(x.value)

            magn_image = magn_image.get_TYXarray()
        except Exception as e:
            logging.getLogger(__name__).exception('Error loading magnified image %s',magn_image_path)
            remove_all_log_handlers()
            raise
    else:
        magn_image = None
        magn_image_metadata = []

    total_events_mask, total_events_graph, events_list = event_filter(mask.get_TYXarray(), graph, event, timecorrection, magn_image, tp_before, tp_after, output_path, output_basename)

    # Save mask and graph
    output_name=os.path.join(output_path, output_basename+'.ome.tif')
    logger.info("Saving mask to %s", output_name)
    ome_metadata=OmeTiffWriter.build_ome(data_shapes=[total_events_mask.shape],
                                         data_types=[total_events_mask.dtype],
                                         dimension_order=["TCYX"],
                                         channel_names=[mask.channel_names],
                                         physical_pixel_sizes=[PhysicalPixelSizes(X=mask.physical_pixel_sizes[0],Y=mask.physical_pixel_sizes[1],Z=mask.physical_pixel_sizes[2])])
    ome_metadata.structured_annotations.append(CommentAnnotation(value=buffered_handler.get_messages(),namespace="VLabApp"))
    for x in mask_metadata + graph_metadata + magn_image_metadata:
        ome_metadata.structured_annotations.append(CommentAnnotation(value=x,namespace="VLabApp"))
    OmeTiffWriter.save(total_events_mask, output_name, ome_xml=ome_metadata)

    output_name=os.path.join(output_path, output_basename+'.graphmlz')
    logger.info("Saving cell tracking graph to %s", output_name)
    #add metadata
    total_events_graph['VLabApp:Annotation:1'] = buffered_handler.get_messages()
    for i, x in enumerate(mask_metadata + graph_metadata + magn_image_metadata):
        total_events_graph['VLabApp:Annotation:'+str(i+2)] = x
    total_events_graph.write_graphmlz(output_name)

    # If required, save cropped events
    # Note: currently it is possible only with fusions
    if cropsave:
        if magn_image_path:
            magn_image = gf.Image(magn_image_path) #
            magn_image.imread()
            # load magn_image metdata
            magn_image_metadata = []
            if magn_image.ome_metadata:
                for i,x in enumerate(magn_image.ome_metadata.structured_annotations):
                    if isinstance(x, CommentAnnotation) and x.namespace == "VLabApp":
                        if len(magn_image_metadata) == 0:
                            magn_image_metadata.append("Metadata for "+magn_image.path+":\n"+x.value)
                        else:
                            magn_image_metadata.append(x.value)
            magn_image = magn_image.get_TYXarray()
        else:
            magn_image = None
        save_cropped_events(events_list, mask.get_TYXarray().shape[0], total_events_mask, magn_image, chcropimage_path, BFimage_path, output_path, output_basename, mask_physical_pixel_sizes=mask.physical_pixel_sizes, metadata=mask_metadata + graph_metadata + magn_image_metadata)


    remove_all_log_handlers()
    logger.info("Done!\n")
