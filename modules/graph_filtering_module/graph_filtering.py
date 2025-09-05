import os
import sys
import time
import concurrent.futures
import logging
import napari
import igraph as ig
from PyQt5.QtWidgets import QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QGroupBox, QApplication, QLabel, QFormLayout, QSpinBox, QCheckBox, QSizePolicy
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCursor
from modules.graph_filtering_module import graph_filtering_functions as f
from general import general_functions as gf


def process_initializer():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s (%(name)s) [%(levelname)s] %(message)s", handlers=[logging.StreamHandler(sys.stdout)], force=True)


class GraphFiltering(QWidget):
    def __init__(self, pipeline_layout=False):
        super().__init__()

        self.output_suffix = gf.output_suffixes['graph_filtering']
        self.celltracking_suffix = gf.output_suffixes['cell_tracking']

        self.pipeline_layout = pipeline_layout

        layout = QVBoxLayout()

        label_documentation = gf.CollapsibleLabel('', collapsed=True)
        label_documentation.setText('For each pair of input segmentation mask and cell tracking graph, apply the selected filters and save the filtered cell tracking graph and segmentation mask.<br>' +
                                    'Input segmentation mask must have X, Y and T axes. The optional input image must have X, Y and T axes and can optionally have C and/or Z axes.<br>' +
                                    '<br>' +
                                    'Additional information: <a href="' + os.path.join(os.path.dirname(__file__), '..', '..', 'doc', 'site', 'graph_filtering_module', 'reference.html') + '">Documentation</a>')

        groupbox = QGroupBox("Documentation")
        layout2 = QVBoxLayout()
        layout2.addWidget(label_documentation)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        self.mask_graph_table = gf.FileTableWidget2(header_1="Mask", header_2="Graph", filenames_suffix_1='.ome.tif', filenames_suffix_2='.graphmlz', filenames_filter=self.celltracking_suffix)
        self.mask_graph_table.file_table_changed.connect(self.mask_graph_table_changed)
        if not self.pipeline_layout:
            groupbox = QGroupBox('Input files (segmentation masks and cell tracking graphs)')
            layout2 = QVBoxLayout()
            layout2.addWidget(self.mask_graph_table)
            groupbox.setLayout(layout2)
            layout.addWidget(groupbox)

        self.output_settings = gf.OutputSettings(extensions=['.ome.tif', '.graphmlz'], output_suffix=self.output_suffix, pipeline_layout=self.pipeline_layout)
        groupbox = QGroupBox("Output")
        layout2 = QVBoxLayout()
        layout2.addWidget(self.output_settings)
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

        # filter number of missing cells
        self.filter_n_missing_yn = QGroupBox("Missing cells")
        self.filter_n_missing_yn.setCheckable(True)
        self.filter_n_missing_yn.setChecked(False)
        layout3 = QFormLayout()
        help_label = QLabel("Keep only cell tracks with at most the selected number of missing cells.")
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

        # place the remaining filters in a collapsible widget
        collapsible = gf.CollapsibleWidget("", collapsed_icon="▶ [show more filters]", expanded_icon="▼ [hide]", expanded=False)
        layout3 = QVBoxLayout()
        layout3.setContentsMargins(0, 0, 0, 0)
        collapsible.content.setLayout(layout3)
        layout2.addWidget(collapsible)

        # filter cell area (all cells)
        self.filter_all_cells_area_yn = QGroupBox("Cell area (all cells)")
        self.filter_all_cells_area_yn.setCheckable(True)
        self.filter_all_cells_area_yn.setChecked(False)
        layout4 = QFormLayout()
        help_label = QLabel("Keep only cell tracks with all cell area within [min,max] range.")
        help_label.setWordWrap(True)
        help_label.setMinimumWidth(10)
        layout4.addRow(help_label)
        self.all_cells_min_area = QSpinBox()
        self.all_cells_min_area.setMinimum(0)
        self.all_cells_min_area.setMaximum(100000)
        self.all_cells_min_area.setValue(0)
        layout4.addRow("Min area (pixel):", self.all_cells_min_area)
        self.all_cells_max_area = QSpinBox()
        self.all_cells_max_area.setMinimum(0)
        self.all_cells_max_area.setMaximum(100000)
        self.all_cells_max_area.setValue(100000)
        layout4.addRow("Max area (pixel):", self.all_cells_max_area)
        self.filter_all_cells_area_yn.setLayout(layout4)
        layout3.addWidget(self.filter_all_cells_area_yn)

        # filter cell area (at least one cell)
        self.filter_one_cell_area_yn = QGroupBox("Cell area (at least one cell)")
        self.filter_one_cell_area_yn.setCheckable(True)
        self.filter_one_cell_area_yn.setChecked(False)
        layout4 = QFormLayout()
        help_label = QLabel("Keep only cell tracks with at least one cell area within [min,max] range.")
        help_label.setWordWrap(True)
        help_label.setMinimumWidth(10)
        layout4.addRow(help_label)
        self.one_cell_min_area = QSpinBox()
        self.one_cell_min_area.setMinimum(0)
        self.one_cell_min_area.setMaximum(100000)
        self.one_cell_min_area.setValue(0)
        layout4.addRow("Min area (pixel):", self.one_cell_min_area)
        self.one_cell_max_area = QSpinBox()
        self.one_cell_max_area.setMinimum(0)
        self.one_cell_max_area.setMaximum(100000)
        self.one_cell_max_area.setValue(100000)
        layout4.addRow("Max area (pixel):", self.one_cell_max_area)
        self.filter_one_cell_area_yn.setLayout(layout4)
        layout3.addWidget(self.filter_one_cell_area_yn)

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
        layout4 = QVBoxLayout()
        help_label = QLabel("Keep only cell tracks with selected topologies.")
        help_label.setWordWrap(True)
        help_label.setMinimumWidth(10)
        layout4.addWidget(help_label)
        self.topology_yn = []
        for g in self.graph_topologies:
            layout5 = QHBoxLayout()
            self.topology_yn.append(QCheckBox())
            self.topology_yn[-1].setChecked(False)
            layout5.addWidget(self.topology_yn[-1])
            label = QLabel()
            label.setPixmap(f.get_graph_qpixmap(g, 150, 50))
            label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            # label.setScaledContents(True)
            layout5.addWidget(label)
            layout4.addLayout(layout5)
        self.filter_topology_yn.setLayout(layout4)
        layout3.addWidget(self.filter_topology_yn)

        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        self.nprocesses = QSpinBox()
        self.nprocesses.setMinimum(1)
        self.nprocesses.setMaximum(os.cpu_count())
        self.nprocesses.setValue(1)
        if not self.pipeline_layout:
            groupbox = QGroupBox("Multi-processing")
            layout2 = QFormLayout()
            layout2.addRow("Number of processes:", self.nprocesses)
            groupbox.setLayout(layout2)
            layout.addWidget(groupbox)

        self.display_results = QGroupBox("Show (and edit) results in napari")
        self.display_results.setCheckable(True)
        self.display_results.setChecked(False)
        self.input_image = gf.FileLineEdit(label='Images', filetypes=gf.imagetypes)
        if not self.pipeline_layout:
            layout2 = QVBoxLayout()
            layout2.addWidget(QLabel("Input image:"))
            layout2.addWidget(self.input_image)
            self.display_results.setLayout(layout2)
            layout.addWidget(self.display_results)

        self.submit_button = QPushButton("Submit")
        self.submit_button.clicked.connect(self.submit)
        if not self.pipeline_layout:
            layout.addWidget(self.submit_button, alignment=Qt.AlignCenter)

        self.setLayout(layout)

        self.logger = logging.getLogger(__name__)

    def mask_graph_table_changed(self):
        if self.mask_graph_table.rowCount() > 1:
            self.display_results.setChecked(False)
        self.display_results.setEnabled(self.mask_graph_table.rowCount() <= 1)

    def get_widgets_state(self):
        widgets_state = {
            'mask_graph_table': self.mask_graph_table.get_file_table(),
            'use_input_folder': self.output_settings.use_input_folder.isChecked(),
            'use_custom_folder': self.output_settings.use_custom_folder.isChecked(),
            'output_folder': self.output_settings.output_folder.text(),
            'output_user_suffix': self.output_settings.output_user_suffix.text(),
            'filter_border_yn': self.filter_border_yn.isChecked(),
            'border_width': self.border_width.value(),
            'filter_all_cells_area_yn': self.filter_all_cells_area_yn.isChecked(),
            'all_cells_min_area': self.all_cells_min_area.value(),
            'all_cells_max_area': self.all_cells_max_area.value(),
            'filter_one_cell_area_yn': self.filter_one_cell_area_yn.isChecked(),
            'one_cell_min_area': self.one_cell_min_area.value(),
            'one_cell_max_area': self.one_cell_max_area.value(),
            'filter_track_length_yn': self.filter_track_length_yn.isChecked(),
            'nframes': self.nframes.value(),
            'filter_n_missing_yn': self.filter_n_missing_yn.isChecked(),
            'nmissing': self.nmissing.value(),
            'filter_n_divisions_yn': self.filter_n_divisions_yn.isChecked(),
            'min_ndivisions': self.min_ndivisions.value(),
            'max_ndivisions': self.max_ndivisions.value(),
            'nframes_stable_division': self.nframes_stable_division.value(),
            'filter_n_fusions_yn': self.filter_n_fusions_yn.isChecked(),
            'min_nfusions': self.min_nfusions.value(),
            'max_nfusions': self.max_nfusions.value(),
            'nframes_stable_fusion': self.nframes_stable_fusion.value(),
            'filter_topology_yn': self.filter_topology_yn.isChecked(),
            'topologies': [t.isChecked() for t in self.topology_yn],
            'input_image': self.input_image.text(),
            'display_results': self.display_results.isChecked(),
            'nprocesses': self.nprocesses.value()}
        return widgets_state

    def set_widgets_state(self, widgets_state):
        self.mask_graph_table.set_file_table(widgets_state['mask_graph_table'])
        self.output_settings.use_input_folder.setChecked(widgets_state['use_input_folder'])
        self.output_settings.use_custom_folder.setChecked(widgets_state['use_custom_folder'])
        self.output_settings.output_folder.setText(widgets_state['output_folder'])
        self.output_settings.output_user_suffix.setText(widgets_state['output_user_suffix'])
        self.filter_border_yn.setChecked(widgets_state['filter_border_yn'])
        self.border_width.setValue(widgets_state['border_width'])
        self.filter_all_cells_area_yn.setChecked(widgets_state['filter_all_cells_area_yn'])
        self.all_cells_min_area.setValue(widgets_state['all_cells_min_area'])
        self.all_cells_max_area.setValue(widgets_state['all_cells_max_area'])
        self.filter_one_cell_area_yn.setChecked(widgets_state['filter_one_cell_area_yn'])
        self.one_cell_min_area.setValue(widgets_state['one_cell_min_area'])
        self.one_cell_max_area.setValue(widgets_state['one_cell_max_area'])
        self.filter_track_length_yn.setChecked(widgets_state['filter_track_length_yn'])
        self.nframes.setValue(widgets_state['nframes'])
        self.filter_n_missing_yn.setChecked(widgets_state['filter_n_missing_yn'])
        self.nmissing.setValue(widgets_state['nmissing'])
        self.filter_n_divisions_yn.setChecked(widgets_state['filter_n_divisions_yn'])
        self.min_ndivisions.setValue(widgets_state['min_ndivisions'])
        self.max_ndivisions.setValue(widgets_state['max_ndivisions'])
        self.nframes_stable_division.setValue(widgets_state['nframes_stable_division'])
        self.filter_n_fusions_yn.setChecked(widgets_state['filter_n_fusions_yn'])
        self.min_nfusions.setValue(widgets_state['min_nfusions'])
        self.max_nfusions.setValue(widgets_state['max_nfusions'])
        self.nframes_stable_fusion.setValue(widgets_state['nframes_stable_fusion'])
        self.filter_topology_yn.setChecked(widgets_state['filter_topology_yn'])
        for i, checked in enumerate(widgets_state['topologies']):
            self.topology_yn[i].setChecked(checked)
        self.input_image.setText(widgets_state['input_image'])
        self.display_results.setChecked(widgets_state['display_results'])
        self.nprocesses.setValue(widgets_state['nprocesses'])

    def submit(self):
        # This is a temporary workaround to avoid having multiple conflicting
        # logging to metadata and log file, which could happen when a napari
        # window is already opened.
        # TODO: find a better solution.
        if napari.current_viewer():
            self.logger.error('To avoid potential log file corruption, close all napari windows and try again.')
            return

        if self.input_image.isEnabled():
            image_path = self.input_image.text()
        else:
            image_path = ""

        mask_graph_paths = self.mask_graph_table.get_file_table()
        mask_paths = [mask_path for mask_path, graph_path in mask_graph_paths]
        graph_paths = [graph_path for mask_path, graph_path in mask_graph_paths]
        output_basenames = [self.output_settings.get_basename(mask_path) for mask_path in mask_paths]
        output_paths = [self.output_settings.get_path(mask_path) for mask_path in mask_paths]

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
        if self.output_settings.output_folder.text() == '' and not self.output_settings.use_input_folder.isChecked():
            self.logger.error('Output folder missing')
            self.output_settings.output_folder.setFocus()
            return
        output_files = [os.path.join(d, f) for d, f in zip(output_paths, output_basenames)]
        duplicates = [x for x, y in zip(mask_paths, output_files) if output_files.count(y) > 1]
        if len(duplicates) > 0:
            self.logger.error('More than one input file will output to the same file (output files will be overwritten).\nEither use input mask and graph folder as output folder or avoid processing masks and graphs from different input folders.\nProblematic input files (masks):\n%s', '\n'.join(duplicates[:4] + (['...'] if len(duplicates) > 4 else [])))
            return

        # check input files are valid
        for path in mask_paths:
            try:
                image = gf.Image(path)
            except Exception:
                self.logger.exception('Error loading:\n %s\n\nError message:', path)
                return

        # disable messagebox error handler
        messagebox_error_handler = None
        for h in logging.getLogger().handlers:
            if h.get_name() == 'messagebox_error_handler':
                messagebox_error_handler = h
                logging.getLogger().removeHandler(messagebox_error_handler)
                break

        QApplication.setOverrideCursor(QCursor(Qt.BusyCursor))
        QApplication.processEvents()

        arguments = []
        for mask_path, graph_path, output_path, output_basename in zip(mask_paths, graph_paths, output_paths, output_basenames):
            arguments.append((image_path, mask_path, graph_path, output_path, output_basename, filters, self.display_results.isChecked(), graph_topologies))
        if not arguments:
            return
        nprocesses = min(len(arguments), self.nprocesses.value())

        status_dialog = gf.StatusTableDialog(mask_paths)
        status_dialog.ok_button.setEnabled(False)
        status_dialog.setModal(True)
        status_dialog.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.CustomizeWindowHint)
        status_dialog.show()
        QApplication.processEvents()
        time.sleep(0.01)

        hide_status_dialog = False
        if self.display_results.isChecked():
            QApplication.processEvents()
            time.sleep(0.01)
            hide_status_dialog = True
            for i, args in enumerate(arguments):
                try:
                    f.main(*args)
                    status_dialog.set_status(i, 'Success')
                except Exception as e:
                    self.logger.exception("An exception occurred")
                    status_dialog.set_status(i, 'Failed', str(e))
                    hide_status_dialog = False
                QApplication.processEvents()
                time.sleep(0.01)
        else:
            with concurrent.futures.ProcessPoolExecutor(max_workers=nprocesses, initializer=process_initializer) as executor:
                future_reg = {executor.submit(f.main, *args): i for i, args in enumerate(arguments)}
                QApplication.processEvents()
                time.sleep(0.01)
                for future in concurrent.futures.as_completed(future_reg):
                    try:
                        future.result()
                        status_dialog.set_status(future_reg[future], 'Success')
                    except Exception as e:
                        self.logger.exception("An exception occurred")
                        status_dialog.set_status(future_reg[future], 'Failed', str(e))
                    QApplication.processEvents()
                    time.sleep(0.01)

        # Restore cursor
        QApplication.restoreOverrideCursor()
        status_dialog.ok_button.setEnabled(True)
        if hide_status_dialog:
            status_dialog.hide()

        # re-enable messagebox error handler
        if messagebox_error_handler is not None:
            logging.getLogger().addHandler(messagebox_error_handler)

        self.logger.info("Done")
