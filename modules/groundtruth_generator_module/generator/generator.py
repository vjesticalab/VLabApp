import os
from PyQt5.QtWidgets import QGridLayout, QVBoxLayout, QRadioButton, QGroupBox, QHBoxLayout, QFileDialog, QLabel, QLineEdit, QPushButton, QCheckBox, QWidget, QFrame
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt
from modules.groundtruth_generator_module.generator import generator_functions as f
from general import general_functions as gf
import logging


class Generator(QWidget):
    def __init__(self):
        super().__init__()
        
        # Upload
        self.selected_folder = QLineEdit()
        self.selected_folder.setMinimumWidth(300)
        self.browse_button1 = QPushButton("Browse", self)
        self.browse_button1.clicked.connect(self.browse_input)

        # Define path where to save
        self.use_input_folder = QRadioButton("Use input image folder\n(ground_truth sub-folder)")
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

        # Submit
        self.submit_button = QPushButton("Submit", self)
        self.submit_button.clicked.connect(self.process_input)
        self.submission_num_failed = 0
        self.label_error = None

        # Layout
        layout = QVBoxLayout()
        groupbox = QGroupBox("Images to process")
        layout2 = QGridLayout()
        layout2.addWidget(self.selected_folder, 0, 0)
        layout2.addWidget(self.browse_button1, 0, 1)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

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

        layout.addWidget(self.submit_button, alignment=Qt.AlignCenter)
        self.setLayout(layout)

        self.logger = logging.getLogger(__name__)
              
    def browse_input(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        self.selected_folder1.setText(folder_path)

    def browse_output(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        self.output_folder.setText(folder_path)
    
    def process_input(self):
    
        def check_inputs(image_paths):
            if len(image_paths) == 0:
                self.logger.error('Image missing')
                self.add_image_button.setFocus()
                return False
            for path in image_paths:
                if not os.path.isfile(path):
                    self.logger.error('Image not found\n' + path)
                    self.add_image_button.setFocus()
                    return False
            if self.output_folder.text() == '' and not self.use_input_folder.isChecked():
                self.logger.error('Output folder missing')
                self.output_folder.setFocus()
                return False
            return True
        
        image_path = self.selected_folder.text()

        if not check_inputs(image_path):
            return

        if self.use_input_folder.isChecked():
            output_path = os.path.join(os.path.dirname(image_path), 'ground_truth')
        else:
            output_path = self.output_folder.text()
        
        # Output path
        if not os.path.exists(output_path):
            os.makedirs(output_path)

        f.main(image_path, output_path)