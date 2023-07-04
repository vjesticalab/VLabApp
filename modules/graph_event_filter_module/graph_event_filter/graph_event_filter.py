import os
import logging
from PyQt5.QtWidgets import QGridLayout, QLabel, QSpinBox, QFileDialog, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QMessageBox, QGroupBox, QRadioButton, QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCursor
from modules.graph_event_filter_module.graph_event_filter import graph_event_filter_functions as f
from general import general_functions as gf


class DropFileLineEdit(QLineEdit):
    """
    A QLineEdit with drop support for files.
    """

    def __init__(self, parent=None, filetypes=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.filetypes = filetypes

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls:
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            if url.isLocalFile():
                if os.path.isfile(url.toLocalFile()):
                    filename = url.toLocalFile()
                    if self.filetypes is None or os.path.splitext(filename)[1] in self.filetypes:
                        self.setText(filename)


class DropFolderLineEdit(QLineEdit):
    """
    A QLineEdit with drop support for folder.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls:
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            if url.isLocalFile():
                if os.path.isdir(url.toLocalFile()):
                    self.setText(url.toLocalFile())


class GraphEventFilter(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout()

        self.imagetypes = ['.nd2', '.tif', '.tiff']
        self.graphtypes = ['.graphmlz']

        # Browse segmentation mask
        self.input_mask = DropFileLineEdit(filetypes=self.imagetypes)
        browse_button = QPushButton("Browse", self)
        browse_button.clicked.connect(self.browse_mask)
        groupbox = QGroupBox("Segmentation mask")
        layout2 = QVBoxLayout()
        layout2.addWidget(self.input_mask)
        layout2.addWidget(browse_button, alignment=Qt.AlignCenter)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        # Browse cell graph
        self.input_graph = DropFileLineEdit(filetypes=self.graphtypes)
        browse_button = QPushButton("Browse", self)
        browse_button.clicked.connect(self.browse_graph)
        groupbox = QGroupBox("Cell tracking graph")
        layout2 = QVBoxLayout()
        layout2.addWidget(self.input_graph)
        layout2.addWidget(browse_button, alignment=Qt.AlignCenter)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        # Browse type of event
        radiobutton1 = QRadioButton("Fusion")
        radiobutton1.setChecked(True)
        radiobutton1.event = "fusion"
        radiobutton1.toggled.connect(self.btnstate)
        radiobutton2 = QRadioButton("Division")
        radiobutton2.event = "division"
        radiobutton2.toggled.connect(self.btnstate)
        
        groupbox = QGroupBox("Type of event")
        layout2 = QGridLayout()
        layout2.addWidget(radiobutton1, 0, 0)
        layout2.addWidget(radiobutton2, 0, 1)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        # Number timepoints before and after event
        label_before = QLabel("Number of timepoints before event")
        self.spinBox_before = QSpinBox(self)
        self.spinBox_before.setRange(0, 100)
        label_after = QLabel("Number of timepoints after event")
        self.spinBox_after = QSpinBox(self)
        self.spinBox_after.setRange(0, 100)
        groupbox = QGroupBox("Timepoints")
        layout2 = QGridLayout()
        layout2.addWidget(label_before, 0, 0, 1, 2)
        layout2.addWidget(self.spinBox_before, 0, 2, 1, 1)
        layout2.addWidget(label_after, 1, 0, 1, 2)
        layout2.addWidget(self.spinBox_after, 1, 2, 1, 1)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        # Output directory
        self.use_input_folder = QRadioButton("Use input image folder\n(graph_event_filter sub-folder)")
        self.use_input_folder.setChecked(True)
        self.use_custom_folder = QRadioButton("Use custom folder:")
        self.use_custom_folder.setChecked(False)
        self.output_folder = DropFolderLineEdit()
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
    
    def btnstate(self):
        radioButton = self.sender()
        if radioButton.isChecked():
            self.event_type = radioButton.event

    def process_input(self):
        mask_path = self.input_mask.text()
        graph_path = self.input_graph.text()
        event = self.event_type
        tp_before = self.spinBox_before.text()
        tp_after = self.spinBox_after.text()

        # check input
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
            output_path = os.path.join(os.path.dirname(mask_path), 'graph_event_filter')
        else:
            output_path = self.output_folder.text()
        self.logger.info("Event filtering (mask %s, graph %s)", mask_path, graph_path)

        QApplication.setOverrideCursor(QCursor(Qt.BusyCursor))
        QApplication.processEvents()
        try:
            f.main(mask_path, graph_path, event, tp_before, tp_after, output_path)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            self.logger.error(str(e))
            raise e
        QApplication.restoreOverrideCursor()

        self.logger.info("Done")
