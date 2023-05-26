import os
import logging
from PyQt5.QtWidgets import QFileDialog, QLabel, QLineEdit, QCheckBox, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QMessageBox, QListWidget, QAbstractItemView, QGroupBox
from PyQt5.QtCore import Qt
from modules.segmentation_module.segmentation import segmentation_functions as f
from modules.segmentation_module.graphGenerator import graph_functions

class Segmentation(QWidget):
    def __init__(self):
        super().__init__()

        self.image_list = QListWidget()
        self.image_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.add_image_button = QPushButton("Add images", self)
        self.add_image_button.clicked.connect(self.add_image)
        self.add_folder_button = QPushButton("Add folder", self)
        self.add_folder_button.clicked.connect(self.add_folder)
        self.remove_button = QPushButton("Remove selected", self)
        self.remove_button.clicked.connect(self.remove)

        self.selected_model = QLineEdit()
        self.browse_button = QPushButton("Browse", self)
        self.browse_button.clicked.connect(self.browse_model)

        self.use_input_folder = QCheckBox(
            "Use input image folder (segmentation_masks_raw sub-folder)")
        self.use_input_folder.setChecked(True)
        self.use_input_folder.clicked.connect(self.use_input_folder_clicked)
        self.output_folder = QLineEdit()
        self.browse_button2 = QPushButton("Browse", self)
        self.browse_button2.clicked.connect(self.browse_output)
        self.output_folder.setEnabled(not self.use_input_folder.isChecked())
        self.browse_button2.setEnabled(not self.use_input_folder.isChecked())

        self.use_gpu = QCheckBox("Use GPU")
        self.use_gpu.setChecked(False)

        self.display_results = QCheckBox("Show results in napari")
        self.display_results.setChecked(True)

        self.submit_button = QPushButton("Submit", self)
        self.submit_button.clicked.connect(self.process_input)
        self.display3 = QLabel(
            "<i>This step can require also several minutes</i>")

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
        layout3.addWidget(self.browse_button, alignment=Qt.AlignCenter)
        layout3.addWidget(self.selected_model)
        layout2.addLayout(layout3)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        groupbox = QGroupBox("Output folder")
        layout2 = QVBoxLayout()
        layout2.addWidget(self.use_input_folder)
        layout3 = QHBoxLayout()
        layout3.addWidget(self.browse_button2, alignment=Qt.AlignCenter)
        layout3.addWidget(self.output_folder)
        layout2.addLayout(layout3)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        layout.addWidget(self.use_gpu)
        layout.addWidget(self.display_results)
        layout.addWidget(self.submit_button, alignment=Qt.AlignCenter)
        layout.addWidget(self.display3)
        self.setLayout(layout)

        self.logger = logging.getLogger(__name__)


    def add_image(self):
        file_paths, _ = QFileDialog.getOpenFileNames(self,
                                                     "Select Files",
                                                     filter="Images (*.tif, *tiff, *.nd2)")
        for file_path in file_paths:
            if file_path and len(self.image_list.findItems(file_path, Qt.MatchExactly)) == 0:
                self.image_list.addItem(file_path)

    def add_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        images = [os.path.join(folder_path, i)
                  for i in os.listdir(folder_path)
                  if i.endswith('.nd2') or i.endswith('.tif') or i.endswith('.tiff')]
        self.image_list.addItems([i for i in images
                                  if len(self.image_list.findItems(i, Qt.MatchExactly)) == 0])

    def remove(self):
        for item in self.image_list.selectedItems():
            self.image_list.takeItem(self.image_list.row(item))

    def browse_model(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File")
        self.selected_model.setText(file_path)

    def browse_output(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        self.output_folder.setText(folder_path)

    def use_input_folder_clicked(self):
        self.output_folder.setEnabled(not self.use_input_folder.isChecked())
        self.browse_button2.setEnabled(not self.use_input_folder.isChecked())

    def process_input(self):
        image_paths = [self.image_list.item(x).text()
                       for x in range(self.image_list.count())]
        model_path = self.selected_model.text()

        # check input
        if len(image_paths) == 0:
            QMessageBox.warning(self, 'Error', 'Image missing')
            self.add_image_button.setFocus()
            return
        if not os.path.isfile(model_path):
            QMessageBox.warning(self, 'Error', 'Model missing')
            self.selected_model.setFocus()
            return
        if self.output_folder.text() == '' and not self.use_input_folder.isChecked():
            QMessageBox.warning(self, 'Error', 'Output folder missing')
            self.output_folder.setFocus()
            return

        if os.path.isfile(model_path):
            for image_path in image_paths:
                if os.path.isfile(image_path):
                    if self.use_input_folder.isChecked():
                        output_path = os.path.join(os.path.dirname(
                            image_path), 'segmentation_masks_raw')
                    else:
                        output_path = self.output_folder.text()
                    self.logger.info("Segmenting image %s", image_path)
                    try:
                        f.main(image_path, model_path, output_path=output_path,
                               display_results=self.display_results.isChecked(), use_gpu=self.use_gpu.isChecked())
                    except Exception as e:
                        self.logger.error(str(e))
                        raise e
                else:
                    self.logger.warning("Unable to locate file %s", image_path)
        else:
            self.logger.warning("Model file %s not found", model_path)

        self.logger.info("Done")
