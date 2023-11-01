import os
import logging
import re
import igraph as ig
from PyQt5.QtWidgets import QFileDialog, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QGroupBox, QRadioButton, QApplication, QLabel, QFormLayout, QSpinBox, QCheckBox, QSizePolicy
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCursor
from modules.graph_filtering_module import graph_filtering_functions as f
from general import general_functions as gf


class GraphFiltering(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout()

        self.imagetypes = ['.nd2', '.tif', '.tiff']
        self.graphtypes = ['.graphmlz']

        self.input_mask = gf.DropFileLineEdit(filetypes=self.imagetypes)
        browse_button3 = QPushButton("Browse", self)
        browse_button3.clicked.connect(self.browse_mask)
        groupbox = QGroupBox("Segmentation mask")
        layout2 = QVBoxLayout()
        layout3 = QHBoxLayout()
        layout3.addWidget(self.input_mask)
        layout3.addWidget(browse_button3, alignment=Qt.AlignCenter)
        layout2.addLayout(layout3)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        self.input_graph = gf.DropFileLineEdit(filetypes=self.graphtypes)
        browse_button4 = QPushButton("Browse", self)
        browse_button4.clicked.connect(self.browse_graph)
        groupbox = QGroupBox("Cell tracking graph")
        layout2 = QVBoxLayout()
        layout3 = QHBoxLayout()
        layout3.addWidget(self.input_graph)
        layout3.addWidget(browse_button4, alignment=Qt.AlignCenter)
        layout2.addLayout(layout3)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        self.use_input_folder = QRadioButton("Use input image folder (graph_filtering sub-folder)")
        self.use_input_folder.setChecked(True)
        self.use_custom_folder = QRadioButton("Use custom folder:")
        self.use_custom_folder.setChecked(False)
        self.output_folder = gf.DropFolderLineEdit()
        browse_button2 = QPushButton("Browse", self)
        browse_button2.clicked.connect(self.browse_output)
        self.output_folder.setEnabled(self.use_custom_folder.isChecked())
        browse_button2.setEnabled(self.use_custom_folder.isChecked())
        self.use_custom_folder.toggled.connect(self.output_folder.setEnabled)
        self.use_custom_folder.toggled.connect(browse_button2.setEnabled)
        groupbox = QGroupBox("Output folder")
        layout2 = QVBoxLayout()
        layout2.addWidget(self.use_input_folder)
        layout2.addWidget(self.use_custom_folder)
        layout3 = QHBoxLayout()
        layout3.addWidget(self.output_folder)
        layout3.addWidget(browse_button2, alignment=Qt.AlignCenter)
        layout2.addLayout(layout3)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        groupbox = QGroupBox("Options")
        layout2 = QVBoxLayout()
        # filter border cells
        self.filter_border = QGroupBox("Border")
        self.filter_border.setCheckable(True)
        self.filter_border.setChecked(False)
        self.filter_border.setToolTip('Keep only cell tracks with no cell touching the border.')
        layout3 = QFormLayout()
        help_label = QLabel("Remove cell tracks with at least one cell touching the border.")
        help_label.setWordWrap(True)
        help_label.setMinimumWidth(10)
        layout3.addRow(help_label)
        self.border_width = QSpinBox()
        self.border_width.setMinimum(1)
        self.border_width.setMaximum(100)
        self.border_width.setValue(2)
        layout3.addRow("Border width (pixel):",self.border_width)
        self.filter_border.setLayout(layout3)
        layout2.addWidget(self.filter_border)
        # filter cell area (all cells)
        self.filter_all_cells_area_range = QGroupBox("Cell area (all cells)")
        self.filter_all_cells_area_range.setCheckable(True)
        self.filter_all_cells_area_range.setChecked(False)
        layout3 = QFormLayout()
        help_label = QLabel("Keep only cell tracks with all cell area within [min,max] range.")
        help_label.setWordWrap(True)
        help_label.setMinimumWidth(10)
        layout3.addRow(help_label)
        self.all_cells_min_area = QSpinBox()
        self.all_cells_min_area.setMinimum(0)
        self.all_cells_min_area.setMaximum(100000)
        self.all_cells_min_area.setValue(0)
        layout3.addRow("Min area (pixel):", self.all_cells_min_area)
        self.all_cells_max_area = QSpinBox()
        self.all_cells_max_area.setMinimum(0)
        self.all_cells_max_area.setMaximum(100000)
        self.all_cells_max_area.setValue(100000)
        layout3.addRow("Max area (pixel):", self.all_cells_max_area)
        self.filter_all_cells_area_range.setLayout(layout3)
        layout2.addWidget(self.filter_all_cells_area_range)
        # filter cell area (at least one cell)
        self.filter_one_cell_area_range = QGroupBox("Cell area (at least one cell)")
        self.filter_one_cell_area_range.setCheckable(True)
        self.filter_one_cell_area_range.setChecked(False)
        layout3 = QFormLayout()
        help_label = QLabel("Keep only cell tracks with at least one cell area within [min,max] range.")
        help_label.setWordWrap(True)
        help_label.setMinimumWidth(10)
        layout3.addRow(help_label)
        self.one_cell_min_area = QSpinBox()
        self.one_cell_min_area.setMinimum(0)
        self.one_cell_min_area.setMaximum(100000)
        self.one_cell_min_area.setValue(0)
        layout3.addRow("Min area (pixel):", self.one_cell_min_area)
        self.one_cell_max_area = QSpinBox()
        self.one_cell_max_area.setMinimum(0)
        self.one_cell_max_area.setMaximum(100000)
        self.one_cell_max_area.setValue(100000)
        layout3.addRow("Max area (pixel):", self.one_cell_max_area)
        self.filter_one_cell_area_range.setLayout(layout3)
        layout2.addWidget(self.filter_one_cell_area_range)
        # filter cell track length
        self.filter_nframes = QGroupBox("Cell track length")
        self.filter_nframes.setCheckable(True)
        self.filter_nframes.setChecked(False)
        layout3 = QFormLayout()
        help_label = QLabel("Keep only cell tracks spanning at least the select number of frames.")
        help_label.setWordWrap(True)
        help_label.setMinimumWidth(10)
        layout3.addRow(help_label)
        self.nframes = QSpinBox()
        self.nframes.setMinimum(0)
        self.nframes.setMaximum(100000)
        self.nframes.setValue(0)
        self.filter_nframes.setLayout(layout3)
        layout3.addRow("Min track length (frames):", self.nframes)
        layout2.addWidget(self.filter_nframes)
        # filter number of missing cells
        self.filter_nmissing = QGroupBox("Missing cells")
        self.filter_nmissing.setCheckable(True)
        self.filter_nmissing.setChecked(False)
        layout3 = QFormLayout()
        help_label = QLabel("Keep only cell tracks with at most the selected number of missing cell mask.")
        help_label.setWordWrap(True)
        help_label.setMinimumWidth(10)
        layout3.addRow(help_label)
        self.nmissing = QSpinBox()
        self.nmissing.setMinimum(0)
        self.nmissing.setMaximum(100000)
        self.nmissing.setValue(100000)
        self.filter_nmissing.setLayout(layout3)
        layout3.addRow("Max missing cells:", self.nmissing)
        layout2.addWidget(self.filter_nmissing)
        # filter n_divisions
        self.filter_ndivisions = QGroupBox("Cell divisions")
        self.filter_ndivisions.setCheckable(True)
        self.filter_ndivisions.setChecked(False)
        layout3 = QFormLayout()
        help_label = QLabel("Keep only cell tracks with a number of divisions events within [min,max] range. Each division event must be surrounded by the specified number of stable frames.")
        help_label.setWordWrap(True)
        help_label.setMinimumWidth(10)
        layout3.addRow(help_label)
        self.min_ndivisions = QSpinBox()
        self.min_ndivisions.setMinimum(0)
        self.min_ndivisions.setMaximum(100000)
        self.min_ndivisions.setValue(0)
        layout3.addRow("Min divisions:", self.min_ndivisions)
        self.max_ndivisions = QSpinBox()
        self.max_ndivisions.setMinimum(0)
        self.max_ndivisions.setMaximum(100000)
        self.max_ndivisions.setValue(100000)
        layout3.addRow("Max divisions:", self.max_ndivisions)
        self.stable_ndivisions = QSpinBox()
        self.stable_ndivisions.setMinimum(0)
        self.stable_ndivisions.setMaximum(100000)
        self.stable_ndivisions.setValue(1)
        layout3.addRow("Min stable size (frames):", self.stable_ndivisions)
        self.filter_ndivisions.setLayout(layout3)
        layout2.addWidget(self.filter_ndivisions)
        # filter n_fusions
        self.filter_nfusions = QGroupBox("Cell fusions")
        self.filter_nfusions.setCheckable(True)
        self.filter_nfusions.setChecked(False)
        layout3 = QFormLayout()
        help_label = QLabel("Keep only cell tracks with a number of fusions events within [min,max] range. Each division event must be surrounded by the specified number of stable frames.")
        help_label.setWordWrap(True)
        help_label.setMinimumWidth(10)
        layout3.addRow(help_label)
        self.min_nfusions = QSpinBox()
        self.min_nfusions.setMinimum(0)
        self.min_nfusions.setMaximum(100000)
        self.min_nfusions.setValue(0)
        layout3.addRow("Min fusions:", self.min_nfusions)
        self.max_nfusions = QSpinBox()
        self.max_nfusions.setMinimum(0)
        self.max_nfusions.setMaximum(100000)
        self.max_nfusions.setValue(100000)
        layout3.addRow("Max fusions:", self.max_nfusions)
        self.stable_nfusions = QSpinBox()
        self.stable_nfusions.setMinimum(0)
        self.stable_nfusions.setMaximum(100000)
        self.stable_nfusions.setValue(1)
        layout3.addRow("Min stable size (frames):", self.stable_nfusions)
        self.filter_nfusions.setLayout(layout3)
        layout2.addWidget(self.filter_nfusions)
        # filter topologies
        self.graph_topologies = []
        # 0 division, 0 fusion
        self.graph_topologies.append(
            f.simplify_graph(ig.Graph(directed=True,
                                    edges=[[0, 1]])))
        # 1 division, 0 fusion
        self.graph_topologies.append(
            f.simplify_graph(ig.Graph(directed=True,
                                    edges=[[0, 1],
                                           [1, 2],
                                           [1, 3]])))
        # 0 division, 1 fusion
        self.graph_topologies.append(
            f.simplify_graph(ig.Graph(directed=True,
                                    edges=[[0, 2],
                                           [1, 2],
                                           [2, 3]])))
        # 1 division, 1 fusion
        self.graph_topologies.append(
            f.simplify_graph(ig.Graph(directed=True,
                                    edges=[[0, 1],
                                           [1, 2],
                                           [1, 2],
                                           [2, 3]])))
        # 1 division, 1 fusion
        self.graph_topologies.append(
            f.simplify_graph(ig.Graph(directed=True,
                                    edges=[[0, 2],
                                           [1, 2],
                                           [2, 3],
                                           [3, 4],
                                           [3, 5]])))
        # 1 division, 1 fusion
        self.graph_topologies.append(
            f.simplify_graph(ig.Graph(directed=True,
                                    edges=[[0, 2],
                                           [1, 3],
                                           [2, 4],
                                           [2, 3],
                                           [3, 5]])))
        # 2 divisions
        self.graph_topologies.append(
            f.simplify_graph(ig.Graph(directed=True,
                                    edges=[[0, 1],
                                           [1, 2],
                                           [1, 3],
                                           [3, 4],
                                           [3, 5]])))
        # 2 fusions
        self.graph_topologies.append(
            f.simplify_graph(ig.Graph(directed=True,
                                    edges=[[0, 4],
                                           [1, 3],
                                           [2, 3],
                                           [3, 4],
                                           [4, 5]])))
        self.filter_topology = QGroupBox("Graph topology")
        self.filter_topology.setCheckable(True)
        self.filter_topology.setChecked(False)
        layout3 = QVBoxLayout()
        help_label = QLabel("Keep only cell tracks with selected topologies.")
        help_label.setWordWrap(True)
        help_label.setMinimumWidth(10)
        layout3.addWidget(help_label)
        self.topology_yn = []
        for g in self.graph_topologies:
            layout4 = QHBoxLayout()
            self.topology_yn.append(QCheckBox())
            self.topology_yn[-1].setChecked(False)
            layout4.addWidget(self.topology_yn[-1])
            label = QLabel()
            label.setPixmap(f.get_graph_qpixmap(g, 150, 50))
            label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            # label.setScaledContents(True)
            layout4.addWidget(label)
            layout3.addLayout(layout4)
        self.filter_topology.setLayout(layout3)
        layout2.addWidget(self.filter_topology)

        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)


        self.display_results = QGroupBox("Show (and edit) results in napari")
        self.display_results.setCheckable(True)
        self.display_results.setChecked(True)
        self.input_image = gf.DropFileLineEdit(filetypes=self.imagetypes)
        browse_button1 = QPushButton("Browse", self)
        browse_button1.clicked.connect(self.browse_image)
        layout2 = QVBoxLayout()
        layout2.addWidget(QLabel("Input image:"))
        layout3 = QHBoxLayout()
        layout3.addWidget(self.input_image)
        layout3.addWidget(browse_button1, alignment=Qt.AlignCenter)
        layout2.addLayout(layout3)
        self.display_results.setLayout(layout2)
        layout.addWidget(self.display_results)

        self.submit_button = QPushButton("Submit", self)
        self.submit_button.clicked.connect(self.process_input)
        layout.addWidget(self.submit_button, alignment=Qt.AlignCenter)

        self.setLayout(layout)

        self.logger = logging.getLogger(__name__)

    def browse_image(self):
        file_path, _ = QFileDialog.getOpenFileName(self, 'Select Files', filter='Images ('+' '.join(['*'+x for x in self.imagetypes])+')')
        self.input_image.setText(file_path)

    def browse_mask(self):
        file_path, _ = QFileDialog.getOpenFileName(self, 'Select Files', filter='Images ('+' '.join(['*'+x for x in self.imagetypes])+')')
        self.input_mask.setText(file_path)

    def browse_graph(self):
        file_path, _ = QFileDialog.getOpenFileName(self, 'Select Files', filter='Cell tracking graphs ('+' '.join(['*'+x for x in self.graphtypes])+')')
        self.input_graph.setText(file_path)

    def browse_output(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        self.output_folder.setText(folder_path)

    def process_input(self):
        image_path = self.input_image.text()
        mask_path = self.input_mask.text()
        graph_path = self.input_graph.text()

        filters = []
        graph_topologies = None
        if self.filter_border.isChecked():
            filters.append(('border',self.border_width.value()))
        if self.filter_all_cells_area_range.isChecked():
            filters.append(('cell_area_all', self.all_cells_min_area.value(), self.all_cells_max_area.value()))
        if self.filter_one_cell_area_range.isChecked():
            filters.append(('cell_area_one', self.one_cell_min_area.value(), self.one_cell_max_area.value()))
        if self.filter_nframes.isChecked():
            filters.append(('track_length', self.nframes.value()))
        if self.filter_nmissing.isChecked():
            filters.append(('n_missing', self.nmissing.value()))
        if self.filter_ndivisions.isChecked():
            stable_overlap_fraction=0
            filters.append(('n_divisions', self.min_ndivisions.value(), self.max_ndivisions.value(), self.stable_ndivisions.value(), stable_overlap_fraction))
        if self.filter_nfusions.isChecked():
            stable_overlap_fraction=0
            filters.append(('n_fusions', self.min_nfusions.value(), self.max_nfusions.value(), self.stable_nfusions.value(), stable_overlap_fraction))
        if self.filter_topology.isChecked():
            graph_topologies = self.graph_topologies
            topology_ids=[i for i, checkbox in enumerate(self.topology_yn) if checkbox.isChecked()]
            filters.append(('topology', topology_ids))

        # check input
        if image_path != '' and not os.path.isfile(image_path):
            self.logger.error('Image: not a valid file')
            self.input_image.setFocus()
            return
        if mask_path == '':
            self.logger.error('Segmentation mask missing')
            self.input_mask.setFocus()
            return
        if not os.path.isfile(mask_path):
            self.logger.error('Segmentation mask: not a valid file')
            self.input_mask.setFocus()
            return
        if graph_path == '':
            self.logger.error('Cell tracking graph missing')
            self.input_graph.setFocus()
            return
        if not os.path.isfile(graph_path):
            self.logger.error('Cell tracking graph: not a valid file')
            self.input_graph.setFocus()
            return

        if self.output_folder.text() == '' and not self.use_input_folder.isChecked():
            self.logger.error('Output folder missing')
            self.output_folder.setFocus()
            return

        if self.use_input_folder.isChecked():
            output_path = os.path.join(os.path.dirname(mask_path), 'graph_filtering')
        else:
            output_path = self.output_folder.text()
        self.logger.info("Graph filtering (image %s, mask %s, graph %s)", image_path, mask_path, graph_path)

        QApplication.setOverrideCursor(QCursor(Qt.BusyCursor))
        QApplication.processEvents()
        mask_basename, mask_extension=os.path.splitext(os.path.basename(mask_path))
        output_basename=re.sub("_masks{0,1}$","",mask_basename)
        try:
            f.main(image_path, mask_path, graph_path, output_path, output_basename, filters, display_results=self.display_results.isChecked(),graph_topologies=graph_topologies)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            self.logger.error(str(e))
            raise e
        QApplication.restoreOverrideCursor()

        self.logger.info("Done")
