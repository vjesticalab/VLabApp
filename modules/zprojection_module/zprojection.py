import logging
import os
from PyQt5.QtWidgets import QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QGroupBox, QRadioButton, QApplication, QFileDialog, QComboBox, QSpinBox, QLabel, QFormLayout
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCursor
from modules.zprojection_module import zprojection_functions as f
from general import general_functions as gf


class zProjection(QWidget):
    def __init__(self):
        super().__init__()

        # Documentation
        label_documentation = QLabel()
        label_documentation.setOpenExternalLinks(True)
        label_documentation.setText('<a href="file://' + os.path.join(os.path.dirname(__file__), "doc", "METHODS.html") + '">Methods</a>')

        # Input images
        self.imagetypes = ['.nd2', '.tif', '.tiff']
        self.image_list = gf.FileListWidget(filetypes=self.imagetypes, filenames_filter='')

        # Output folders
        self.use_input_folder = QRadioButton("Use input image folder (zprojection sub-folder)")
        self.use_input_folder.setChecked(True)
        self.use_custom_folder = QRadioButton("Use custom folder:")
        self.use_custom_folder.setChecked(False)
        self.output_folder = gf.DropFolderLineEdit()
        self.browse_button2 = QPushButton("Browse", self)
        self.browse_button2.clicked.connect(self.browse_output)
        self.output_folder.setEnabled(self.use_custom_folder.isChecked())
        self.browse_button2.setEnabled(self.use_custom_folder.isChecked())
        self.use_custom_folder.toggled.connect(self.output_folder.setEnabled)
        self.use_custom_folder.toggled.connect(self.browse_button2.setEnabled)

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
        self.projection_mode_fixed_zmin.setMaximum(20)
        self.projection_mode_fixed_zmin.setValue(4)
        self.projection_mode_fixed_zmin.valueChanged.connect(self.projection_mode_fixed_zmin_changed)
        self.projection_mode_fixed_zmax = QSpinBox()
        self.projection_mode_fixed_zmax.setMinimum(0)
        self.projection_mode_fixed_zmax.setMaximum(20)
        self.projection_mode_fixed_zmax.setValue(6)
        self.projection_mode_fixed_zmax.valueChanged.connect(self.projection_mode_fixed_zmax_changed)
        # all
        self.projection_mode_all = QRadioButton("All Z sections")
        self.projection_mode_all.setChecked(False)
        self.projection_mode_all.setToolTip('Project all Z sections.')
        # Z-Projection type
        self.projection_type = QComboBox(self)
        self.projection_type.addItem("max")
        self.projection_type.addItem("min")
        self.projection_type.addItem("mean")
        self.projection_type.addItem("median")
        self.projection_type.addItem("std")
        self.projection_type.setCurrentText("mean")
        self.projection_type.setDisabled(self.projection_mode_bestZ.isChecked())
        self.projection_mode_bestZ.toggled.connect(self.projection_type.setDisabled)
        # Submit
        self.submit_button = QPushButton("Submit", self)
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
        groupbox = QGroupBox('Images to process')
        layout2 = QVBoxLayout()
        layout2.addWidget(self.image_list)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        # Output folders
        groupbox = QGroupBox("Output folder")
        layout2 = QVBoxLayout()
        layout2.addWidget(self.use_input_folder)
        layout2.addWidget(self.use_custom_folder)
        layout3 = QHBoxLayout()
        layout3.addWidget(self.output_folder)
        layout3.addWidget(self.browse_button2, alignment=Qt.AlignCenter)
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
        layout.addWidget(self.submit_button, alignment=Qt.AlignCenter)
        self.setLayout(layout)

        self.logger = logging.getLogger(__name__)

    def browse_output(self):
        # Browse folders in order to choose the output one
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        self.output_folder.setText(folder_path)
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        self.output_folder.setText(folder_path)

    def projection_mode_fixed_zmin_changed(self, value):
        if self.projection_mode_fixed_zmax.value() < value:
            self.projection_mode_fixed_zmax.setValue(value)

    def projection_mode_fixed_zmax_changed(self, value):
        if self.projection_mode_fixed_zmin.value() > value:
            self.projection_mode_fixed_zmin.setValue(value)

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

        image_paths = self.image_list.get_file_list()
        output_basenames = [os.path.splitext(os.path.basename(path))[0] for path in image_paths]
        if self.use_input_folder.isChecked():
            output_paths = [os.path.join(os.path.dirname(path), 'zprojection') for path in image_paths]
        else:
            output_paths = [self.output_folder.text() for path in image_paths]

        if not check_inputs(image_paths, output_paths, output_basenames):
            return

        projection_type = self.projection_type.currentText()
        if self.projection_mode_bestZ.isChecked():
            projection_zrange = 0
        elif self.projection_mode_around_bestZ.isChecked():
            projection_zrange = self.projection_mode_around_bestZ_zrange.value()
        elif self.projection_mode_fixed.isChecked():
            projection_zrange = (self.projection_mode_fixed_zmin.value(), self.projection_mode_fixed_zmax.value())
        elif self.projection_mode_all.isChecked():
            projection_zrange = None

        for image_path, output_path, output_basename in zip(image_paths, output_paths, output_basenames):
            if os.path.isfile(image_path):
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
                except Exception as e:
                    self.logger.error("Projection failed.\n%s", str(e))
                # Restore cursor
                QApplication.restoreOverrideCursor()
            else:
                self.logger.error("Unable to locate file %s", image_path)

        self.logger.info("Done")
