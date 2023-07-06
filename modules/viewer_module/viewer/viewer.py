from PyQt5.QtWidgets import QFileDialog, QLabel, QPushButton, QVBoxLayout, QWidget, QGroupBox, QGridLayout
from PyQt5.QtCore import Qt
from general import general_functions as gf
import napari
import logging

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
        
        # Layout
        layout = QVBoxLayout()
        groupbox = QGroupBox("Open napari to visualize mask(s) or image(s)")
        layout2 = QVBoxLayout()
        layout2.addWidget(self.button1, alignment=Qt.AlignCenter)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
        groupbox = QGroupBox("Open napari to visualize a graph")
        layout2 = QVBoxLayout()
        layout.addWidget(groupbox)
        layout2.addWidget(QLabel("Select the graph:"))
        layout3 = QGridLayout()
        layout3.addWidget(self.input_graph, 0, 0)
        layout3.addWidget(browse_button, 0, 1)
        layout2.addLayout(layout3)
        layout2.addWidget(self.button2, alignment=Qt.AlignCenter)
        groupbox.setLayout(layout2)
        self.setLayout(layout)

    def browse_graph(self):
        file_path, _ = QFileDialog.getOpenFileName(self, 'Select Files', filter='Cell tracking graphs ('+' '.join(['*'+x for x in self.graphtypes])+')')
        self.input_graph.setText(file_path)

    def open_napari(self):
        """
        Open an empty napari window
        """
        viewer = napari.Viewer()
        viewer.show(block=True)

    def open_graph(self):
        """
        Open a napari window with the selected graph
        """
        graph_path = self.input_graph.text()
        if graph_path == '':
            self.logger.error('Cell tracking graph missing')
            self.input_graph.setFocus()
            return
        viewer = napari.Viewer()
        try:
            gf.plot_graph(viewer, graph_path)
        except Exception as e:
            logging.error('Error in opening the graph: '+str(e))


