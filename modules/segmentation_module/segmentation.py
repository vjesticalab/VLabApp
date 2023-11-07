import logging
import os
from PyQt5.QtWidgets import QFileDialog, QCheckBox, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QGroupBox, QRadioButton, QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCursor
from modules.segmentation_module import segmentation_functions as f
from general import general_functions as gf


class Segmentation(QWidget):
    def __init__(self):
        super().__init__()

        self.imagetypes = ['.nd2', '.tif', '.tiff']
        self.image_list = gf.FileListWidget(filetypes=self.imagetypes, filenames_filter='_BF')
        self.image_list.file_list_changed.connect(self.image_list_changed)

        self.selected_model = gf.DropFileLineEdit()
        default_model_path = '/Volumes/D2c/Lab_VjesticaLabApps/Cellpose_v2/20230704_CellposeModels/models/cellpose_projection_best_nepochs_5000'
        self.selected_model.setText(default_model_path)
        self.browse_button = QPushButton("Browse", self)
        self.browse_button.clicked.connect(self.browse_model)

        self.use_input_folder = QRadioButton("Use input image folder (segmentation_masks sub-folder)")
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

        self.display_results = QCheckBox("Show results in napari")
        self.display_results.setChecked(False)

        self.submit_button = QPushButton("Submit", self)
        self.submit_button.clicked.connect(self.submit)

        # Layout
        layout = QVBoxLayout()
        groupbox = QGroupBox('Images to process')
        layout2 = QVBoxLayout()
        layout2.addWidget(self.image_list)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
        groupbox = QGroupBox("Cellpose model")
        layout2 = QVBoxLayout()
        layout3 = QHBoxLayout()
        layout3.addWidget(self.selected_model)
        layout3.addWidget(self.browse_button, alignment=Qt.AlignCenter)
        layout2.addLayout(layout3)
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
        layout.addWidget(self.display_results)
        layout.addWidget(self.submit_button, alignment=Qt.AlignCenter)
        self.setLayout(layout)

        self.logger = logging.getLogger(__name__)

    def image_list_changed(self):
        if self.image_list.count() > 1:
            self.display_results.setChecked(False)
        self.display_results.setEnabled(self.image_list.count() <= 1)

    def browse_model(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File")
        self.selected_model.setText(file_path)

    def browse_output(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        self.output_folder.setText(folder_path)

    def submit(self):
        """
        Retrieve the input parameters
        Iterate over the image paths given performing f.main() function
        """
        def check_inputs(image_paths, model_path):
            if len(image_paths) == 0:
                self.logger.error('Image missing')
                return False
            for path in image_paths:
                if not os.path.isfile(path):
                    self.logger.error('Image not found: %s', path)
                    return False
            if model_path == '':
                self.logger.error('Model missing')
                self.selected_model.setFocus()
                return False
            if not os.path.isfile(model_path):
                self.logger.error('Model not found: %s', model_path)
                self.selected_model.setFocus()
                return False
            if self.output_folder.text() == '' and not self.use_input_folder.isChecked():
                self.logger.error('Output folder missing')
                self.output_folder.setFocus()
                return False
            return True

        image_paths = self.image_list.get_file_list()
        model_path = self.selected_model.text()

        if not check_inputs(image_paths, model_path):
            return

        for image_path in image_paths:
            if os.path.isfile(image_path):
                if self.use_input_folder.isChecked():
                    output_path = os.path.join(os.path.dirname(image_path), 'segmentation_masks')
                else:
                    output_path = self.output_folder.text()
                self.logger.info("Segmenting image %s", image_path)
                QApplication.setOverrideCursor(QCursor(Qt.BusyCursor))
                QApplication.processEvents()

                try:
                    f.main(image_path, model_path, output_path, self.display_results.isChecked())
                except Exception as e:
                    self.logger.error("Segmentation failed.\n%s", str(e))

                QApplication.restoreOverrideCursor()
            else:
                self.logger.error("Image %s not found", image_path)

        self.logger.info("Done")
