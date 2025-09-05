import os
import logging
from platform import python_version, platform
import numpy as np
import igraph as ig
from general import general_functions as gf
from bioio.writers import OmeTiffWriter
from bioio import PhysicalPixelSizes
from ome_types.model import CommentAnnotation
from version import __version__ as vlabapp_version


def remove_all_log_handlers():
    # remove all handlers for this module
    while len(logging.getLogger(__name__).handlers) > 0:
        logging.getLogger(__name__).removeHandler(logging.getLogger(__name__).handlers[0])


def filter_graph(graph, events_type, nframes_before, nframes_after, filter_nmissing, nmissing, stable_overlap_fraction=0):
    """
    Select events (fusions of divisions) with specified number of stable frames before and after the event and number of missing cells (only allowed immediately around the event).
    Return the subgraph obtained by keeping only the selected events with the specified number of frames before and after the event.
    Evaluate the properties of the graph and store it in its vertices and edges attributes.

    Parameters
    ---------------------
    graph: igraph.Graph
        cell tracking graph, modified in-place.
    events_type: str
        Type of events to select ('division' or 'fusion').
    nframes_before: int
        number of stable frames before the event.
    nframes_after: int
        number of stable frames after the event.
    filter_nmissing: bool
        filter-out cell tracks with more than `nmissing` missing cells. Filtering is done after event selection, i.e. with one cell track per selected event.
    nmissing: int
        maximum number of missing cells per cell track.
    stable_overlap_fraction: float
        edges are considered as not stable if overlap_fraction_target < `stable_overlap_fraction` or overlap_fraction_source < `stable_overlap_fraction`.

    Returns
    -------
    igraph.Graph
        The subgraph formed by the selected events with the specified number of frames before and after the event.
    """

    if events_type not in ['fusion', 'division']:
        raise TypeError(f"Invalid events_type {events_type}")

    # Set "stable" subgraph = if source vertex has a unique outgoing edge and target vertex has a unique incoming edge
    graph.es['stable'] = False
    graph.es.select(lambda edge: abs(edge['frame_source']-edge['frame_target']) == 1 and edge['mask_id_source'] == edge['mask_id_target'] and graph.outdegree(edge.source) == 1 and graph.indegree(edge.target) == 1)['stable'] = True
    # Flag edge with low overlap as not stable
    graph.es.select(overlap_fraction_source_lt=stable_overlap_fraction)['stable'] = False
    graph.es.select(overlap_fraction_target_lt=stable_overlap_fraction)['stable'] = False
    # Evaluate length of "stable" subgraph and store it as vertex attribute
    g2 = graph.subgraph_edges(graph.es.select(stable=True), delete_vertices=False)
    components = g2.connected_components(mode='weak')
    for i, n in enumerate(components.sizes()):
        graph.vs[components[i]]['stable_component_frame_start'] = min(graph.vs[components[i]]['frame'])
        graph.vs[components[i]]['stable_component_frame_end'] = max(graph.vs[components[i]]['frame'])
        graph.vs[components[i]]['stable_component_size'] = n

    # search for events
    if events_type == 'division':
        # keep only divisions
        vs_events = graph.vs.select(lambda v:
                                    v.indegree() <= 1 and
                                    v.outdegree() == 2 and
                                    all(v2.indegree() <= 1 and v2.outdegree() <= 1 for v2 in v.neighbors()))
        # check number of stable frames before and after division
        vs_events = vs_events.select(lambda v:
                                     v['frame'] - v['stable_component_frame_start'] + 1 >= nframes_before and
                                     min(v2['stable_component_frame_end'] - v['frame'] for v2 in v.neighbors(mode='out')) >= nframes_after)
        if filter_nmissing:
            # check number of missing cells
            vs_events = vs_events.select(lambda v: np.sum([e['frame_target']-e['frame_source']-1 for e in v.incident(mode='out')]) <= nmissing)
    elif events_type == 'fusion':
        # keep only fusions
        vs_events = graph.vs.select(lambda v:
                                    v.indegree() == 2 and
                                    v.outdegree() <= 1 and
                                    all(v2.indegree() <= 1 and v2.outdegree() <= 1 for v2 in v.neighbors()))
        # check number of stable frames before and after fusion
        vs_events = vs_events.select(lambda v:
                                     min(v['frame'] - v2['stable_component_frame_start'] for v2 in v.neighbors(mode='in')) >= nframes_before and
                                     v['stable_component_frame_end'] - v['frame'] + 1 >= nframes_after)
        if filter_nmissing:
            # check number of missing cells
            vs_events = vs_events.select(lambda v: np.sum([e['frame_target']-e['frame_source']-1 for e in v.incident(mode='in')]) <= nmissing)

    # add attribute event_id
    graph.vs['event_id'] = 0
    eid = 1
    for v in vs_events:
        if events_type == 'division':
            # select vertices before division
            vs_before = graph.vs.select(frame_ge=v['frame'] - nframes_before + 1,
                                        frame_le=v['frame'],
                                        mask_id_eq=v['mask_id'])
            # select vertices after division
            vs_after = graph.vs.select(frame_ge=v['frame'] + 1,
                                       frame_le=v['frame'] + nframes_after,
                                       mask_id_in=[v2['mask_id'] for v2 in v.neighbors(mode='out')])
            # Make sure all mask_ids are present (could be missing in case of missing cells). If not, ignore the event
            if not all([v2['mask_id'] in vs_after['mask_id'] for v2 in v.neighbors(mode='out')]):
                continue
        elif events_type == 'fusion':
            # select vertices before fusion
            vs_before = graph.vs.select(frame_ge=v['frame'] - nframes_before,
                                        frame_le=v['frame'] - 1,
                                        mask_id_in=[v2['mask_id'] for v2 in v.neighbors(mode='in')])
            # select vertices after fusion
            vs_after = graph.vs.select(frame_ge=v['frame'],
                                       frame_le=v['frame'] + nframes_after - 1,
                                       mask_id_eq=v['mask_id'])

            # Make sure all mask_ids are present (could be missing in case of missing cells). If not, ignore the event
            if not all([v2['mask_id'] in vs_before['mask_id'] for v2 in v.neighbors(mode='in')]):
                continue
        # Check if vertices are associated to more than one event. If yes, ignore the event.
        if max(vs_before['event_id']) > 0:
            continue
        if max(vs_after['event_id']) > 0:
            continue

        vs_before['event_id'] = eid
        vs_after['event_id'] = eid
        eid += 1

    # select edges connecting vertices with same non-zero event_id and extract subgraph
    es = graph.es.select(lambda edge: graph.vs[edge.source]['event_id'] == graph.vs[edge.target]['event_id'] and graph.vs[edge.source]['event_id'] > 0)
    subgraph = graph.subgraph_edges(es, delete_vertices=True)

    # remove temporary attributes
    del graph.vs['stable_component_frame_start']
    del graph.vs['stable_component_frame_end']
    del graph.vs['stable_component_size']
    del graph.vs['event_id']
    del graph.es['stable']
    del subgraph.vs['stable_component_frame_start']
    del subgraph.vs['stable_component_frame_end']
    del subgraph.vs['stable_component_size']
    del subgraph.es['stable']

    return subgraph


def save(mask, graph, output_path, output_basename, metadata=None):
    """
    Save cell tracking graph and mask as  `output_path`/`output_basename`.graphmlz and `output_path`/`output_basename`.ome.tif.

    Parameters
    ----------
    mask: gf.Image
        a 3D (TYX) 16bit unsigned integer mask.
    graph: igraph.Graph
        a graph to plot.
    output_path: str
        output directory
    output_basename: str
        output basename
    """
    logger = logging.getLogger(__name__)
    if not os.path.isdir(output_path):
        logger.debug("creating: %s", output_path)
        os.makedirs(output_path)

    if metadata is None:
        metadata = []

    output_file = os.path.join(output_path, output_basename+".ome.tif")
    logger.info("Saving segmentation mask to %s", output_file)
    ome_metadata = OmeTiffWriter.build_ome(data_shapes=[mask.image[0, :, 0, 0, :, :].shape],
                                           data_types=[mask.dtype],
                                           dimension_order=["TYX"],
                                           channel_names=[mask.channel_names],
                                           physical_pixel_sizes=[PhysicalPixelSizes(X=mask.physical_pixel_sizes[0], Y=mask.physical_pixel_sizes[1], Z=mask.physical_pixel_sizes[2])])
    ome_metadata.structured_annotations.append(CommentAnnotation(value=buffered_handler.get_messages(), namespace="VLabApp"))
    for x in metadata:
        ome_metadata.structured_annotations.append(CommentAnnotation(value=x, namespace="VLabApp"))
    OmeTiffWriter.save(mask.image[0, :, 0, 0, :, :], output_file, ome_xml=ome_metadata)

    output_file = os.path.join(output_path, output_basename+".graphmlz")
    logger.info("Saving cell tracking graph to %s", output_file)
    # add metadata
    graph['VLabApp:Annotation:1'] = buffered_handler.get_messages()
    for i, x in enumerate(metadata):
        graph['VLabApp:Annotation:'+str(i+2)] = x
    graph.write_graphmlz(output_file)

    # create logfile
    logfile = os.path.join(output_path, output_basename+".log")
    with open(logfile, 'w') as f:
        f.write(buffered_handler.get_messages())


def main(mask_path, graph_path, output_path, output_basename, events_type, nframes_before, nframes_after, filter_border, border_width, filter_nmissing, nmissing):
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
    events_type: str
        Type of events to select ('division' or 'fusion').
    nframes_before: int
        number of stable frames before the event.
    nframes_after: int
        number of stable frames after the event.
    filter_border: bool
        filter-out cell tracks touching the border. Filtering is done after event selection, i.e. with one cell track per selected event.
    border_width: int
        border width (pixels).
    filter_nmissing: bool
        filter-out cell tracks with more than `nmissing` missing cells. Filtering is done after event selection, i.e. with one cell track per selected event.
    nmissing: int
        maximum number of missing cells per cell track.
    """

    try:
        ###########################
        # Setup logging
        ###########################
        logger = logging.getLogger(__name__)
        logger.info("EVENTS SELECTION MODULE")
        if not os.path.isdir(output_path):
            logger.debug("creating: %s", output_path)
            os.makedirs(output_path)

        logger.setLevel(logging.DEBUG)

        # Log to file:
        # saved at the end, using the content of the BufferedHandler.

        # Log to memory
        global buffered_handler
        buffered_handler = gf.BufferedHandler()
        buffered_handler.setFormatter(logging.Formatter('%(asctime)s (VLabApp - events selection module) [%(levelname)s] %(message)s'))
        buffered_handler.setLevel(logging.INFO)
        buffered_handler.addFilter(gf.IgnoreDuplicate("Manually editing mask"))
        logger.addHandler(buffered_handler)

        logger.info("System info:")
        logger.info("- platform: %s", platform())
        logger.info("- python version: %s", python_version())
        logger.info("- VLabApp version: %s", vlabapp_version)
        logger.info("- numpy version: %s", np.__version__)
        logger.info("- igraph version: %s", ig.__version__)
        logger.info("Input mask path: %s", mask_path)
        logger.info("Input graph path: %s", graph_path)

        ###########################
        # Load mask and graph
        ###########################
        # Load mask
        logger.debug("loading %s", mask_path)
        try:
            mask = gf.Image(mask_path)
            mask.imread()
        except Exception:
            logger.exception('Error loading mask %s', mask_path)
            # Remove all handlers for this module
            remove_all_log_handlers()
            raise

        # load mask metadata
        mask_metadata = []
        if mask.ome_metadata:
            for x in mask.ome_metadata.structured_annotations:
                if isinstance(x, CommentAnnotation) and x.namespace == "VLabApp":
                    if len(mask_metadata) == 0:
                        mask_metadata.append("Metadata for "+mask.path+":\n"+x.value)
                    else:
                        mask_metadata.append(x.value)

        # Load graph
        logger.debug("loading %s", graph_path)
        graph = gf.load_cell_tracking_graph(graph_path, mask.dtype)

        # graph metadata
        graph_metadata = []
        for a in graph.attributes():
            if a.startswith('VLabApp:Annotation'):
                if len(graph_metadata) == 0:
                    graph_metadata.append("Metadata for "+graph_path+":\n"+graph[a])
                else:
                    graph_metadata.append(graph[a])

        ###########################
        # select events
        ###########################
        if graph.vcount() == 0:
            logger.warning("Input mask and graph are empty")
            logger.info("Selected events: %s", 0)
        else:
            logger.info("Selecting events: type of events_type=%s, number frames before=%s, number frames after=%s, missing cells filter=%s, max missing cell=%s", events_type, nframes_before, nframes_after, filter_nmissing, nmissing)
            graph = filter_graph(graph, events_type, nframes_before, nframes_after, filter_nmissing, nmissing)
            logger.info("Selected events: %s", len(set(graph.vs['event_id'])))

            # Relabel mask and graph
            logger.info("Relabelling mask and graph")
            mask_id_event_id = sorted(set(zip(graph.vs['mask_id'], graph.vs['event_id'])))
            mask_id_event_id_to_new_mask_ids = {pair: i+1 for i, pair in enumerate(mask_id_event_id)}
            frame_to_mask_id_new_mask_id = {frame: {(mask_id, mask_id_event_id_to_new_mask_ids[(mask_id, event_id)]) for mask_id, event_id in zip(graph.vs.select(frame_eq=frame)['mask_id'], graph.vs.select(frame_eq=frame)['event_id'])} for frame in range(mask.sizes['T'])}
            for frame in range(mask.sizes['T']):
                map_id = np.repeat(0, mask.image[:, frame, :, :, :, :].max()+1).astype(mask.dtype)
                for mask_id, new_mask_id in frame_to_mask_id_new_mask_id[frame]:
                    map_id[mask_id] = new_mask_id
                mask.image[:, frame, :, :, :, :] = map_id[mask.image[:, frame, :, :, :, :]]
                graph.vs.select(frame_eq=frame)['mask_id'] = map_id[graph.vs.select(frame_eq=frame)['mask_id']]
                graph.es.select(frame_source_eq=frame)['mask_id_source'] = map_id[graph.es.select(frame_source_eq=frame)['mask_id_source']]
                graph.es.select(frame_target_eq=frame)['mask_id_target'] = map_id[graph.es.select(frame_target_eq=frame)['mask_id_target']]

            if filter_border:
                border_mask_ids = np.unique(
                    np.concatenate([
                        np.unique(mask.image[:, :, :, :, :border_width, :]),
                        np.unique(mask.image[:, :, :, :, -border_width:, :]),
                        np.unique(mask.image[:, :, :, :, :, :border_width]),
                        np.unique(mask.image[:, :, :, :, :, -border_width:])]))
                border_mask_ids = border_mask_ids[border_mask_ids > 0]
                # search for event_ids to remove
                event_ids_to_remove = set(graph.vs.select(mask_id_in=border_mask_ids)['event_id'])
                logger.info("Filtering cells touching the border (border width: %s): removing %s events", border_width, len(event_ids_to_remove))
                # mask_ids to keep
                mask_ids_to_keep = set(graph.vs.select(event_id_notin=event_ids_to_remove)['mask_id'])
                # filter graph
                graph = graph.subgraph([v.index for v in graph.vs.select(mask_id_in=mask_ids_to_keep)])

                # relabel
                map_id = np.repeat(0, mask.image.max()+1).astype(mask.dtype)
                n_ids = 1
                for mask_id in mask_ids_to_keep:
                    map_id[mask_id] = n_ids
                    n_ids += 1
                mask.image = map_id[mask.image]
                graph.vs['mask_id'] = map_id[graph.vs['mask_id']]
                graph.es['mask_id_source'] = map_id[graph.es['mask_id_source']]
                graph.es['mask_id_target'] = map_id[graph.es['mask_id_target']]


            nevents = len(set(graph.vs['event_id']))
            if nevents == 0:
                logger.warning("No events found: output mask and cell tracking graph are empty.")

            # remove temporary attribute
            del graph.vs['event_id']

        ###########################
        # save
        ###########################
        save(mask, graph, output_path, output_basename, metadata=mask_metadata+graph_metadata)

        # Remove all handlers for this module
        remove_all_log_handlers()

    except Exception:
        # Remove all handlers for this module
        remove_all_log_handlers()
        raise
