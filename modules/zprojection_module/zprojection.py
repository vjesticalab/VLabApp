import logging
import os
from PyQt5.QtWidgets import QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QGroupBox, QRadioButton, QApplication, QFileDialog, QComboBox, QSpinBox, QLabel, QFormLayout, QLineEdit
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCursor
from modules.zprojection_module import zprojection_functions as f
from general import general_functions as gf


class zProjection(QWidget):
    def __init__(self, pipeline_layout=False):
        super().__init__()

        self.output_suffix = gf.output_suffixes['zprojection']

        self.pipeline_layout = pipeline_layout

        # Documentation
        label_documentation = gf.CollapsibleLabel('', collapsed=True)
        label_documentation.setText('For each input image,  perform a z-stack projection and save the z-projected image.<br>' +
                                    'Input images must have X, Y and Z axes and can optionally have C and/or T axes.<br><br>' +
                                    'Additional information: <a href="' + os.path.join(os.path.dirname(__file__), "doc", "METHODS.html") + '">Methods</a>')

        # Input images
        self.image_list = gf.FileListWidget(filetypes=gf.imagetypes, filenames_filter='')

        # Output folders
        self.use_input_folder = QRadioButton("Use input file folder")
        self.use_input_folder.setChecked(True)
        self.use_input_folder.toggled.connect(self.update_output_filename_label)
        self.use_custom_folder = QRadioButton("Use custom folder (same for all the input files)")
        self.use_custom_folder.setChecked(False)
        self.use_custom_folder.toggled.connect(self.update_output_filename_label)
        self.output_folder = gf.DropFolderLineEdit()
        self.output_folder.textChanged.connect(self.update_output_filename_label)
        self.browse_button2 = QPushButton("Browse")
        self.browse_button2.clicked.connect(self.browse_output)
        self.output_folder.setVisible(self.use_custom_folder.isChecked())
        self.browse_button2.setVisible(self.use_custom_folder.isChecked())
        self.use_custom_folder.toggled.connect(self.output_folder.setVisible)
        self.use_custom_folder.toggled.connect(self.browse_button2.setVisible)
        self.output_filename_label = QLineEdit()
        self.output_filename_label.setFrame(False)
        self.output_filename_label.setEnabled(False)
        self.output_filename_label.textChanged.connect(self.output_filename_label.setToolTip)

        # Z-Projection range
        # only bestZ
        self.projection_mode_bestZ = QRadioButton("Z section with best focus")
        self.projection_mode_bestZ.setChecked(False)
        self.projection_mode_bestZ.setToolTip('Keep only Z section with best focus.')
        self.projection_mode_bestZ.toggled.connect(self.update_output_filename_label)
        # around bestZ
        self.projection_mode_around_bestZ = QRadioButton("Range around Z section with best focus")
        self.projection_mode_around_bestZ.setChecked(True)
        self.projection_mode_around_bestZ.setToolTip('Project all Z sections with Z in the interval [bestZ-range,bestZ+range], where bestZ is the Z section with best focus.')
        self.projection_mode_around_bestZ.toggled.connect(self.update_output_filename_label)
        self.projection_mode_around_bestZ_zrange = QSpinBox()
        self.projection_mode_around_bestZ_zrange.setMinimum(1)
        self.projection_mode_around_bestZ_zrange.setMaximum(20)
        self.projection_mode_around_bestZ_zrange.setValue(3)
        self.projection_mode_around_bestZ_zrange.valueChanged.connect(self.update_output_filename_label)
        # fixed range
        self.projection_mode_fixed = QRadioButton("Fixed range")
        self.projection_mode_fixed.setChecked(False)
        self.projection_mode_fixed.setToolTip('Project all Z sections with Z in the interval [from,to].')
        self.projection_mode_fixed.toggled.connect(self.update_output_filename_label)
        self.projection_mode_fixed_zmin = QSpinBox()
        self.projection_mode_fixed_zmin.setMinimum(0)
        self.projection_mode_fixed_zmin.setMaximum(20)
        self.projection_mode_fixed_zmin.setValue(4)
        self.projection_mode_fixed_zmin.valueChanged.connect(self.projection_mode_fixed_zmin_changed)
        self.projection_mode_fixed_zmin.valueChanged.connect(self.update_output_filename_label)
        self.projection_mode_fixed_zmax = QSpinBox()
        self.projection_mode_fixed_zmax.setMinimum(0)
        self.projection_mode_fixed_zmax.setMaximum(20)
        self.projection_mode_fixed_zmax.setValue(6)
        self.projection_mode_fixed_zmax.valueChanged.connect(self.projection_mode_fixed_zmax_changed)
        self.projection_mode_fixed_zmax.valueChanged.connect(self.update_output_filename_label)
        # all
        self.projection_mode_all = QRadioButton("All Z sections")
        self.projection_mode_all.setChecked(False)
        self.projection_mode_all.setToolTip('Project all Z sections.')
        self.projection_mode_all.toggled.connect(self.update_output_filename_label)
        # Z-Projection type
        self.projection_type = QComboBox()
        self.projection_type.addItem("max")
        self.projection_type.addItem("min")
        self.projection_type.addItem("mean")
        self.projection_type.addItem("median")
        self.projection_type.addItem("std")
        self.projection_type.setCurrentText("mean")
        self.projection_type.setDisabled(self.projection_mode_bestZ.isChecked())
        self.projection_type.currentTextChanged.connect(self.update_output_filename_label)
        self.projection_mode_bestZ.toggled.connect(self.projection_type.setDisabled)
        # Submit
        self.submit_button = QPushButton("Submit")
        self.submit_button.clicked.connect(self.submit)

        # Layout
        layout = QVBoxLayout()
        # Documentation
        groupbox = QGroupBox("Documentation")
        layout2 = QVBoxLayout()
        layout2.addWidget(label_documentation)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        # Input images
        if not self.pipeline_layout:
            groupbox = QGroupBox('Input files (images)')
            layout2 = QVBoxLayout()
            layout2.addWidget(self.image_list)
            groupbox.setLayout(layout2)
            layout.addWidget(groupbox)

        # Output folders
        groupbox = QGroupBox('Output')
        layout2 = QVBoxLayout()
        if not self.pipeline_layout:
            layout2.addWidget(QLabel("Folder:"))
            layout2.addWidget(self.use_input_folder)
            layout2.addWidget(self.use_custom_folder)
            layout3 = QHBoxLayout()
            layout3.addWidget(self.output_folder)
            layout3.addWidget(self.browse_button2, alignment=Qt.AlignCenter)
            layout2.addLayout(layout3)
        layout3 = QFormLayout()
        layout3.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        suffix = QLineEdit(self.output_suffix+"<projection>")
        suffix.setDisabled(True)
        suffix.setFixedWidth(suffix.fontMetrics().width(suffix.text()+"  "))
        suffix.setAlignment(Qt.AlignRight)
        layout3.addRow("Suffix:", suffix)
        layout3.addRow("Filename:", self.output_filename_label)
        layout2.addLayout(layout3)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        groupbox = QGroupBox("Options")
        layout2 = QFormLayout()
        # Z-Projection range
        widget = QWidget()
        layout3 = QVBoxLayout()
        # only bestZ
        layout3.addWidget(self.projection_mode_bestZ)
        # around bestZ
        layout3.addWidget(self.projection_mode_around_bestZ)
        groupbox2 = QGroupBox()
        groupbox2.setToolTip('Project all Z sections with Z in the interval [bestZ-range,bestZ+range], where bestZ is the Z section with best focus.')
        groupbox2.setVisible(self.projection_mode_around_bestZ.isChecked())
        self.projection_mode_around_bestZ.toggled.connect(groupbox2.setVisible)
        layout4 = QFormLayout()
        layout4.addRow("Range:", self.projection_mode_around_bestZ_zrange)
        groupbox2.setLayout(layout4)
        layout3.addWidget(groupbox2)
        # fixed range
        layout3.addWidget(self.projection_mode_fixed)
        groupbox2 = QGroupBox()
        groupbox2.setToolTip('Project all Z sections with Z in the interval [from,to].')
        groupbox2.setVisible(self.projection_mode_fixed.isChecked())
        self.projection_mode_fixed.toggled.connect(groupbox2.setVisible)
        layout4 = QHBoxLayout()
        layout5 = QFormLayout()
        layout5.addRow("From:", self.projection_mode_fixed_zmin)
        layout4.addLayout(layout5)
        layout5 = QFormLayout()
        layout5.addRow("To:", self.projection_mode_fixed_zmax)
        layout4.addLayout(layout5)
        groupbox2.setLayout(layout4)
        layout3.addWidget(groupbox2)
        # all
        layout3.addWidget(self.projection_mode_all)
        widget.setLayout(layout3)
        layout2.addRow("Projection range:", widget)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
        # Z-Projection type
        layout2.addRow("Projection type:", self.projection_type)

        # Submit
        if not self.pipeline_layout:
            layout.addWidget(self.submit_button, alignment=Qt.AlignCenter)

        self.setLayout(layout)

        self.logger = logging.getLogger(__name__)

        self.update_output_filename_label()

    def browse_output(self):
        # Browse folders in order to choose the output one
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder_path != '':
            self.output_folder.setText(folder_path)

    def projection_mode_fixed_zmin_changed(self, value):
        if self.projection_mode_fixed_zmax.value() < value:
            self.projection_mode_fixed_zmax.setValue(value)

    def projection_mode_fixed_zmax_changed(self, value):
        if self.projection_mode_fixed_zmin.value() > value:
            self.projection_mode_fixed_zmin.setValue(value)

    def update_output_filename_label(self):
        if self.pipeline_layout:
            output_path = "<output folder>"
        elif self.use_input_folder.isChecked():
            output_path = "<input folder>"
        else:
            output_path = self.output_folder.text().rstrip("/")
        projection_type = self.projection_type.currentText()
        if self.projection_mode_bestZ.isChecked():
            projection_zrange = 0
        elif self.projection_mode_around_bestZ.isChecked():
            projection_zrange = self.projection_mode_around_bestZ_zrange.value()
        elif self.projection_mode_fixed.isChecked():
            projection_zrange = (self.projection_mode_fixed_zmin.value(), self.projection_mode_fixed_zmax.value())
        elif self.projection_mode_all.isChecked():
            projection_zrange = None
        projection_suffix = self.get_projection_suffix(None, projection_zrange, projection_type)

        self.output_filename_label.setText(os.path.join(output_path, "<input basename>" + self.output_suffix + projection_suffix+".ome.tif"))

    def get_projection_suffix(self, image_path, projection_zrange, projection_type):
        if projection_zrange is None:
            if image_path is not None:
                im = gf.Image(image_path)
                maxZ = im.sizes['Z']
            else:
                maxZ = 11
            output_suffix_reference = 'f'
            output_suffix_range = '0-'+str(maxZ)
            output_suffix_projection_type = projection_type
        elif isinstance(projection_zrange, int):
            output_suffix_reference = 'b'
            output_suffix_range = str(projection_zrange)
            if projection_zrange > 0:
                output_suffix_projection_type = projection_type
            else:
                output_suffix_projection_type = 'none'
        elif isinstance(projection_zrange, tuple) and len(projection_zrange):
            output_suffix_reference = 'f'
            output_suffix_range = str(min(projection_zrange)) + '-' + str(max(projection_zrange))
            if max(projection_zrange) > min(projection_zrange):
                output_suffix_projection_type = projection_type
            else:
                output_suffix_projection_type = 'none'
        else:
            self.logger.error('Invalid projection_zrange: %s', str(projection_zrange))
            raise TypeError(f"Invalid projection_zrange: {projection_zrange}")
        return output_suffix_reference + output_suffix_range + output_suffix_projection_type

    def get_widgets_state(self):
        widgets_state = {
            'image_list': self.image_list.get_file_list(),
            'use_input_folder': self.use_input_folder.isChecked(),
            'use_custom_folder': self.use_custom_folder.isChecked(),
            'output_folder': self.output_folder.text(),
            'projection_mode_bestZ': self.projection_mode_bestZ.isChecked(),
            'projection_mode_around_bestZ': self.projection_mode_around_bestZ.isChecked(),
            'projection_mode_around_bestZ_zrange': self.projection_mode_around_bestZ_zrange.value(),
            'projection_mode_fixed': self.projection_mode_fixed.isChecked(),
            'projection_mode_fixed_zmin': self.projection_mode_fixed_zmin.value(),
            'projection_mode_fixed_zmax': self.projection_mode_fixed_zmax.value(),
            'projection_mode_all': self.projection_mode_all.isChecked(),
            'projection_type': self.projection_type.currentText()}
        return widgets_state

    def set_widgets_state(self, widgets_state):
        self.image_list.set_file_list(widgets_state['image_list'])
        self.use_input_folder.setChecked(widgets_state['use_input_folder'])
        self.use_custom_folder.setChecked(widgets_state['use_custom_folder'])
        self.output_folder.setText(widgets_state['output_folder'])
        self.projection_mode_bestZ.setChecked(widgets_state['projection_mode_bestZ'])
        self.projection_mode_around_bestZ.setChecked(widgets_state['projection_mode_around_bestZ'])
        self.projection_mode_around_bestZ_zrange.setValue(widgets_state['projection_mode_around_bestZ_zrange'])
        self.projection_mode_fixed.setChecked(widgets_state['projection_mode_fixed'])
        self.projection_mode_fixed_zmin.setValue(widgets_state['projection_mode_fixed_zmin'])
        self.projection_mode_fixed_zmax.setValue(widgets_state['projection_mode_fixed_zmax'])
        self.projection_mode_all.setChecked(widgets_state['projection_mode_all'])
        self.projection_type.setCurrentText(widgets_state['projection_type'])

    def submit(self):
        """
        Retrieve the input parameters
        Iterate over the image paths given performing projection with f.main() function
        """
        def check_inputs(image_paths, output_paths, output_basenames):
            """
            Check if the inputs are valid
            Return: True if valid, False otherwise
            """
            if len(image_paths) == 0:
                self.logger.error('Image missing')
                return False
            for path in image_paths:
                if not os.path.isfile(path):
                    self.logger.error('Image not found: %s', path)
                    return False
            if self.output_folder.text() == '' and not self.use_input_folder.isChecked():
                self.logger.error('Output folder missing')
                self.output_folder.setFocus()
                return False
            output_files = [os.path.join(d, f) for d, f in zip(output_paths, output_basenames)]
            duplicates = [x for x, y in zip(image_paths, output_files) if output_files.count(y) > 1]
            if len(duplicates) > 0:
                self.logger.error('More than one input file will output to the same file (output files will be overwritten).\nEither use input image folder as output folder or avoid processing images from different input folders.\nProblematic input files:\n%s', '\n'.join(duplicates[:4] + (['...'] if len(duplicates) > 4 else [])))
                return False
            return True

        projection_type = self.projection_type.currentText()
        if self.projection_mode_bestZ.isChecked():
            projection_zrange = 0
        elif self.projection_mode_around_bestZ.isChecked():
            projection_zrange = self.projection_mode_around_bestZ_zrange.value()
        elif self.projection_mode_fixed.isChecked():
            projection_zrange = (self.projection_mode_fixed_zmin.value(), self.projection_mode_fixed_zmax.value())
        elif self.projection_mode_all.isChecked():
            projection_zrange = None

        image_paths = self.image_list.get_file_list()
        # prepare output suffix (incl. projection)
        output_basenames = [gf.splitext(os.path.basename(path))[0] + self.output_suffix + self.get_projection_suffix(path, projection_zrange, projection_type) for path in image_paths]
        if self.use_input_folder.isChecked():
            output_paths = [os.path.dirname(path) for path in image_paths]
        else:
            output_paths = [self.output_folder.text() for path in image_paths]

        if not check_inputs(image_paths, output_paths, output_basenames):
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
        for image_path, output_path, output_basename in zip(image_paths, output_paths, output_basenames):
            # Set output directory for each image path
            if not output_path.endswith('/'):
                output_path += '/'
            if not os.path.exists(output_path):
                os.makedirs(output_path)
            # Set log and cursor info
            self.logger.info("Image %s", image_path)
            QApplication.setOverrideCursor(QCursor(Qt.BusyCursor))
            QApplication.processEvents()
            # Perform projection
            try:
                f.main(image_path, output_path, output_basename, projection_type, projection_zrange)
                status.append("Success")
                error_messages.append(None)
            except Exception as e:
                status.append("Failed")
                error_messages.append(str(e))
                self.logger.exception("Projection failed")
            # Restore cursor
            QApplication.restoreOverrideCursor()

        if any(s != 'Success' for s in status):
            msg = gf.StatusTableDialog('Warning', status, error_messages, image_paths)
            msg.exec_()

        # re-enable messagebox error handler
        if messagebox_error_handler is not None:
            logging.getLogger().addHandler(messagebox_error_handler)

        self.logger.info("Done")
