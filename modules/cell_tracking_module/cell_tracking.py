import os
import sys
import time
import concurrent.futures
import logging
from PyQt5.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget, QGroupBox, QApplication, QSpinBox, QFormLayout
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCursor
from modules.cell_tracking_module import cell_tracking_functions as f
from general import general_functions as gf


def process_initializer():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s (%(name)s) [%(levelname)s] %(message)s", handlers=[logging.StreamHandler(sys.stdout)], force=True)


class CellTracking(QWidget):
    def __init__(self, pipeline_layout=False):
        super().__init__()

        self.output_suffix = gf.output_suffixes['cell_tracking']
        self.mask_suffix = gf.output_suffixes['segmentation']

        self.pipeline_layout = pipeline_layout

        label_documentation = gf.CollapsibleLabel('', collapsed=True)
        label_documentation.setText('For each input segmentation mask, perform cell tracking, save the cell tracking graph and segmentation mask with relabelled cells.<br>' +
                                    'Input segmentation mask must have X, Y and T axes. The optional input image must have X, Y and T axes and can optionally have C and/or Z axes.<br>' +
                                    '<br>' +
                                    'Additional information: <a href="' + os.path.join(os.path.dirname(__file__), '..', '..', 'doc', 'site', 'cell_tracking_module', 'reference.html') + '">Documentation</a>')

        self.mask_list = gf.FileListWidget(filetypes=gf.imagetypes, filenames_filter=self.mask_suffix)
        self.mask_list.file_list_changed.connect(self.mask_list_changed)

        self.output_settings = gf.OutputSettings(extensions=['.ome.tif', '.graphmlz'], output_suffix=self.output_suffix, pipeline_layout=self.pipeline_layout)

        self.min_area = QSpinBox()
        self.min_area.setMinimum(0)
        self.min_area.setMaximum(10000)
        self.min_area.setValue(300)
        self.min_area.setToolTip('Remove labelled regions with area (number of pixels) below this value.')

        self.max_delta_frame = QSpinBox()
        self.max_delta_frame.setMinimum(1)
        self.max_delta_frame.setMaximum(50)
        self.max_delta_frame.setValue(5)
        self.max_delta_frame.setToolTip('Number of previous frames to consider when creating the cell tracking graph.')

        self.min_overlap_fraction = QSpinBox()
        self.min_overlap_fraction.setMinimum(0)
        self.min_overlap_fraction.setMaximum(100)
        self.min_overlap_fraction.setValue(20)
        self.min_overlap_fraction.setSuffix("%")
        self.min_overlap_fraction.setToolTip('minimum overlap fraction (w.r.t mask area) to consider when creating edges in the cell tracking graph.')

        self.stable_overlap_fraction = QSpinBox()
        self.stable_overlap_fraction.setMinimum(0)
        self.stable_overlap_fraction.setMaximum(100)
        self.stable_overlap_fraction.setValue(90)
        self.stable_overlap_fraction.setSuffix("%")
        self.stable_overlap_fraction.setToolTip('Cell tracking graph edges corresponding to an overlap fraction below this value are considered as not stable.')

        self.nframes_defect = QSpinBox()
        self.nframes_defect.setMinimum(1)
        self.nframes_defect.setMaximum(50)
        self.nframes_defect.setValue(2)
        self.nframes_defect.setToolTip('Maximum size of the defect (number of frames).')
        self.nframes_defect.valueChanged.connect(self.nframes_defect_changed)

        self.max_delta_frame_interpolation = QSpinBox()
        self.max_delta_frame_interpolation.setMinimum(1)
        self.max_delta_frame_interpolation.setMaximum(50)
        self.max_delta_frame_interpolation.setValue(3)
        self.max_delta_frame_interpolation.setToolTip('Number of previous and subsequent frames to consider for mask interpolation.')
        self.max_delta_frame_interpolation.valueChanged.connect(self.max_delta_frame_interpolation_changed)

        self.nframes_stable = QSpinBox()
        self.nframes_stable.setMinimum(1)
        self.nframes_stable.setMaximum(50)
        self.nframes_stable.setValue(3)
        self.nframes_stable.setToolTip('Minimum number of stable frames before and after the defect.')
        self.nframes_stable.valueChanged.connect(self.nframes_stable_changed)

        self.nprocesses = QSpinBox()
        self.nprocesses.setMinimum(1)
        self.nprocesses.setMaximum(os.cpu_count())
        self.nprocesses.setValue(1)

        self.display_results = QGroupBox("Show (and edit) results in napari")
        self.display_results.setCheckable(True)
        self.display_results.setChecked(False)
        self.input_image = gf.FileLineEdit(label='Images', filetypes=gf.imagetypes)

        self.submit_button = QPushButton("Submit")
        self.submit_button.clicked.connect(self.submit)

        layout = QVBoxLayout()
        groupbox = QGroupBox("Documentation")
        layout2 = QVBoxLayout()
        layout2.addWidget(label_documentation)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        if not self.pipeline_layout:
            groupbox = QGroupBox('Input files (segmentation masks)')
            layout2 = QVBoxLayout()
            layout2.addWidget(self.mask_list)
            groupbox.setLayout(layout2)
            layout.addWidget(groupbox)

        groupbox = QGroupBox("Output")
        layout2 = QVBoxLayout()
        layout2.addWidget(self.output_settings)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
        groupbox = QGroupBox("Options")
        layout2 = QFormLayout()
        layout2.addRow(QLabel("Cell tracking graph:"))
        layout2.addRow("Min area:", self.min_area)
        layout2.addRow("Max delta frame:", self.max_delta_frame)
        layout2.addRow("Min overlap fraction:", self.min_overlap_fraction)
        self.auto_clean = QGroupBox("Automatic cleaning")
        self.auto_clean.setCheckable(True)
        self.auto_clean.setChecked(True)
        layout3 = QFormLayout()
        layout3.addRow("Stable overlap fraction:", self.stable_overlap_fraction)
        layout3.addRow("Max defect size (frames):", self.nframes_defect)
        layout3.addRow("Max delta frame (interpolation):", self.max_delta_frame_interpolation)
        layout3.addRow("Min stable size (frames):", self.nframes_stable)
        self.auto_clean.setLayout(layout3)
        layout2.addRow(self.auto_clean)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        if not self.pipeline_layout:
            groupbox = QGroupBox("Multi-processing")
            layout2 = QFormLayout()
            layout2.addRow("Number of processes:", self.nprocesses)
            groupbox.setLayout(layout2)
            layout.addWidget(groupbox)
            layout2 = QVBoxLayout()
            layout2.addWidget(QLabel("Input image:"))
            layout2.addWidget(self.input_image)
            self.display_results.setLayout(layout2)
            layout.addWidget(self.display_results)
            layout.addWidget(self.submit_button, alignment=Qt.AlignCenter)

        self.setLayout(layout)

        self.logger = logging.getLogger(__name__)

    def mask_list_changed(self):
        if self.mask_list.count() > 1:
            self.display_results.setChecked(False)
        self.display_results.setEnabled(self.mask_list.count() <= 1)

    def nframes_defect_changed(self, value):
        # Set nframes_defect <= max_delta_frame_interpolation <= nframes_stable
        if self.nframes_stable.value() < value:
            self.nframes_stable.setValue(value)
        if self.max_delta_frame_interpolation.value() < value:
            self.max_delta_frame_interpolation.setValue(value)

    def max_delta_frame_interpolation_changed(self, value):
        # Set nframes_defect <= max_delta_frame_interpolation <= nframes_stable
        if self.nframes_stable.value() < value:
            self.nframes_stable.setValue(value)
        if self.nframes_defect.value() > value:
            self.nframes_defect.setValue(value)

    def nframes_stable_changed(self, value):
        # Set nframes_defect <= max_delta_frame_interpolation <= nframes_stable
        if self.nframes_defect.value() > value:
            self.nframes_defect.setValue(value)
        if self.max_delta_frame_interpolation.value() > value:
            self.max_delta_frame_interpolation.setValue(value)

    def get_widgets_state(self):
        widgets_state = {
            'mask_list': self.mask_list.get_file_list(),
            'use_input_folder': self.output_settings.use_input_folder.isChecked(),
            'use_custom_folder': self.output_settings.use_custom_folder.isChecked(),
            'output_folder': self.output_settings.output_folder.text(),
            'output_user_suffix': self.output_settings.output_user_suffix.text(),
            'min_area': self.min_area.value(),
            'max_delta_frame': self.max_delta_frame.value(),
            'min_overlap_fraction': self.min_overlap_fraction.value(),
            'auto_clean': self.auto_clean.isChecked(),
            'stable_overlap_fraction': self.stable_overlap_fraction.value(),
            'nframes_defect': self.nframes_defect.value(),
            'max_delta_frame_interpolation': self.max_delta_frame_interpolation.value(),
            'nframes_stable': self.nframes_stable.value(),
            'input_image': self.input_image.text(),
            'display_results': self.display_results.isChecked(),
            'nprocesses': self.nprocesses.value()}
        return widgets_state

    def set_widgets_state(self, widgets_state):
        self.mask_list.set_file_list(widgets_state['mask_list'])
        self.output_settings.use_input_folder.setChecked(widgets_state['use_input_folder'])
        self.output_settings.use_custom_folder.setChecked(widgets_state['use_custom_folder'])
        self.output_settings.output_folder.setText(widgets_state['output_folder'])
        self.output_settings.output_user_suffix.setText(widgets_state['output_user_suffix'])
        self.min_area.setValue(widgets_state['min_area'])
        self.max_delta_frame.setValue(widgets_state['max_delta_frame'])
        self.min_overlap_fraction.setValue(widgets_state['min_overlap_fraction'])
        self.auto_clean.setChecked(widgets_state['auto_clean'])
        self.stable_overlap_fraction.setValue(widgets_state['stable_overlap_fraction'])
        self.nframes_defect.setValue(widgets_state['nframes_defect'])
        self.max_delta_frame_interpolation.setValue(widgets_state['max_delta_frame_interpolation'])
        self.nframes_stable.setValue(widgets_state['nframes_stable'])
        self.input_image.setText(widgets_state['input_image'])
        self.display_results.setChecked(widgets_state['display_results'])
        self.nprocesses.setValue(widgets_state['nprocesses'])

    def submit(self):
        if self.input_image.isEnabled():
            image_path = self.input_image.text()
        else:
            image_path = ""
        mask_paths = self.mask_list.get_file_list()
        output_basenames = [self.output_settings.get_basename(path) for path in mask_paths]
        output_paths = [self.output_settings.get_path(path) for path in mask_paths]

        # check inputs
        if image_path != '' and not os.path.isfile(image_path):
            self.logger.error('Image: not a valid file')
            self.input_image.setFocus()
            return
        if len(mask_paths) == 0:
            self.logger.error('Segmentation mask missing')
            return
        for path in mask_paths:
            if not os.path.isfile(path):
                self.logger.error('Segmentation mask not found: %s', path)
                return
        if self.output_settings.output_folder.text() == '' and not self.output_settings.use_input_folder.isChecked():
            self.logger.error('Output folder missing')
            self.output_settings.output_folder.setFocus()
            return
        output_files = [os.path.join(d, f) for d, f in zip(output_paths, output_basenames)]
        duplicates = [x for x, y in zip(mask_paths, output_files) if output_files.count(y) > 1]
        if len(duplicates) > 0:
            self.logger.error('More than one input file will output to the same file (output files will be overwritten).\nEither use input mask folder as output folder or avoid processing masks from different input folders.\nProblematic input files:\n%s', '\n'.join(duplicates[:4] + (['...'] if len(duplicates) > 4 else [])))
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
        for mask_path, output_path, output_basename in zip(mask_paths, output_paths, output_basenames):
            arguments.append((image_path, mask_path, output_path,
                              output_basename,
                              self.min_area.value(),
                              self.max_delta_frame.value(),
                              self.min_overlap_fraction.value()/100.0,
                              self.auto_clean.isChecked(),
                              self.max_delta_frame_interpolation.value(),
                              self.nframes_defect.value(),
                              self.nframes_stable.value(),
                              self.stable_overlap_fraction.value()/100.0,
                              self.display_results.isChecked()))
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
