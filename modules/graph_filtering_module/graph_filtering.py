import os
import logging
from PyQt5.QtWidgets import QFileDialog, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QGroupBox, QRadioButton, QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCursor
from modules.graph_filtering_module import graph_filtering_functions as f
from general import general_functions as gf


class GraphFiltering(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout()

        self.imagetypes = ['.nd2', '.tif', '.tiff']
        self.graphtypes = ['.graphmlz']

        self.input_image = gf.DropFileLineEdit(filetypes=self.imagetypes)
        browse_button = QPushButton("Browse", self)
        browse_button.clicked.connect(self.browse_image)
        groupbox = QGroupBox("Image")
        layout2 = QVBoxLayout()
        layout3 = QHBoxLayout()
        layout3.addWidget(self.input_image)
        layout3.addWidget(browse_button, alignment=Qt.AlignCenter)
        layout2.addLayout(layout3)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        self.input_mask = gf.DropFileLineEdit(filetypes=self.imagetypes)
        browse_button = QPushButton("Browse", self)
        browse_button.clicked.connect(self.browse_mask)
        groupbox = QGroupBox("Segmentation mask")
        layout2 = QVBoxLayout()
        layout3 = QHBoxLayout()
        layout3.addWidget(self.input_mask)
        layout3.addWidget(browse_button, alignment=Qt.AlignCenter)
        layout2.addLayout(layout3)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        self.input_graph = gf.DropFileLineEdit(filetypes=self.graphtypes)
        browse_button = QPushButton("Browse", self)
        browse_button.clicked.connect(self.browse_graph)
        groupbox = QGroupBox("Cell tracking graph")
        layout2 = QVBoxLayout()
        layout3 = QHBoxLayout()
        layout3.addWidget(self.input_graph)
        layout3.addWidget(browse_button, alignment=Qt.AlignCenter)
        layout2.addLayout(layout3)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        self.use_input_folder = QRadioButton("Use input image folder\n(graph_filtering sub-folder)")
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

        self.submit_button = QPushButton("Submit", self)
        self.submit_button.clicked.connect(self.process_input)
        layout.addWidget(self.submit_button, alignment=Qt.AlignCenter)

        self.setLayout(layout)

        self.logger = logging.getLogger(__name__)

    def browse_image(self):
        file_path, _ = QFileDialog.getOpenFileName(self, 'Select Files', filter='Images ('+' '.join(['*'+x for x in self.imagetypes])+')')
        self.input_image.setText(file_path)

    def browse_mask(self):
        file_path, _ = QFileDialog.getOpenFileName(self, 'Select Files', filter='Images ('+' '.join(['*'+x for x in self.imagetypes])+')')
        self.input_mask.setText(file_path)

    def browse_graph(self):
        file_path, _ = QFileDialog.getOpenFileName(self, 'Select Files', filter='Cell tracking graphs ('+' '.join(['*'+x for x in self.graphtypes])+')')
        self.input_graph.setText(file_path)

    def browse_output(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        self.output_folder.setText(folder_path)

    def process_input(self):
        image_path = self.input_image.text()
        mask_path = self.input_mask.text()
        graph_path = self.input_graph.text()

        # check input
        if image_path == '':
            self.logger.error('Image missing')
            self.input_image.setFocus()
            return
        if not os.path.isfile(image_path):
            self.logger.error('Image: not a valid file')
            self.input_image.setFocus()
            return
        if mask_path == '':
            self.logger.error('Segmentation mask missing')
            self.input_mask.setFocus()
            return
        if not os.path.isfile(mask_path):
            self.logger.error('Segmentation mask: not a valid file')
            self.input_mask.setFocus()
            return
        if graph_path == '':
            self.logger.error('Cell tracking graph missing')
            self.input_graph.setFocus()
            return
        if not os.path.isfile(graph_path):
            self.logger.error('Cell tracking graph: not a valid file')
            self.input_graph.setFocus()
            return

        if self.output_folder.text() == '' and not self.use_input_folder.isChecked():
            self.logger.error('Output folder missing')
            self.output_folder.setFocus()
            return

        if self.use_input_folder.isChecked():
            output_path = os.path.join(os.path.dirname(image_path), 'graph_filtering')
        else:
            output_path = self.output_folder.text()
        self.logger.info("Graph filtering (image %s, mask %s, graph %s)", image_path, mask_path, graph_path)

        QApplication.setOverrideCursor(QCursor(Qt.BusyCursor))
        QApplication.processEvents()
        try:
            f.main(image_path, mask_path, graph_path, output_path=output_path, display_results=True)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            self.logger.error(str(e))
            raise e
        QApplication.restoreOverrideCursor()

        self.logger.info("Done")
