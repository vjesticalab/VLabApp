import os
import re
from PyQt5.QtWidgets import QFileDialog, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QGroupBox, QGridLayout, QScrollArea, QGroupBox, QTextEdit, QSizePolicy
from PyQt5.QtCore import Qt
from general import general_functions as gf
import napari
import logging
import igraph as ig
import numpy as np
from ome_types.model import CommentAnnotation
from modules.cell_tracking_module.cell_tracking_functions import plot_cell_tracking_graph
from modules.registration_module.registration_functions import EditTransformationMatrix, PlotTransformation
from matplotlib.backend_bases import MouseButton

class ImageMaskGraphViewer(QWidget):
    def __init__(self):
        super().__init__()

        label_documentation = QLabel()
        label_documentation.setOpenExternalLinks(True)
        label_documentation.setWordWrap(True)
        label_documentation.setText('View an image, a segmentation mask and/or a cell tracking graph in <a href="https://napari.org">napari</a>.<br>' +
                                    'Images and masks with X and Y axes and any combination of T, C and Z axes are supported.<br>' +
                                    'Image, mask and graph are optional. However, a cell tracking graph cannot be viewed without the corresponding segmentation mask.')
        self.input_image = gf.DropFileLineEdit(filetypes=gf.imagetypes)
        browse_image_button = QPushButton("Browse", self)
        browse_image_button.clicked.connect(self.browse_image)
        self.input_mask = gf.DropFileLineEdit(filetypes=gf.imagetypes)
        self.input_mask.textChanged.connect(self.input_mask_changed)
        browse_mask_button = QPushButton("Browse", self)
        browse_mask_button.clicked.connect(self.browse_mask)
        self.input_graph = gf.DropFileLineEdit(filetypes=gf.graphtypes)
        self.input_graph.textChanged.connect(self.input_graph_changed)
        browse_graph_button = QPushButton("Browse", self)
        browse_graph_button.clicked.connect(self.browse_graph)
        self.open_button = QPushButton("Open napari", self)
        self.open_button.clicked.connect(self.open)

        layout = QVBoxLayout()
        groupbox = QGroupBox("Documentation")
        layout2 = QVBoxLayout()
        collapsible_widget = gf.CollapsibleWidget('', collapsed_icon="▶ (show)", expanded_icon="▼ (hide)", expanded=False)
        collapsible_widget.content.setLayout(QVBoxLayout())
        collapsible_widget.content.layout().addWidget(label_documentation)
        collapsible_widget.content.layout().setContentsMargins(0,0,0,0)
        layout2.addWidget(collapsible_widget)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
        groupbox = QGroupBox("Image")
        layout2 = QHBoxLayout()
        layout2.addWidget(self.input_image)
        layout2.addWidget(browse_image_button, alignment=Qt.AlignCenter)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
        groupbox = QGroupBox("Segmentation mask")
        layout2 = QHBoxLayout()
        layout2.addWidget(self.input_mask)
        layout2.addWidget(browse_mask_button, alignment=Qt.AlignCenter)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
        groupbox = QGroupBox("Cell tracking graph")
        layout2 = QHBoxLayout()
        layout2.addWidget(self.input_graph)
        layout2.addWidget(browse_graph_button, alignment=Qt.AlignCenter)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

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
            res = re.match('(.*)'+gf.output_suffixes['segmentation']+'.*$',os.path.basename(mask_path))
            if res:
                for ext in gf.imagetypes:
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
            res = re.match('(.*)'+gf.output_suffixes['segmentation']+'.*$',os.path.basename(graph_path))
            if res:
                for ext in gf.imagetypes:
                    image_path = os.path.join(os.path.dirname(graph_path),res.group(1)) + ext
                    if os.path.isfile(image_path):
                        self.input_image.setPlaceholderText(image_path)
                        self.input_image.setToolTip(image_path)
                        break

    def browse_graph(self):
        file_path, _ = QFileDialog.getOpenFileName(self, 'Select Files', filter='Cell tracking graphs ('+' '.join(['*'+x for x in gf.graphtypes])+')')
        self.input_graph.setText(file_path)

    def browse_mask(self):
        file_path, _ = QFileDialog.getOpenFileName(self, 'Select Files', filter='Images ('+' '.join(['*'+x for x in gf.imagetypes])+')')
        self.input_mask.setText(file_path)

    def browse_image(self):
        file_path, _ = QFileDialog.getOpenFileName(self, 'Select Files', filter='Images ('+' '.join(['*'+x for x in gf.imagetypes])+')')
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
            except:
                self.logger.exception('Error loading mask')
                return
        if graph_path != '':
            try:
                graph = gf.load_cell_tracking_graph(graph_path,mask.image.dtype)
            except:
                self.logger.exception('Error loading graph')
                return
        if image_path != '':
            try:
                image = gf.Image(image_path)
                image.imread()
            except:
                self.logger.exception('Error loading image')
                return

        viewer_images = napari.Viewer(title=mask_path if mask_path != '' else image_path)
        if image_path != '':
            viewer_images.add_image(image.image, channel_axis=2, name=['Image [' + x + ']' for x in image.channel_names] if image.channel_names else 'Image')
            # channel axis is already used as channel_axis (layers) => it is not in viewer.dims:
            viewer_images.dims.axis_labels = ('F', 'T', 'Z', 'Y', 'X')
        if mask_path != '':
            #Assume a TYX mask, broadcast to FTZYX with F and Z axis containing shallow copies (C axis is used as channel_axis):
            mask_TYX = mask.get_TYXarray()
            sizeF = image.image.shape[0] if image_path != '' else 1
            sizeZ = image.image.shape[3] if image_path != '' else 1
            mask_FTZYX=np.broadcast_to(mask_TYX[np.newaxis,:,np.newaxis,:,:], (sizeF, mask_TYX.shape[0], sizeZ, mask_TYX.shape[1], mask_TYX.shape[2]))
            # the resulting mask_FTZYX is read only. To make it writeable:
            # mask_FTZYX.flags['WRITEABLE']=True
            mask_layer = viewer_images.add_labels(mask_FTZYX, name="Cell mask")
            viewer_images.dims.axis_labels = ('F', 'T', 'Z', 'Y', 'X')
            #mask_layer = viewer_images.add_labels(mask.image, name="Cell mask", channel_axis=2)
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



class RegistrationViewer(QWidget):
    def __init__(self):
        super().__init__()

        label_documentation = QLabel()
        label_documentation.setOpenExternalLinks(True)
        label_documentation.setWordWrap(True)
        label_documentation.setText('View a registration matrix in <a href="https://napari.org">napari</a>.<br>' +
                                    'Important: select an image that has not been registered.<br>' +
                                    'Input images must have X, Y and T axes and can optionally have Z and/or C axes.')
        self.input_image = gf.DropFileLineEdit(filetypes=gf.imagetypes)
        self.input_image.textChanged.connect(self.input_image_changed)
        browse_image_button = QPushButton("Browse", self)
        browse_image_button.clicked.connect(self.browse_image)
        self.input_matrix = gf.DropFileLineEdit(filetypes=gf.matrixtypes)
        self.input_matrix.textChanged.connect(self.input_matrix_changed)
        browse_matrix_button = QPushButton("Browse", self)
        browse_matrix_button.clicked.connect(self.browse_matrix)
        self.open_button = QPushButton("Open napari", self)
        self.open_button.clicked.connect(self.open)

        layout = QVBoxLayout()
        groupbox = QGroupBox("Documentation")
        layout2 = QVBoxLayout()
        collapsible_widget = gf.CollapsibleWidget('', collapsed_icon="▶ (show)", expanded_icon="▼ (hide)", expanded=False)
        collapsible_widget.content.setLayout(QVBoxLayout())
        collapsible_widget.content.layout().addWidget(label_documentation)
        collapsible_widget.content.layout().setContentsMargins(0,0,0,0)
        layout2.addWidget(collapsible_widget)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
        groupbox = QGroupBox("Image (before registration)")
        layout2 = QHBoxLayout()
        layout2.addWidget(self.input_image)
        layout2.addWidget(browse_image_button, alignment=Qt.AlignCenter)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
        groupbox = QGroupBox("Registration matrix")
        layout2 = QHBoxLayout()
        layout2.addWidget(self.input_matrix)
        layout2.addWidget(browse_matrix_button, alignment=Qt.AlignCenter)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        layout.addWidget(self.open_button, alignment=Qt.AlignCenter)

        self.setLayout(layout)

        self.logger = logging.getLogger(__name__)

    def browse_image(self):
        file_path, _ = QFileDialog.getOpenFileName(self, 'Select Files', filter='Images ('+' '.join(['*'+x for x in gf.imagetypes])+')')
        self.input_image.setText(file_path)

    def browse_matrix(self):
        file_path, _ = QFileDialog.getOpenFileName(self, 'Select Files', filter='Transformation matrices ('+' '.join(['*'+x for x in gf.matrixtypes])+')')
        self.input_matrix.setText(file_path)

    def input_image_changed(self):
        image_path=self.input_image.text()
        self.input_image.setPlaceholderText('')
        self.input_image.setToolTip('')
        self.input_matrix.setPlaceholderText('')
        self.input_matrix.setToolTip('')
        if os.path.isfile(image_path):
            #get path with matrix filetype (self.matricestype), containing gf.output_suffixes['registration'] and with same unique identifier
            matrix_paths = [path for path in os.listdir(os.path.dirname(image_path)) if any(path.endswith(matricestype) for matricestype in gf.matrixtypes) and gf.output_suffixes['registration'] in path and os.path.basename(path).split('_')[0] == os.path.basename(image_path).split('_')[0]]
            if len(matrix_paths) > 0:
                matrix_path = os.path.join(os.path.dirname(image_path),sorted(matrix_paths, key=len)[0])
                if os.path.isfile(matrix_path):
                    self.input_matrix.setPlaceholderText(matrix_path)
                    self.input_matrix.setToolTip(matrix_path)

    def input_matrix_changed(self):
        matrix_path=self.input_matrix.text()
        self.input_image.setPlaceholderText('')
        self.input_image.setToolTip('')
        self.input_matrix.setPlaceholderText('')
        self.input_matrix.setToolTip('')
        if os.path.isfile(matrix_path):
            res = re.match('(.*)'+gf.output_suffixes['registration']+'.*$',os.path.basename(matrix_path))
            if res:
                for ext in gf.imagetypes:
                    image_path = os.path.join(os.path.dirname(matrix_path),res.group(1)) + ext
                    if os.path.isfile(image_path):
                        self.input_image.setPlaceholderText(image_path)
                        self.input_image.setToolTip(image_path)
                        break

    def open(self):
        #EditTransformationMatrix, PlotTransformation
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
        if image_path != '' and not os.path.isfile(image_path):
            self.logger.error('Invalid image path')
            self.input_image.setFocus()
            return
        if matrix_path != '' and not os.path.isfile(matrix_path):
            self.logger.error('Invalid matrix path')
            self.input_matrix.setFocus()
            return

        try:
            image = gf.Image(image_path)
            image.imread()
        except:
            self.logger.exception('Error loading image')
            return

        # Check 'F' axis has size 1
        if image.sizes['F'] != 1:
            logging.getLogger(__name__).error('Image %s has a F axis with size > 1', str(image_path))
            raise TypeError(f"Image {image_path} has a F axis with size > 1")

        viewer = napari.Viewer()
        # assuming a FTCZYX image:
        viewer.add_image(image.image, channel_axis=2, name=['Image [' + x + ']' for x in image.channel_names] if image.channel_names else 'Image')
        # channel axis is already used as channel_axis (layers) => it is not in viewer.dims:
        viewer.dims.axis_labels = ('F', 'T', 'Z', 'Y', 'X')


        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        edit_transformation_matrix = EditTransformationMatrix(viewer, matrix_path, read_only=True)
        scroll_area.setWidget(edit_transformation_matrix)
        viewer.window.add_dock_widget(scroll_area, area='right', name="Edit transformation matrix")

        plot_transformation = PlotTransformation(viewer, edit_transformation_matrix.tmat)
        plot_transformation.fig.canvas.mpl_connect('button_press_event', lambda event: viewer.dims.set_point(1,round(event.xdata)) if event.button is event.button is MouseButton.LEFT and event.inaxes else None)
        plot_transformation.fig.canvas.mpl_connect('motion_notify_event', lambda event: viewer.dims.set_point(1,round(event.xdata)) if event.button is MouseButton.LEFT and event.inaxes else None)
        viewer.window.add_dock_widget(plot_transformation, area="bottom")

        edit_transformation_matrix.tmat_changed.connect(plot_transformation.update)


class MetadataViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.filetypes = gf.imagetypes + gf.graphtypes + gf.matrixtypes

        label_documentation = QLabel()
        label_documentation.setOpenExternalLinks(True)
        label_documentation.setWordWrap(True)
        label_documentation.setText('Display the VLabApp metadata for a file generated with this software. The file can be an image, a segmentation mask, a cell tracking graph or a registration matrix).')
        self.input_file = gf.DropFileLineEdit(filetypes=self.filetypes)
        self.input_file.textChanged.connect(self.input_file_changed)
        browse_file_button = QPushButton("Browse", self)
        browse_file_button.clicked.connect(self.browse_file)

        layout = QVBoxLayout()
        groupbox = QGroupBox("Documentation")
        layout2 = QVBoxLayout()
        collapsible_widget = gf.CollapsibleWidget('', collapsed_icon="▶ (show)", expanded_icon="▼ (hide)", expanded=False)
        collapsible_widget.content.setLayout(QVBoxLayout())
        collapsible_widget.content.layout().addWidget(label_documentation)
        collapsible_widget.content.layout().setContentsMargins(0,0,0,0)
        layout2.addWidget(collapsible_widget)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
        groupbox = QGroupBox("File")
        layout2 = QHBoxLayout()
        layout2.addWidget(self.input_file)
        layout2.addWidget(browse_file_button, alignment=Qt.AlignCenter)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        self.metadata_text = QTextEdit()
        self.metadata_text.setLineWrapMode(QTextEdit.NoWrap)
        self.metadata_text.setReadOnly(True)
        self.metadata_text.setVisible(False)
        layout.addWidget(self.metadata_text,stretch=1)
        layout.addStretch()
        
        self.setLayout(layout)

        self.logger = logging.getLogger(__name__)

    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, 'Select Files', filter='Images, cell tracking graphs or transformation matrices   ('+' '.join(['*'+x for x in gf.imagetypes])+')')
        self.input_file.setText(file_path)

    def input_file_changed(self):
        file_path=self.input_file.text()
        self.metadata_text.setPlainText('')
        self.metadata_text.setVisible(False)
        if os.path.isfile(file_path):
            self.show_metadata()

    def show_metadata(self):
        file_path=self.input_file.text()

        vlabapp_metadata = []
        image_metadata = None
        if gf.splitext(file_path)[1] in gf.imagetypes:
            image = gf.Image(file_path)
            if image.ome_metadata:
                for i,x in enumerate(image.ome_metadata.structured_annotations):
                    if isinstance(x, CommentAnnotation) and x.namespace == "VLabApp":
                        vlabapp_metadata.append(x.value)
            image_metadata = 'Dimensions: (' + ', '.join([k+': '+str(v) for (k, v) in image.sizes.items() if v > 1]) + ')\n'
            if image.channel_names:
                image_metadata += 'Channel names: \"' + '\", \"'.join([n for n in image.channel_names]) + '\"\n'
            if image.physical_pixel_sizes:
                image_metadata += 'Physical pixel sizes: (' + ', '.join([a+': '+str(v)+' \u03bcm' for a, v in zip(("X","Y","Z"),image.physical_pixel_sizes)]) + ')\n'
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
            graph = gf.load_cell_tracking_graph(file_path,'uint16')
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


class Viewer(QWidget):
    def __init__(self):
        super().__init__()

        window = QVBoxLayout(self)
        tabwizard = gf.TabWizard()

        tabwizard.addPage(gf.Page(widget=ImageMaskGraphViewer()), "View image, masks and/or graph")
        tabwizard.addPage(gf.Page(widget=RegistrationViewer()), "View registration matrix")
        tabwizard.addPage(gf.Page(widget=MetadataViewer(), add_stretch=False), "View metadata")

        window.addWidget(tabwizard)


        self.logger = logging.getLogger(__name__)


