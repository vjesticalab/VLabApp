import os
import logging
import re
import igraph as ig
from PyQt5.QtWidgets import QFileDialog, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QGroupBox, QRadioButton, QApplication, QLabel, QFormLayout, QSpinBox, QCheckBox, QSizePolicy, QLineEdit
from PyQt5.QtCore import Qt, QRegExp
from PyQt5.QtGui import QCursor, QRegExpValidator
from modules.graph_filtering_module import graph_filtering_functions as f
from general import general_functions as gf


class GraphFiltering(QWidget):
    def __init__(self):
        super().__init__()

        self.output_suffix = '_vGF'
        self.celltracking_suffix = '_vTG'

        layout = QVBoxLayout()

        self.imagetypes = ['.nd2', '.tif', '.tiff', '.ome.tif', '.ome.tiff']

        self.mask_graph_table = gf.FileTableWidget2(header_1="Mask", header_2="Graph", filenames_suffix_1='.ome.tif', filenames_suffix_2='.graphmlz', filenames_filter=self.celltracking_suffix)
        self.mask_graph_table.file_table_changed.connect(self.mask_graph_table_changed)
        groupbox = QGroupBox('Segmentation masks and cell tracking graphs to process')
        layout2 = QVBoxLayout()
        layout2.addWidget(self.mask_graph_table)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        self.use_input_folder = QRadioButton("Use input mask and graph folder")
        self.use_input_folder.setChecked(True)
        self.use_input_folder.toggled.connect(self.update_output_filename_label)
        self.use_custom_folder = QRadioButton("Use custom folder")
        self.use_custom_folder.setChecked(False)
        self.use_custom_folder.toggled.connect(self.update_output_filename_label)
        self.output_folder = gf.DropFolderLineEdit()
        self.output_folder.textChanged.connect(self.update_output_filename_label)
        browse_button2 = QPushButton("Browse", self)
        browse_button2.clicked.connect(self.browse_output)
        self.output_folder.setVisible(self.use_custom_folder.isChecked())
        browse_button2.setVisible(self.use_custom_folder.isChecked())
        self.use_custom_folder.toggled.connect(self.output_folder.setVisible)
        self.use_custom_folder.toggled.connect(browse_button2.setVisible)
        self.output_user_suffix = QLineEdit()
        self.output_user_suffix.setToolTip('Allowed characters: A-Z, a-z, 0-9 and -')
        self.output_user_suffix.setValidator(QRegExpValidator(QRegExp('[A-Za-z0-9-]*')))
        self.output_user_suffix.textChanged.connect(self.update_output_filename_label)
        self.output_filename_label1 = QLineEdit()
        self.output_filename_label1.setFrame(False)
        self.output_filename_label1.setEnabled(False)
        self.output_filename_label1.textChanged.connect(self.output_filename_label1.setToolTip)
        self.output_filename_label2 = QLineEdit()
        self.output_filename_label2.setFrame(False)
        self.output_filename_label2.setEnabled(False)
        self.output_filename_label2.textChanged.connect(self.output_filename_label2.setToolTip)
        groupbox = QGroupBox("Output")
        layout2 = QVBoxLayout()
        layout2.addWidget(QLabel("Folder:"))
        layout2.addWidget(self.use_input_folder)
        layout2.addWidget(self.use_custom_folder)
        layout3 = QHBoxLayout()
        layout3.addWidget(self.output_folder)
        layout3.addWidget(browse_button2, alignment=Qt.AlignCenter)
        layout2.addLayout(layout3)
        layout3 = QFormLayout()
        layout3.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        layout4 = QHBoxLayout()
        layout4.setSpacing(0)
        suffix = QLineEdit(self.output_suffix)
        suffix.setDisabled(True)
        suffix.setFixedWidth(suffix.fontMetrics().width(suffix.text()+"  "))
        suffix.setAlignment(Qt.AlignRight)
        layout4.addWidget(suffix)
        layout4.addWidget(self.output_user_suffix)
        layout3.addRow("Suffix:", layout4)
        layout4 = QVBoxLayout()
        layout4.setSpacing(0)
        layout4.addWidget(self.output_filename_label1)
        layout4.addWidget(self.output_filename_label2)
        layout3.addRow("Filename:", layout4)
        layout2.addLayout(layout3)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        groupbox = QGroupBox("Options")
        layout2 = QVBoxLayout()
        # filter border cells
        self.filter_border_yn = QGroupBox("Border")
        self.filter_border_yn.setCheckable(True)
        self.filter_border_yn.setChecked(False)
        self.filter_border_yn.setToolTip('Keep only cell tracks with no cell touching the border.')
        layout3 = QFormLayout()
        help_label = QLabel("Remove cell tracks with at least one cell touching the border.")
        help_label.setWordWrap(True)
        help_label.setMinimumWidth(10)
        layout3.addRow(help_label)
        self.border_width = QSpinBox()
        self.border_width.setMinimum(1)
        self.border_width.setMaximum(100)
        self.border_width.setValue(2)
        layout3.addRow("Border width (pixel):", self.border_width)
        self.filter_border_yn.setLayout(layout3)
        layout2.addWidget(self.filter_border_yn)
        # filter cell area (all cells)
        self.filter_all_cells_area_yn = QGroupBox("Cell area (all cells)")
        self.filter_all_cells_area_yn.setCheckable(True)
        self.filter_all_cells_area_yn.setChecked(False)
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
        self.filter_all_cells_area_yn.setLayout(layout3)
        layout2.addWidget(self.filter_all_cells_area_yn)
        # filter cell area (at least one cell)
        self.filter_one_cell_area_yn = QGroupBox("Cell area (at least one cell)")
        self.filter_one_cell_area_yn.setCheckable(True)
        self.filter_one_cell_area_yn.setChecked(False)
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
        self.filter_one_cell_area_yn.setLayout(layout3)
        layout2.addWidget(self.filter_one_cell_area_yn)
        # filter cell track length
        self.filter_track_length_yn = QGroupBox("Cell track length")
        self.filter_track_length_yn.setCheckable(True)
        self.filter_track_length_yn.setChecked(False)
        layout3 = QFormLayout()
        help_label = QLabel("Keep only cell tracks spanning at least the select number of frames.")
        help_label.setWordWrap(True)
        help_label.setMinimumWidth(10)
        layout3.addRow(help_label)
        self.nframes = QSpinBox()
        self.nframes.setMinimum(0)
        self.nframes.setMaximum(100000)
        self.nframes.setValue(0)
        self.filter_track_length_yn.setLayout(layout3)
        layout3.addRow("Min track length (frames):", self.nframes)
        layout2.addWidget(self.filter_track_length_yn)
        # filter number of missing cells
        self.filter_n_missing_yn = QGroupBox("Missing cells")
        self.filter_n_missing_yn.setCheckable(True)
        self.filter_n_missing_yn.setChecked(False)
        layout3 = QFormLayout()
        help_label = QLabel("Keep only cell tracks with at most the selected number of missing cell mask.")
        help_label.setWordWrap(True)
        help_label.setMinimumWidth(10)
        layout3.addRow(help_label)
        self.nmissing = QSpinBox()
        self.nmissing.setMinimum(0)
        self.nmissing.setMaximum(100000)
        self.nmissing.setValue(100000)
        self.filter_n_missing_yn.setLayout(layout3)
        layout3.addRow("Max missing cells:", self.nmissing)
        layout2.addWidget(self.filter_n_missing_yn)
        # filter n_divisions
        self.filter_n_divisions_yn = QGroupBox("Cell divisions")
        self.filter_n_divisions_yn.setCheckable(True)
        self.filter_n_divisions_yn.setChecked(False)
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
        self.nframes_stable_division = QSpinBox()
        self.nframes_stable_division.setMinimum(0)
        self.nframes_stable_division.setMaximum(100000)
        self.nframes_stable_division.setValue(1)
        layout3.addRow("Min stable size (frames):", self.nframes_stable_division)
        self.filter_n_divisions_yn.setLayout(layout3)
        layout2.addWidget(self.filter_n_divisions_yn)
        # filter n_fusions
        self.filter_n_fusions_yn = QGroupBox("Cell fusions")
        self.filter_n_fusions_yn.setCheckable(True)
        self.filter_n_fusions_yn.setChecked(False)
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
        self.nframes_stable_fusion = QSpinBox()
        self.nframes_stable_fusion.setMinimum(0)
        self.nframes_stable_fusion.setMaximum(100000)
        self.nframes_stable_fusion.setValue(1)
        layout3.addRow("Min stable size (frames):", self.nframes_stable_fusion)
        self.filter_n_fusions_yn.setLayout(layout3)
        layout2.addWidget(self.filter_n_fusions_yn)
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
        self.filter_topology_yn = QGroupBox("Graph topology")
        self.filter_topology_yn.setCheckable(True)
        self.filter_topology_yn.setChecked(False)
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
        self.filter_topology_yn.setLayout(layout3)
        layout2.addWidget(self.filter_topology_yn)

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
        self.submit_button.clicked.connect(self.submit)
        layout.addWidget(self.submit_button, alignment=Qt.AlignCenter)

        self.setLayout(layout)

        self.logger = logging.getLogger(__name__)

        self.update_output_filename_label()

    def mask_graph_table_changed(self):
        if self.mask_graph_table.rowCount() > 1:
            self.display_results.setChecked(False)
        self.display_results.setEnabled(self.mask_graph_table.rowCount() <= 1)

    def browse_image(self):
        file_path, _ = QFileDialog.getOpenFileName(self, 'Select Files', filter='Images ('+' '.join(['*'+x for x in self.imagetypes])+')')
        self.input_image.setText(file_path)

    def browse_output(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        self.output_folder.setText(folder_path)

    def update_output_filename_label(self):
        if self.use_input_folder.isChecked():
            output_path = "<input folder>"
        else:
            output_path = self.output_folder.text().rstrip("/")

        self.output_filename_label1.setText(os.path.join(output_path,"<input basename>" + self.output_suffix + self.output_user_suffix.text() + ".ome.tif"))
        self.output_filename_label2.setText(os.path.join(output_path,"<input basename>" + self.output_suffix + self.output_user_suffix.text() + ".graphmlz"))

    def submit(self):
        if self.input_image.isEnabled():
            image_path = self.input_image.text()
        else:
            image_path = ""

        mask_graph_paths = self.mask_graph_table.get_file_table()
        mask_paths = [mask_path for mask_path, graph_path in mask_graph_paths]
        graph_paths = [graph_path for mask_path, graph_path in mask_graph_paths]
        user_suffix = self.output_user_suffix.text()
        output_basenames = [gf.splitext(os.path.basename(mask_path))[0] + self.output_suffix + user_suffix for mask_path in mask_paths]
        if self.use_input_folder.isChecked():
            output_paths = [os.path.dirname(mask_path) for mask_path in mask_paths]
        else:
            output_paths = [self.output_folder.text() for path in mask_paths]

        filters = []
        graph_topologies = None
        if self.filter_border_yn.isChecked():
            filters.append(('filter_border', self.border_width.value()))
        if self.filter_all_cells_area_yn.isChecked():
            filters.append(('filter_all_cells_area', self.all_cells_min_area.value(), self.all_cells_max_area.value()))
        if self.filter_one_cell_area_yn.isChecked():
            filters.append(('filter_one_cell_area', self.one_cell_min_area.value(), self.one_cell_max_area.value()))
        if self.filter_track_length_yn.isChecked():
            filters.append(('filter_track_length', self.nframes.value()))
        if self.filter_n_missing_yn.isChecked():
            filters.append(('filter_n_missing', self.nmissing.value()))
        if self.filter_n_divisions_yn.isChecked():
            stable_overlap_fraction = 0
            filters.append(('filter_n_divisions', self.min_ndivisions.value(), self.max_ndivisions.value(), self.nframes_stable_division.value(), stable_overlap_fraction))
        if self.filter_n_fusions_yn.isChecked():
            stable_overlap_fraction = 0
            filters.append(('filter_n_fusions', self.min_nfusions.value(), self.max_nfusions.value(), self.nframes_stable_fusion.value(), stable_overlap_fraction))
        if self.filter_topology_yn.isChecked():
            graph_topologies = self.graph_topologies
            topology_ids = [i for i, checkbox in enumerate(self.topology_yn) if checkbox.isChecked()]
            filters.append(('filter_topology', topology_ids))

        # check input
        if image_path != '' and not os.path.isfile(image_path):
            self.logger.error('Image: not a valid file')
            self.input_image.setFocus()
            return
        if len(mask_graph_paths) == 0:
            self.logger.error('Segmentation mask and cell tracking graph missing')
            return
        for mask_path in mask_paths:
            if not os.path.isfile(mask_path):
                self.logger.error('Segmentation mask not found: %s', mask_path)
                return
        for graph_path in graph_paths:
            if not os.path.isfile(graph_path):
                self.logger.error('Cell tracking graph not found: %s', graph_path)
                return
        if self.output_folder.text() == '' and not self.use_input_folder.isChecked():
            self.logger.error('Output folder missing')
            self.output_folder.setFocus()
            return
        output_files = [os.path.join(d, f) for d, f in zip(output_paths, output_basenames)]
        duplicates = [x for x, y in zip(mask_paths, output_files) if output_files.count(y) > 1]
        if len(duplicates) > 0:
            self.logger.error('More than one input file will output to the same file (output files will be overwritten).\nEither use input mask and graph folder as output folder or avoid processing masks and graphs from different input folders.\nProblematic input files (masks):\n%s', '\n'.join(duplicates[:4] + (['...'] if len(duplicates) > 4 else [])))
            return

        # disable messagebox error handler
        messagebox_error_handler = None
        for h in logging.getLogger().handlers:
            if h.get_name() == 'messagebox_error_handler':
                messagebox_error_handler = h
                logging.getLogger().removeHandler(messagebox_error_handler)
                break

        status = []
        error_messages = []
        for mask_path, graph_path, output_path, output_basename in zip(mask_paths, graph_paths, output_paths, output_basenames):
            self.logger.info("Graph filtering (image %s, mask %s, graph %s)", image_path, mask_path, graph_path)

            QApplication.setOverrideCursor(QCursor(Qt.BusyCursor))
            QApplication.processEvents()
            try:
                f.main(image_path, mask_path, graph_path, output_path, output_basename, filters, display_results=self.display_results.isChecked(), graph_topologies=graph_topologies)
                status.append("Success")
                error_messages.append(None)
            except Exception as e:
                status.append("Failed")
                error_messages.append(str(e))
                self.logger.exception('Filtering failed')
            QApplication.restoreOverrideCursor()

        if any(s != 'Success' for s in status):
            msg = gf.StatusTableDialog('Warning', status, error_messages, mask_paths)
            msg.exec_()

        # re-enable messagebox error handler
        if messagebox_error_handler is not None:
            logging.getLogger().addHandler(messagebox_error_handler)

        self.logger.info("Done")
