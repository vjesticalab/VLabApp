import os
from PyQt5.QtWidgets import QVBoxLayout, QRadioButton, QGroupBox, QHBoxLayout, QFileDialog, QPushButton, QWidget, QLineEdit, QLabel, QFormLayout
from PyQt5.QtCore import Qt, QRegExp
from PyQt5.QtGui import QRegExpValidator
from modules.groundtruth_generator_module import generator_functions as f
from general import general_functions as gf
import logging


class Generator(QWidget):
    def __init__(self):
        super().__init__()

        self.output_suffix = '_vGT'

        # Input widgets
        self.imagetypes = ['.nd2', '.tif', '.tiff', '.ome.tif', '.ome.tiff']
        self.image_list = gf.FileListWidget(filetypes=self.imagetypes)
        # Output widgets
        self.use_input_folder = QRadioButton("Use input image folder")
        self.use_input_folder.setChecked(True)
        self.use_input_folder.toggled.connect(self.update_output_filename_label)
        self.use_custom_folder = QRadioButton("Use custom folder")
        self.use_custom_folder.setChecked(False)
        self.use_custom_folder.toggled.connect(self.update_output_filename_label)
        self.output_folder = gf.DropFolderLineEdit()
        self.output_folder.textChanged.connect(self.update_output_filename_label)
        self.browse_button2 = QPushButton("Browse", self)
        self.browse_button2.clicked.connect(self.browse_output)
        self.output_folder.setVisible(self.use_custom_folder.isChecked())
        self.browse_button2.setVisible(self.use_custom_folder.isChecked())
        self.use_custom_folder.toggled.connect(self.output_folder.setVisible)
        self.use_custom_folder.toggled.connect(self.browse_button2.setVisible)
        self.output_user_suffix = QLineEdit()
        self.output_user_suffix.setToolTip('Allowed characters: A-Z, a-z, 0-9 and -')
        self.output_user_suffix.setValidator(QRegExpValidator(QRegExp('[A-Za-z0-9-]*')))
        self.output_user_suffix.textChanged.connect(self.update_output_filename_label)
        self.output_filename_label = QLineEdit()
        self.output_filename_label.setFrame(False)
        self.output_filename_label.setEnabled(False)
        self.output_filename_label.textChanged.connect(self.output_filename_label.setToolTip)
        # Submit
        self.submit_button = QPushButton("Submit", self)
        self.submit_button.clicked.connect(self.submit)
        self.submission_num_failed = 0
        self.label_error = None

        # Layout
        layout = QVBoxLayout()
        groupbox = QGroupBox('Images to process')
        layout2 = QVBoxLayout()
        layout2.addWidget(self.image_list)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
        groupbox = QGroupBox("Output")
        layout2 = QVBoxLayout()
        layout2.addWidget(QLabel("Folder:"))
        layout2.addWidget(self.use_input_folder)
        layout2.addWidget(self.use_custom_folder)
        layout3 = QHBoxLayout()
        layout3.addWidget(self.output_folder)
        layout3.addWidget(self.browse_button2, alignment=Qt.AlignCenter)
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
        layout3.addRow("Filename:", self.output_filename_label)
        layout2.addLayout(layout3)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
        layout.addWidget(self.submit_button, alignment=Qt.AlignCenter)
        self.setLayout(layout)

        self.logger = logging.getLogger(__name__)

        self.update_output_filename_label()

    def browse_output(self):
        # Browse folders in order to choose the output one
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        self.output_folder.setText(folder_path)

    def update_output_filename_label(self):
        if self.use_input_folder.isChecked():
            output_path = "<input folder>"
        else:
            output_path = self.output_folder.text().rstrip("/")

        self.output_filename_label.setText(os.path.join(output_path,"<input basename>" + self.output_suffix + self.output_user_suffix.text() + ".ome.tif"))

    def submit(self):
        """
        Retrieve the input parameters
        Iterate over the image paths given performing f.main() function
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
                    self.logger.error('Image not found %s', path)
                    return False
            if self.output_folder.text() == '' and not self.use_input_folder.isChecked():
                self.logger.error('Output folder missing')
                self.output_folder.setFocus()
                return False
            return True

        image_paths = self.image_list.get_file_list()

        if not check_inputs(image_paths):
            return

        for image_path in image_paths:
            if os.path.isfile(image_path):
                # Set output directory for each image path
                if self.use_input_folder.isChecked():
                    output_path = os.path.dirname(image_path)
                else:
                    output_path = self.output_folder.text()
                if not output_path.endswith('/'): output_path += '/'
                if not os.path.exists(output_path): os.makedirs(output_path)
                output_basename = gf.splitext(os.path.basename(image_path))[0] + self.output_suffix + self.output_user_suffix.text()
                # Set log and cursor info
                self.logger.info("Image %s", image_path)
                # Perform projection
                try:
                    f.main(image_path, output_path, output_basename)
                except Exception as e:
                    self.logger.error("Generation failed.\n%s", str(e))
            else:
                self.logger.error("Unable to locate file %s", image_path)

        self.logger.info("Done")
