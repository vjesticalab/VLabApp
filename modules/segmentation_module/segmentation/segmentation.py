import logging
import os
import logging
from PyQt5.QtWidgets import QFileDialog, QLineEdit, QCheckBox, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QMessageBox, QListWidget, QAbstractItemView, QGroupBox, QRadioButton, QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCursor
from modules.segmentation_module.segmentation import segmentation_functions as f
from general import general_functions as gf


class Segmentation(QWidget):
    def __init__(self):
        super().__init__()

        self.imagetypes = ['.nd2', '.tif', '.tiff']
        self.image_list = gf.DropFilesListWidget(filetypes=self.imagetypes)
        self.image_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.add_image_button = QPushButton("Add images", self)
        self.add_image_button.clicked.connect(self.add_image)
        self.add_folder_button = QPushButton("Add folder", self)
        self.add_folder_button.clicked.connect(self.add_folder)
        self.remove_button = QPushButton("Remove selected", self)
        self.remove_button.clicked.connect(self.remove)

        self.selected_model = gf.DropFileLineEdit()
        self.browse_button = QPushButton("Browse", self)
        self.browse_button.clicked.connect(self.browse_model)

        self.use_input_folder = QRadioButton("Use input image folder\n(segmentation_masks sub-folder)")
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

        self.use_gpu = QCheckBox("Use GPU")
        self.use_gpu.setChecked(False)

        self.display_results = QCheckBox("Show results in napari")
        self.display_results.setChecked(False)

        self.submit_button = QPushButton("Submit", self)
        self.submit_button.clicked.connect(self.click)

        # Layout
        layout = QVBoxLayout()

        groupbox = QGroupBox("Images to process")
        layout2 = QVBoxLayout()
        layout2.addWidget(self.image_list)
        layout3 = QHBoxLayout()
        layout3.addWidget(self.add_image_button)
        layout3.addWidget(self.add_folder_button)
        layout3.addWidget(self.remove_button)
        layout2.addLayout(layout3)
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

        layout.addWidget(self.use_gpu)
        layout.addWidget(self.display_results)
        layout.addWidget(self.submit_button, alignment=Qt.AlignCenter)
        self.setLayout(layout)

        self.logger = logging.getLogger(__name__)

    def add_image(self):
        file_paths, _ = QFileDialog.getOpenFileNames(self, 'Select Files', filter='Images ('+' '.join(['*'+x for x in self.imagetypes])+')')
        for file_path in file_paths:
            if file_path and len(self.image_list.findItems(file_path, Qt.MatchExactly)) == 0:
                self.image_list.addItem(file_path)

    def add_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder_path:
            images = [os.path.join(folder_path, i) for i in os.listdir(folder_path) if os.path.splitext(i)[1] in self.imagetypes]
            self.image_list.addItems([i for i in images if len(self.image_list.findItems(i, Qt.MatchExactly)) == 0])

    def remove(self):
        for item in self.image_list.selectedItems():
            self.image_list.takeItem(self.image_list.row(item))

    def browse_model(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File")
        self.selected_model.setText(file_path)

    def browse_output(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        self.output_folder.setText(folder_path)

    def click(self):

        def check_inputs(image_paths, model_path):
            if len(image_paths) == 0:
                self.logger.error('Image missing')
                self.add_image_button.setFocus()
                return False
            for path in image_paths:
                if not os.path.isfile(path):
                    self.logger.error('Image not found\n' + path)
                    self.add_image_button.setFocus()
                    return False
            if not os.path.isfile(model_path):
                self.logger.error('Model missing')
                self.selected_model.setFocus()
                return False
            if self.output_folder.text() == '' and not self.use_input_folder.isChecked():
                self.logger.error('Output folder missing')
                self.output_folder.setFocus()
                return False
            if self.display_results.isChecked() and len(image_paths) > 1:
                display_results = QMessageBox.question(self, 'Show results in napari?', "All images will be loaded into memory and a new napari window will be opened for each image.\nDo you really want to show images in napari?", QMessageBox.Yes | QMessageBox.No)
                if display_results == QMessageBox.No:
                    self.display_results.setChecked(False)
            return True

        image_paths = [self.image_list.item(x).text() for x in range(self.image_list.count())]
        model_path = self.selected_model.text()

        if not check_inputs(image_paths, model_path):
            return
        
        if os.path.isfile(model_path):
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
                        f.main(image_path, model_path, output_path, self.display_results.isChecked(), self.use_gpu.isChecked())
                    except Exception as e:
                        self.logger.error("Segmentation failed.\n" + str(e))
                    
                    QApplication.restoreOverrideCursor()
                else:
                    self.logger.error("Unable to locate file %s", image_path)
        else:
            self.logger.error("Model file %s not found", model_path)

        self.logger.info("Done")
