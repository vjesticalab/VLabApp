import os
import re
import logging
from PyQt5.QtWidgets import QFileDialog, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QScrollArea, QGroupBox, QTextEdit
from PyQt5.QtCore import Qt
from general import general_functions as gf
import napari
import numpy as np
from ome_types.model import CommentAnnotation
from modules.cell_tracking_module.cell_tracking_functions import plot_cell_tracking_graph
from modules.registration_module.registration_functions import EditTransformationMatrix, PlotTransformation
from matplotlib.backend_bases import MouseButton


class ImageMaskGraphViewer(QWidget):
    def __init__(self):
        super().__init__()

        label_documentation = gf.CollapsibleLabel('', collapsed=True)
        label_documentation.setText('View an image, a segmentation mask and/or a cell tracking graph in <a href="https://napari.org">napari</a>.<br>' +
                                    'Images and masks with X and Y axes and any combination of T, C and Z axes are supported.<br>' +
                                    'Image, mask and graph are optional. However, a cell tracking graph cannot be viewed without the corresponding segmentation mask.<br>' +
                                    '<br>' +
                                    'Additional information: <a href="' + os.path.join(os.path.dirname(__file__), '..', '..', 'doc', 'site', 'viewer_image_mask_graph_module', 'reference.html') + '">Documentation</a>')

        self.input_image = gf.FileLineEdit(label='Images', filetypes=gf.imagetypes)
        self.input_mask = gf.FileLineEdit(label='Images', filetypes=gf.imagetypes)
        self.input_mask.textChanged.connect(self.input_mask_changed)
        self.input_graph = gf.FileLineEdit(label='Cell tracking graphs', filetypes=gf.graphtypes)
        self.input_graph.textChanged.connect(self.input_graph_changed)
        self.open_button = QPushButton("Open napari", self)
        self.open_button.clicked.connect(self.open)

        layout = QVBoxLayout()
        groupbox = QGroupBox("Documentation")
        layout2 = QVBoxLayout()
        layout2.addWidget(label_documentation)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
        groupbox = QGroupBox("Image")
        layout2 = QVBoxLayout()
        layout2.addWidget(self.input_image)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
        groupbox = QGroupBox("Segmentation mask")
        layout2 = QVBoxLayout()
        layout2.addWidget(self.input_mask)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
        groupbox = QGroupBox("Cell tracking graph")
        layout2 = QVBoxLayout()
        layout2.addWidget(self.input_graph)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        layout.addWidget(self.open_button, alignment=Qt.AlignCenter)

        self.setLayout(layout)

        self.logger = logging.getLogger(__name__)

    def input_mask_changed(self):
        mask_path = self.input_mask.text()
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
            res = re.match('(.*)'+gf.output_suffixes['segmentation']+'.*$', os.path.basename(mask_path))
            if res:
                for ext in gf.imagetypes:
                    image_path = os.path.join(os.path.dirname(mask_path), res.group(1)) + ext
                    if os.path.isfile(image_path):
                        self.input_image.setPlaceholderText(image_path)
                        self.input_image.setToolTip(image_path)
                        break

    def input_graph_changed(self):
        graph_path = self.input_graph.text()
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
            res = re.match('(.*)'+gf.output_suffixes['segmentation']+'.*$', os.path.basename(graph_path))
            if res:
                for ext in gf.imagetypes:
                    image_path = os.path.join(os.path.dirname(graph_path), res.group(1)) + ext
                    if os.path.isfile(image_path):
                        self.input_image.setPlaceholderText(image_path)
                        self.input_image.setToolTip(image_path)
                        break

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
            self.logger.error('Missing mask path (mandatory when graph path is not empty)')
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

        if mask_path != '':
            try:
                mask = gf.Image(mask_path)
                mask.imread()
            except Exception:
                self.logger.exception('Error loading mask')
                return
        if graph_path != '':
            try:
                graph = gf.load_cell_tracking_graph(graph_path, mask.image.dtype)
            except Exception:
                self.logger.exception('Error loading graph')
                return
        if image_path != '':
            try:
                image = gf.Image(image_path)
                image.imread()
            except Exception:
                self.logger.exception('Error loading image')
                return

        viewer_images = napari.Viewer(title=mask_path if mask_path != '' else image_path)
        if image_path != '':
            layers = viewer_images.add_image(image.image, channel_axis=2, name=['Image [' + x + ']' for x in image.channel_names] if image.channel_names else 'Image')
            for layer in layers:
                layer.editable = False
            # channel axis is already used as channel_axis (layers) => it is not in viewer.dims:
            viewer_images.dims.axis_labels = ('F', 'T', 'Z', 'Y', 'X')
        if mask_path != '':
            # Assume a TYX mask, broadcast to FTZYX with F and Z axis containing shallow copies (C axis is used as channel_axis):
            mask_TYX = mask.get_TYXarray()
            sizeF = image.image.shape[0] if image_path != '' else 1
            sizeZ = image.image.shape[3] if image_path != '' else 1
            mask_FTZYX = np.broadcast_to(mask_TYX[np.newaxis, :, np.newaxis, :, :], (sizeF, mask_TYX.shape[0], sizeZ, mask_TYX.shape[1], mask_TYX.shape[2]))
            # the resulting mask_FTZYX is read only. To make it writeable:
            # mask_FTZYX.flags['WRITEABLE']=True
            mask_layer = viewer_images.add_labels(mask_FTZYX, name="Cell mask")
            viewer_images.dims.axis_labels = ('F', 'T', 'Z', 'Y', 'X')
            mask_layer.help = "LEFT-CLICK to set view"
            mask_layer.editable = False

        if graph_path != '':
            viewer_graph = napari.Viewer(title='Cell tracking graph')
            # Hide "layer controls" and "layer list" docks
            viewer_graph.window._qt_viewer.dockLayerControls.toggleViewAction().trigger()
            viewer_graph.window._qt_viewer.dockLayerList.toggleViewAction().trigger()
            plot_cell_tracking_graph(viewer_graph, viewer_images, mask_layer, graph, mask_layer.get_color(range(mask.image.max()+1)), selectable=False)

            # add dock widget with help and close button
            layout = QVBoxLayout()
            groupbox = QGroupBox("Help")
            layout2 = QVBoxLayout()
            help_label = QLabel("Image viewer (this viewer):\nLEFT-CLICK on the Cell mask layer to center the view on the corresponding vertex in the cell tracking graph viewer.\n\nCell tracking graph viewer:\nVertices (squares) correspond to labelled regions (mask id) at a given frame. Edges correspond to overlap between mask. Vertices are ordered by time along the horizontal axis (time increases from left to right).\nLEFT-CLICK on a vertex to center the view on the corresponding mask in this viewer.")
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


class RegistrationViewer(QWidget):
    def __init__(self):
        super().__init__()

        label_documentation = gf.CollapsibleLabel('', collapsed=True)
        label_documentation.setText('View a registration matrix in <a href="https://napari.org">napari</a>.<br>' +
                                    'Important: select an image that has not been registered.<br>' +
                                    'Input images must have X, Y and T axes and can optionally have Z and/or C axes.<br>' +
                                    '<br>' +
                                    'Additional information: <a href="' + os.path.join(os.path.dirname(__file__), '..', '..', 'doc', 'site', 'viewer_registration_module', 'reference.html') + '">Documentation</a>')
        self.input_image = gf.FileLineEdit(label='Images', filetypes=gf.imagetypes)
        self.input_image.textChanged.connect(self.input_image_changed)
        self.input_matrix = gf.FileLineEdit(label='Transformation matrices', filetypes=gf.matrixtypes)
        self.input_matrix.textChanged.connect(self.input_matrix_changed)
        self.open_button = QPushButton("Open napari", self)
        self.open_button.clicked.connect(self.open)

        layout = QVBoxLayout()
        groupbox = QGroupBox("Documentation")
        layout2 = QVBoxLayout()
        layout2.addWidget(label_documentation)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
        groupbox = QGroupBox("Image (before registration)")
        layout2 = QVBoxLayout()
        layout2.addWidget(self.input_image)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
        groupbox = QGroupBox("Registration matrix")
        layout2 = QVBoxLayout()
        layout2.addWidget(self.input_matrix)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        layout.addWidget(self.open_button, alignment=Qt.AlignCenter)

        self.setLayout(layout)

        self.logger = logging.getLogger(__name__)

    def input_image_changed(self):
        image_path = self.input_image.text()
        self.input_image.setPlaceholderText('')
        self.input_image.setToolTip('')
        self.input_matrix.setPlaceholderText('')
        self.input_matrix.setToolTip('')
        if os.path.isfile(image_path):
            # get path with matrix filetype (self.matricestype), containing gf.output_suffixes['registration'] and with same unique identifier
            matrix_paths = [path for path in os.listdir(os.path.dirname(image_path)) if any(path.endswith(matricestype) for matricestype in gf.matrixtypes) and gf.output_suffixes['registration'] in path and os.path.basename(path).split('_')[0] == os.path.basename(image_path).split('_')[0]]
            if len(matrix_paths) > 0:
                matrix_path = os.path.join(os.path.dirname(image_path), sorted(matrix_paths, key=len)[0])
                if os.path.isfile(matrix_path):
                    self.input_matrix.setPlaceholderText(matrix_path)
                    self.input_matrix.setToolTip(matrix_path)

    def input_matrix_changed(self):
        matrix_path = self.input_matrix.text()
        self.input_image.setPlaceholderText('')
        self.input_image.setToolTip('')
        self.input_matrix.setPlaceholderText('')
        self.input_matrix.setToolTip('')
        if os.path.isfile(matrix_path):
            res = re.match('(.*)'+gf.output_suffixes['registration']+'.*$', os.path.basename(matrix_path))
            if res:
                for ext in gf.imagetypes:
                    image_path = os.path.join(os.path.dirname(matrix_path), res.group(1)) + ext
                    if os.path.isfile(image_path):
                        self.input_image.setPlaceholderText(image_path)
                        self.input_image.setToolTip(image_path)
                        break

    def open(self):
        matrix_path = self.input_matrix.text()
        if matrix_path == '':
            matrix_path = self.input_matrix.placeholderText()
        image_path = self.input_image.text()
        if image_path == '':
            image_path = self.input_image.placeholderText()

        if image_path == '':
            self.logger.error('Missing image path')
            self.input_image.setFocus()
            return
        if matrix_path == '':
            self.logger.error('Missing matrix path')
            self.input_matrix.setFocus()
            return
        if not os.path.isfile(image_path):
            self.logger.error('Invalid image path')
            self.input_image.setFocus()
            return
        if not os.path.isfile(matrix_path):
            self.logger.error('Invalid matrix path')
            self.input_matrix.setFocus()
            return

        try:
            image = gf.Image(image_path)
            image.imread()
        except Exception:
            self.logger.exception('Error loading image')
            return

        # Check 'F' axis has size 1
        if image.sizes['F'] != 1:
            logging.getLogger(__name__).error('Image %s has a F axis with size > 1', str(image_path))
            raise TypeError(f"Image {image_path} has a F axis with size > 1")

        viewer = napari.Viewer()
        # assuming a FTCZYX image:
        layers = viewer.add_image(image.image, channel_axis=2, name=['Image [' + x + ']' for x in image.channel_names] if image.channel_names else 'Image')
        for layer in layers:
            layer.editable = False

        # channel axis is already used as channel_axis (layers) => it is not in viewer.dims:
        viewer.dims.axis_labels = ('F', 'T', 'Z', 'Y', 'X')

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        edit_transformation_matrix = EditTransformationMatrix(viewer, matrix_path, read_only=True)
        scroll_area.setWidget(edit_transformation_matrix)
        viewer.window.add_dock_widget(scroll_area, area='right', name="Edit transformation matrix")

        plot_transformation = PlotTransformation(viewer, edit_transformation_matrix.tmat)
        plot_transformation.fig.canvas.mpl_connect('button_press_event', lambda event: viewer.dims.set_point(1, round(event.xdata)) if event.button is event.button is MouseButton.LEFT and event.inaxes else None)
        plot_transformation.fig.canvas.mpl_connect('motion_notify_event', lambda event: viewer.dims.set_point(1, round(event.xdata)) if event.button is MouseButton.LEFT and event.inaxes else None)
        viewer.window.add_dock_widget(plot_transformation, area="bottom")

        edit_transformation_matrix.tmat_changed.connect(plot_transformation.update)


class MetadataViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.filetypes = gf.imagetypes + gf.graphtypes + gf.matrixtypes

        label_documentation = gf.CollapsibleLabel('', collapsed=True)
        label_documentation.setText('Display the VLabApp metadata for a file generated with this software. The file can be an image, a segmentation mask, a cell tracking graph or a registration matrix).<br>' +
                                    '<br>' +
                                    'Additional information: <a href="' + os.path.join(os.path.dirname(__file__), '..', '..', 'doc', 'site', 'viewer_metadata_module', 'reference.html') + '">Documentation</a>')

        self.input_file = gf.FileLineEdit(label='Images, cell tracking graphs or transformation matrices', filetypes=self.filetypes)
        self.input_file.textChanged.connect(self.input_file_changed)

        layout = QVBoxLayout()
        groupbox = QGroupBox("Documentation")
        layout2 = QVBoxLayout()
        layout2.addWidget(label_documentation)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
        groupbox = QGroupBox("File")
        layout2 = QVBoxLayout()
        layout2.addWidget(self.input_file)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        self.metadata_text = QTextEdit()
        self.metadata_text.setLineWrapMode(QTextEdit.NoWrap)
        self.metadata_text.setReadOnly(True)
        self.metadata_text.setVisible(False)
        layout.addWidget(self.metadata_text, stretch=1)
        layout.addStretch()

        self.setLayout(layout)

        self.logger = logging.getLogger(__name__)

    def input_file_changed(self):
        file_path = self.input_file.text()
        self.metadata_text.setPlainText('')
        self.metadata_text.setVisible(False)
        if os.path.isfile(file_path):
            self.show_metadata()

    def show_metadata(self):
        file_path = self.input_file.text()

        vlabapp_metadata = []
        image_metadata = None
        if gf.splitext(file_path)[1] in gf.imagetypes:
            image = gf.Image(file_path)
            if image.ome_metadata:
                for x in image.ome_metadata.structured_annotations:
                    if isinstance(x, CommentAnnotation) and x.namespace == "VLabApp":
                        vlabapp_metadata.append(x.value)
            image_metadata = 'Dimensions: (' + ', '.join([k+': '+str(v) for (k, v) in image.sizes.items() if v > 1]) + ')\n'
            if image.channel_names:
                image_metadata += 'Channel names: \"' + '\", \"'.join(list(image.channel_names)) + '\"\n'
            if image.physical_pixel_sizes:
                image_metadata += 'Physical pixel sizes: (' + ', '.join([a+': '+str(v)+' \u03bcm' for a, v in zip(("X", "Y", "Z"), image.physical_pixel_sizes)]) + ')\n'
            image_metadata += 'Data type: ' + str(image.dtype) + '\n'
        elif gf.splitext(file_path)[1] in gf.matrixtypes:
            metadata_tmp = ''
            with open(file_path) as f:
                for line in f:
                    if line.startswith('# Metadata for') and not line.startswith("# timePoint,"):
                        vlabapp_metadata.append(metadata_tmp)
                        metadata_tmp = ''
                    if line.startswith('# ') and not line.startswith("# timePoint,"):
                        metadata_tmp += line[2:]
            if metadata_tmp:
                vlabapp_metadata.append(metadata_tmp)
        elif gf.splitext(file_path)[1] in gf.graphtypes:
            graph = gf.load_cell_tracking_graph(file_path, 'uint16')
            for a in graph.attributes():
                if a.startswith('VLabApp:Annotation'):
                    vlabapp_metadata.append(graph[a])

        text = ''
        if image_metadata:
            text += image_metadata
            if len(vlabapp_metadata) > 0:
                text += '\n---------------------------------------------\n\n'

        text += '\n\n'.join(vlabapp_metadata)
        self.metadata_text.setPlainText(text)
        self.metadata_text.setVisible(True)
