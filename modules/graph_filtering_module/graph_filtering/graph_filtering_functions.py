import os
import logging
from platform import python_version, platform
import numpy as np
import napari
import tifffile
import igraph as ig
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QGridLayout, QWidget, QPushButton, QLabel, QSpinBox, QScrollArea, QGroupBox, QCheckBox, QMessageBox, QSizePolicy
from PyQt5.QtCore import Qt, QPoint, QPointF
from PyQt5.QtGui import QCursor, QPixmap, QPainter, QPen, QIcon, QPolygonF
from general import general_functions as gf


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

# inspired by https://stackoverflow.com/a/44692178
class IgnoreDuplicate(logging.Filter):
    """
    logging filter to ignore duplicate messages.

    Examples
    --------
    logger=logging.getLogger()
    filter=IgnoreDuplicate()
    logger.addFilter(filter)
    logger.info("message1")
    logger.info("message1")
    logger.removeFilter(filter)

    filter=IgnoreDuplicate("message2")
    logger.addFilter(filter)
    logger.info("message1")
    logger.info("message1")
    logger.info("message2")
    logger.info("message2")
    logger.removeFilter(filter)

    """

    def __init__(self, message=None):
        logging.Filter.__init__(self)
        self.last = None
        self.message = message

    def filter(self, record):
        current = (record.module, record.levelno, record.msg)
        if self.message is None or self.message == record.msg:
            # add other fields if you need more granular comparison, depends on your app
            if self.last is None or current != self.last:
                self.last = current
                return True
            return False
        self.last = current
        return True


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
    #Note: for each pair of vertices (v1,v2), _is_multiple returns all edges connecting v1 to v2 except one. We want all edges connecting v1 to v2.
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
    g_xmin = min([p[0] for p in layout.coords])
    g_xmax = max([p[0] for p in layout.coords])
    g_ymin = min([p[1] for p in layout.coords])
    g_ymax = max([p[1] for p in layout.coords])
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


class GraphFilteringWidget(QWidget):
    """
    A widget to use inside napari
    """

    def __init__(self, mask: gf.Image, graph, viewer_images, image_path, output_path):
        super().__init__()
        self.logger = logging.getLogger(__name__)

        self.mask = mask.get_TZXarray()
        ## WARNING: graph should not be modified
        self.graph = graph
        self.viewer_images = viewer_images
        self.image_path = image_path
        self.output_path = output_path

        # True if filter settings have been changed but filtering has not been applied:
        self.mask_need_filtering = False
        # True if mask have been modified since last save (or not yet saved):
        self.mask_modified = True

        # Graph topologies to search for (existing topologies):
        components = self.graph.connected_components(mode='weak')
        self.graph_topologies = []
        graph_topologies_sortkey = []
        # Ignore topologies with more than max_fusion_divisions fusions or divisions
        max_fusion_divisions = 4
        # Ignore topologies with more than max_others events of type: cells dividing in more than 2 or more than 2 cells merging
        max_others = 0
        min_vertices = 2
        for cmp in components:
            g = simplify_graph(self.graph.subgraph(cmp))
            if not any([g.isomorphic(g2) for g2 in self.graph_topologies]):
                nothers = len(g.vs.select(lambda v: v.indegree() > 2 or v.outdegree() > 2))
                nfusions = len(g.vs.select(_indegree=2))
                ndivisions = len(g.vs.select(_outdegree=2))
                #nvertices, ignoring intermediate nodes with indegree == outdegree == 1
                nvertices = len(g.vs.select(lambda v: not ( v.indegree() == 1 and v.outdegree() == 1)))
                if nfusions+ndivisions <= max_fusion_divisions and nothers <= max_others and nvertices >= min_vertices:
                    self.graph_topologies.append(g)
                    graph_topologies_sortkey.append((nfusions+ndivisions, nfusions, ndivisions, nothers, nvertices))

        # Order by sortkey (using lexicographical order)
        idx = np.lexsort(np.array(graph_topologies_sortkey).T)
        self.graph_topologies = np.array(self.graph_topologies)[idx].tolist()
        del graph_topologies_sortkey

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

        # self.cell_tracks_topology[n]=[i1,i2,...] => self.cell_track[n] is isomorphic to self.graph_topologies[i1] and  self.graph_topologies[i2] and ...
        self.cell_tracks_topology = None

        self.evaluate_cell_tracks_properties(first_run=True)
        self.selected_cell_tracks = self.cell_tracks

        layout = QVBoxLayout()

        # No cells touching the border
        self.filter_border = QGroupBox("Border")
        self.filter_border.setCheckable(True)
        self.filter_border.setChecked(False)
        self.filter_border.toggled.connect(self.filters_changed)
        self.filter_border.setToolTip('Keep only cell tracks with no cell touching the border.')
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
        self.filter_border.setLayout(layout2)
        layout.addWidget(self.filter_border)

        # All cells area within range value
        self.filter_all_cells_area_range = QGroupBox("Cell area (all cells)")
        self.filter_all_cells_area_range.setCheckable(True)
        self.filter_all_cells_area_range.setChecked(False)
        self.filter_all_cells_area_range.toggled.connect(self.filters_changed)
        layout2 = QGridLayout()
        help_label = QLabel("Keep only cell tracks with all cell area within [min,max] range.")
        help_label.setWordWrap(True)
        help_label.setMinimumWidth(10)
        layout2.addWidget(help_label, 0, 0, 1, 2)
        self.all_cells_min_area = QSpinBox()
        self.all_cells_min_area.setMinimum(0)
        self.all_cells_min_area.setMaximum( max([x['max_area'] for x in self.cell_tracks]))
        self.all_cells_min_area.setValue(min([x['min_area'] for x in self.cell_tracks]))
        self.all_cells_min_area.valueChanged.connect(self.filters_changed)
        layout2.addWidget(QLabel("Min area (pixel)"), 1, 0)
        layout2.addWidget(self.all_cells_min_area, 1, 1)
        self.all_cells_max_area = QSpinBox()
        self.all_cells_max_area.setMinimum(0)
        self.all_cells_max_area.setMaximum( max([x['max_area'] for x in self.cell_tracks]))
        self.all_cells_max_area.setValue(max([x['max_area'] for x in self.cell_tracks]))
        self.all_cells_max_area.valueChanged.connect(self.filters_changed)
        layout2.addWidget(QLabel("Max area (pixel)"), 2, 0)
        layout2.addWidget(self.all_cells_max_area, 2, 1)
        self.filter_all_cells_area_range.setLayout(layout2)
        layout.addWidget(self.filter_all_cells_area_range)

        # At least one cell area within range value
        self.filter_one_cell_area_range = QGroupBox("Cell area (at least one cell)")
        self.filter_one_cell_area_range.setCheckable(True)
        self.filter_one_cell_area_range.setChecked(False)
        self.filter_one_cell_area_range.toggled.connect(self.filters_changed)
        layout2 = QGridLayout()
        help_label = QLabel("Keep only cell tracks with at least one cell area within [min,max] range.")
        help_label.setWordWrap(True)
        help_label.setMinimumWidth(10)
        layout2.addWidget(help_label, 0, 0, 1, 2)
        self.one_cell_min_area = QSpinBox()
        self.one_cell_min_area.setMinimum(0)
        self.one_cell_min_area.setMaximum( max([x['max_area'] for x in self.cell_tracks]))
        self.one_cell_min_area.setValue(min([x['min_area'] for x in self.cell_tracks]))
        self.one_cell_min_area.valueChanged.connect(self.filters_changed)
        layout2.addWidget(QLabel("Min area (pixel)"), 1, 0)
        layout2.addWidget(self.one_cell_min_area, 1, 1)
        self.one_cell_max_area = QSpinBox()
        self.one_cell_max_area.setMinimum(0)
        self.one_cell_max_area.setMaximum( max([x['max_area'] for x in self.cell_tracks]))
        self.one_cell_max_area.setValue(max([x['max_area'] for x in self.cell_tracks]))
        self.one_cell_max_area.valueChanged.connect(self.filters_changed)
        layout2.addWidget(QLabel("Max area (pixel)"), 2, 0)
        layout2.addWidget(self.one_cell_max_area, 2, 1)
        self.filter_one_cell_area_range.setLayout(layout2)
        layout.addWidget(self.filter_one_cell_area_range)

        # cell track length
        self.filter_nframes = QGroupBox("Cell track length")
        self.filter_nframes.setCheckable(True)
        self.filter_nframes.setChecked(False)
        self.filter_nframes.toggled.connect(self.filters_changed)
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
        self.filter_nframes.setLayout(layout2)
        layout2.addWidget(QLabel("Min track length (frames)"), 1, 0)
        layout2.addWidget(self.nframes, 1, 1)
        layout.addWidget(self.filter_nframes)

        # n_missing
        self.filter_nmissing = QGroupBox("Missing cells")
        self.filter_nmissing.setCheckable(True)
        self.filter_nmissing.setChecked(False)
        self.filter_nmissing.toggled.connect(self.filters_changed)
        layout2 = QGridLayout()
        help_label = QLabel("Keep only cell tracks with at most the selected number of missing cell mask.")
        help_label.setWordWrap(True)
        help_label.setMinimumWidth(10)
        layout2.addWidget(help_label, 0, 0, 1, 2)
        self.nmissing = QSpinBox()
        self.nmissing.setMinimum(0)
        self.nmissing.setMaximum(max([x['n_missing'] for x in self.cell_tracks]))
        self.nmissing.setValue(max([x['n_missing'] for x in self.cell_tracks]))
        self.nmissing.valueChanged.connect(self.filters_changed)
        self.filter_nmissing.setLayout(layout2)
        layout2.addWidget(QLabel("Max missing cells"), 1, 0)
        layout2.addWidget(self.nmissing, 1, 1)
        layout.addWidget(self.filter_nmissing)

        # n_divisions
        self.filter_ndivisions = QGroupBox("Cell divisions")
        self.filter_ndivisions.setCheckable(True)
        self.filter_ndivisions.setChecked(False)
        self.filter_ndivisions.toggled.connect(self.filters_changed)
        layout2 = QGridLayout()
        help_label = QLabel("Keep only cell tracks with a number of divisions events within [min,max] range. Each division event must be surrounded by the specified number of stable frames.")
        help_label.setWordWrap(True)
        help_label.setMinimumWidth(10)
        layout2.addWidget(help_label, 0, 0, 1, 2)
        self.min_ndivisions = QSpinBox()
        self.min_ndivisions.setMinimum(0)
        self.min_ndivisions.setMaximum( max([x['n_divisions'] for x in self.cell_tracks]))
        self.min_ndivisions.setValue(min([x['n_divisions'] for x in self.cell_tracks]))
        self.min_ndivisions.valueChanged.connect(self.filters_changed)
        layout2.addWidget(QLabel("Min divisions"), 1, 0)
        layout2.addWidget(self.min_ndivisions, 1, 1)
        self.max_ndivisions = QSpinBox()
        self.max_ndivisions.setMinimum(0)
        self.max_ndivisions.setMaximum( max([x['n_divisions'] for x in self.cell_tracks]))
        self.max_ndivisions.setValue(max([x['n_divisions'] for x in self.cell_tracks]))
        self.max_ndivisions.valueChanged.connect(self.filters_changed)
        layout2.addWidget(QLabel("Max divisions"), 2, 0)
        layout2.addWidget(self.max_ndivisions, 2, 1)
        self.stable_ndivisions = QSpinBox()
        self.stable_ndivisions.setMinimum(0)
        self.stable_ndivisions.setMaximum(mask.sizes['T'])
        self.stable_ndivisions.setValue(1)
        self.stable_ndivisions.valueChanged.connect(self.filters_changed)
        layout2.addWidget(QLabel("Min stable size (frames):"), 3, 0)
        layout2.addWidget(self.stable_ndivisions, 3, 1)
        self.filter_ndivisions.setLayout(layout2)
        layout.addWidget(self.filter_ndivisions)

        # n_fusions
        self.filter_nfusions = QGroupBox("Cell fusions")
        self.filter_nfusions.setCheckable(True)
        self.filter_nfusions.setChecked(False)
        self.filter_nfusions.toggled.connect(self.filters_changed)
        layout2 = QGridLayout()
        help_label = QLabel("Keep only cell tracks with a number of fusions events within [min,max] range. Each division event must be surrounded by the specified number of stable frames.")
        help_label.setWordWrap(True)
        help_label.setMinimumWidth(10)
        layout2.addWidget(help_label, 0, 0, 1, 2)
        self.min_nfusions = QSpinBox()
        self.min_nfusions.setMinimum(0)
        self.min_nfusions.setMaximum( max([x['n_fusions'] for x in self.cell_tracks]))
        self.min_nfusions.setValue(min([x['n_fusions'] for x in self.cell_tracks]))
        self.min_nfusions.valueChanged.connect(self.filters_changed)
        layout2.addWidget(QLabel("Min fusions"), 1, 0)
        layout2.addWidget(self.min_nfusions, 1, 1)
        self.max_nfusions = QSpinBox()
        self.max_nfusions.setMinimum(0)
        self.max_nfusions.setMaximum( max([x['n_fusions'] for x in self.cell_tracks]))
        self.max_nfusions.setValue(max([x['n_fusions'] for x in self.cell_tracks]))
        self.max_nfusions.valueChanged.connect(self.filters_changed)
        layout2.addWidget(QLabel("Max fusions"), 2, 0)
        layout2.addWidget(self.max_nfusions, 2, 1)
        self.stable_nfusions = QSpinBox()
        self.stable_nfusions.setMinimum(0)
        self.stable_nfusions.setMaximum(mask.sizes['T'])
        self.stable_nfusions.setValue(1)
        self.stable_nfusions.valueChanged.connect(self.filters_changed)
        layout2.addWidget(QLabel("Min stable size (frames):"), 3, 0)
        layout2.addWidget(self.stable_nfusions, 3, 1)
        self.filter_nfusions.setLayout(layout2)
        layout.addWidget(self.filter_nfusions)

        # Topologies
        self.filter_topology = QGroupBox("Graph topology")
        self.filter_topology.setCheckable(True)
        self.filter_topology.setChecked(False)
        self.filter_topology.toggled.connect(self.filters_changed)
        layout2 = QVBoxLayout()
        help_label = QLabel("Keep only cell tracks with selected topologies.")
        help_label.setWordWrap(True)
        help_label.setMinimumWidth(10)
        layout2.addWidget(help_label)
        self.topology_yn = []
        for i, g in enumerate(self.graph_topologies):
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
        self.filter_topology.setLayout(layout2)
        layout.addWidget(self.filter_topology)

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
        ## TODO: replace by proper napari close event once implemented (https://forum.image.sc/t/handle-of-close-event-in-napari/61039)
        self.viewer_images.window._qt_window.destroyed.connect(self.on_viewer_images_close)

        # Add a handler to output messages to napari status bar
        handler = NapariStatusBarHandler(self.viewer_images)
        handler.setFormatter(logging.Formatter('%(message)s'))
        handler.setLevel(logging.DEBUG)
        self.logger.addHandler(handler)

        self.logger.debug("Ready")

    def evaluate_cell_tracks_properties(self, first_run=False):

        if first_run:
            stable_nfusions = 0
            stable_ndivisions = 0
        else:
            stable_nfusions = self.stable_nfusions.value()
            stable_ndivisions = self.stable_ndivisions.value()
        # Number of border pixels. Must be >= 1
        border_width = 2
        # Flag edges with overlap_fraction_source<stable_overlap_fraction or overlap_fraction_target<stable_overlap_fraction as unstable
        stable_overlap_fraction = 0

        # Search for stable portions of the graph (vertices connected only to vertices in consecutive frames with same mask_id)
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
            n_missing = np.sum([ e['frame_target'] - e['frame_source'] - 1 for e in g2.es])
            # Number fusion events with stable neighborhood
            n_fusions = np.sum([1 if v.indegree() > 1 and min([v2['stable_component_size'] for v2 in v.neighbors()]) >= stable_nfusions+1 else 0 for v in g2.vs])
            # Number division events with stable neighborhood
            n_divisions = np.sum([1 if v.outdegree() > 1 and min([v2['stable_component_size'] for v2 in v.neighbors()]) >= stable_ndivisions+1 else 0 for v in g2.vs])
            min_area = np.min(g2.vs['area'])
            max_area = np.max(g2.vs['area'])
            # Topology
            g2_simplified = simplify_graph(g2)
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

    def filters_changed(self):
        self.mask_need_filtering = True
        self.filter_button.setStyleSheet("background: darkred;")
        self.save_button.setText("Filter && Save")

    def filter(self, closing=False):

        # Set cursor to BusyCursor
        napari.qt.get_app().setOverrideCursor(QCursor(Qt.BusyCursor))
        napari.qt.get_app().processEvents()

        self.evaluate_cell_tracks_properties()

        self.selected_cell_tracks = self.cell_tracks

        # No cells touching the border
        if self.filter_border.isChecked():
            # Find mask_id touching the border (assuming mask T,Y,X axes)
            self.logger.debug("finding mask ids touching border")
            border_mask_ids = np.unique(
                np.concatenate([
                    np.unique(self.mask[:, :self.border_width.value(), :]),
                    np.unique(self.mask[:, -self.border_width.value():, :]),
                    np.unique(self.mask[:, :, :self.border_width.value()]),
                    np.unique(self.mask[:, :, -self.border_width.value():])]))
            border_mask_ids = border_mask_ids[border_mask_ids > 0]
            self.logger.debug("filtering cell touching border")
            self.selected_cell_tracks = [x for x in self.selected_cell_tracks if np.isin(x['mask_ids'], border_mask_ids).any() == False]

        # All cells area within range value
        if self.filter_all_cells_area_range.isChecked():
            self.logger.debug("filtering cell area (all cells) in range: [%s,%s]", self.all_cells_min_area.value(), self.all_cells_max_area.value())
            self.selected_cell_tracks = [x for x in self.selected_cell_tracks if x['min_area'] >= self.all_cells_min_area.value() and x['max_area'] <= self.all_cells_max_area.value()]

        # At least one cell area within range value
        if self.filter_one_cell_area_range.isChecked():
            self.logger.debug("filtering cell area (at least one cell) in range: [%s,%s]", self.one_cell_min_area.value(), self.one_cell_max_area.value())
            self.selected_cell_tracks = [x for x in self.selected_cell_tracks if x['min_area'] >= self.one_cell_min_area.value() and x['max_area'] <= self.one_cell_max_area.value()]

        # Cell track length
        if self.filter_nframes.isChecked():
            self.logger.debug("filtering cell track length: %s", self.nframes.value())
            self.selected_cell_tracks = [x for x in self.selected_cell_tracks if x['frame_max']-x['frame_min']+1 >= self.nframes.value()]

        # n_missing
        if self.filter_nmissing.isChecked():
            self.logger.debug("filtering number of missing cells: %s", self.nframes.value())
            self.selected_cell_tracks = [x for x in self.selected_cell_tracks if x['n_missing'] <= self.nmissing.value()]

        # n_divisions
        if self.filter_ndivisions.isChecked():
            self.logger.debug("filtering number of divisions in range: [%s,%s]", self.min_ndivisions.value(), self.max_ndivisions.value())
            self.selected_cell_tracks = [x for x in self.selected_cell_tracks if x['n_divisions'] >= self.min_ndivisions.value() and x['n_divisions'] <= self.max_ndivisions.value()]

        # n_fusions
        if self.filter_nfusions.isChecked():
            self.logger.debug("filtering number of fusions in range: [%s,%s]", self.min_nfusions.value(), self.max_nfusions.value())
            self.selected_cell_tracks = [x for x in self.selected_cell_tracks if x['n_fusions'] >= self.min_nfusions.value() and x['n_fusions'] <= self.max_nfusions.value()]

        # Topology
        if self.filter_topology.isChecked():
            selected_topologies = [i for i, checkbox in enumerate(self.topology_yn) if checkbox.isChecked()]
            self.logger.debug("filtering topology: %s",  ", ".join([str(i) for i in selected_topologies]))
            self.selected_cell_tracks = [x for x in self.selected_cell_tracks if np.isin(x['graph_topology'], selected_topologies).any()]
        
        self.logger.debug("Selected cell tracks: %s/%s", len(self.selected_cell_tracks), len(self.cell_tracks))
        if not closing:
            self.logger.debug("selecting mask_ids")
            if len(self.selected_cell_tracks) > 0:
                selected_mask_ids = np.unique(np.concatenate(([x['mask_ids'] for x in self.selected_cell_tracks])))
            else:
                selected_mask_ids = np.array([], dtype=self.mask.dtype)
            self.logger.debug("copying mask")
            selected_mask = self.mask.copy()
            if len(self.selected_cell_tracks) != len(self.cell_tracks):
                self.logger.debug("filtering mask")
                selected_mask[np.logical_not(np.isin(selected_mask, selected_mask_ids))] = 0

            self.logger.debug("adding to viewer_images")
            self.viewer_images.layers['Selected cell mask'].data = selected_mask
            self.logger.debug("refreshing viewer_images")
            self.viewer_images.layers['Selected cell mask'].refresh()

        self.mask_modified = True
        self.save_button.setStyleSheet("background: darkred;")
        self.mask_need_filtering = False
        self.filter_button.setStyleSheet("")
        self.save_button.setText("Save")
        self.logger.debug("done")
        # Restore cursor
        napari.qt.get_app().restoreOverrideCursor()

    def save(self, closing=False, relabel_mask_ids=True):
        # Set cursor to BusyCursor
        napari.qt.get_app().setOverrideCursor(QCursor(Qt.BusyCursor))
        napari.qt.get_app().processEvents()
        self.logger.debug("Done")

        if self.mask_need_filtering:
            self.filter(closing)

        output_files = []
        for n, cell_track in enumerate(self.selected_cell_tracks):
            self.logger.debug("preparing cell track %s/%s", n,len(self.selected_cell_tracks))
            self.logger.debug("filtering graph")
            g2 = self.graph.subgraph(cell_track['graph_vertices'])
            self.logger.debug("filtering mask")
            selected_mask = self.mask.copy()
            selected_mask[np.logical_not(np.isin(selected_mask, cell_track['mask_ids']))] = 0

            # Relabel mask ids to consecutive integer starting from 1 (keeping 0 for background)
            if relabel_mask_ids:
                self.logger.debug("relabelling filtered mask and graph")
                # Create mapping table
                map_id = np.repeat(0, np.max(np.unique(selected_mask))+1).astype(selected_mask.dtype)
                map_id[0] = 0
                n_ids = 1
                for mask_id in cell_track['mask_ids']:
                    map_id[mask_id] = n_ids
                    n_ids += 1
                selected_mask = map_id[selected_mask]
                g2.vs['mask_id'] = map_id[g2.vs['mask_id']].astype(selected_mask.dtype)
                g2.es['mask_id_source'] = map_id[g2.es['mask_id_source']].astype(selected_mask.dtype)
                g2.es['mask_id_target'] = map_id[g2.es['mask_id_target']].astype(selected_mask.dtype)

            ## TODO: adapt metadata to more generic input files (other axes)
            output_file1 = os.path.join(self.output_path, os.path.splitext(os.path.basename(self.image_path))[0]+"_celltrack"+str(n)+"_mask.tif")
            self.logger.info("Cell track %s/%s: saving segmentation mask to %s", n, len(self.selected_cell_tracks), output_file1)
            tifffile.imwrite(output_file1, selected_mask, metadata={'axes': 'TYX'}, compression='zlib')
            output_files.append(output_file1)

            output_file3 = os.path.join(self.output_path, os.path.splitext(os.path.basename(self.image_path))[0]+"_celltrack"+str(n)+"_graph.graphmlz")
            self.logger.info("Cell track %s/%s: saving cell tracking graph to %s", n, len(self.selected_cell_tracks), output_file3)
            g2.write_graphmlz(output_file3)
            output_files.append(output_file3)

        if not closing:
            self.mask_modified = False
            self.save_button.setStyleSheet("")

        # Restore cursor
        napari.qt.get_app().restoreOverrideCursor()

        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setWindowTitle('Files saved')
        msg.setText('Mask and graph saved')
        msg.setDetailedText("\n".join(output_files))
        msg.exec()

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

    def __del__(self):
        # Remove all handlers for this module
        while len(self.logger.handlers) > 0:
            self.logger.removeHandler(self.logger.handlers[0])
        self.logger.info("Done")


def main(image_path, mask_path, graph_path, output_path, display_results=True):
    """
    Load mask (`mask_path`), cell tracking graph (`graph_path`).
    Save the selected mask and cell tracking graph into `output_path` directory.

    Parameters
    ----------
    image_path: str
        input image path (tif or nd2 image with axes T,Y,X) to be shown in napari.
        Use empty string to ignore.
    mask_path: str
        segmentation mask (uint16 tif image with axes T,Y,X).
    graph_path: str
        cell tracking graph (graphmlz format).
    output_path: str
        output directory.
    display_results: bool
        display image, mask and results in napari.
    """

    ###########################
    # setup logging
    ###########################
    logger = logging.getLogger(__name__)
    logger.info("GRAPH FILTERING MODULE")
    if not os.path.isdir(output_path):
        logger.debug("creating: %s", output_path)
        os.makedirs(output_path)

    # log to file
    logfile = os.path.join(output_path, os.path.splitext(os.path.basename(image_path))[0]+".log")
    logger.setLevel(logging.DEBUG)
    logger.debug("writing log output to: %s", logfile)
    logfile_handler = logging.FileHandler(logfile, mode='w')
    logfile_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    logfile_handler.setLevel(logging.INFO)
    logfile_handler.addFilter(IgnoreDuplicate("Manually editing mask"))
    logger.addHandler(logfile_handler)

    logger.info("System info:\nplatform: %s\npython version: %s\nigraph version: %s\nnumpy version: %s\nnapari version: %s", platform(), python_version(), ig.__version__, np.__version__, napari.__version__)
    logger.info("image: %s", image_path)
    logger.info("mask: %s", mask_path)
    logger.info("graph: %s", graph_path)
    logger.info("output: %s", output_path)

    ###########################
    # Load image, mask and graph
    ###########################

    # Load image
    logger.debug("loading %s", image_path)
    image = gf.Image(image_path)
    image.imread()

    # Load mask
    logger.debug("loading %s", mask_path)
    mask = gf.Image(mask_path)
    mask.imread()

    # Load graph
    logger.debug("loading %s", graph_path)
    graph = ig.Graph().Read_GraphMLz(graph_path)
    # Adjust attibute types
    graph.vs['frame'] = np.array(graph.vs['frame'], dtype='int32')
    graph.vs['mask_id'] = np.array(graph.vs['mask_id'], dtype=mask.image.dtype)
    graph.vs['area'] = np.array(graph.vs['area'], dtype='int64')
    graph.es['overlap_area'] = np.array(graph.es['overlap_area'], dtype='int64')
    graph.es['frame_source'] = np.array(graph.es['frame_source'], dtype='int32')
    graph.es['frame_target'] = np.array(graph.es['frame_target'], dtype='int32')
    graph.es['mask_id_source'] = np.array(graph.es['mask_id_source'], dtype=mask.image.dtype)
    graph.es['mask_id_target'] = np.array(graph.es['mask_id_target'], dtype=mask.image.dtype)
    # Remove useless attribute
    del graph.vs['id']

    ###########################
    # Napari
    ###########################

    if display_results:
        logger.debug("displaying image and mask")
        viewer_images = napari.Viewer(title=image_path)
        viewer_images.add_image(image.get_TZXarray(), name="Image")
        layer = viewer_images.add_labels(mask.get_TZXarray(), name="Cell mask", visible=False)
        layer.editable = False
        selected_mask_layer = viewer_images.add_labels(mask.get_TZXarray(), name="Selected cell mask")
        selected_mask_layer.editable = False

        # add GraphFilteringWidget to napari
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(GraphFilteringWidget(mask, graph, viewer_images, image_path, output_path))
        viewer_images.window.add_dock_widget(scroll_area, area='right', name="Cell tracking")
