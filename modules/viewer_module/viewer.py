import os
import re
from PyQt5.QtWidgets import QFileDialog, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QGroupBox, QGridLayout, QScrollArea, QGroupBox
from PyQt5.QtCore import Qt
from general import general_functions as gf
from modules.cell_tracking_module.cell_tracking_functions import plot_cell_tracking_graph
import napari
import logging
import igraph as ig
import numpy as np

class ImageMaskGraphViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.graphtypes = ['.graphmlz']
        self.imagetypes = ['.nd2', '.tif', '.tiff', '.ome.tif', '.ome.tiff']
        self.output_suffixes = { 'zprojection': '_vPR',
                                 'groundtruth_generator': '_vGT',
                                 'registration': '_vRG',
                                 'segmentation': '_vSM',
                                 'cell_tracking': '_vTG',
                                 'graph_filtering': '_vGF',
                                 'events_filter': '_vEF'}

        layout = QVBoxLayout()
        layout.setContentsMargins(0,0,0,0)
        self.input_image = gf.DropFileLineEdit(filetypes=self.imagetypes)
        browse_image_button = QPushButton("Browse", self)
        browse_image_button.clicked.connect(self.browse_image)
        self.input_mask = gf.DropFileLineEdit(filetypes=self.imagetypes)
        self.input_mask.textChanged.connect(self.input_mask_changed)
        browse_mask_button = QPushButton("Browse", self)
        browse_mask_button.clicked.connect(self.browse_mask)
        self.input_graph = gf.DropFileLineEdit(filetypes=self.graphtypes)
        self.input_graph.textChanged.connect(self.input_graph_changed)
        browse_graph_button = QPushButton("Browse", self)
        browse_graph_button.clicked.connect(self.browse_graph)
        self.open_button = QPushButton("Open napari", self)
        self.open_button.clicked.connect(self.open)

        layout.addWidget(QLabel("Image:"))
        layout2 = QHBoxLayout()
        layout2.addWidget(self.input_image)
        layout2.addWidget(browse_image_button, alignment=Qt.AlignCenter)
        layout.addLayout(layout2)
        layout.addWidget(QLabel("Segmentation mask:"))
        layout2 = QHBoxLayout()
        layout2.addWidget(self.input_mask)
        layout2.addWidget(browse_mask_button, alignment=Qt.AlignCenter)
        layout.addLayout(layout2)
        layout.addWidget(QLabel("Cell tracking graph:"))
        layout2 = QHBoxLayout()
        layout2.addWidget(self.input_graph)
        layout2.addWidget(browse_graph_button, alignment=Qt.AlignCenter)
        layout.addLayout(layout2)

        layout.addWidget(self.open_button, alignment=Qt.AlignCenter)
        self.setLayout(layout)

        self.logger = logging.getLogger(__name__)

    def input_mask_changed(self):
        mask_path=self.input_mask.text()
        self.input_image.setPlaceholderText('')
        self.input_image.setToolTip('')
        self.input_mask.setPlaceholderText('')
        self.input_mask.setToolTip('')
        self.input_graph.setPlaceholderText('')
        self.input_graph.setToolTip('')
        if os.path.isfile(mask_path):
            graph_path = gf.splitext(mask_path)[0] + '.graphmlz'
            if os.path.isfile(graph_path):
                self.input_graph.setPlaceholderText(graph_path)
                self.input_graph.setToolTip(graph_path)
            res = re.match('(.*)'+self.output_suffixes['segmentation']+'.*$',os.path.basename(mask_path))
            if res:
                for ext in self.imagetypes:
                    image_path = os.path.join(os.path.dirname(mask_path),res.group(1)) + ext
                    if os.path.isfile(image_path):
                        self.input_image.setPlaceholderText(image_path)
                        self.input_image.setToolTip(image_path)
                        break

    def input_graph_changed(self):
        graph_path=self.input_graph.text()
        self.input_image.setPlaceholderText('')
        self.input_image.setToolTip('')
        self.input_mask.setPlaceholderText('')
        self.input_mask.setToolTip('')
        self.input_graph.setPlaceholderText('')
        self.input_graph.setToolTip('')
        if os.path.isfile(graph_path):
            mask_path = gf.splitext(graph_path)[0] + '.ome.tif'
            if os.path.isfile(mask_path):
                self.input_mask.setPlaceholderText(mask_path)
                self.input_mask.setToolTip(mask_path)
            res = re.match('(.*)'+self.output_suffixes['segmentation']+'.*$',os.path.basename(graph_path))
            if res:
                for ext in self.imagetypes:
                    image_path = os.path.join(os.path.dirname(graph_path),res.group(1)) + ext
                    if os.path.isfile(image_path):
                        self.input_image.setPlaceholderText(image_path)
                        self.input_image.setToolTip(image_path)
                        break

    def browse_graph(self):
        file_path, _ = QFileDialog.getOpenFileName(self, 'Select Files', filter='Cell tracking graphs ('+' '.join(['*'+x for x in self.graphtypes])+')')
        self.input_graph.setText(file_path)

    def browse_mask(self):
        file_path, _ = QFileDialog.getOpenFileName(self, 'Select Files', filter='Images ('+' '.join(['*'+x for x in self.imagetypes])+')')
        self.input_mask.setText(file_path)

    def browse_image(self):
        file_path, _ = QFileDialog.getOpenFileName(self, 'Select Files', filter='Images ('+' '.join(['*'+x for x in self.imagetypes])+')')
        self.input_image.setText(file_path)

    def open(self):
        """
        Open a napari window with the selected graph
        """
        graph_path = self.input_graph.text()
        if graph_path == '':
            graph_path = self.input_graph.placeholderText()
        mask_path = self.input_mask.text()
        if mask_path == '':
            mask_path = self.input_mask.placeholderText()
        image_path = self.input_image.text()
        if image_path == '':
            image_path = self.input_image.placeholderText()

        if graph_path != '' and mask_path == '':
            self.logger.error('Missing mask path')
            self.input_graph.setFocus()
            return
        if image_path != '' and not os.path.isfile(image_path):
            self.logger.error('Invalid image path')
            self.input_image.setFocus()
            return
        if mask_path != '' and not os.path.isfile(mask_path):
            self.logger.error('Invalid mask path')
            self.input_mask.setFocus()
            return
        if graph_path != '' and not os.path.isfile(graph_path):
            self.logger.error('Invalid graph path')
            self.input_graph.setFocus()
            return

        #image mask graph
        #0 0 0 => X
        #0 0 1 => X (missing mask)
        #0 1 0 => OK
        #0 1 1 => OK
        #1 0 0 => OK
        #1 0 1 => X (missing mask)
        #1 1 0 => OK
        #1 1 1 => OK

        if mask_path != '':
            try:
                mask = gf.Image(mask_path)
                mask.imread()
            except Exception as e:
                self.logger.exception('Error loading mask')
                return
        if graph_path != '':
            try:
                graph = gf.load_cell_tracking_graph(graph_path,mask.image.dtype)
            except Exception as e:
                self.logger.exception('Error loading graph')
                return
        if image_path != '':
            try:
                image = gf.Image(image_path)
                image.imread()
            except Exception as e:
                self.logger.exception('Error loading image')
                return

        viewer_images = napari.Viewer(title=mask_path if mask_path != '' else image_path)
        if image_path != '':
            viewer_images.add_image(image.get_TYXarray(), name="Image")
        if mask_path != '':
            mask_layer = viewer_images.add_labels(mask.get_TYXarray(), name="Cell mask")
            mask_layer.help = "<left-click> to set view"
            mask_layer.editable = False
            # In the current version of napari (v0.4.17), editable is set to True whenever we change the axis value by clicking on the corresponding slider.
            # This is a quick and dirty hack to force the layer to stay non-editable.
            mask_layer.events.editable.connect(lambda e: setattr(e.source,'editable',False))

        if graph_path != '':
            viewer_graph = napari.Viewer(title='Cell tracking graph')
            # Hide "layer controls" and "layer list" docks
            viewer_graph.window._qt_viewer.dockLayerControls.toggleViewAction().trigger()
            viewer_graph.window._qt_viewer.dockLayerList.toggleViewAction().trigger()
            plot_cell_tracking_graph(viewer_graph, viewer_images, mask_layer, graph, mask_layer.get_color(range(mask.image.max()+1)),selectable=False)

            #add dock widget with help and close button
            layout = QVBoxLayout()
            groupbox = QGroupBox("Help")
            layout2 = QVBoxLayout()
            help_label = QLabel("Image viewer (this viewer):\n<left-click> on the Cell mask layer to center the view on the corresponding vertex in the cell tracking graph viewer.\n\nCell tracking graph viewer:\nVertices (squares) correspond to mask regions (mask id) at a given frame. Edges correspond to overlap between mask. Vertices are ordered by time along the horizontal axis (time increases from left to right).\n<left-click> on a vertex to center the view on the corresponding mask in this viewer.")
            help_label.setWordWrap(True)
            help_label.setMinimumWidth(10)
            layout2.addWidget(help_label)
            # Create a button to quit
            button = QPushButton("Quit")
            button.clicked.connect(viewer_graph.close)
            button.clicked.connect(viewer_images.close)
            layout2.addWidget(button)
            groupbox.setLayout(layout2)
            layout.addWidget(groupbox)
            layout.addStretch()

            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setWidget(QWidget())
            scroll_area.widget().setLayout(layout)
            viewer_images.window.add_dock_widget(scroll_area, area='right', name="Cell tracking")


class Viewer(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout()

        # View image, mask and/or cell tracking graph
        groupbox = QGroupBox("View image, mask and/or cell-tracking graph")
        layout2 = QVBoxLayout()
        layout.addWidget(groupbox)
        layout2.addWidget(ImageMaskGraphViewer())
        groupbox.setLayout(layout2)

        self.setLayout(layout)

        self.logger = logging.getLogger(__name__)


