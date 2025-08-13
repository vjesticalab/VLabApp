import os
import sys
import re
import time
import logging
import concurrent.futures
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QCheckBox, QComboBox, QFormLayout, QPushButton, QVBoxLayout, QWidget, QHBoxLayout, QApplication, QSpinBox, QRadioButton, QGroupBox
from PyQt5.QtGui import QCursor
from modules.registration_module import registration_functions as f
from general import general_functions as gf


def process_initializer():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s (%(name)s) [%(levelname)s] %(message)s", handlers=[logging.StreamHandler(sys.stdout)], force=True)


class Perform(QWidget):
    def __init__(self, pipeline_layout=False):
        super().__init__()

        self.output_suffix = gf.output_suffixes['registration']

        self.pipeline_layout = pipeline_layout

        # Documentation
        label_documentation = gf.CollapsibleLabel('', collapsed=True)
        label_documentation.setText('For each input image, estimate the shift between consecutive time frames, apply the resulting transformation matrix to the input image. Save the transformation matrix and the registered image.<br>' +
                                    'Input images must have X, Y and T axes. Images with additional Z and/or C axis are supported (Z axis will be projected and only the chosen channel will be selected before evaluating the transformation).<br>' +
                                    '<br>' +
                                    'Additional information: <a href="' + os.path.join(os.path.dirname(__file__), '..', '..', 'doc', 'site', 'registration_module', 'reference.html#registration') + '">Documentation</a>')

        self.image_list = gf.FileListWidget(filetypes=gf.imagetypes, filenames_filter='_BF', filenames_exclude_filter=self.output_suffix)
        self.channel_position = QSpinBox()
        self.channel_position.setMinimum(0)
        self.channel_position.setMaximum(100)
        self.channel_position.setValue(0)

        self.output_settings = gf.OutputSettings(extensions=['.csv', '.ome.tif'], output_suffix=self.output_suffix, pipeline_layout=self.pipeline_layout)

        # Z-Projection range
        # only bestZ
        self.projection_mode_bestZ = QRadioButton("Z section with best focus")
        self.projection_mode_bestZ.setChecked(False)
        self.projection_mode_bestZ.setToolTip('Keep only Z section with best focus.')
        # around bestZ
        self.projection_mode_around_bestZ = QRadioButton("Range around Z section with best focus")
        self.projection_mode_around_bestZ.setChecked(True)
        self.projection_mode_around_bestZ.setToolTip('Project all Z sections with Z in the interval [bestZ-range,bestZ+range], where bestZ is the Z section with best focus.')
        self.projection_mode_around_bestZ_zrange = QSpinBox()
        self.projection_mode_around_bestZ_zrange.setMinimum(0)
        self.projection_mode_around_bestZ_zrange.setMaximum(20)
        self.projection_mode_around_bestZ_zrange.setValue(3)
        # fixed range
        self.projection_mode_fixed = QRadioButton("Fixed range")
        self.projection_mode_fixed.setChecked(False)
        self.projection_mode_fixed.setToolTip('Project all Z sections with Z in the interval [from,to].')
        self.projection_mode_fixed_zmin = QSpinBox()
        self.projection_mode_fixed_zmin.setMinimum(0)
        self.projection_mode_fixed_zmin.setMaximum(6)
        self.projection_mode_fixed_zmin.setValue(4)
        self.projection_mode_fixed_zmin.valueChanged.connect(self.projection_mode_fixed_zmin_changed)
        self.projection_mode_fixed_zmax = QSpinBox()
        self.projection_mode_fixed_zmax.setMinimum(4)
        self.projection_mode_fixed_zmax.setMaximum(20)
        self.projection_mode_fixed_zmax.setValue(6)
        self.projection_mode_fixed_zmax.valueChanged.connect(self.projection_mode_fixed_zmax_changed)
        # all
        self.projection_mode_all = QRadioButton("All Z sections")
        self.projection_mode_all.setChecked(False)
        self.projection_mode_all.setToolTip('Project all Z sections.')
        # Z-Projection type
        self.projection_type = QComboBox()
        self.projection_type.addItem("max")
        self.projection_type.addItem("min")
        self.projection_type.addItem("mean")
        self.projection_type.addItem("median")
        self.projection_type.addItem("std")
        self.projection_type.setCurrentText("std")
        self.projection_type.setDisabled(self.projection_mode_bestZ.isChecked())
        self.projection_mode_bestZ.toggled.connect(self.projection_type.setDisabled)
        # registration method
        self.registration_method = QComboBox()
        self.registration_method.addItem("stackreg")
        self.registration_method.addItem("phase correlation")
        self.registration_method.addItem("feature matching (ORB)")
        self.registration_method.addItem("feature matching (BRISK)")
        self.registration_method.addItem("feature matching (AKAZE)")
        self.registration_method.addItem("feature matching (SIFT)")
        self.registration_method.setCurrentText("feature matching (SIFT)")
        self.coalignment_yn = QCheckBox("Co-align files with the same unique identifier (part of the filename before the first \"_\")")
        self.skip_cropping_yn = QCheckBox("Do NOT crop aligned image")
        self.submit_button = QPushButton("Submit")
        self.submit_button.clicked.connect(self.submit)
        self.nprocesses = QSpinBox()
        self.nprocesses.setMinimum(1)
        self.nprocesses.setMaximum(os.cpu_count())
        self.nprocesses.setValue(1)

        # T-range
        # all
        self.time_mode_all = QRadioButton("All time points")
        self.time_mode_all.setChecked(True)
        # fixed range
        self.time_mode_fixed = QRadioButton("Time point range")
        self.time_mode_fixed.setChecked(False)
        self.time_mode_fixed_tmin = QSpinBox()
        self.time_mode_fixed_tmin.setMinimum(0)
        self.time_mode_fixed_tmin.setMaximum(1000)
        self.time_mode_fixed_tmin.valueChanged.connect(self.time_mode_fixed_tmin_changed)
        self.time_mode_fixed_tmax = QSpinBox()
        self.time_mode_fixed_tmax.setMinimum(0)
        self.time_mode_fixed_tmax.setMaximum(1000)
        self.time_mode_fixed_tmax.setValue(1000)
        self.time_mode_fixed_tmax.valueChanged.connect(self.time_mode_fixed_tmax_changed)

        # Layout
        layout = QVBoxLayout()
        # Documentation
        groupbox = QGroupBox("Documentation")
        layout2 = QVBoxLayout()
        layout2.addWidget(label_documentation)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        if not self.pipeline_layout:
            groupbox = QGroupBox('Input files (images)')
            layout2 = QVBoxLayout()
            layout2.addWidget(self.image_list)
            groupbox.setLayout(layout2)
            layout.addWidget(groupbox)

        groupbox = QGroupBox("Output")
        layout2 = QVBoxLayout()
        layout2.addWidget(self.output_settings)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        groupbox = QGroupBox("Options")
        layout3 = QFormLayout()
        layout3.setLabelAlignment(Qt.AlignLeft)
        layout3.setFormAlignment(Qt.AlignLeft)
        groupbox2 = QGroupBox("If multiple channels:")
        layout4 = QFormLayout()
        layout4.addRow("Channel position:", self.channel_position)
        groupbox2.setLayout(layout4)
        layout3.addRow(groupbox2)

        groupbox2 = QGroupBox("If multiple z:")
        layout4 = QFormLayout()
        # Z-Projection range
        widget = QWidget()
        layout5 = QVBoxLayout()
        layout5.addWidget(self.projection_mode_bestZ)
        layout5.addWidget(self.projection_mode_around_bestZ)
        groupbox3 = QGroupBox()
        groupbox3.setToolTip('Project all Z sections with Z in the interval [bestZ-range,bestZ+range], where bestZ is the Z section with best focus.')
        groupbox3.setVisible(self.projection_mode_around_bestZ.isChecked())
        self.projection_mode_around_bestZ.toggled.connect(groupbox3.setVisible)
        layout6 = QFormLayout()
        layout6.addRow("Range:", self.projection_mode_around_bestZ_zrange)
        groupbox3.setLayout(layout6)
        layout5.addWidget(groupbox3)
        layout5.addWidget(self.projection_mode_fixed)
        groupbox3 = QGroupBox()
        groupbox3.setToolTip('Project all Z sections with Z in the interval [from,to].')
        groupbox3.setVisible(self.projection_mode_fixed.isChecked())
        self.projection_mode_fixed.toggled.connect(groupbox3.setVisible)
        layout6 = QHBoxLayout()
        layout7 = QFormLayout()
        layout7.addRow("From:", self.projection_mode_fixed_zmin)
        layout6.addLayout(layout7)
        layout7 = QFormLayout()
        layout7.addRow("To:", self.projection_mode_fixed_zmax)
        layout6.addLayout(layout7)
        groupbox3.setLayout(layout6)
        layout5.addWidget(groupbox3)
        layout5.addWidget(self.projection_mode_all)
        widget.setLayout(layout5)
        layout4.addRow("Projection range:", widget)
        layout4.addRow("Projection type:", self.projection_type)
        groupbox2.setLayout(layout4)
        layout3.addRow(groupbox2)

        groupbox2 = QGroupBox("If multiple time points:")
        layout8 = QVBoxLayout()
        layout8.addWidget(self.time_mode_all)
        groupbox2.setLayout(layout8)
        layout8.addWidget(self.time_mode_fixed)
        groupboxt1 = QGroupBox()
        groupboxt1.setVisible(self.time_mode_fixed.isChecked())
        self.time_mode_fixed.toggled.connect(groupboxt1.setVisible)
        layout9 = QHBoxLayout()
        layout10 = QFormLayout()
        layout10.addRow("From:", self.time_mode_fixed_tmin)
        layout9.addLayout(layout10)
        layout10 = QFormLayout()
        layout10.addRow("To:", self.time_mode_fixed_tmax)
        layout9.addLayout(layout10)
        groupboxt1.setLayout(layout9)
        layout8.addWidget(groupboxt1)
        layout3.addRow(groupbox2)

        layout3.addRow("Registration method:", self.registration_method)
        layout3.addRow(self.coalignment_yn)
        layout3.addRow(self.skip_cropping_yn)
        groupbox.setLayout(layout3)
        layout.addWidget(groupbox)

        if not self.pipeline_layout:
            groupbox = QGroupBox("Multi-processing")
            layout2 = QFormLayout()
            layout2.addRow("Number of processes:", self.nprocesses)
            groupbox.setLayout(layout2)
            layout.addWidget(groupbox)
            layout.addWidget(self.submit_button, alignment=Qt.AlignCenter)

        self.setLayout(layout)

        self.logger = logging.getLogger(__name__)


    def get_widgets_state(self):
        widgets_state = {
            'image_list': self.image_list.get_file_list(),
            'use_input_folder': self.output_settings.use_input_folder.isChecked(),
            'use_custom_folder': self.output_settings.use_custom_folder.isChecked(),
            'output_folder': self.output_settings.output_folder.text(),
            'output_user_suffix': self.output_settings.output_user_suffix.text(),
            'channel_position': self.channel_position.value(),
            'projection_mode_bestZ': self.projection_mode_bestZ.isChecked(),
            'projection_mode_around_bestZ': self.projection_mode_around_bestZ.isChecked(),
            'projection_mode_around_bestZ_zrange': self.projection_mode_around_bestZ_zrange.value(),
            'projection_mode_fixed': self.projection_mode_fixed.isChecked(),
            'projection_mode_fixed_zmin': self.projection_mode_fixed_zmin.value(),
            'projection_mode_fixed_zmax': self.projection_mode_fixed_zmax.value(),
            'projection_mode_all': self.projection_mode_all.isChecked(),
            'projection_type': self.projection_type.currentText(),
            'time_mode_all': self.time_mode_all.isChecked(),
            'time_mode_fixed': self.time_mode_fixed.isChecked(),
            'time_mode_fixed_tmin': self.time_mode_fixed_tmin.value(),
            'time_mode_fixed_tmax': self.time_mode_fixed_tmax.value(),
            'registration_method': self.registration_method.currentText(),
            'coalignment_yn': self.coalignment_yn.isChecked(),
            'skip_cropping_yn': self.skip_cropping_yn.isChecked(),
            'nprocesses': self.nprocesses.value()}
        return widgets_state

    def set_widgets_state(self, widgets_state):
        self.image_list.set_file_list(widgets_state['image_list'])
        self.output_settings.use_input_folder.setChecked(widgets_state['use_input_folder'])
        self.output_settings.use_custom_folder.setChecked(widgets_state['use_custom_folder'])
        self.output_settings.output_folder.setText(widgets_state['output_folder'])
        self.output_settings.output_user_suffix.setText(widgets_state['output_user_suffix'])
        self.channel_position.setValue(widgets_state['channel_position'])
        self.projection_mode_bestZ.setChecked(widgets_state['projection_mode_bestZ'])
        self.projection_mode_around_bestZ.setChecked(widgets_state['projection_mode_around_bestZ'])
        self.projection_mode_around_bestZ_zrange.setValue(widgets_state['projection_mode_around_bestZ_zrange'])
        self.projection_mode_fixed.setChecked(widgets_state['projection_mode_fixed'])
        self.projection_mode_fixed_zmin.setValue(widgets_state['projection_mode_fixed_zmin'])
        self.projection_mode_fixed_zmax.setValue(widgets_state['projection_mode_fixed_zmax'])
        self.projection_mode_all.setChecked(widgets_state['projection_mode_all'])
        self.projection_type.setCurrentText(widgets_state['projection_type'])
        self.time_mode_all.setChecked(widgets_state['time_mode_all'])
        self.time_mode_fixed.setChecked(widgets_state['time_mode_fixed'])
        self.time_mode_fixed_tmin.setValue(widgets_state['time_mode_fixed_tmin'])
        self.time_mode_fixed_tmax.setValue(widgets_state['time_mode_fixed_tmax'])
        self.registration_method.setCurrentText(widgets_state['registration_method'])
        self.coalignment_yn.setChecked(widgets_state['coalignment_yn'])
        self.skip_cropping_yn.setChecked(widgets_state['skip_cropping_yn'])
        self.nprocesses.setValue(widgets_state['nprocesses'])

    def submit(self):
        image_paths = self.image_list.get_file_list()

        # Arianna 26/07/23: added the three options channel_name, channel_position, projection_type
        # Arianna 06/03/24: added the time points option
        channel_position = self.channel_position.value()
        projection_type = self.projection_type.currentText()
        if self.projection_mode_bestZ.isChecked():
            projection_zrange = 0
        elif self.projection_mode_around_bestZ.isChecked():
            projection_zrange = self.projection_mode_around_bestZ_zrange.value()
        elif self.projection_mode_fixed.isChecked():
            projection_zrange = (self.projection_mode_fixed_zmin.value(), self.projection_mode_fixed_zmax.value())
        elif self.projection_mode_all.isChecked():
            projection_zrange = None

        if self.time_mode_fixed.isChecked():
            timepoint_range = (self.time_mode_fixed_tmin.value(), self.time_mode_fixed_tmax.value())
        else:
            timepoint_range = None

        registration_method = self.registration_method.currentText()
        coalignment = self.coalignment_yn.isChecked()
        skip_crop_decision = self.skip_cropping_yn.isChecked()

        # check inputs
        if len(image_paths) == 0:
            self.logger.error('Image missing')
            return
        for path in image_paths:
            if not os.path.isfile(path):
                self.logger.error('Image not found\n%s', path)
                return

        output_paths = [self.output_settings.get_path(path) for path in image_paths]
        output_basenames = [self.output_settings.get_basename(path) for path in image_paths]
        if coalignment:
            coalign_image_paths_list = []
            coalign_output_basenames_list = []
            for image_path in image_paths:
                coalign_image_paths = []
                coalign_output_basenames = []
                unique_identifier = gf.splitext(os.path.basename(image_path))[0].split('_')[0]
                for im in os.listdir(os.path.dirname(image_path)):
                    if im.startswith(unique_identifier+'_') and self.output_suffix not in im and any(im.endswith(imagetype) for imagetype in gf.imagetypes):
                        coalign_image_path = os.path.join(os.path.dirname(image_path), im)
                        if os.path.normpath(coalign_image_path) not in [os.path.normpath(p) for p in image_paths]:
                            coalign_output_basename = self.output_settings.get_basename(coalign_image_path)
                            coalign_image_paths.append(coalign_image_path)
                            coalign_output_basenames.append(coalign_output_basename)
                coalign_image_paths_list.append(coalign_image_paths)
                coalign_output_basenames_list.append(coalign_output_basenames)
        else:
            coalign_image_paths_list = [None]*len(image_paths)
            coalign_output_basenames_list = [None]*len(image_paths)

        input_files = image_paths.copy()
        output_files = [os.path.join(d, f) for d, f in zip(output_paths, output_basenames)]
        duplicates = [x for x, y in zip(input_files, output_files) if output_files.count(y) > 1]
        if len(duplicates) > 0:
            self.logger.error('More than one input file will output to the same file (output files will be overwritten).\nEither use input image folder as output folder or avoid processing images from different input folders.\nProblematic input files:\n%s', '\n'.join(duplicates[:4] + (['...'] if len(duplicates) > 4 else [])))
            return
        if coalignment:
            for image_path, output_path, coalign_output_basenames in zip(image_paths, output_paths, coalign_output_basenames_list):
                input_files += [image_path for f in coalign_output_basenames]
                output_files += [os.path.join(output_path, f) for f in coalign_output_basenames]
            duplicates = [x for x, y in zip(input_files, output_files) if output_files.count(y) > 1]
            duplicates = list(dict.fromkeys(duplicates))
            if len(duplicates) > 0:
                self.logger.error('More than one input file will output to the same file (output files will be overwritten).\nAvoid processing images with same unique identifier when co-aligning files with same unique identifier.\nProblematic input files:\n%s', '\n'.join(duplicates[:4] + (['...'] if len(duplicates) > 4 else [])))
                return

        # check input files are valid
        for path in input_files:
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
        for image_path, output_path, output_basename, coalign_image_paths, coalign_output_basenames in zip(image_paths, output_paths, output_basenames, coalign_image_paths_list, coalign_output_basenames_list):
            # collect arguments
            arguments.append((image_path, output_path, output_basename, channel_position, projection_type, projection_zrange, timepoint_range, skip_crop_decision, registration_method, coalign_image_paths, coalign_output_basenames))
        if not arguments:
            return
        nprocesses = min(len(arguments), self.nprocesses.value())
        self.logger.info("Using %s cores to perform registration", nprocesses)

        status_dialog = gf.StatusTableDialog(image_paths)
        status_dialog.ok_button.setEnabled(False)
        status_dialog.setModal(True)
        status_dialog.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.CustomizeWindowHint)
        status_dialog.show()
        QApplication.processEvents()
        time.sleep(0.01)

        with concurrent.futures.ProcessPoolExecutor(max_workers=nprocesses, initializer=process_initializer) as executor:
            future_reg = {executor.submit(f.registration_main, *args): i for i, args in enumerate(arguments)}
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

    def projection_mode_fixed_zmin_changed(self, value):
        self.projection_mode_fixed_zmax.setMinimum(value)

    def projection_mode_fixed_zmax_changed(self, value):
        self.projection_mode_fixed_zmin.setMaximum(value)

    def time_mode_fixed_tmin_changed(self, value):
        self.time_mode_fixed_tmax.setMinimum(value)

    def time_mode_fixed_tmax_changed(self, value):
        self.time_mode_fixed_tmin.setMaximum(value)


class Align(QWidget):
    def __init__(self, pipeline_layout=False):
        super().__init__()

        self.output_suffix = gf.output_suffixes['registration']

        self.pipeline_layout = pipeline_layout

        # Documentation
        label_documentation = gf.CollapsibleLabel('', collapsed=True)
        label_documentation.setText('For each input image, load a pre-existing transformation matrix, apply the transformation matrix to the input image and save the resulting registered image.<br>' +
                                    'The transformation matrix must be in the same folder as the input image. Matching between image and transformation matrix is based on the unique identifier, i.e. part of the filename before the first \"_\".<br>' +
                                    'Input images must have X, Y and T axes and can optionally have Z and/or C axes.<br>' +
                                    '<br>' +
                                    'Additional information: <a href="' + os.path.join(os.path.dirname(__file__), '..', '..', 'doc', 'site', 'registration_module', 'reference.html#alignment') + '">Documentation</a>')

        self.image_matrix_table = gf.ImageMatrixTableWidget2(filetypes=gf.imagetypes, filenames_filter='', filenames_exclude_filter=self.output_suffix)

        self.output_settings = gf.OutputSettings(extensions=['.ome.tif'], output_suffix=self.output_suffix, pipeline_layout=self.pipeline_layout)

        self.skip_cropping_yn = QCheckBox("Do NOT crop aligned image")
        self.submit_button = QPushButton("Submit")
        self.submit_button.clicked.connect(self.submit)

        self.nprocesses = QSpinBox()
        self.nprocesses.setMinimum(1)
        self.nprocesses.setMaximum(os.cpu_count())
        self.nprocesses.setValue(1)

        # Layout
        layout = QVBoxLayout()
        # Documentation
        groupbox = QGroupBox("Documentation")
        layout2 = QVBoxLayout()
        layout2.addWidget(label_documentation)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
        if not self.pipeline_layout:
            groupbox = QGroupBox('Images to align using pre-existing registration matrices')
            layout2 = QVBoxLayout()
            layout2.addWidget(self.image_matrix_table)
            groupbox.setLayout(layout2)
            layout.addWidget(groupbox)
        groupbox = QGroupBox("Output")
        layout2 = QVBoxLayout()
        layout2.addWidget(self.output_settings)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
        groupbox = QGroupBox("Options")
        layout2 = QVBoxLayout()
        layout2.addWidget(self.skip_cropping_yn)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
        if not self.pipeline_layout:
            groupbox = QGroupBox("Multi-processing")
            layout2 = QFormLayout()
            layout2.addRow("Number of processes:", self.nprocesses)
            groupbox.setLayout(layout2)
            layout.addWidget(groupbox)
            layout.addWidget(self.submit_button, alignment=Qt.AlignCenter)

        self.setLayout(layout)

        self.logger = logging.getLogger(__name__)

    def get_widgets_state(self):
        widgets_state = {
            'image_matrix_table': self.image_matrix_table.get_file_table(),
            'use_input_folder': self.output_settings.use_input_folder.isChecked(),
            'use_custom_folder': self.output_settings.use_custom_folder.isChecked(),
            'output_folder': self.output_settings.output_folder.text(),
            'output_user_suffix': self.output_settings.output_user_suffix.text(),
            'skip_cropping_yn': self.skip_cropping_yn.isChecked(),
            'nprocesses': self.nprocesses.value()}
        return widgets_state

    def set_widgets_state(self, widgets_state):
        self.image_matrix_table.set_file_table(widgets_state['image_matrix_table'])
        self.output_settings.use_input_folder.setChecked(widgets_state['use_input_folder'])
        self.output_settings.use_custom_folder.setChecked(widgets_state['use_custom_folder'])
        self.output_settings.output_folder.setText(widgets_state['output_folder'])
        self.output_settings.output_user_suffix.setText(widgets_state['output_user_suffix'])
        self.skip_cropping_yn.setChecked(widgets_state['skip_cropping_yn'])
        self.nprocesses.setValue(widgets_state['nprocesses'])

    def submit(self):
        image_matrix_paths = self.image_matrix_table.get_file_table()
        image_paths = [image_path for image_path, matrix_path in image_matrix_paths]
        matrix_paths = [matrix_path for image_path, matrix_path in image_matrix_paths]
        skip_crop_decision = self.skip_cropping_yn.isChecked()

        # check inputs
        if len(image_paths) == 0:
            self.logger.error('Image missing')
            return
        for path in image_paths:
            if not os.path.isfile(path):
                self.logger.error('Image not found\n%s', path)
                return
        if len(matrix_paths) == 0:
            self.logger.error('Matrix missing')
            return
        for path in matrix_paths:
            if not os.path.isfile(path):
                self.logger.error('Matrix not found\n%s', path)
                return
        # check input files are valid
        for path in image_paths:
            try:
                image = gf.Image(path)
            except Exception:
                self.logger.exception('Error loading:\n %s\n\nError message:', path)
                return

        output_basenames = [self.output_settings.get_basename(path) for path in image_paths]
        output_paths = [self.output_settings.get_path(path) for path in image_paths]
        output_files = [os.path.join(d, f) for d, f in zip(output_paths, output_basenames)]
        duplicates = [x for x, y in zip(image_paths, output_files) if output_files.count(y) > 1]
        if len(duplicates) > 0:
            self.logger.error('More than one input file will output to the same file (output files will be overwritten).\nEither use input image folder as output folder or avoid processing images from different input folders.\nProblematic input files:\n%s', '\n'.join(duplicates[:4] + (['...'] if len(duplicates) > 4 else [])))
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
        for image_path, matrix_path, output_path, output_basename in zip(image_paths, matrix_paths, output_paths, output_basenames):
            arguments.append((image_path, matrix_path, output_path, output_basename, skip_crop_decision))
        if not arguments:
            return
        nprocesses = min(len(arguments), self.nprocesses.value())

        status_dialog = gf.StatusTableDialog(image_paths)
        status_dialog.ok_button.setEnabled(False)
        status_dialog.setModal(True)
        status_dialog.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.CustomizeWindowHint)
        status_dialog.show()
        QApplication.processEvents()
        time.sleep(0.01)

        with concurrent.futures.ProcessPoolExecutor(max_workers=nprocesses, initializer=process_initializer) as executor:
            future_reg = {executor.submit(f.alignment_main, *args): i for i, args in enumerate(arguments)}
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


class ManualEdit(QWidget):
    def __init__(self):
        super().__init__()

        label_documentation = gf.CollapsibleLabel('', collapsed=True)
        label_documentation.setText('View and modify an existing transformation matrix in <a href="https://napari.org">napari</a>.<br>' +
                                    'Important: select an image that has not been registered.<br>' +
                                    'Input images must have X, Y and T axes and can optionally have Z and/or C axes.<br>' +
                                    '<br>' +
                                    'Additional information: <a href="' + os.path.join(os.path.dirname(__file__), '..', '..', 'doc', 'site', 'registration_module', 'reference.html#editing-manual') + '">Documentation</a>')
        self.input_image = gf.FileLineEdit(label='Images', filetypes=gf.imagetypes)
        self.input_image.textChanged.connect(self.input_image_changed)
        self.input_matrix = gf.FileLineEdit(label='Transformation matrices', filetypes=gf.matrixtypes)
        self.input_matrix.textChanged.connect(self.input_matrix_changed)
        self.button_submit = QPushButton('Submit')
        self.button_submit.clicked.connect(self.submit)

        # Layout
        layout = QVBoxLayout()
        groupbox = QGroupBox("Documentation")
        layout2 = QVBoxLayout()
        layout2.addWidget(label_documentation)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
        groupbox = QGroupBox("Input image (before registration)")
        layout2 = QVBoxLayout()
        layout2.addWidget(self.input_image)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
        groupbox = QGroupBox("Matrix to edit")
        layout2 = QVBoxLayout()
        layout2.addWidget(self.input_matrix)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
        layout.addWidget(self.button_submit, alignment=Qt.AlignCenter)

        self.setLayout(layout)

        self.logger = logging.getLogger(__name__)

    def input_image_changed(self):
        image_path = self.input_image.text()
        self.input_image.setPlaceholderText('')
        self.input_image.setToolTip('')
        self.input_matrix.setPlaceholderText('')
        self.input_matrix.setToolTip('')
        if os.path.isfile(image_path):
            # get path with matrix filetype (self.matricestype), containing gf.output_suffixes['registration'] and with same unique identifier
            matrix_paths = [path for path in os.listdir(os.path.dirname(image_path)) if any(path.endswith(matricestype) for matricestype in gf.matrixtypes) and gf.output_suffixes['registration'] in path and os.path.basename(path).split('_')[0] == gf.splitext(os.path.basename(image_path))[0].split('_')[0]]
            if len(matrix_paths) > 0:
                matrix_path = os.path.join(os.path.dirname(image_path), sorted(matrix_paths, key=len)[0])
                if os.path.isfile(matrix_path):
                    self.input_matrix.setPlaceholderText(matrix_path)
                    self.input_matrix.setToolTip(matrix_path)

    def input_matrix_changed(self):
        matrix_path = self.input_matrix.text()
        self.input_image.setPlaceholderText('')
        self.input_image.setToolTip('')
        self.input_matrix.setPlaceholderText('')
        self.input_matrix.setToolTip('')
        if os.path.isfile(matrix_path):
            res = re.match('(.*)'+gf.output_suffixes['registration']+'.*$', os.path.basename(matrix_path))
            if res:
                for ext in gf.imagetypes:
                    image_path = os.path.join(os.path.dirname(matrix_path), res.group(1)) + ext
                    if os.path.isfile(image_path):
                        self.input_image.setPlaceholderText(image_path)
                        self.input_image.setToolTip(image_path)
                        break

    def submit(self):
        image_path = self.input_image.text()
        if image_path == '':
            image_path = self.input_image.placeholderText()
        matrix_path = self.input_matrix.text()
        if matrix_path == '':
            matrix_path = self.input_matrix.placeholderText()

        if image_path == '':
            self.logger.error('Image missing')
            self.input_image.setFocus()
            return
        if not os.path.isfile(image_path):
            self.logger.error('Image not found %s', image_path)
            self.input_image.setFocus()
            return
        if matrix_path == '':
            self.logger.error('Matrix missing')
            self.input_matrix.setFocus()
            return
        if not os.path.isfile(matrix_path):
            self.logger.error('Matrix not found %s', matrix_path)
            self.input_matrix.setFocus()
            return

        self.logger.info('Manually editing %s (image: %s', matrix_path, image_path)
        try:
            f.manual_edit_main(image_path, matrix_path)
        except Exception:
            self.logger.exception('Manual editing failed')

        self.logger.info("Done")
