import os
import logging
from platform import python_version, platform
import numpy as np
import napari
import tifffile
import igraph as ig
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QGridLayout, QWidget, QPushButton, QLabel, QSpinBox, QScrollArea, QGroupBox, QCheckBox, QMessageBox, QSizePolicy
from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QCursor, QPixmap, QPainter, QPen, QPolygonF
from general import general_functions as gf
from aicsimageio.writers import OmeTiffWriter
from aicsimageio.types import PhysicalPixelSizes
from ome_types.model import CommentAnnotation
from version import __version__ as vlabapp_version


class NapariStatusBarHandler(logging.Handler):
    """
    logging handler to send message to the status bar of a napari viewer.

    Examples
    --------
    viewer=napari.viewer()
    handler=NapariStatusBarHandler(viewer)
    logging.getLogger().addHandler(handler)
    """

    def __init__(self, viewer):
        logging.Handler.__init__(self)
        self.status_bar = viewer.window._qt_window.statusBar()

    def emit(self, record):
        msg = self.format(record)
        self.status_bar.showMessage(msg)
        # force repainting to update message even when busy
        self.status_bar.repaint()


def simplify_graph(g):
    """
    Simplify graph by contracting chains of vertices with indegree=1 and outdegree=1.
    Resulting multi-edges are removed by inserting a vertex into each duplicated edge.

    Parameters
    ----------
    g: igraph.Graph
        a graph to simplify

    Returns
    -------
    igraph.Graph
        simplified graph.
    """
    # copy graph
    g = g.copy()
    # remove attributes
    for a in g.es.attribute_names():
        del g.es[a]
    for a in g.vs.attribute_names():
        del g.vs[a]
    # select subgraph of vertices with indegree 1 and outdegree 1 (i.e. boring vertices to be removed)
    vs_boring = g.vs.select(_indegree=1, _outdegree=1)
    # keep the subgraph with outgoing edges from boring vertices
    g2 = g.subgraph_edges(g.es.select(_source_in=vs_boring),
                          delete_vertices=False)
    # find connected components of this subgraph and contract them
    components = g2.connected_components(mode='weak')
    g.contract_vertices(components.membership)
    # remove self-loops
    g.simplify(multiple=False)
    # deal with multi edges: insert a node in each multi edge
    # Note: for each pair of vertices (v1,v2), _is_multiple returns all edges connecting v1 to v2 except one. We want all edges connecting v1 to v2.
    multi_edges = set([(e.source, e.target) for e in g.es.select(_is_multiple=True)])
    if len(multi_edges) > 0:
        edges_new = []
        edges_toremove = []
        n = 0
        for s, t in multi_edges:
            for e in g.es.select(_source=s, _target=t):
                edges_new.append((e.source, g.vcount()+n))
                edges_new.append((g.vcount()+n, e.target))
                edges_toremove.append(e)
                n += 1
        g.delete_edges(edges_toremove)
        g.add_vertices(n)
        g.add_edges(edges_new)
    return g


def get_graph_qpixmap(g, w, h, hide_intermediate=True):
    """
    Plot graph on a QPIxmap

    Parameters
    ----------
    g: igraph.Graph
        a graph to plot
    w: int
        QPixmap width
    h: int
        QPixmap height
    hide_intermediate: bool
        Do not draw vertice with indegree==1 and outdegree==1.

    Returns
    -------
    QPixmap
    """
    border = 0.15*min(w, h)  # fraction of min(w,h)
    point_size = 0.1*min(w, h)  # fraction of min(w,h)
    edge_width = 0.05*min(w, h)  # fraction of min(w,h)
    arrow_size = 3*edge_width
    layout = g.layout_sugiyama()  # layers=g.topological_sorting())
    layout.rotate(-90)
    g_xmin = min(p[0] for p in layout.coords)
    g_xmax = max(p[0] for p in layout.coords)
    g_ymin = min(p[1] for p in layout.coords)
    g_ymax = max(p[1] for p in layout.coords)
    g_w = g_xmax-g_xmin
    g_h = g_ymax-g_ymin
    if g_w < 0.0001:
        g_w = 1
    if g_h < 0.0001:
        g_h = 1
    coords = [[border+(w-2*border)*(p[0]-g_xmin)/g_w,
               border + (h-2*border)*(p[1]-g_ymin)/g_h] for p in layout.coords]

    image = QPixmap(w, h)
    image.fill(Qt.white)
    painter = QPainter(image)
    # draw edges
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(Qt.gray, edge_width, Qt.SolidLine, Qt.RoundCap))
    for i, j in [(e.source, e.target) for e in g.es]:
        painter.drawLine(QPointF(coords[i][0], coords[i][1]),
                         QPointF(coords[j][0], coords[j][1]))
    # draw arrows on edges
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(Qt.gray)
    painter.setPen(QPen(Qt.gray, 0))
    for i, j in [(e.source, e.target) for e in g.es]:
        arrow = QPolygonF()
        cx = (coords[j][0]+coords[i][0])/2
        cy = (coords[j][1]+coords[i][1])/2
        dx = (coords[j][0]-coords[i][0])
        dy = (coords[j][1]-coords[i][1])
        d = np.sqrt(dx**2+dy**2)
        dx = dx/d
        dy = dy/d
        nx = dy
        ny = -dx
        arrow.append(QPointF(cx-0.2*arrow_size*dx+arrow_size*nx/2,
                             cy-0.2*arrow_size*dy+arrow_size*ny/2))
        arrow.append(QPointF(cx+0.8*arrow_size*dx, cy+0.8*arrow_size*dy))
        arrow.append(QPointF(cx-0.2*arrow_size*dx-arrow_size*nx/2,
                             cy-0.2*arrow_size*dy-arrow_size*ny/2))
        painter.drawPolygon(arrow)
    # draw vertices
    painter.setBrush(Qt.black)
    painter.setPen(QPen(Qt.black, 0))
    for i in g.vs.indices:
        if not hide_intermediate or not (g.vs[i].indegree() == 1 and g.vs[i].outdegree() == 1):
            painter.drawEllipse(QPointF(coords[i][0], coords[i][1]),
                                point_size, point_size)
    painter.end()
    return image


class CellTracksFiltering:
    """
    A class to manipulate (currently only filter) cell tracking graph and mask.
    """

    # TODO: pass the mask as an Image object, instead of using the quick&dirty hack to pass the additional parameters mask_physical_pixel_sizes and mask_channel_names.
    def __init__(self, mask, graph, graph_topologies=None, mask_physical_pixel_sizes=(None, None, None), mask_channel_names=None, metadata=None):
        """
        Parameters
        ----------
        mask: ndarray
            a 3D (TYX) 16bit unsigned integer (uint16) numpy array
        graph: igraph.Graph
            a graph to plot.
        graph_topologies: list of igraph.Graph
            list of graph topologies. If None, create from graph.
        """

        self.logger = logging.getLogger(__name__)
        self.mask = mask
        self.mask_physical_pixel_sizes = mask_physical_pixel_sizes
        self.mask_channel_names = mask_channel_names
        self.graph = graph
        self.metadata = metadata if metadata is not None else []
        self.cell_tracks = None
        self.selected_cell_track_ids = None
        # store cell tracks topologies. I.e. self.cell_tracks_topology[n]=[i1,i2,...] => self.cell_track[n] is isomorphic to self.graph_topologies[i1] and  self.graph_topologies[i2] and ...
        self.cell_tracks_topology = None
        # graph topologies to search for
        self.graph_topologies = []

        # store last used parameters in self._evaluate_cell_tracks()
        self.nframes_stable_fusion = None
        self.nframes_stable_division = None
        self.stable_overlap_fraction = None

        if graph_topologies is None:
            # extract existing topologies from graph
            components = self.graph.connected_components(mode='weak')
            self.graph_topologies = []
            graph_topologies_sortkey = []
            # Ignore topologies with more than max_fusion_divisions fusions or divisions
            max_fusion_divisions = 4
            # Ignore topologies with more than max_others events of type: cells dividing in more than 2 or more than 2 cells merging
            max_others = 0
            # Ignore topologies with less than min_vertices vertices
            min_vertices = 2
            for cmp in components:
                g = simplify_graph(self.graph.subgraph(cmp))
                if not any(g.isomorphic(g2) for g2 in self.graph_topologies):
                    nothers = len(g.vs.select(lambda v: v.indegree() > 2 or v.outdegree() > 2))
                    nfusions = len(g.vs.select(_indegree=2))
                    ndivisions = len(g.vs.select(_outdegree=2))
                    # nvertices, ignoring intermediate nodes with indegree == outdegree == 1
                    nvertices = len(g.vs.select(lambda v: not (v.indegree() == 1 and v.outdegree() == 1)))
                    if nfusions+ndivisions <= max_fusion_divisions and nothers <= max_others and nvertices >= min_vertices:
                        self.graph_topologies.append(g)
                        graph_topologies_sortkey.append((nfusions+ndivisions, nfusions, ndivisions, nothers, nvertices))

            # Order by sortkey (using lexicographical order)
            idx = np.lexsort(np.array(graph_topologies_sortkey).T)
            self.graph_topologies = np.array(self.graph_topologies)[idx].tolist()
            del graph_topologies_sortkey
        else:
            self.graph_topologies = []
            for g in graph_topologies:
                self.graph_topologies.append(simplify_graph(g))
            """# # to use user defined topologies instead:
            # self.graph_topologies = []
            # # 0 division, 0 fusion
            # self.graph_topologies.append(
            #     simplify_graph(ig.Graph(directed=True,
            #                             edges=[[0, 1]])))
            # # 1 division, 0 fusion
            # self.graph_topologies.append(
            #     simplify_graph(ig.Graph(directed=True,
            #                             edges=[[0, 1],
            #                                    [1, 2],
            #                                    [1, 3]])))
            # # 0 division, 1 fusion
            # self.graph_topologies.append(
            #     simplify_graph(ig.Graph(directed=True,
            #                             edges=[[0, 2],
            #                                    [1, 2],
            #                                    [2, 3]])))
            # # 1 division, 1 fusion
            # self.graph_topologies.append(
            #     simplify_graph(ig.Graph(directed=True,
            #                             edges=[[0, 1],
            #                                    [1, 2],
            #                                    [1, 2],
            #                                    [2, 3]])))
            # # 1 division, 1 fusion
            # self.graph_topologies.append(
            #     simplify_graph(ig.Graph(directed=True,
            #                             edges=[[0, 2],
            #                                    [1, 2],
            #                                    [2, 3],
            #                                    [3, 4],
            #                                    [3, 5]])))
            # # 1 division, 1 fusion
            # self.graph_topologies.append(
            #     simplify_graph(ig.Graph(directed=True,
            #                             edges=[[0, 2],
            #                                    [1, 3],
            #                                    [2, 4],
            #                                    [2, 3],
            #                                    [3, 5]])))
            # # 2 divisions
            # self.graph_topologies.append(
            #     simplify_graph(ig.Graph(directed=True,
            #                             edges=[[0, 1],
            #                                    [1, 2],
            #                                    [1, 3],
            #                                    [3, 4],
            #                                    [3, 5]])))
            # # 2 fusions
            # self.graph_topologies.append(
            #     simplify_graph(ig.Graph(directed=True,
            #                             edges=[[0, 4],
            #                                    [1, 3],
            #                                    [2, 3],
            #                                    [3, 4],
            #                                    [4, 5]])))"""

        self._evaluate_cell_tracks()
        self.selected_cell_track_ids = set(range(len(self.cell_tracks)))

    def _evaluate_cell_tracks(self, nframes_stable_fusion=0, nframes_stable_division=0, stable_overlap_fraction=0):
        """
        Evaluate cell tracks (connected components of the cell tracking graph) and their properties.

        Parameters
        ----------
        nframes_stable_fusion: int
            minimum number of stable frames before and after a fusion event for it to be considered as a fusion.
        nframes_stable_division: int
            minimum number of stable frames before and after a division event for it to be considered as a division.
        stable_overlap_fraction: float
            edges are considered as not stable if overlap_fraction_target < `stable_overlap_fraction` or overlap_fraction_source < `stable_overlap_fraction`.

        Notes
        -------
        This function populates the `cell_tracks` attribute.
        `cell_tracks` is list of dict. Each element of the list is a dict
        that correspond to one cell track with the following keys:
                graph_vertices: list of int
                    indices of vertices in the cell track (in `graph`).
                mask_ids: ndarray
                    mask ids of the vertices in the cell track.
                frame_min: int
                    minimum frame across all vertices in the cell track.
                frame_max: int
                    maximum frame across all vertices in the cell track.
                n_missing: int
                     number of missing vertices in the cell track (i.e. edges spanning more than 1 frame).
                n_fusions: int
                     number of fusions events (surrounded by `nframes_stable_fusion` stable frames) in the cell track.
                n_divisions: int
                     number of divisions events (surrounded by `nframes_stable_fusion` stable frames) in the cell track.
                min_area: int
                     minimum cell area in the cell track.
                max_area: int
                     maximum cell area in the cell track.
                graph_topology: list of int
                     list of indices. For each index `i` in the list, the cell track is isomorphic to the topology `graph_topologies[i]`.
        """
        self.logger.debug("evaluating cell tracks")

        self.nframes_stable_fusion = nframes_stable_fusion
        self.nframes_stable_division = nframes_stable_division
        self.stable_overlap_fraction = stable_overlap_fraction

        # Flag edges as stable if source vertex has a unique outgoing edge and target vertex has a unique incoming edge
        self.graph.es['stable'] = False
        self.graph.es.select(lambda edge: abs(edge['frame_source']-edge['frame_target']) == 1 and edge['mask_id_source'] == edge['mask_id_target'] and self.graph.outdegree(edge.source) == 1 and self.graph.indegree(edge.target) == 1)['stable']=True
        # Flag edge with low overlap as unstable
        self.graph.es.select(overlap_fraction_source_lt=stable_overlap_fraction)['stable'] = False
        self.graph.es.select(overlap_fraction_target_lt=stable_overlap_fraction)['stable'] = False

        # Evaluate length of "stable edges" regions (size of connected components in the subgraph of "stable edges") and store it as vertex attribute
        g2 = self.graph.subgraph_edges(self.graph.es.select(stable=True),
                                       delete_vertices=False)
        components = g2.connected_components(mode='weak')
        for i, n in enumerate(components.sizes()):
            self.graph.vs[components[i]]['stable_component_size'] = n

        # Eval cell tracks (i.e. connected components of the cell tracking graph)
        self.logger.debug("finding connected components")
        components = self.graph.connected_components(mode='weak')

        # Topology
        if self.cell_tracks_topology is None:
            self.cell_tracks_topology = []
            for cmp in components:
                # self.cell_tracks_topology[n]=[i1,i2,...] => self.cell_track[n] is isomorphic to self.graph_topologies[i1] and  self.graph_topologies[i2] and ...
                g2 = simplify_graph(self.graph.subgraph(cmp))
                self.cell_tracks_topology.append([i for i, g3 in enumerate(self.graph_topologies) if g2.isomorphic(g3)])

        self.logger.debug("building table of cell tracks properties")
        self.cell_tracks = []
        for i, cmp in enumerate(components):
            g2 = self.graph.subgraph(cmp)
            mask_ids = np.unique(g2.vs['mask_id'])
            frame_min = np.min(g2.vs['frame'])
            frame_max = np.max(g2.vs['frame'])
            # Number of missing mask regions (edges spanning more than 1 frame)
            n_missing = np.sum(e['frame_target'] - e['frame_source'] - 1 for e in g2.es)
            # Number fusion events with stable neighborhood
            n_fusions = np.sum(1 if v.indegree() > 1 and min(v2['stable_component_size'] for v2 in v.neighbors()) >= nframes_stable_fusion+1 else 0 for v in g2.vs)
            # Number division events with stable neighborhood
            n_divisions = np.sum(1 if v.outdegree() > 1 and min(v2['stable_component_size'] for v2 in v.neighbors()) >= nframes_stable_division+1 else 0 for v in g2.vs)
            min_area = np.min(g2.vs['area'])
            max_area = np.max(g2.vs['area'])
            # Topology
            self.cell_tracks.append({'graph_vertices': cmp,
                                     'mask_ids': mask_ids,
                                     'frame_min': frame_min,
                                     'frame_max': frame_max,
                                     'n_missing': n_missing,
                                     'n_fusions': n_fusions,
                                     'n_divisions': n_divisions,
                                     'min_area': min_area,
                                     'max_area': max_area,
                                     'graph_topology': self.cell_tracks_topology[i]})

    def get_max_area(self):
        return [x['max_area'] for x in self.cell_tracks]

    def get_min_area(self):
        return [x['min_area'] for x in self.cell_tracks]

    def get_n_missing(self):
        return [x['n_missing'] for x in self.cell_tracks]

    def get_n_divisions(self):
        return [x['n_divisions'] for x in self.cell_tracks]

    def get_n_fusions(self):
        return [x['n_fusions'] for x in self.cell_tracks]

    def filter_border(self, border_width):
        """
        Filter out cell tracks with at least one cell touching the border of the mask.

        Parameters
        ----------
        border_width: int
            thickness of the border (in pixel). It should be strictly greater than 0.
        """

        # Find mask_id touching the border (assuming mask T,Y,X axes)
        self.logger.info("filtering cell touching the border (border width: %s)", border_width)
        border_mask_ids = np.unique(
            np.concatenate([
                np.unique(self.mask[:, :border_width, :]),
                np.unique(self.mask[:, -border_width:, :]),
                np.unique(self.mask[:, :, :border_width]),
                np.unique(self.mask[:, :, -border_width:])]))
        border_mask_ids = border_mask_ids[border_mask_ids > 0]
        self.selected_cell_track_ids = [i for i in self.selected_cell_track_ids if np.isin(self.cell_tracks[i]['mask_ids'], border_mask_ids).any() == False]

    def filter_all_cells_area(self, min_area, max_area):
        """
        Keep only cell tracks with all cell area within the interval [`min_area`,`max_area`].

        Parameters
        ----------
        min_area: int
            minimum area (number of pixels)
        max_area: int
            maximum area (number of pixels)
        """
        self.logger.info("filtering cell area (keep cell tracks with all cells area in [%s,%s])", min_area, max_area)
        self.selected_cell_track_ids = [i for i in self.selected_cell_track_ids if self.cell_tracks[i]['min_area'] >= min_area and self.cell_tracks[i]['max_area'] <= max_area]

    def filter_one_cell_area(self, min_area, max_area):
        """
        Keep only cell tracks with at least one cell with area < `max_area` and at least one cell with area > `min_area` (not necessarily the same cell).

        Parameters
        ----------
        min_area: int
            minimum area (number of pixels)
        max_area: int
            maximum area (number of pixels)
        """
        self.logger.info("filtering cell area (keep cell tracks with at least one area in [%s,%s])", min_area, max_area)
        self.selected_cell_track_ids = [i for i in self.selected_cell_track_ids if self.cell_tracks[i]['max_area'] >= min_area and self.cell_tracks[i]['min_area'] <= max_area]

    def filter_track_length(self, track_length):
        """
        Keep only cell tracks spanning at least `track_length`.

        Parameters
        ----------
        track_length: int
            minimum track length (number of frames).
        """
        self.logger.info("filtering cell track length (keep cell tracks with minimum track length: %s)", track_length)
        self.selected_cell_track_ids = [i for i in self.selected_cell_track_ids if self.cell_tracks[i]['frame_max']-self.cell_tracks[i]['frame_min']+1 >= track_length]

    def filter_n_missing(self, n):
        """
        Keep only cell tracks with at most `n` missing cell masks (i.e. edges spanning more than 1 frame).

        Parameters
        ----------
        n: int
            maximum number of missing cell masks.
        """
        self.logger.info("filtering number of missing cells (maximum number of missing cells: %s", n)
        self.selected_cell_track_ids = [i for i in self.selected_cell_track_ids if self.cell_tracks[i]['n_missing'] <= n]

    def filter_n_divisions(self, min_n, max_n, nframes_stable, stable_overlap_fraction):
        """
        Keep only cell tracks with a number of division events within [`min_n`,`max_n`] interval. Each division event must be surrounded by the `nframes_stable` stable frames.

        Parameters
        ----------
        min_n: int
            minimum number of division event.
        max_n: int
            maximum number of division event.
        nframes_stable: int
            minimum number of stable frames before and after a division event for it to be considered as a division.
        stable_overlap_fraction: float
            edges are considered as not stable if overlap_fraction_target < `stable_overlap_fraction` or overlap_fraction_source < `stable_overlap_fraction`.
        """
        if not nframes_stable == self.nframes_stable_division or not stable_overlap_fraction == self.stable_overlap_fraction:
            self._evaluate_cell_tracks(self.nframes_stable_fusion, nframes_stable, stable_overlap_fraction)

        self.logger.info("filtering number of divisions (number of divisions in [%s,%s], number of stable frames: %s)", min_n, max_n, nframes_stable)
        self.selected_cell_track_ids = [i for i in self.selected_cell_track_ids if self.cell_tracks[i]['n_divisions'] >= min_n and self.cell_tracks[i]['n_divisions'] <= max_n]

    def filter_n_fusions(self, min_n, max_n, nframes_stable, stable_overlap_fraction):
        """
        Keep only cell tracks with a number of fusion events within [`min_n`,`max_n`] interval. Each fusion event must be surrounded by the `nframes_stable` stable frames.

        Parameters
        ----------
        min_n: int
            minimum number of fusion event.
        max_n: int
            maximum number of fusion event.
        nframes_stable: int
            minimum number of stable frames before and after a fusion event for it to be considered as a fusion.
        stable_overlap_fraction: float
            edges are considered as not stable if overlap_fraction_target < `stable_overlap_fraction` or overlap_fraction_source < `stable_overlap_fraction`.
        """
        if not nframes_stable == self.nframes_stable_fusion or not stable_overlap_fraction == self.stable_overlap_fraction:
            self._evaluate_cell_tracks(nframes_stable, self.nframes_stable_division, stable_overlap_fraction)

        self.logger.info("filtering number of fusions (number fusions in [%s,%s], number of stable frames: %s)", min_n, max_n, nframes_stable)
        self.selected_cell_track_ids = [i for i in self.selected_cell_track_ids if self.cell_tracks[i]['n_fusions'] >= min_n and self.cell_tracks[i]['n_fusions'] <= max_n]

    def filter_topology(self, selected_topologies):
        """
        Keep only cell tracks with topology matching at least of the topologies self.graph_topologies[i] for i in selected_topologies.

        Parameters
        ----------
        selected_topologies: list of int
            indices of topologies for list self.graph_topologies.
        """

        self.logger.info("filtering topology (topologies: %s)",  ", ".join([str(i) for i in selected_topologies]))
        self.selected_cell_track_ids = [i for i in self.selected_cell_track_ids if np.isin(self.cell_tracks[i]['graph_topology'], selected_topologies).any()]

    def reset_filters(self):
        """
        Remove filters
        """
        self.logger.info("resetting filters")
        self.selected_cell_track_ids = set(range(len(self.cell_tracks)))

    def get_mask(self, relabel_mask_ids=False):
        """
        Parameters
        ----------
        relabel_mask_ids: bool
            relabel mask ids to consecutive integer starting from 1 (keeping 0 for background).

        Returns
        -------
        ndarray
            filtered cell mask
        """
        selected_cell_tracks = [self.cell_tracks[i] for i in self.selected_cell_track_ids]
        self.logger.debug("Selected cell tracks: %s/%s", len(selected_cell_tracks), len(self.cell_tracks))
        self.logger.debug("selecting mask_ids")
        if len(selected_cell_tracks) > 0:
            selected_mask_ids = np.unique(np.concatenate(([x['mask_ids'] for x in selected_cell_tracks])))
        else:
            selected_mask_ids = np.array([], dtype=self.mask.dtype)
        self.logger.debug("copying mask")
        selected_mask = self.mask.copy()
        if len(selected_cell_tracks) != len(self.cell_tracks):
            self.logger.debug("filtering mask")
            selected_mask[np.logical_not(np.isin(selected_mask, selected_mask_ids))] = 0

        # relabel mask ids to consecutive integer starting from 1 (keeping 0 for background)
        if relabel_mask_ids:
            self.logger.debug("relabelling filtered mask")
            # create mapping table
            map_id = np.repeat(0, np.max(self.mask)+1).astype(self.mask.dtype)
            map_id[0] = 0
            n_ids = 1
            for mask_id in selected_mask_ids:
                map_id[mask_id] = n_ids
                n_ids += 1
            selected_mask = map_id[selected_mask]

        self.logger.debug("Done")
        return selected_mask

    def get_graph(self, relabel_mask_ids=False):
        """
        Parameters
        ----------
        relabel_mask_ids: bool
            relabel mask ids to consecutive integer starting from 1 (keeping 0 for background).

        Returns
        -------
        igraph.Graph
            filtered cell tracking graph
        """
        selected_cell_tracks = [self.cell_tracks[i] for i in self.selected_cell_track_ids]
        self.logger.debug("Selected cell tracks: %s/%s", len(selected_cell_tracks), len(self.cell_tracks))
        self.logger.debug("filtering graph")
        if len(selected_cell_tracks) > 0:
            selected_mask_ids = np.unique(np.concatenate(([x['mask_ids'] for x in selected_cell_tracks])))
            selected_graph_vertices = np.unique(np.concatenate(([x['graph_vertices'] for x in selected_cell_tracks])))
        else:
            selected_mask_ids = np.array([], dtype=self.mask.dtype)
            selected_graph_vertices = np.array([], dtype='int')
        g2 = self.graph.subgraph(selected_graph_vertices)

        # relabel mask ids to consecutive integer starting from 1 (keeping 0 for background)
        if relabel_mask_ids:
            self.logger.debug("relabelling filtered graph")
            # create mapping table
            map_id = np.repeat(0, np.max(self.mask)+1).astype(self.mask.dtype)
            map_id[0] = 0
            n_ids = 1
            for mask_id in selected_mask_ids:
                map_id[mask_id] = n_ids
                n_ids += 1
            g2.vs['mask_id'] = map_id[g2.vs['mask_id']].astype(self.mask.dtype)
            g2.es['mask_id_source'] = map_id[g2.es['mask_id_source']].astype(self.mask.dtype)
            g2.es['mask_id_target'] = map_id[g2.es['mask_id_target']].astype(self.mask.dtype)

        self.logger.debug("Done")
        return g2

    def save(self, output_path, output_basename, relabel_mask_ids=True):
        """
        Save filtered cell tracking graph and cell mask as  `output_path`/`output_basename`.graphmlz and `output_path`/`output_basename`.ome.tif.

        Parameters
        ----------
        output_path: str
            output directory
        output_basename: str
            output basename
        relabel_mask_ids: bool
            relabel mask ids to consecutive integer starting from 1 (keeping 0 for background).
        """
        if not os.path.isdir(output_path):
            self.logger.debug("creating: %s", output_path)
            os.makedirs(output_path)

        self.logger.info("Selected cell tracks: %s/%s", len(self.selected_cell_track_ids), len(self.cell_tracks))
        output_file = os.path.join(output_path, output_basename+".ome.tif")
        self.logger.info("Saving segmentation mask to %s", output_file)
        selected_mask = self.get_mask(relabel_mask_ids)
        selected_mask = selected_mask[:, np.newaxis, :, :]
        ome_metadata=OmeTiffWriter.build_ome(data_shapes=[selected_mask.shape],
                                             data_types=[selected_mask.dtype],
                                             dimension_order=["TCYX"],
                                             channel_names=[self.mask_channel_names],
                                             physical_pixel_sizes=[PhysicalPixelSizes(X=self.mask_physical_pixel_sizes[0], Y=self.mask_physical_pixel_sizes[1], Z=self.mask_physical_pixel_sizes[2])])
        ome_metadata.structured_annotations.append(CommentAnnotation(value=buffered_handler.get_messages(),namespace="VLabApp"))
        for x in self.metadata:
            ome_metadata.structured_annotations.append(CommentAnnotation(value=x,namespace="VLabApp"))
        OmeTiffWriter.save(selected_mask, output_file, ome_xml=ome_metadata)

        output_file = os.path.join(output_path, output_basename+".graphmlz")
        self.logger.info("Saving cell tracking graph to %s", output_file)
        g = self.get_graph(relabel_mask_ids)
        #add metadata
        g['VLabApp:Annotation:1'] = buffered_handler.get_messages()
        for i, x in enumerate(self.metadata):
            g['VLabApp:Annotation:'+str(i+2)] = x
        g.write_graphmlz(output_file)


class GraphFilteringWidget(QWidget):
    """
    A widget to use inside napari
    """

    # TODO: pass the mask as an Image object, instead of using the quick&dirty hack to pass the additional parameters mask_physical_pixel_sizes and mask_channel_names.
    def __init__(self, mask, graph, viewer_images, image_path, output_path, output_basename, graph_topologies=None, mask_physical_pixel_sizes=(None, None, None), mask_channel_names=None, metadata=None):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.mask = mask.get_TYXarray()
        self.graph = graph
        self.viewer_images = viewer_images
        self.image_path = image_path
        self.output_path = output_path
        self.output_basename = output_basename

        # True if filter settings have been changed but filtering has not been applied:
        self.mask_need_filtering = False
        # True if mask have been modified since last save (or not yet saved):
        self.mask_modified = True

        self.cell_tracks_filtering = CellTracksFiltering(self.mask, self.graph, graph_topologies=graph_topologies, mask_physical_pixel_sizes=mask_physical_pixel_sizes, mask_channel_names=mask_channel_names, metadata=metadata)

        layout = QVBoxLayout()

        # No cells touching the border
        self.filter_border_yn = QGroupBox("Border")
        self.filter_border_yn.setCheckable(True)
        self.filter_border_yn.setChecked(False)
        self.filter_border_yn.toggled.connect(self.filters_changed)
        self.filter_border_yn.setToolTip('Keep only cell tracks with no cell touching the border.')
        layout2 = QGridLayout()
        help_label = QLabel("Remove cell tracks with at least one cell touching the border.")
        help_label.setWordWrap(True)
        help_label.setMinimumWidth(10)
        layout2.addWidget(help_label, 0, 0, 1, 2)
        self.border_width = QSpinBox()
        self.border_width.setMinimum(1)
        self.border_width.setMaximum(100)
        self.border_width.setValue(2)
        self.border_width.valueChanged.connect(self.filters_changed)
        layout2.addWidget(QLabel("Border width (pixel)"), 1, 0)
        layout2.addWidget(self.border_width, 1, 1)
        self.filter_border_yn.setLayout(layout2)
        layout.addWidget(self.filter_border_yn)

        # All cells area within range value
        self.filter_all_cells_area_yn = QGroupBox("Cell area (all cells)")
        self.filter_all_cells_area_yn.setCheckable(True)
        self.filter_all_cells_area_yn.setChecked(False)
        self.filter_all_cells_area_yn.toggled.connect(self.filters_changed)
        layout2 = QGridLayout()
        help_label = QLabel("Keep only cell tracks with all cell area within [min,max] range.")
        help_label.setWordWrap(True)
        help_label.setMinimumWidth(10)
        layout2.addWidget(help_label, 0, 0, 1, 2)
        self.all_cells_min_area = QSpinBox()
        self.all_cells_min_area.setMinimum(0)
        self.all_cells_min_area.setMaximum(max(self.cell_tracks_filtering.get_max_area()))
        self.all_cells_min_area.setValue(min(self.cell_tracks_filtering.get_min_area()))
        self.all_cells_min_area.valueChanged.connect(self.filters_changed)
        layout2.addWidget(QLabel("Min area (pixel)"), 1, 0)
        layout2.addWidget(self.all_cells_min_area, 1, 1)
        self.all_cells_max_area = QSpinBox()
        self.all_cells_max_area.setMinimum(0)
        self.all_cells_max_area.setMaximum(max(self.cell_tracks_filtering.get_max_area()))
        self.all_cells_max_area.setValue(max(self.cell_tracks_filtering.get_max_area()))
        self.all_cells_max_area.valueChanged.connect(self.filters_changed)
        layout2.addWidget(QLabel("Max area (pixel)"), 2, 0)
        layout2.addWidget(self.all_cells_max_area, 2, 1)
        self.filter_all_cells_area_yn.setLayout(layout2)
        layout.addWidget(self.filter_all_cells_area_yn)

        # At least one cell area within range value
        self.filter_one_cell_area_yn = QGroupBox("Cell area (at least one cell)")
        self.filter_one_cell_area_yn.setCheckable(True)
        self.filter_one_cell_area_yn.setChecked(False)
        self.filter_one_cell_area_yn.toggled.connect(self.filters_changed)
        layout2 = QGridLayout()
        help_label = QLabel("Keep only cell tracks with at least one cell area within [min,max] range.")
        help_label.setWordWrap(True)
        help_label.setMinimumWidth(10)
        layout2.addWidget(help_label, 0, 0, 1, 2)
        self.one_cell_min_area = QSpinBox()
        self.one_cell_min_area.setMinimum(0)
        self.one_cell_min_area.setMaximum(max(self.cell_tracks_filtering.get_max_area()))
        self.one_cell_min_area.setValue(min(self.cell_tracks_filtering.get_min_area()))
        self.one_cell_min_area.valueChanged.connect(self.filters_changed)
        layout2.addWidget(QLabel("Min area (pixel)"), 1, 0)
        layout2.addWidget(self.one_cell_min_area, 1, 1)
        self.one_cell_max_area = QSpinBox()
        self.one_cell_max_area.setMinimum(0)
        self.one_cell_max_area.setMaximum(max(self.cell_tracks_filtering.get_max_area()))
        self.one_cell_max_area.setValue(max(self.cell_tracks_filtering.get_max_area()))
        self.one_cell_max_area.valueChanged.connect(self.filters_changed)
        layout2.addWidget(QLabel("Max area (pixel)"), 2, 0)
        layout2.addWidget(self.one_cell_max_area, 2, 1)
        self.filter_one_cell_area_yn.setLayout(layout2)
        layout.addWidget(self.filter_one_cell_area_yn)

        # cell track length
        self.filter_track_length_yn = QGroupBox("Cell track length")
        self.filter_track_length_yn.setCheckable(True)
        self.filter_track_length_yn.setChecked(False)
        self.filter_track_length_yn.toggled.connect(self.filters_changed)
        layout2 = QGridLayout()
        help_label = QLabel("Keep only cell tracks spanning at least the select number of frames.")
        help_label.setWordWrap(True)
        help_label.setMinimumWidth(10)
        layout2.addWidget(help_label, 0, 0, 1, 2)
        self.nframes = QSpinBox()
        self.nframes.setMinimum(0)
        self.nframes.setMaximum(mask.sizes['T'])
        self.nframes.setValue(0)
        self.nframes.valueChanged.connect(self.filters_changed)
        self.filter_track_length_yn.setLayout(layout2)
        layout2.addWidget(QLabel("Min track length (frames)"), 1, 0)
        layout2.addWidget(self.nframes, 1, 1)
        layout.addWidget(self.filter_track_length_yn)

        # n_missing
        self.filter_n_missing_yn = QGroupBox("Missing cells")
        self.filter_n_missing_yn.setCheckable(True)
        self.filter_n_missing_yn.setChecked(False)
        self.filter_n_missing_yn.toggled.connect(self.filters_changed)
        layout2 = QGridLayout()
        help_label = QLabel("Keep only cell tracks with at most the selected number of missing cell mask.")
        help_label.setWordWrap(True)
        help_label.setMinimumWidth(10)
        layout2.addWidget(help_label, 0, 0, 1, 2)
        self.nmissing = QSpinBox()
        self.nmissing.setMinimum(0)
        self.nmissing.setMaximum(max(self.cell_tracks_filtering.get_n_missing()))
        self.nmissing.setValue(max(self.cell_tracks_filtering.get_n_missing()))
        self.nmissing.valueChanged.connect(self.filters_changed)
        self.filter_n_missing_yn.setLayout(layout2)
        layout2.addWidget(QLabel("Max missing cells"), 1, 0)
        layout2.addWidget(self.nmissing, 1, 1)
        layout.addWidget(self.filter_n_missing_yn)

        # n_divisions
        self.filter_n_divisions_yn = QGroupBox("Cell divisions")
        self.filter_n_divisions_yn.setCheckable(True)
        self.filter_n_divisions_yn.setChecked(False)
        self.filter_n_divisions_yn.toggled.connect(self.filters_changed)
        layout2 = QGridLayout()
        help_label = QLabel("Keep only cell tracks with a number of divisions events within [min,max] range. Each division event must be surrounded by the specified number of stable frames.")
        help_label.setWordWrap(True)
        help_label.setMinimumWidth(10)
        layout2.addWidget(help_label, 0, 0, 1, 2)
        self.min_ndivisions = QSpinBox()
        self.min_ndivisions.setMinimum(0)
        self.min_ndivisions.setMaximum(max(self.cell_tracks_filtering.get_n_divisions()))
        self.min_ndivisions.setValue(min(self.cell_tracks_filtering.get_n_divisions()))
        self.min_ndivisions.valueChanged.connect(self.filters_changed)
        layout2.addWidget(QLabel("Min divisions"), 1, 0)
        layout2.addWidget(self.min_ndivisions, 1, 1)
        self.max_ndivisions = QSpinBox()
        self.max_ndivisions.setMinimum(0)
        self.max_ndivisions.setMaximum(max(self.cell_tracks_filtering.get_n_divisions()))
        self.max_ndivisions.setValue(max(self.cell_tracks_filtering.get_n_divisions()))
        self.max_ndivisions.valueChanged.connect(self.filters_changed)
        layout2.addWidget(QLabel("Max divisions"), 2, 0)
        layout2.addWidget(self.max_ndivisions, 2, 1)
        self.nframes_stable_division = QSpinBox()
        self.nframes_stable_division.setMinimum(0)
        self.nframes_stable_division.setMaximum(mask.sizes['T'])
        self.nframes_stable_division.setValue(1)
        self.nframes_stable_division.valueChanged.connect(self.filters_changed)
        layout2.addWidget(QLabel("Min stable size (frames):"), 3, 0)
        layout2.addWidget(self.nframes_stable_division, 3, 1)
        self.filter_n_divisions_yn.setLayout(layout2)
        layout.addWidget(self.filter_n_divisions_yn)

        # n_fusions
        self.filter_n_fusions_yn = QGroupBox("Cell fusions")
        self.filter_n_fusions_yn.setCheckable(True)
        self.filter_n_fusions_yn.setChecked(False)
        self.filter_n_fusions_yn.toggled.connect(self.filters_changed)
        layout2 = QGridLayout()
        help_label = QLabel("Keep only cell tracks with a number of fusions events within [min,max] range. Each division event must be surrounded by the specified number of stable frames.")
        help_label.setWordWrap(True)
        help_label.setMinimumWidth(10)
        layout2.addWidget(help_label, 0, 0, 1, 2)
        self.min_nfusions = QSpinBox()
        self.min_nfusions.setMinimum(0)
        self.min_nfusions.setMaximum(max(self.cell_tracks_filtering.get_n_fusions()))
        self.min_nfusions.setValue(min(self.cell_tracks_filtering.get_n_fusions()))
        self.min_nfusions.valueChanged.connect(self.filters_changed)
        layout2.addWidget(QLabel("Min fusions"), 1, 0)
        layout2.addWidget(self.min_nfusions, 1, 1)
        self.max_nfusions = QSpinBox()
        self.max_nfusions.setMinimum(0)
        self.max_nfusions.setMaximum(max(self.cell_tracks_filtering.get_n_fusions()))
        self.max_nfusions.setValue(max(self.cell_tracks_filtering.get_n_fusions()))
        self.max_nfusions.valueChanged.connect(self.filters_changed)
        layout2.addWidget(QLabel("Max fusions"), 2, 0)
        layout2.addWidget(self.max_nfusions, 2, 1)
        self.nframes_stable_fusion = QSpinBox()
        self.nframes_stable_fusion.setMinimum(0)
        self.nframes_stable_fusion.setMaximum(mask.sizes['T'])
        self.nframes_stable_fusion.setValue(1)
        self.nframes_stable_fusion.valueChanged.connect(self.filters_changed)
        layout2.addWidget(QLabel("Min stable size (frames):"), 3, 0)
        layout2.addWidget(self.nframes_stable_fusion, 3, 1)
        self.filter_n_fusions_yn.setLayout(layout2)
        layout.addWidget(self.filter_n_fusions_yn)

        # Topologies
        self.filter_topology_yn = QGroupBox("Graph topology")
        self.filter_topology_yn.setCheckable(True)
        self.filter_topology_yn.setChecked(False)
        self.filter_topology_yn.toggled.connect(self.filters_changed)
        layout2 = QVBoxLayout()
        help_label = QLabel("Keep only cell tracks with selected topologies.")
        help_label.setWordWrap(True)
        help_label.setMinimumWidth(10)
        layout2.addWidget(help_label)
        self.topology_yn = []
        for g in self.cell_tracks_filtering.graph_topologies:
            layout3 = QHBoxLayout()
            self.topology_yn.append(QCheckBox())
            self.topology_yn[-1].setChecked(False)
            self.topology_yn[-1].stateChanged.connect(self.filters_changed)
            layout3.addWidget(self.topology_yn[-1])
            label = QLabel()
            label.setPixmap(get_graph_qpixmap(g, 150, 50))
            label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            # label.setScaledContents(True)
            layout3.addWidget(label)
            layout2.addLayout(layout3)
        self.filter_topology_yn.setLayout(layout2)
        layout.addWidget(self.filter_topology_yn)

        # Filter button
        layout2 = QHBoxLayout()
        self.filter_button = QPushButton("Filter", self)
        self.filter_button.clicked.connect(self.filter)
        layout2.addWidget(self.filter_button)

        # Save button
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.save)
        layout2.addWidget(self.save_button)

        # Create a button to quit
        button = QPushButton("Quit")
        button.clicked.connect(self.quit)
        layout2.addWidget(button)

        layout.addLayout(layout2)

        # Add spacer (to avoid filling whole space when the widget is inside a QScrollArea)
        layout.addStretch(1)
        self.setLayout(layout)

        if self.mask_modified:
            self.save_button.setStyleSheet("background: darkred;")
        if self.mask_need_filtering:
            self.filter_button.setStyleSheet("background: darkred;")
            self.save_button.setText("Filter && Save")

        # To allow saving image & mask before closing (__del__ is called too late)
        # TODO: replace by proper napari close event once implemented (https://forum.image.sc/t/handle-of-close-event-in-napari/61039)
        self.viewer_images.window._qt_window.destroyed.connect(self.on_viewer_images_close)

        # Add a handler to output messages to napari status bar
        handler = NapariStatusBarHandler(self.viewer_images)
        handler.setFormatter(logging.Formatter('%(message)s'))
        handler.setLevel(logging.DEBUG)
        self.logger.addHandler(handler)

        self.logger.debug("Ready")

    def filters_changed(self):
        self.mask_need_filtering = True
        self.filter_button.setStyleSheet("background: darkred;")
        self.save_button.setText("Filter && Save")

    def filter(self, closing=False):

        # Set cursor to BusyCursor
        napari.qt.get_app().setOverrideCursor(QCursor(Qt.BusyCursor))
        napari.qt.get_app().processEvents()

        self.cell_tracks_filtering.reset_filters()

        # No cells touching the border
        if self.filter_border_yn.isChecked():
            self.cell_tracks_filtering.filter_border(self.border_width.value())

        # All cells area within range value
        if self.filter_all_cells_area_yn.isChecked():
            self.cell_tracks_filtering.filter_all_cells_area(self.all_cells_min_area.value(), self.all_cells_max_area.value())

        # At least one cell area within range value
        if self.filter_one_cell_area_yn.isChecked():
            self.cell_tracks_filtering.filter_one_cell_area(self.one_cell_min_area.value(), self.one_cell_max_area.value())

        # Cell track length
        if self.filter_track_length_yn.isChecked():
            self.cell_tracks_filtering.filter_track_length(self.nframes.value())

        # n_missing
        if self.filter_n_missing_yn.isChecked():
            self.cell_tracks_filtering.filter_n_missing(self.nmissing.value())

        # n_divisions
        if self.filter_n_divisions_yn.isChecked():
            stable_overlap_fraction = 0
            self.cell_tracks_filtering.filter_n_divisions(self.min_ndivisions.value(), self.max_ndivisions.value(), self.nframes_stable_division.value(), stable_overlap_fraction)

        # n_fusions
        if self.filter_n_fusions_yn.isChecked():
            stable_overlap_fraction = 0
            self.cell_tracks_filtering.filter_n_fusions(self.min_nfusions.value(), self.max_nfusions.value(), self.nframes_stable_fusion.value(), stable_overlap_fraction)

        # Topology
        if self.filter_topology_yn.isChecked():
            topology_ids = [i for i, checkbox in enumerate(self.topology_yn) if checkbox.isChecked()]
            self.cell_tracks_filtering.filter_topology(topology_ids)

        if not closing:
            selected_mask = self.cell_tracks_filtering.get_mask()
            self.logger.debug("adding to viewer_images")
            self.viewer_images.layers['Selected cell mask'].data = selected_mask
            self.viewer_images.layers['Selected cell mask'].editable = False
            self.logger.debug("refreshing viewer_images")
            self.viewer_images.layers['Selected cell mask'].refresh()

        self.mask_modified = True
        self.save_button.setStyleSheet("background: darkred;")
        self.mask_need_filtering = False
        self.filter_button.setStyleSheet("")
        self.save_button.setText("Save")
        self.logger.debug("Done")
        # Restore cursor
        napari.qt.get_app().restoreOverrideCursor()

    def save(self, closing=False, relabel_mask_ids=True):
        """
        Save one mask and one graph file with all selected tracks
        """
        # Set cursor to BusyCursor
        napari.qt.get_app().setOverrideCursor(QCursor(Qt.BusyCursor))
        napari.qt.get_app().processEvents()
        self.logger.debug("Done")

        if self.mask_need_filtering:
            self.filter(closing)

        self.cell_tracks_filtering.save(self.output_path, self.output_basename, relabel_mask_ids)

        if not closing:
            self.mask_modified = False
            self.save_button.setStyleSheet("")

        # restore cursor
        napari.qt.get_app().restoreOverrideCursor()

        QMessageBox.information(self, 'Files saved', 'Mask and graph saved to\n' + os.path.join(self.output_path, self.output_basename+".ome.tif") + "\n" + os.path.join(self.output_path, self.output_basename+".graphmlz"))

    def quit(self):
        self.viewer_images.close()

    def on_viewer_images_close(self):
        if self.mask_modified:
            if self.mask_need_filtering:
                save = QMessageBox.question(self, 'Save changes',  "Filter and save changes before closing?", QMessageBox.Yes | QMessageBox.No)
            else:
                save = QMessageBox.question(self, 'Save changes', "Save changes before closing?", QMessageBox.Yes | QMessageBox.No)
            if save == QMessageBox.Yes:
                self.save(closing=True)
        else:
            if self.mask_need_filtering:
                save = QMessageBox.question(self, 'Save changes', "Filter and save changes before closing?", QMessageBox.Yes | QMessageBox.No)
                if save == QMessageBox.Yes:
                    self.save(closing=True)
        # Remove all handlers for this module
        while len(self.logger.handlers) > 0:
            self.logger.removeHandler(self.logger.handlers[0])
        self.logger.debug("Done")

    def __del__(self):
        # Remove all handlers for this module
        while len(self.logger.handlers) > 0:
            self.logger.removeHandler(self.logger.handlers[0])
        self.logger.debug("Done")


def main(image_path, mask_path, graph_path, output_path, output_basename, filters, display_results=True, graph_topologies=None):
    """
    Load mask (`mask_path`), cell tracking graph (`graph_path`).
    Save the selected mask and cell tracking graph into `output_path` directory.

    Parameters
    ----------
    image_path: str
        input image path (tif, ome-tif or nd2 image with axes T,Y,X) to be shown in napari.
        Use empty string to ignore.
    mask_path: str
        segmentation mask (uint16 tif or ome-tif image with axes T,Y,X).
    graph_path: str
        cell tracking graph (graphmlz format).
    output_path: str
        output directory.
    output_basename: str
        output basename. Output file will be saved as `output_path`/`output_basename`.ome.tif, `output_path`/`output_basename`.graphmlz and `output_path`/`output_basename`.log.
    filters: list of tuple
        list of filters to apply. Each filter is defined by a tuple with filter name (str) as first element, following by filter parameters.
        Possible filters are (see CellTrackingFiltering for more information):
            ('filter_border',border_width)
            ('filter_all_cells_area', min_area, max_area)
            ('filter_one_cell_area', min_area, max_area)
            ('filter_track_length', track_length)
            ('filter_n_missing', n)
            ('filter_n_divisions', min_n, max_n, nframes_stable, stable_overlap_fraction)
            ('filter_n_fusions', min_n, max_n, nframes_stable, stable_overlap_fraction)
            ('filter_topology', selected_topologies)
    display_results: bool
        display image, mask and results in napari.
    graph_topologies: list of igraph.Graph
        list of graph topologies. If None, create from graph. (only used when display_results == True)
    """

    ###########################
    # Setup logging
    ###########################
    logger = logging.getLogger(__name__)
    logger.info("GRAPH FILTERING MODULE")
    if not os.path.isdir(output_path):
        logger.debug("creating: %s", output_path)
        os.makedirs(output_path)

    # Log to file
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
    buffered_handler.setFormatter(logging.Formatter('%(asctime)s (VLabApp - graph filtering module) [%(levelname)s] %(message)s'))
    buffered_handler.setLevel(logging.INFO)
    logger.addHandler(buffered_handler)

    logger.info("System info:")
    logger.info("- platform: %s", platform())
    logger.info("- python version: %s", python_version())
    logger.info("- VLabApp version: %s", vlabapp_version)
    logger.info("- numpy version: %s", np.__version__)
    logger.info("- igraph version: %s", ig.__version__)
    if display_results:
        logger.info("- napari version: %s", napari.__version__)

    if image_path:
        logger.info("Input image path: %s", image_path)
    logger.info("Input mask path: %s", mask_path)
    logger.info("Input graph path: %s", graph_path)
    logger.info("Output path: %s", output_path)
    logger.info("Output basename: %s", output_basename)

    ###########################
    # Load image, mask and graph
    ###########################

    # Load image
    if image_path != '':
        logger.debug("loading %s", image_path)
        try:
            image = gf.Image(image_path)
            image.imread()
        except:
            logger.exception('Error loading image %s', image_path)
            # stop using logfile
            logger.removeHandler(logfile_handler)
            logger.removeHandler(buffered_handler)
            raise

    # Load mask
    logger.debug("loading %s", mask_path)
    try:
        mask = gf.Image(mask_path)
        mask.imread()
    except:
        logger.exception('Error loading mask %s', mask_path)
        # stop using logfile
        logger.removeHandler(logfile_handler)
        logger.removeHandler(buffered_handler)
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

    ###########################
    # filter
    ###########################

    if display_results:
        logger.debug("displaying image and mask")
        viewer_images = napari.Viewer(title=image_path)
        if image_path != '':
            viewer_images.add_image(image.get_TYXarray(), name="Image")
        layer = viewer_images.add_labels(mask.get_TYXarray(), name="Cell mask", visible=False)
        layer.editable = False
        # In the current version of napari (v0.4.17), editable is set to True whenever we change the axis value by clicking on the corresponding slider.
        # This is a quick and dirty hack to force the layer to stay non-editable.
        layer.events.editable.connect(lambda e: setattr(e.source,'editable',False))
        selected_mask_layer = viewer_images.add_labels(mask.get_TYXarray(), name="Selected cell mask")
        selected_mask_layer.editable = False
        # In the current version of napari (v0.4.17), editable is set to True whenever we change the axis value by clicking on the corresponding slider.
        # This is a quick and dirty hack to force the layer to stay non-editable.
        selected_mask_layer.events.editable.connect(lambda e: setattr(e.source,'editable',False))

        # add GraphFilteringWidget to napari
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        graph_filtering_widget = GraphFilteringWidget(mask, graph, viewer_images, image_path, output_path, output_basename, graph_topologies=graph_topologies, mask_physical_pixel_sizes=mask.physical_pixel_sizes, mask_channel_names=mask.channel_names, metadata=mask_metadata+graph_metadata)
        scroll_area.setWidget(graph_filtering_widget)
        viewer_images.window.add_dock_widget(scroll_area, area='right', name="Cell tracking")
        if len(filters) > 0:
            for filter_name, *filter_params in filters:
                if filter_name == 'filter_border':
                    graph_filtering_widget.filter_border_yn.setChecked(True)
                    graph_filtering_widget.border_width.setValue(filter_params[0])
                elif filter_name == 'filter_all_cells_area':
                    graph_filtering_widget.filter_all_cells_area_yn.setChecked(True)
                    graph_filtering_widget.all_cells_min_area.setValue(filter_params[0])
                    graph_filtering_widget.all_cells_max_area.setValue(filter_params[1])
                elif filter_name == 'filter_one_cell_area':
                    graph_filtering_widget.filter_one_cell_area_yn.setChecked(True)
                    graph_filtering_widget.one_cell_min_area.setValue(filter_params[0])
                    graph_filtering_widget.one_cell_max_area.setValue(filter_params[1])
                elif filter_name == 'filter_track_length':
                    graph_filtering_widget.filter_track_length_yn.setChecked(True)
                    graph_filtering_widget.nframes.setValue(min(mask.sizes['T'], filter_params[0]))
                elif filter_name == 'filter_n_missing':
                    graph_filtering_widget.filter_n_missing_yn.setChecked(True)
                    graph_filtering_widget.nmissing.setValue(filter_params[0])
                elif filter_name == 'filter_n_divisions':
                    graph_filtering_widget.filter_n_divisions_yn.setChecked(True)
                    graph_filtering_widget.min_ndivisions.setValue(filter_params[0])
                    graph_filtering_widget.max_ndivisions.setValue(filter_params[1])
                    graph_filtering_widget.nframes_stable_division.setValue(filter_params[2])
                elif filter_name == 'filter_n_fusions':
                    graph_filtering_widget.filter_n_fusions_yn.setChecked(True)
                    graph_filtering_widget.min_nfusions.setValue(filter_params[0])
                    graph_filtering_widget.max_nfusions.setValue(filter_params[1])
                    graph_filtering_widget.nframes_stable_fusion.setValue(filter_params[2])
                elif filter_name == 'filter_topology':
                    graph_filtering_widget.filter_topology_yn.setChecked(True)
                    for i in filter_params[0]:
                        graph_filtering_widget.topology_yn[i].setChecked(True)
                else:
                    logger.error("ignoring unknown filter %s.", filter_name)
            graph_filtering_widget.filter()
    else:
        cell_tracks_filtering = CellTracksFiltering(mask.get_TYXarray(), graph, graph_topologies=graph_topologies, mask_physical_pixel_sizes=mask.physical_pixel_sizes, mask_channel_names=mask.channel_names, metadata=mask_metadata+graph_metadata)
        if len(filters) > 0:
            for filter_name, *filter_params in filters:
                if filter_name == 'filter_border':
                    cell_tracks_filtering.filter_border(filter_params[0])
                elif filter_name == 'filter_all_cells_area':
                    cell_tracks_filtering.filter_all_cells_area(filter_params[0], filter_params[1])
                elif filter_name == 'filter_one_cell_area':
                    cell_tracks_filtering.filter_one_cell_area(filter_params[0], filter_params[1])
                elif filter_name == 'filter_track_length':
                    cell_tracks_filtering.filter_track_length(min(mask.sizes['T'], filter_params[0]))
                elif filter_name == 'filter_n_missing':
                    cell_tracks_filtering.filter_n_missing(filter_params[0])
                elif filter_name == 'filter_n_divisions':
                    cell_tracks_filtering.filter_n_divisions(filter_params[0], filter_params[1], filter_params[2], filter_params[3])
                elif filter_name == 'filter_n_fusions':
                    cell_tracks_filtering.filter_n_fusions(filter_params[0], filter_params[1], filter_params[2], filter_params[3])
                elif filter_name == 'filter_topology':
                    cell_tracks_filtering.filter_topology(filter_params[0])
                else:
                    logger.error("ignoring unknown filter %s.", filter_name)

        cell_tracks_filtering.save(output_path, output_basename, relabel_mask_ids=True)
        # stop using logfile
        logger.removeHandler(logfile_handler)
        logger.removeHandler(buffered_handler)
