import os
import logging
from PyQt5.QtWidgets import QGridLayout, QLabel, QSpinBox, QFileDialog, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QGroupBox, QRadioButton, QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCursor
from modules.fusion_correction_module import fusion_correction_functions as f
from general import general_functions as gf


class FusionCorrection(QWidget):
    def __init__(self):
        super().__init__()
        self.imagetypes = ['.nd2', '.tif', '.tiff']
        self.graphtypes = ['.graphmlz']

        # Browse segmentation mask
        self.input_mask = gf.DropFileLineEdit(filetypes=self.imagetypes)
        browse_button0 = QPushButton("Browse", self)
        browse_button0.clicked.connect(self.add_mask)

        # Browse channel image
        self.input_chimage = gf.DropFileLineEdit(filetypes=self.imagetypes)
        browse_button1 = QPushButton("Browse", self)
        browse_button1.clicked.connect(self.add_chimage)
        
        # Browse cell graph
        self.input_graph = gf.DropFileLineEdit(filetypes=self.graphtypes)
        browse_button2 = QPushButton("Browse", self)
        browse_button2.clicked.connect(self.add_graph)

        # Number timepoints before and after event
        label_before = QLabel("Number of timepoints before event")
        self.spinBox_before = QSpinBox(self)
        self.spinBox_before.setRange(0, 40)
        self.spinBox_before.setValue(5)
        label_after = QLabel("Number of timepoints after event")
        self.spinBox_after = QSpinBox(self)
        self.spinBox_after.setRange(0, 40)
        self.spinBox_after.setValue(5)
        
        # Output directory
        self.use_input_folder = QRadioButton("Use input image folder (graph_event_filter sub-folder)")
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
        
        self.submit_button = QPushButton("Submit", self)
        self.submit_button.clicked.connect(self.submit)

        # Layout
        layout = QVBoxLayout()
        groupbox = QGroupBox("Segmentation mask")
        layout2 = QVBoxLayout()
        layout2.addWidget(self.input_mask)
        layout2.addWidget(browse_button0, alignment=Qt.AlignCenter)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
        groupbox = QGroupBox("Cell tracking graph")
        layout2 = QVBoxLayout()
        layout2.addWidget(self.input_graph)
        layout2.addWidget(browse_button2, alignment=Qt.AlignCenter)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
        groupbox = QGroupBox("Magnified image")
        layout2 = QVBoxLayout()
        layout2.addWidget(self.input_chimage)
        layout2.addWidget(browse_button1, alignment=Qt.AlignCenter)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
        groupbox = QGroupBox("Timepoints")
        layout2 = QGridLayout()
        layout2.addWidget(label_before, 0, 0, 1, 2)
        layout2.addWidget(self.spinBox_before, 0, 2, 1, 1)
        layout2.addWidget(label_after, 1, 0, 1, 2)
        layout2.addWidget(self.spinBox_after, 1, 2, 1, 1)
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

    def add_mask(self):
        # Add the selected mask as input
        file_path, _ = QFileDialog.getOpenFileName(self, 'Select Files', filter='Images ('+' '.join(['*'+x for x in self.imagetypes])+')')
        self.input_mask.setText(file_path)
    
    def add_chimage(self):
        # Add the selected mask as input
        file_path, _ = QFileDialog.getOpenFileName(self, 'Select Files', filter='Images ('+' '.join(['*'+x for x in self.imagetypes])+')')
        self.input_chimage.setText(file_path)

    def add_graph(self):
        # Add the selected graph as input
        file_path, _ = QFileDialog.getOpenFileName(self, 'Select Files', filter='Cell tracking graphs ('+' '.join(['*'+x for x in self.graphtypes])+')')
        self.input_graph.setText(file_path)

    def browse_output(self):
        # Browse folders in order to choose the output one
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        self.output_folder.setText(folder_path)
    
    def submit(self):
        """
        Retrieve the input parameters and process them in f.main()
        """
        mask_path = self.input_mask.text()
        graph_path = self.input_graph.text()
        chimage_path = self.input_chimage.text()
        tp_before = int(self.spinBox_before.text())
        tp_after = int(self.spinBox_after.text())

        # Check inputs
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
        if chimage_path == '':
            self.logger.error('Magnified image missing')
            self.input_mask.setFocus()
            return
        if not os.path.isfile(chimage_path):
            self.logger.error('Magnified image: not a valid file')
            self.input_mask.setFocus()
            return
        if self.output_folder.text() == '' and not self.use_input_folder.isChecked():
            self.logger.error('Output folder missing')
            self.output_folder.setFocus()
            return

        # Set output_path
        if self.use_input_folder.isChecked():
            output_path = os.path.join(os.path.dirname(mask_path), 'fusion_correction')
        else:
            output_path = self.output_folder.text()
        self.logger.info("Fusion correction (mask %s, graph %s)", mask_path, graph_path)

        QApplication.setOverrideCursor(QCursor(Qt.BusyCursor))
        QApplication.processEvents()
        try:
            f.main(mask_path, graph_path, chimage_path, tp_before, tp_after, output_path)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            self.logger.error(str(e))
            raise e
        QApplication.restoreOverrideCursor()

        self.logger.info("Done")
