import os
import sys
import time
import concurrent.futures
import logging
from PyQt5.QtWidgets import QPushButton, QVBoxLayout, QWidget, QGroupBox, QApplication, QLabel, QFormLayout, QSpinBox, QComboBox
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCursor
from modules.events_selection_module import events_selection_functions as f
from general import general_functions as gf


def process_initializer():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s (%(name)s) [%(levelname)s] %(message)s", handlers=[logging.StreamHandler(sys.stdout)], force=True)


class EventsSelection(QWidget):
    def __init__(self, pipeline_layout=False):
        super().__init__()

        self.output_suffix = gf.output_suffixes['events_selection']
        self.celltracking_suffix = gf.output_suffixes['cell_tracking']

        self.pipeline_layout = pipeline_layout

        layout = QVBoxLayout()

        label_documentation = gf.CollapsibleLabel('', collapsed=True)
        label_documentation.setText('For each pair of input segmentation mask and cell tracking graph, select a user specified number of stable frames around fusion (or division) events and erase all non-selected cells from the segmentation mask and cell tracking graph.<br>' +
                                    'Input segmentation mask must have X, Y and T axes.<br>' +
                                    '<br>' +
                                    'Additional information: <a href="' + os.path.join(os.path.dirname(__file__), '..', '..', 'doc', 'site', 'events_selection_module', 'reference.html') + '">Documentation</a>')

        groupbox = QGroupBox("Documentation")
        layout2 = QVBoxLayout()
        layout2.addWidget(label_documentation)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        self.mask_graph_table = gf.FileTableWidget2(header_1="Mask", header_2="Graph", filenames_suffix_1='.ome.tif', filenames_suffix_2='.graphmlz', filenames_filter=self.celltracking_suffix)
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
        layout2 = QFormLayout()

        # events type
        self.events_type = QComboBox()
        self.events_type.addItem("division")
        self.events_type.addItem("fusion")
        self.events_type.setCurrentText("division")
        layout2.addRow('Type of events:', self.events_type)

        self.nframes_before = QSpinBox()
        self.nframes_before.setMinimum(0)
        self.nframes_before.setMaximum(100000)
        self.nframes_before.setValue(1)
        layout2.addRow("Number of frames (before event):", self.nframes_before)
        self.nframes_after = QSpinBox()
        self.nframes_after.setMinimum(0)
        self.nframes_after.setMaximum(100000)
        self.nframes_after.setValue(2)
        layout2.addRow("Number of frames (after event):", self.nframes_after)

        # filter border cells
        self.filter_border_yn = QGroupBox("Border filter")
        self.filter_border_yn.setCheckable(True)
        self.filter_border_yn.setChecked(True)
        layout3 = QFormLayout()
        help_label = QLabel("Remove resulting cell tracks with at least one cell touching the border.")
        help_label.setWordWrap(True)
        help_label.setMinimumWidth(10)
        layout3.addRow(help_label)
        self.border_width = QSpinBox()
        self.border_width.setMinimum(1)
        self.border_width.setMaximum(100)
        self.border_width.setValue(2)
        layout3.addRow("Border width (pixel):", self.border_width)
        self.filter_border_yn.setLayout(layout3)
        layout2.addRow(self.filter_border_yn)

        # filter number of missing cells
        self.filter_nmissing_yn = QGroupBox("Missing cells filter")
        self.filter_nmissing_yn.setCheckable(True)
        self.filter_nmissing_yn.setChecked(True)
        layout3 = QFormLayout()
        help_label = QLabel("Keep only cell tracks with at most the selected number of missing cells (missing cells are only allowed around the fusion/division event).")
        help_label.setWordWrap(True)
        help_label.setMinimumWidth(10)
        layout3.addRow(help_label)
        self.nmissing = QSpinBox()
        self.nmissing.setMinimum(0)
        self.nmissing.setMaximum(100000)
        self.nmissing.setValue(2)
        self.filter_nmissing_yn.setLayout(layout3)
        layout3.addRow("Max missing cells:", self.nmissing)
        layout2.addRow(self.filter_nmissing_yn)

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

        self.submit_button = QPushButton("Submit")
        self.submit_button.clicked.connect(self.submit)
        if not self.pipeline_layout:
            layout.addWidget(self.submit_button, alignment=Qt.AlignCenter)

        self.setLayout(layout)

        self.logger = logging.getLogger(__name__)

    def get_widgets_state(self):
        widgets_state = {
            'mask_graph_table': self.mask_graph_table.get_file_table(),
            'use_input_folder': self.output_settings.use_input_folder.isChecked(),
            'use_custom_folder': self.output_settings.use_custom_folder.isChecked(),
            'output_folder': self.output_settings.output_folder.text(),
            'output_user_suffix': self.output_settings.output_user_suffix.text(),
            'events_type': self.events_type.currentText(),
            'nframes_before': self.nframes_before.value(),
            'nframes_after': self.nframes_after.value(),
            'filter_border_yn': self.filter_border_yn.isChecked(),
            'border_width': self.border_width.value(),
            'filter_nmissing_yn': self.filter_nmissing_yn.isChecked(),
            'nmissing': self.nmissing.value(),
            'nprocesses': self.nprocesses.value()}
        return widgets_state

    def set_widgets_state(self, widgets_state):
        self.mask_graph_table.set_file_table(widgets_state['mask_graph_table'])
        self.output_settings.use_input_folder.setChecked(widgets_state['use_input_folder'])
        self.output_settings.use_custom_folder.setChecked(widgets_state['use_custom_folder'])
        self.output_settings.output_folder.setText(widgets_state['output_folder'])
        self.output_settings.output_user_suffix.setText(widgets_state['output_user_suffix'])
        self.events_type.setCurrentText(widgets_state['events_type'])
        self.nframes_before.setValue(widgets_state['nframes_before'])
        self.nframes_after.setValue(widgets_state['nframes_after'])
        self.filter_border_yn.setChecked(widgets_state['filter_border_yn'])
        self.border_width.setValue(widgets_state['border_width'])
        self.filter_nmissing_yn.setChecked(widgets_state['filter_nmissing_yn'])
        self.nmissing.setValue(widgets_state['nmissing'])
        self.nprocesses.setValue(widgets_state['nprocesses'])

    def submit(self):
        mask_graph_paths = self.mask_graph_table.get_file_table()
        mask_paths = [mask_path for mask_path, graph_path in mask_graph_paths]
        graph_paths = [graph_path for mask_path, graph_path in mask_graph_paths]
        output_basenames = [self.output_settings.get_basename(mask_path) for mask_path in mask_paths]
        output_paths = [self.output_settings.get_path(mask_path) for mask_path in mask_paths]

        # check input
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
            arguments.append((mask_path,
                              graph_path,
                              output_path,
                              output_basename,
                              self.events_type.currentText(),
                              self.nframes_before.value(),
                              self.nframes_after.value(),
                              self.filter_border_yn.isChecked(),
                              self.border_width.value(),
                              self.filter_nmissing_yn.isChecked(),
                              self.nmissing.value()))

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

        # re-enable messagebox error handler
        if messagebox_error_handler is not None:
            logging.getLogger().addHandler(messagebox_error_handler)

        self.logger.info("Done")
