import logging
from PyQt5.QtWidgets import QFileDialog, QLineEdit, QCheckBox, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QMessageBox, QListWidget, QAbstractItemView, QGroupBox, QRadioButton, QApplication
from PyQt5.QtCore import Qt
from modules.zprojection_module.zprojection import zprojection_functions as f
from general import general_functions as gf
import napari



class Viewer(QWidget):
    def __init__(self):
        super().__init__()
       
        self.button1 = QPushButton("Open", self)
        self.button1.clicked.connect(self.open_napari)

        self.graphtypes = ['.graphmlz']
        self.input_graph = gf.DropFileLineEdit(filetypes=self.graphtypes)
        browse_button = QPushButton("Browse", self)
        browse_button.clicked.connect(self.browse_graph)
        self.button2 = QPushButton("Open", self)
        self.button2.clicked.connect(self.open_graph)
        

        layout = QVBoxLayout()

        groupbox = QGroupBox("Open napari to visualize mask(s) or image(s)")
        layout2 = QVBoxLayout()
        layout2.addWidget(self.button1, alignment=Qt.AlignCenter)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        groupbox = QGroupBox("Open napari to visualize a graph")
        layout2 = QVBoxLayout()
        layout.addWidget(groupbox)
        layout2.addWidget(self.input_graph)
        layout2.addWidget(browse_button, alignment=Qt.AlignCenter)
        layout2.addWidget(self.button2, alignment=Qt.AlignCenter)
        groupbox.setLayout(layout2)

        self.setLayout(layout)

    def browse_graph(self):
        file_path, _ = QFileDialog.getOpenFileName(self, 'Select Files', filter='Cell tracking graphs ('+' '.join(['*'+x for x in self.graphtypes])+')')
        self.input_graph.setText(file_path)

    def open_napari(self):
        viewer = napari.Viewer()
        viewer.show(block=True)

    def open_graph(self):
        graph_path = self.input_graph.text()
        if graph_path == '':
            self.logger.error('Cell tracking graph missing')
            self.input_graph.setFocus()
            return
        viewer = napari.Viewer()
        gf.plot_graph(viewer, graph_path)

