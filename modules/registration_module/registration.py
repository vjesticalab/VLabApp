import os
import re
import logging
import concurrent.futures
from PyQt5.QtCore import Qt, QRegExp
from PyQt5.QtWidgets import QCheckBox, QComboBox, QFormLayout, QPushButton, QVBoxLayout, QWidget, QGridLayout, QLabel, QLineEdit, QHBoxLayout, QApplication, QSpinBox, QRadioButton, QGroupBox, QFileDialog
from PyQt5.QtGui import QCursor, QIntValidator, QRegExpValidator
import numpy as np
import matplotlib
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from modules.registration_module import registration_functions as f
from general import general_functions as gf

matplotlib.use("Qt5Agg")


class Perform(QWidget):
    def __init__(self, pipeline_layout=False):
        super().__init__()

        self.output_suffix = gf.output_suffixes['registration']

        self.pipeline_layout = pipeline_layout

        # Documentation
        label_documentation = gf.CollapsibleLabel('', collapsed=True)
        label_documentation.setText('For each input image, estimate the shift between consecutive time frames, apply the resulting transformation matrix to the input image. Save the transformation matrix and the registered image.<br>' +
                                    'Input images must have X, Y and T axes. Images with additional Z and/or C axis are supported (Z axis will be projected and only the chosen channel will be selected before evaluating the transformation).<br><br>' +
                                    'Additional information: <a href="' + os.path.join(os.path.dirname(__file__), "doc", "METHODS.html") + '">Methods</a>')

        self.image_list = gf.FileListWidget(filetypes=gf.imagetypes, filenames_filter='_BF', filenames_exclude_filter=self.output_suffix)
        self.channel_position = QSpinBox()
        self.channel_position.setMinimum(0)
        self.channel_position.setMaximum(100)
        self.channel_position.setValue(0)

        self.use_input_folder = QRadioButton("Use input image folder")
        self.use_input_folder.setChecked(True)
        self.use_input_folder.toggled.connect(self.update_output_filename_label)
        self.use_custom_folder = QRadioButton("Use custom folder (same for all the input files)")
        self.use_custom_folder.setChecked(False)
        self.use_custom_folder.toggled.connect(self.update_output_filename_label)
        self.output_folder = gf.FolderLineEdit()
        self.output_folder.textChanged.connect(self.update_output_filename_label)
        self.output_folder.setVisible(self.use_custom_folder.isChecked())
        self.use_custom_folder.toggled.connect(self.output_folder.setVisible)
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
        self.register_button = QPushButton("Register")
        self.register_button.clicked.connect(self.register)
        self.n_count = QSpinBox()
        self.n_count.setMinimum(1)
        self.n_count.setMaximum(os.cpu_count())
        self.n_count.setValue(1)
        n_count_label = QLabel("Number of processes:")

        # T-range
        # all
        self.time_mode_all = QRadioButton("All timepoints")
        self.time_mode_all.setChecked(True)
        # fixed range
        self.time_mode_fixed = QRadioButton("Timepoint range")
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
        if not self.pipeline_layout:
            layout2.addWidget(QLabel("Folder:"))
            layout2.addWidget(self.use_input_folder)
            layout2.addWidget(self.use_custom_folder)
            layout2.addWidget(self.output_folder)
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
            layout2.addRow(n_count_label, self.n_count)
            groupbox.setLayout(layout2)
            layout.addWidget(groupbox)
            layout.addWidget(self.register_button, alignment=Qt.AlignCenter)

        self.setLayout(layout)

        self.logger = logging.getLogger(__name__)

        self.update_output_filename_label()

    def get_widgets_state(self):
        widgets_state = {
            'image_list': self.image_list.get_file_list(),
            'use_input_folder': self.use_input_folder.isChecked(),
            'use_custom_folder': self.use_custom_folder.isChecked(),
            'output_folder': self.output_folder.text(),
            'output_user_suffix': self.output_user_suffix.text(),
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
            'n_count': self.n_count.value()}
        return widgets_state

    def set_widgets_state(self, widgets_state):
        self.image_list.set_file_list(widgets_state['image_list'])
        self.use_input_folder.setChecked(widgets_state['use_input_folder'])
        self.use_custom_folder.setChecked(widgets_state['use_custom_folder'])
        self.output_folder.setText(widgets_state['output_folder'])
        self.output_user_suffix.setText(widgets_state['output_user_suffix'])
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
        self.n_count.setValue(widgets_state['n_count'])

    def register(self):
        """
        Consider Unique Identifier as split('_')[0]
        """
        def check_inputs(image_paths):
            """
            Check if the inputs are valid
            Return: True if valid, False otherwise
            """
            if len(image_paths) == 0:
                self.logger.error('Image missing')
                return False
            for path in image_paths:
                if not os.path.isfile(path):
                    self.logger.error('Image not found\n%s', path)
                    return False
            return True

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

        if not check_inputs(image_paths):
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

        # first step: evaluate transformation matrix and align image
        status = []
        error_messages = []
        arguments = []
        if self.use_input_folder.isChecked():
            output_paths = [os.path.dirname(path) for path in image_paths]
        else:
            output_paths = [self.output_folder.text() for path in image_paths]
        user_suffix = self.output_user_suffix.text()
        output_basenames = [gf.splitext(os.path.basename(path))[0] + self.output_suffix + user_suffix for path in image_paths]
        for image_path, output_path, output_basename in zip(image_paths, output_paths, output_basenames):
            # collect arguments
            arguments.append((image_path, output_path, output_basename, channel_position, projection_type, projection_zrange, timepoint_range, skip_crop_decision, registration_method))
        if not arguments:
            return
        n_count = min(len(arguments), self.n_count.value())
        self.logger.info("Using: %s cores to perform registration", n_count)
        # Perform projection
        if len(arguments) == 1:
            try:
                f.registration_main(*arguments[0])
                status.append("Success")
                error_messages.append("")
            except Exception as e:
                status.append("Failed")
                error_messages.append(str(e))
                self.logger.exception("Registration failed")
        else:
            # we go parallel
            with concurrent.futures.ProcessPoolExecutor(max_workers=n_count) as executor:
                future_reg = {
                    executor.submit(f.registration_main, *args): args for args in arguments
                }
                for future in future_reg:
                    try:
                        image_path = future.result()
                        status.append("Success")
                        error_messages.append("")
                    except Exception as e:
                        status.append("Failed")
                        error_messages.append(str(e))
                        self.logger.exception("An exception occurred")
                    else:
                        self.logger.info(" Image: %s Done", image_path)

        # second step: coalign other images
        if coalignment:
            status_alignment = []
            error_messages_alignment = []
            map_run_to_image_no = []
            arguments = []
            if self.use_input_folder.isChecked():
                output_paths = [os.path.dirname(path) for path in image_paths]
            else:
                output_paths = [self.output_folder.text() for path in image_paths]
            user_suffix = self.output_user_suffix.text()
            output_basenames = [gf.splitext(os.path.basename(path))[0] + self.output_suffix + user_suffix for path in image_paths]
            for n, (image_path, output_path, output_basename) in enumerate(zip(image_paths, output_paths, output_basenames)):
                if status[n] == "Success":
                    tmat_path = os.path.join(output_path, output_basename+'.csv')
                    # keep files with same unique identifier, extension in gf.imagetypes, not already aligned (i.e. filename does not contain self.output_suffix)
                    unique_identifier = os.path.basename(image_path).split('_')[0]
                    for im in os.listdir(os.path.dirname(image_path)):
                        if im.startswith(unique_identifier) and self.output_suffix not in im and any(im.endswith(imagetype) for imagetype in gf.imagetypes):
                            coalign_image_path = os.path.join(os.path.dirname(image_path), im)
                            if coalign_image_path not in image_paths:
                                coalignment_output_basename = gf.splitext(os.path.basename(coalign_image_path))[0] + self.output_suffix + user_suffix
                                map_run_to_image_no.append(n)
                                arguments.append((coalign_image_path, tmat_path, output_path, coalignment_output_basename, skip_crop_decision))
            if arguments:
                n_count = min(len(arguments), self.n_count.value())
                self.logger.info("Using: %s cores to perform alignment", n_count)
                # Perform alignment
                if len(arguments) == 1:
                    try:
                        f.alignment_main(*arguments[0])
                        status_alignment.append("Success")
                        error_messages_alignment.append("")
                    except Exception as e:
                        status_alignment.append("Failed")
                        error_messages_alignment.append(str(e))
                        self.logger.exception("Registration failed")
                else:
                    # we go parallel
                    with concurrent.futures.ProcessPoolExecutor(max_workers=n_count) as executor:
                        future_reg = {
                            executor.submit(f.alignment_main, *args): args for args in arguments
                        }
                        for future in future_reg:
                            try:
                                image_path = future.result()
                                status_alignment.append("Success")
                                error_messages_alignment.append("")
                            except Exception as e:
                                status_alignment.append("Failed")
                                error_messages_alignment.append(str(e))
                                self.logger.exception("An exception occurred")
                            else:
                                self.logger.info(" Image: %s Done", image_path)

                # collect statuses and error_messages
                for m, s in enumerate(status_alignment):
                    n = map_run_to_image_no[m]
                    if s != "Success":
                        status[n] = s
                for m, e in enumerate(error_messages_alignment):
                    n = map_run_to_image_no[m]
                    if e != "":
                        error_messages[n] = error_messages[n] + "\n" + e

        # Restore cursor
        QApplication.restoreOverrideCursor()

        if any(s != 'Success' for s in status):
            msg = gf.StatusTableDialog('Warning', status, error_messages, image_paths)
            msg.exec_()

        # re-enable messagebox error handler
        if messagebox_error_handler is not None:
            logging.getLogger().addHandler(messagebox_error_handler)

        self.logger.info("Done")

    def update_output_filename_label(self):
        if self.pipeline_layout:
            output_path = "<output folder>"
        elif self.use_input_folder.isChecked():
            output_path = "<input folder>"
        else:
            output_path = os.path.abspath(self.output_folder.text())

        self.output_filename_label1.setText(os.path.normpath(os.path.join(output_path, "<input basename>" + self.output_suffix + self.output_user_suffix.text() + ".csv")))
        self.output_filename_label2.setText(os.path.normpath(os.path.join(output_path, "<input basename>" + self.output_suffix + self.output_user_suffix.text() + ".ome.tif")))

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
                                    'Input images must have X, Y and T axes and can optionally have Z and/or C axes.')

        self.image_matrix_table = gf.ImageMatrixTableWidget2(filetypes=gf.imagetypes, filenames_filter='', filenames_exclude_filter=self.output_suffix)

        self.use_input_folder = QRadioButton("Use input image folder")
        self.use_input_folder.setChecked(True)
        self.use_input_folder.toggled.connect(self.update_output_filename_label)
        self.use_custom_folder = QRadioButton("Use custom folder (same for all the input files)")
        self.use_custom_folder.setChecked(False)
        self.use_custom_folder.toggled.connect(self.update_output_filename_label)
        self.output_folder = gf.FolderLineEdit()
        self.output_folder.textChanged.connect(self.update_output_filename_label)
        self.output_folder.setVisible(self.use_custom_folder.isChecked())
        self.use_custom_folder.toggled.connect(self.output_folder.setVisible)
        self.output_user_suffix = QLineEdit()
        self.output_user_suffix.setToolTip('Allowed characters: A-Z, a-z, 0-9 and -')
        self.output_user_suffix.setValidator(QRegExpValidator(QRegExp('[A-Za-z0-9-]*')))
        self.output_user_suffix.textChanged.connect(self.update_output_filename_label)
        self.output_filename_label = QLineEdit()
        self.output_filename_label.setFrame(False)
        self.output_filename_label.setEnabled(False)

        self.skip_cropping_yn = QCheckBox("Do NOT crop aligned image")
        self.align_button = QPushButton("Align")
        self.align_button.clicked.connect(self.align)

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
        if not self.pipeline_layout:
            layout2.addWidget(QLabel("Folder:"))
            layout2.addWidget(self.use_input_folder)
            layout2.addWidget(self.use_custom_folder)
            layout2.addWidget(self.output_folder)
        layout3 = QFormLayout()
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
        layout4.addWidget(self.output_filename_label)
        layout3.addRow("Filename:", layout4)
        layout2.addLayout(layout3)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
        groupbox = QGroupBox("Options")
        layout2 = QVBoxLayout()
        layout2.addWidget(self.skip_cropping_yn)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
        if not self.pipeline_layout:
            layout.addWidget(self.align_button, alignment=Qt.AlignCenter)

        self.setLayout(layout)

        self.logger = logging.getLogger(__name__)

        self.update_output_filename_label()

    def update_output_filename_label(self):
        if self.pipeline_layout:
            output_path = "<output folder>"
        elif self.use_input_folder.isChecked():
            output_path = "<input folder>"
        else:
            output_path = os.path.abspath(self.output_folder.text())

        self.output_filename_label.setText(os.path.normpath(os.path.join(output_path, "<input basename>" + self.output_suffix + self.output_user_suffix.text() + ".ome.tif")))

    def get_widgets_state(self):
        widgets_state = {
            'image_matrix_table': self.image_matrix_table.get_file_table(),
            'use_input_folder': self.use_input_folder.isChecked(),
            'use_custom_folder': self.use_custom_folder.isChecked(),
            'output_folder': self.output_folder.text(),
            'output_user_suffix': self.output_user_suffix.text(),
            'skip_cropping_yn': self.skip_cropping_yn.isChecked()}
        return widgets_state

    def set_widgets_state(self, widgets_state):
        self.image_matrix_table.set_file_table(widgets_state['image_matrix_table'])
        self.use_input_folder.setChecked(widgets_state['use_input_folder'])
        self.use_custom_folder.setChecked(widgets_state['use_custom_folder'])
        self.output_folder.setText(widgets_state['output_folder'])
        self.output_user_suffix.setText(widgets_state['output_user_suffix'])
        self.skip_cropping_yn.setChecked(widgets_state['skip_cropping_yn'])

    def align(self):
        def check_inputs(image_paths, matrix_paths):
            """
            Check if the inputs are valid
            Return: True if valid, False otherwise
            """
            if len(image_paths) == 0:
                self.logger.error('Image missing')
                return False
            for path in image_paths:
                if not os.path.isfile(path):
                    self.logger.error('Image not found\n%s', path)
                    return False
            if len(matrix_paths) == 0:
                self.logger.error('Matrix missing')
                return False
            for path in matrix_paths:
                if not os.path.isfile(path):
                    self.logger.error('Matrix not found\n%s', path)
                    return False
            return True

        image_matrix_paths = self.image_matrix_table.get_file_table()
        image_paths = [image_path for image_path, matrix_path in image_matrix_paths]
        matrix_paths = [matrix_path for image_path, matrix_path in image_matrix_paths]
        skip_crop_decision = self.skip_cropping_yn.isChecked()
        if not check_inputs(image_paths, matrix_paths):
            return

        user_suffix = self.output_user_suffix.text()
        output_basenames = [gf.splitext(os.path.basename(path))[0] + self.output_suffix + user_suffix for path in image_paths]
        if self.use_input_folder.isChecked():
            output_paths = [os.path.dirname(path) for path in image_paths]
        else:
            output_paths = [self.output_folder.text() for path in image_paths]

        # disable messagebox error handler
        messagebox_error_handler = None
        for h in logging.getLogger().handlers:
            if h.get_name() == 'messagebox_error_handler':
                messagebox_error_handler = h
                logging.getLogger().removeHandler(messagebox_error_handler)
                break

        status = []
        error_messages = []
        for image_path, matrix_path, output_path, output_basename in zip(image_paths, matrix_paths, output_paths, output_basenames):
            if os.path.isfile(image_path):
                # Set log and cursor info
                self.logger.info("Image %s", image_path)
                QApplication.setOverrideCursor(QCursor(Qt.BusyCursor))
                QApplication.processEvents()
                # Perform projection
                try:
                    f.alignment_main(image_path, matrix_path, output_path, output_basename, skip_crop_decision)
                    status.append("Success")
                    error_messages.append(None)
                except Exception as e:
                    status.append("Failed")
                    error_messages.append(str(e))
                    self.logger.exception("Alignment failed")
                # Restore cursor
                QApplication.restoreOverrideCursor()
                self.logger.info("Done")
            else:
                self.logger.error("Unable to locate file %s", image_path)

        if any(s != 'Success' for s in status):
            msg = gf.StatusTableDialog('Warning', status, error_messages, image_paths)
            msg.exec_()

        # re-enable messagebox error handler
        if messagebox_error_handler is not None:
            logging.getLogger().addHandler(messagebox_error_handler)


class Edit(QWidget):
    def __init__(self):
        super().__init__()

        self.output_suffix = gf.output_suffixes['registration']

        label_documentation = gf.CollapsibleLabel('', collapsed=True)
        label_documentation.setText('Modify the start and end point of existing transformation matrices.')
        self.matrices_list = gf.FileListWidget(filetypes=gf.matrixtypes, filenames_filter=self.output_suffix)
        self.tmin = QSpinBox()
        self.tmin.setMinimum(0)
        self.tmin.setMaximum(1000)
        self.tmin.valueChanged.connect(self.tmin_changed)
        self.tmax = QSpinBox()
        self.tmax.setMinimum(0)
        self.tmax.setMaximum(1000)
        self.tmax.setValue(1000)
        self.tmax.valueChanged.connect(self.tmax_changed)
        self.edit_button = QPushButton('Edit')
        self.edit_button.clicked.connect(self.edit)

        # Layout
        layout = QVBoxLayout()
        # Documentation
        groupbox = QGroupBox("Documentation")
        layout2 = QVBoxLayout()
        layout2.addWidget(label_documentation)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
        groupbox = QGroupBox('Matrices to edit')
        layout2 = QVBoxLayout()
        layout2.addWidget(self.matrices_list)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
        groupbox = QGroupBox('New timepoint range')
        layout2 = QHBoxLayout()
        layout3 = QFormLayout()
        layout3.addRow("From:", self.tmin)
        layout2.addLayout(layout3)
        layout3 = QFormLayout()
        layout3.addRow("To:", self.tmax)
        layout2.addLayout(layout3)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
        layout.addWidget(self.edit_button, alignment=Qt.AlignCenter)

        self.setLayout(layout)

        self.logger = logging.getLogger(__name__)

    def tmin_changed(self, value):
        self.tmax.setMinimum(value)

    def tmax_changed(self, value):
        self.tmin.setMaximum(value)

    def edit(self):
        def check_inputs(transfmat_paths):
            """
            Check if the inputs are valid
            Return: True if valid, False otherwise
            """
            if len(transfmat_paths) == 0:
                self.logger.error('Matrix missing')
                return False
            for path in transfmat_paths:
                if not os.path.isfile(path):
                    self.logger.error('Matrix not found\n%s', path)
                    return False
            return True

        transfmat_paths = self.matrices_list.get_file_list()
        start_timepoint = self.tmin.value()
        end_timepoint = self.tmax.value()

        if not check_inputs(transfmat_paths):
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

        status = []
        error_messages = []
        for transfmat_path in transfmat_paths:
            try:
                f.edit_main(transfmat_path, int(start_timepoint), int(end_timepoint))
                status.append("Success")
                error_messages.append("")
            except Exception as e:
                status.append("Failed")
                error_messages.append(str(e))
                self.logger.exception("Editing failed")

        # Restore cursor
        QApplication.restoreOverrideCursor()

        if any(s != 'Success' for s in status):
            msg = gf.StatusTableDialog('Warning', status, error_messages, transfmat_paths)
            msg.exec_()

        # re-enable messagebox error handler
        if messagebox_error_handler is not None:
            logging.getLogger().addHandler(messagebox_error_handler)


class ManualEdit(QWidget):
    def __init__(self):
        super().__init__()

        label_documentation = gf.CollapsibleLabel('', collapsed=True)
        label_documentation.setText('View and modify an existing transformation matrix in <a href="https://napari.org">napari</a>.<br>' +
                                    'Important: select an image that has not been registered.<br>' +
                                    'Input images must have X, Y and T axes and can optionally have Z and/or C axes.')
        self.input_image = gf.FileLineEdit(label='Images', filetypes=gf.imagetypes)
        self.input_image.textChanged.connect(self.input_image_changed)
        self.input_matrix = gf.FileLineEdit(label='Transformation matrices', filetypes=gf.matrixtypes)
        self.input_matrix.textChanged.connect(self.input_matrix_changed)
        self.button_edit = QPushButton('Edit')
        self.button_edit.clicked.connect(self.edit)

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
        layout.addWidget(self.button_edit, alignment=Qt.AlignCenter)

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
            matrix_paths = [path for path in os.listdir(os.path.dirname(image_path)) if any(path.endswith(matricestype) for matricestype in gf.matrixtypes) and gf.output_suffixes['registration'] in path and os.path.basename(path).split('_')[0] == os.path.basename(image_path).split('_')[0]]
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

    def edit(self):
        def check_inputs(image_path, matrix_path):
            """
            Check if the inputs are valid
            Return: True if valid, False otherwise
            """
            if image_path == '':
                self.logger.error('Image missing')
                self.input_image.setFocus()
                return False
            if not os.path.isfile(image_path):
                self.logger.error('Image not found %s', image_path)
                self.input_image.setFocus()
                return False
            if matrix_path == '':
                self.logger.error('Matrix missing')
                self.input_matrix.setFocus()
                return False
            if not os.path.isfile(matrix_path):
                self.logger.error('Matrix not found %s', matrix_path)
                self.input_matrix.setFocus()
                return False
            return True

        image_path = self.input_image.text()
        if image_path == '':
            image_path = self.input_image.placeholderText()
        matrix_path = self.input_matrix.text()
        if matrix_path == '':
            matrix_path = self.input_matrix.placeholderText()

        if not check_inputs(image_path, matrix_path):
            return
        self.logger.info('Manually editing %s (image: %s', matrix_path, image_path)
        try:
            f.manual_edit_main(image_path, matrix_path)
        except Exception:
            self.logger.exception('Manual editing failed')

        self.logger.info("Done")
