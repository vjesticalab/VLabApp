import logging
import os
import sys
import time
import concurrent.futures
from PyQt5.QtWidgets import QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QGroupBox, QRadioButton, QLabel, QFormLayout, QLineEdit, QComboBox, QApplication, QCheckBox, QSpinBox, QColorDialog
from PyQt5.QtCore import Qt, QRegularExpression, QEvent
from PyQt5.QtGui import QCursor, QRegularExpressionValidator, QColor, QPixmap, QFontMetrics
from modules.file_conversion_module import file_conversion_functions as f
from general import general_functions as gf


def process_initializer():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s (%(name)s) [%(levelname)s] %(message)s", handlers=[logging.StreamHandler(sys.stdout)], force=True)


class MaskGraphConversion(QWidget):
    def __init__(self):
        super().__init__()

        self.celltracking_suffix = gf.output_suffixes['cell_tracking']
        layout = QVBoxLayout()

        # Documentation
        label_documentation = gf.CollapsibleLabel('', collapsed=True)
        label_documentation.setText('Convert segmentation masks and/or cell tracking graphs to various file formats. VLabApp metadata are lost during conversion. The resulting masks and graphs are not meant to be read by this application.<br>' +
                                    '<h3>Available mask formats</h3>' +
                                    '<b>ImageJ (.zip)</b><br>' +
                                    '<a href="https://imagej.net/">ImageJ</a> ROI set (.zip), with ROIs named as "&lt;cell track id&gt;_&lt;time frame&gt;_&lt;mask id&gt;"' +
                                    '<h3>Available graph formats</h3>' +
                                    '<b>List of edges (.tsv)</b><br>' +
                                    'List of edges in tab-separated values format, with header in first row and the following columns:<br>' +
                                    '* id1: source vertex id (correspond to the ImageJ ROI name "&lt;cell_track_id&gt;_&lt;frame1&gt;_&lt;mask_id1&gt;")<br>' +
                                    '* frame1: source vertex time frame<br>' +
                                    '* mask_id1: source vertex mask id<br>' +
                                    '* area1: source vertex area (number of pixels)<br>' +
                                    '* id2: target vertex id (correspond to the ImageJ ROI name "&lt;cell_track_id&gt;_&lt;frame2&gt;_&lt;mask_id2&gt;")<br>' +
                                    '* frame2: target vertex time frame<br>' +
                                    '* mask_id2: target vertex mask id<br>' +
                                    '* area2: target vertex area (number of pixels)<br>' +
                                    '* overlap_area: overlap between source and target vertices (number of pixels)<br>' +
                                    '* cell_track_id: cell track id<br>' +
                                    'Isolated vertices appear in the list with target vertex and edge properties set to "nan".<br>' +
                                    '<br>' +
                                    '<b>Graphviz (.dot)</b><br>' +
                                    '<a href="https://www.graphviz.org/">Graphviz</a> format, with vertices named as "&lt;cell track id&gt;_&lt;time frame&gt;_&lt;mask id&gt;"<br>' +
                                    '<br>' +
                                    '<b>GraphML (.graphml)</b><br>' +
                                    '<a href="http://graphml.graphdrawing.org/">GraphML</a> format (.graphml), with vertices named as "&lt;cell track id&gt;_&lt;time frame&gt;_&lt;mask id&gt;"<br>'
                                    )
        groupbox = QGroupBox('Documentation')
        layout2 = QVBoxLayout()
        layout2.addWidget(label_documentation)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        self.mask_graph_table = gf.FileTableWidget2(header_1='Mask', header_2='Graph', filenames_suffix_1='.ome.tif', filenames_suffix_2='.graphmlz', filenames_filter=self.celltracking_suffix)
        groupbox = QGroupBox('Input files (segmentation masks and cell tracking graphs)')
        layout2 = QVBoxLayout()
        layout2.addWidget(self.mask_graph_table)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        self.use_input_folder = QRadioButton('Use input mask and graph folder')
        self.use_input_folder.setChecked(True)
        self.use_input_folder.toggled.connect(self.update_output_filename_label)
        self.use_custom_folder = QRadioButton('Use custom folder (same for all the input files)')
        self.use_custom_folder.setChecked(False)
        self.use_custom_folder.toggled.connect(self.update_output_filename_label)
        self.output_folder = gf.FolderLineEdit()
        self.output_folder.textChanged.connect(self.update_output_filename_label)
        self.output_folder.setVisible(self.use_custom_folder.isChecked())
        self.use_custom_folder.toggled.connect(self.output_folder.setVisible)
        self.output_user_suffix = QLineEdit()
        self.output_user_suffix.setToolTip('Allowed characters: A-Z, a-z, 0-9 and -')
        self.output_user_suffix.setValidator(QRegularExpressionValidator(QRegularExpression('_?[A-Za-z0-9-]*')))
        self.output_user_suffix.textChanged.connect(self.update_output_filename_label)
        self.output_filename_label_mask = QLineEdit()
        self.output_filename_label_mask.setFrame(False)
        self.output_filename_label_mask.setEnabled(False)
        self.output_filename_label_mask.textChanged.connect(self.output_filename_label_mask.setToolTip)
        self.output_filename_label_graph = QLineEdit()
        self.output_filename_label_graph.setFrame(False)
        self.output_filename_label_graph.setEnabled(False)
        self.output_filename_label_graph.textChanged.connect(self.output_filename_label_graph.setToolTip)
        groupbox = QGroupBox('Output')
        layout2 = QVBoxLayout()
        layout2.addWidget(QLabel('Folder:'))
        layout2.addWidget(self.use_input_folder)
        layout2.addWidget(self.use_custom_folder)
        layout2.addWidget(self.output_folder)
        layout3 = QFormLayout()
        layout3.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        layout3.addRow('Suffix:', self.output_user_suffix)
        layout4 = QVBoxLayout()
        layout4.setSpacing(0)
        layout4.addWidget(self.output_filename_label_mask)
        layout4.addWidget(self.output_filename_label_graph)
        layout3.addRow('Filename:', layout4)
        layout2.addLayout(layout3)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        groupbox = QGroupBox('Options')
        layout2 = QVBoxLayout()
        self.convert_mask = QGroupBox('Convert segmentation mask')
        self.convert_mask.setCheckable(True)
        self.convert_mask.toggled.connect(self.output_filename_label_mask.setVisible)
        layout3 = QFormLayout()
        label_documentation_mask = QLabel('Export segmentation mask as <a href="https://imagej.net/">ImageJ</a> ROI set (.zip)')
        label_documentation_mask.setOpenExternalLinks(True)
        label_documentation_mask.setWordWrap(True)
        layout3.addRow(label_documentation_mask)
        self.convert_mask.setLayout(layout3)
        layout2.addWidget(self.convert_mask)
        self.convert_graph = QGroupBox('Convert cell tracking graph')
        self.convert_graph.setCheckable(True)
        self.convert_graph.toggled.connect(self.output_filename_label_graph.setVisible)
        layout3 = QFormLayout()
        self.output_graph_format = QComboBox()
        self.output_graph_format.addItem('List of edges (.tsv)')
        self.output_graph_format.addItem('Graphviz dot format (.dot)')
        self.output_graph_format.addItem('GraphML format (.graphml)')
        self.output_graph_format.setCurrentText('List of edges (.tsv)')
        self.output_graph_format.currentTextChanged.connect(self.update_output_filename_label)
        layout3.addRow('File format:', self.output_graph_format)
        self.label_documentation_graph = QLabel()
        self.label_documentation_graph.setOpenExternalLinks(True)
        self.label_documentation_graph.setWordWrap(True)
        self.output_graph_format.currentTextChanged.connect(self.update_label_documentation_graph)
        layout3.addRow(self.label_documentation_graph)
        self.convert_graph.setLayout(layout3)
        layout2.addWidget(self.convert_graph)
        self.output_per_celltrack = QCheckBox('Output one file per cell track')
        self.output_per_celltrack.setChecked(False)
        self.output_per_celltrack.toggled.connect(self.update_output_filename_label)
        layout2.addWidget(self.output_per_celltrack)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        groupbox = QGroupBox("Multi-processing")
        layout2 = QFormLayout()
        self.nprocesses = QSpinBox()
        self.nprocesses.setMinimum(1)
        self.nprocesses.setMaximum(os.cpu_count())
        self.nprocesses.setValue(1)
        layout2.addRow("Number of processes:", self.nprocesses)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        self.submit_button = QPushButton('Submit')
        self.submit_button.clicked.connect(self.submit)
        layout.addWidget(self.submit_button, alignment=Qt.AlignCenter)

        self.setLayout(layout)

        self.logger = logging.getLogger(__name__)

        self.update_label_documentation_graph()
        self.update_output_filename_label()

    def update_label_documentation_graph(self):
        if self.output_graph_format.currentText() == 'List of edges (.tsv)':
            self.label_documentation_graph.setText('Export cell tracking graph as a list of edges in tab-separated values format.')
        elif self.output_graph_format.currentText() == 'Graphviz dot format (.dot)':
            self.label_documentation_graph.setText('Export cell tracking graph in <a href="https://www.graphviz.org/">Graphviz</a> format.')
        elif self.output_graph_format.currentText() == 'GraphML format (.graphml)':
            self.label_documentation_graph.setText('Export cell tracking graph in <a href="http://graphml.graphdrawing.org/">GraphML</a> format.')

    def update_output_filename_label(self):
        if self.use_input_folder.isChecked():
            output_path = '<input folder>'
        else:
            output_path = os.path.abspath(self.output_folder.text())

        mask_ext = '.zip'
        if self.output_graph_format.currentText() == 'List of edges (.tsv)':
            graph_ext = '.tsv'
        elif self.output_graph_format.currentText() == 'Graphviz dot format (.dot)':
            graph_ext = '.dot'
        elif self.output_graph_format.currentText() == 'GraphML format (.graphml)':
            graph_ext = '.graphml'

        if self.output_per_celltrack.isChecked():
            celltrack_suffix = '_<cell track id>'
        else:
            celltrack_suffix = ''

        self.output_filename_label_mask.setText(os.path.normpath(os.path.join(output_path, '<input basename>' + self.output_user_suffix.text() + celltrack_suffix + mask_ext)))
        self.output_filename_label_graph.setText(os.path.normpath(os.path.join(output_path, '<input basename>' + self.output_user_suffix.text() + celltrack_suffix + graph_ext)))

    def submit(self):

        mask_graph_paths = self.mask_graph_table.get_file_table()
        mask_paths = [mask_path for mask_path, graph_path in mask_graph_paths]
        graph_paths = [graph_path for mask_path, graph_path in mask_graph_paths]
        user_suffix = self.output_user_suffix.text()
        output_basenames = [gf.splitext(os.path.basename(mask_path))[0] + user_suffix for mask_path in mask_paths]
        if self.use_input_folder.isChecked():
            output_paths = [os.path.dirname(mask_path) for mask_path in mask_paths]
        else:
            output_paths = [self.output_folder.text() for path in mask_paths]

        output_mask_format = 'imagejroi' if self.convert_mask.isChecked() else None
        output_graph_format = None
        if self.convert_graph.isChecked():
            if self.output_graph_format.currentText() == 'List of edges (.tsv)':
                output_graph_format = 'tsv'
            elif self.output_graph_format.currentText() == 'Graphviz dot format (.dot)':
                output_graph_format = 'dot'
            elif self.output_graph_format.currentText() == 'GraphML format (.graphml)':
                output_graph_format = 'graphml'

        # check input
        if len(mask_graph_paths) == 0:
            self.logger.error('Segmentation mask and cell tracking graph missing')
            return
        for mask_path in mask_paths:
            if not os.path.isfile(mask_path):
                self.logger.error('Segmentation mask not found: %s', mask_path)
                return
        for graph_path in graph_paths:
            if not os.path.isfile(graph_path):
                self.logger.error('Cell tracking graph not found: %s', graph_path)
                return
        if self.output_folder.text() == '' and not self.use_input_folder.isChecked():
            self.logger.error('Output folder missing')
            self.output_folder.setFocus()
            return
        if not self.convert_graph.isChecked() and not self.convert_mask.isChecked():
            self.logger.error('Al least one of the conversion options (mask or graph) must be selected.')
            self.convert_mask.setFocus()
            return

        output_files = [os.path.join(d, f) for d, f in zip(output_paths, output_basenames)]
        duplicates = [x for x, y in zip(mask_paths, output_files) if output_files.count(y) > 1]
        if len(duplicates) > 0:
            self.logger.error('More than one input file will output to the same file (output files will be overwritten).\nEither use input mask and graph folder as output folder or avoid processing masks and graphs from different input folders.\nProblematic input files (masks):\n%s', '\n'.join(duplicates[:4] + (['...'] if len(duplicates) > 4 else [])))
            return

        for path in mask_paths:
            try:
                image = gf.Image(path)
            except Exception:
                self.logger.exception('Error loading:\n %s\n\nError message:', path)
                return

        # disable messagebox error handler
        messagebox_error_handler = None
        for h in logging.getLogger().handlers:
            if h.get_name() == 'messagebox_error_handler':
                messagebox_error_handler = h
                logging.getLogger().removeHandler(messagebox_error_handler)
                break

        QApplication.setOverrideCursor(QCursor(Qt.BusyCursor))
        QApplication.processEvents()

        arguments = []
        for mask_path, graph_path, output_path, output_basename in zip(mask_paths, graph_paths, output_paths, output_basenames):
            arguments.append((mask_path,
                              graph_path,
                              output_path,
                              output_basename,
                              output_mask_format,
                              output_graph_format,
                              self.output_per_celltrack.isChecked()))
        if not arguments:
            return
        nprocesses = min(len(arguments), self.nprocesses.value())

        status_dialog = gf.StatusTableDialog(mask_paths)
        status_dialog.ok_button.setEnabled(False)
        status_dialog.setModal(True)
        status_dialog.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.CustomizeWindowHint)
        status_dialog.show()
        QApplication.processEvents()
        time.sleep(0.01)

        with concurrent.futures.ProcessPoolExecutor(max_workers=nprocesses, initializer=process_initializer) as executor:
            future_reg = {executor.submit(f.convert_mask_and_graph, *args): i for i, args in enumerate(arguments)}
            QApplication.processEvents()
            time.sleep(0.01)
            for future in concurrent.futures.as_completed(future_reg):
                try:
                    future.result()
                    status_dialog.set_status(future_reg[future],'Success')
                except Exception as e:
                    self.logger.exception("An exception occurred")
                    status_dialog.set_status(future_reg[future],'Failed',str(e))
                QApplication.processEvents()
                time.sleep(0.01)

        # Restore cursor
        QApplication.restoreOverrideCursor()
        status_dialog.ok_button.setEnabled(True)

        # re-enable messagebox error handler
        if messagebox_error_handler is not None:
            logging.getLogger().addHandler(messagebox_error_handler)

        self.logger.info('Done')


class ImageMaskConversion(QWidget):
    def __init__(self):
        super().__init__()

        self.celltracking_suffix = gf.output_suffixes['cell_tracking']
        layout = QVBoxLayout()

        # Documentation
        label_documentation = gf.CollapsibleLabel('', collapsed=True)
        label_documentation.setText('Convert images and masks to small file-size preview movie (mp4) or image (jpg). The resulting mp4 movies or jpg images are encoded using lossy compression, which results in data loss and distortion. These files should not be used for scientific applications. In addition, when converting to mp4 movie, X and Y axes are resized to the nearest multiple of 16.')
        groupbox = QGroupBox('Documentation')
        layout2 = QVBoxLayout()
        layout2.addWidget(label_documentation)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        self.image_list = gf.FileListWidget(filetypes=gf.imagetypes)
        groupbox = QGroupBox('Input files (images or masks)')
        layout2 = QVBoxLayout()
        layout2.addWidget(self.image_list)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        self.use_input_folder = QRadioButton('Use input image/mask folder')
        self.use_input_folder.setChecked(True)
        self.use_input_folder.toggled.connect(self.update_output_filename_label)
        self.use_custom_folder = QRadioButton('Use custom folder (same for all the input files)')
        self.use_custom_folder.setChecked(False)
        self.use_custom_folder.toggled.connect(self.update_output_filename_label)
        self.output_folder = gf.FolderLineEdit()
        self.output_folder.textChanged.connect(self.update_output_filename_label)
        self.output_folder.setVisible(self.use_custom_folder.isChecked())
        self.use_custom_folder.toggled.connect(self.output_folder.setVisible)
        self.output_user_suffix = QLineEdit()
        self.output_user_suffix.setToolTip('Allowed characters: A-Z, a-z, 0-9 and -')
        self.output_user_suffix.setValidator(QRegularExpressionValidator(QRegularExpression('_?[A-Za-z0-9-]*')))
        self.output_user_suffix.textChanged.connect(self.update_output_filename_label)
        self.output_filename_label = QLineEdit()
        self.output_filename_label.setFrame(False)
        self.output_filename_label.setEnabled(False)
        self.output_filename_label.textChanged.connect(self.output_filename_label.setToolTip)
        groupbox = QGroupBox('Output')
        layout2 = QVBoxLayout()
        layout2.addWidget(QLabel('Folder:'))
        layout2.addWidget(self.use_input_folder)
        layout2.addWidget(self.use_custom_folder)
        layout2.addWidget(self.output_folder)
        layout3 = QFormLayout()
        layout3.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        layout3.addRow('Suffix:', self.output_user_suffix)
        layout4 = QVBoxLayout()
        layout4.setSpacing(0)
        layout4.addWidget(self.output_filename_label)
        layout3.addRow('Filename:', layout4)
        layout2.addLayout(layout3)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        groupbox = QGroupBox('Options')
        layout2 = QVBoxLayout()
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        # input type
        groupbox2 = QGroupBox('Input type:')
        layout3 = QVBoxLayout()
        self.input_type_auto = QRadioButton('Auto-detect')
        self.input_type_auto.setToolTip('Try to detect input file types using a heuristic.')
        self.input_type_auto.setChecked(True)
        layout3.addWidget(self.input_type_auto)
        self.input_type_image = QRadioButton('Images')
        self.input_type_image.setToolTip('Consider all input files as images')
        layout3.addWidget(self.input_type_image)
        self.input_type_mask = QRadioButton('Segmentation masks')
        self.input_type_mask.setToolTip('Consider all input files as segmentation masks')
        layout3.addWidget(self.input_type_mask)
        groupbox2.setLayout(layout3)
        layout2.addWidget(groupbox2)

        # channels
        groupbox2 = QGroupBox('Channels:')
        layout3 = QFormLayout()
        self.autocontrast = QCheckBox('Auto-contrast')
        self.autocontrast.setChecked(True)
        layout3.addRow(self.autocontrast)
        label = QLabel('Channel colors:')
        label.setWordWrap(True)
        layout3.addRow(label)
        colors = ['#FFFFFF', '#FF0000', '#00FF00', '#0000FF', '#00FFFF', '#FF00FF', '#FFFF00']
        self.channel_colors = []
        h = QFontMetrics(self.font()).height()
        for i, color in enumerate(colors):
            pixmap = QPixmap(2*h, h)
            pixmap.fill(QColor(color))
            label = QLabel()
            label.setPixmap(pixmap)
            label.installEventFilter(self)
            self.channel_colors.append(label)
            layout3.addRow('Channel '+str(i)+':', label)
        groupbox2.setLayout(layout3)
        layout2.addWidget(groupbox2)

        groupbox2 = QGroupBox('If multiple z:')
        layout3 = QFormLayout()
        # Z-Projection range
        # only bestZ
        self.projection_mode_bestZ = QRadioButton('Z section with best focus')
        self.projection_mode_bestZ.setChecked(True)
        self.projection_mode_bestZ.setToolTip('Keep only Z section with best focus.')
        # around bestZ
        self.projection_mode_around_bestZ = QRadioButton('Range around Z section with best focus')
        self.projection_mode_around_bestZ.setChecked(False)
        self.projection_mode_around_bestZ.setToolTip('Project all Z sections with Z in the interval [bestZ-range,bestZ+range], where bestZ is the Z section with best focus.')
        self.projection_mode_around_bestZ_zrange = QSpinBox()
        self.projection_mode_around_bestZ_zrange.setMinimum(0)
        self.projection_mode_around_bestZ_zrange.setMaximum(20)
        self.projection_mode_around_bestZ_zrange.setValue(3)
        # fixed range
        self.projection_mode_fixed = QRadioButton('Fixed range')
        self.projection_mode_fixed.setChecked(False)
        self.projection_mode_fixed.setToolTip('Project all Z sections with Z in the interval [from,to].')
        self.projection_mode_fixed_zmin = QSpinBox()
        self.projection_mode_fixed_zmin.setMinimum(0)
        self.projection_mode_fixed_zmin.setMaximum(6)
        self.projection_mode_fixed_zmin.setValue(4)
        self.projection_mode_fixed_zmin.valueChanged.connect(self.projection_mode_fixed_zmin_changed)
        self.projection_mode_fixed_zmax = QSpinBox()
        self.projection_mode_fixed_zmax.setMinimum(4)
        self.projection_mode_fixed_zmax.setMaximum(20)
        self.projection_mode_fixed_zmax.setValue(6)
        self.projection_mode_fixed_zmax.valueChanged.connect(self.projection_mode_fixed_zmax_changed)
        # all
        self.projection_mode_all = QRadioButton('All Z sections')
        self.projection_mode_all.setChecked(False)
        self.projection_mode_all.setToolTip('Project all Z sections.')
        widget = QWidget()
        layout4 = QVBoxLayout()
        layout4.addWidget(self.projection_mode_bestZ)
        layout4.addWidget(self.projection_mode_around_bestZ)
        groupbox3 = QGroupBox()
        groupbox3.setToolTip('Project all Z sections with Z in the interval [bestZ-range,bestZ+range], where bestZ is the Z section with best focus.')
        groupbox3.setVisible(self.projection_mode_around_bestZ.isChecked())
        self.projection_mode_around_bestZ.toggled.connect(groupbox3.setVisible)
        layout5 = QFormLayout()
        layout5.addRow('Range:', self.projection_mode_around_bestZ_zrange)
        groupbox3.setLayout(layout5)
        layout4.addWidget(groupbox3)
        layout4.addWidget(self.projection_mode_fixed)
        groupbox3 = QGroupBox()
        groupbox3.setToolTip('Project all Z sections with Z in the interval [from,to].')
        groupbox3.setVisible(self.projection_mode_fixed.isChecked())
        self.projection_mode_fixed.toggled.connect(groupbox3.setVisible)
        layout5 = QHBoxLayout()
        layout6 = QFormLayout()
        layout6.addRow('From:', self.projection_mode_fixed_zmin)
        layout5.addLayout(layout6)
        layout6 = QFormLayout()
        layout6.addRow('To:', self.projection_mode_fixed_zmax)
        layout5.addLayout(layout6)
        groupbox3.setLayout(layout5)
        layout4.addWidget(groupbox3)
        layout4.addWidget(self.projection_mode_all)
        widget.setLayout(layout4)
        layout3.addRow('Projection range:', widget)
        # Z-Projection type
        self.projection_type = QComboBox()
        self.projection_type.addItem('max')
        self.projection_type.addItem('min')
        self.projection_type.addItem('mean')
        self.projection_type.addItem('median')
        self.projection_type.addItem('std')
        self.projection_type.setCurrentText('mean')
        self.projection_type.setDisabled(self.projection_mode_bestZ.isChecked())
        self.projection_mode_bestZ.toggled.connect(self.projection_type.setDisabled)
        layout3.addRow('Projection type:', self.projection_type)
        groupbox2.setLayout(layout3)
        layout2.addWidget(groupbox2)

        # output format
        groupbox2 = QGroupBox('Output format:')
        layout3 = QVBoxLayout()
        self.output_format_auto = QRadioButton('Auto')
        self.output_format_auto.setToolTip('Convert to mp4 movie if input file has more than one time frame, to jpg otherwise.')
        self.output_format_auto.setChecked(True)
        self.output_format_auto.toggled.connect(self.update_output_filename_label)
        layout3.addWidget(self.output_format_auto)
        self.output_format_jpg = QRadioButton('jpg images')
        self.output_format_jpg.setToolTip('Convert all files to jpg images (first time frame).')
        self.output_format_jpg.toggled.connect(self.update_output_filename_label)
        layout3.addWidget(self.output_format_jpg)
        self.output_format_mp4 = QRadioButton('mp4 movies')
        self.output_format_mp4.setToolTip('Convert all files to mp4 movies. This option can generate unreadable mp4 movies if the number of time frames is too low')
        self.output_format_mp4.toggled.connect(self.update_output_filename_label)
        layout3.addWidget(self.output_format_mp4)
        groupbox2.setLayout(layout3)
        layout2.addWidget(groupbox2)

        # movie option
        groupbox2 = QGroupBox('Output options (mp4 movie):')
        layout3 = QFormLayout()
        self.output_quality = QSpinBox()
        self.output_quality.setMinimum(0)
        self.output_quality.setMaximum(10)
        self.output_quality.setValue(5)
        layout3.addRow('Quality:', self.output_quality)
        self.output_fps = QSpinBox()
        self.output_fps.setMinimum(0)
        self.output_fps.setMaximum(30)
        self.output_fps.setValue(10)
        layout3.addRow('Frames per second:', self.output_fps)
        groupbox2.setLayout(layout3)
        layout2.addWidget(groupbox2)

        groupbox = QGroupBox("Multi-processing")
        layout2 = QFormLayout()
        self.nprocesses = QSpinBox()
        self.nprocesses.setMinimum(1)
        self.nprocesses.setMaximum(os.cpu_count())
        self.nprocesses.setValue(1)
        layout2.addRow("Number of processes:", self.nprocesses)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        self.submit_button = QPushButton('Submit')
        self.submit_button.clicked.connect(self.submit)
        layout.addWidget(self.submit_button, alignment=Qt.AlignCenter)

        self.setLayout(layout)

        self.logger = logging.getLogger(__name__)

        self.update_output_filename_label()

    def update_output_filename_label(self):
        if self.use_input_folder.isChecked():
            output_path = '<input folder>'
        else:
            output_path = os.path.abspath(self.output_folder.text())

        if self.output_format_mp4.isChecked():
            self.output_filename_label.setText(os.path.normpath(os.path.join(output_path, '<input basename>' + self.output_user_suffix.text() + '.mp4')))
        elif self.output_format_jpg.isChecked():
            self.output_filename_label.setText(os.path.normpath(os.path.join(output_path, '<input basename>' + self.output_user_suffix.text() + '.jpg')))
        else:
            self.output_filename_label.setText(os.path.normpath(os.path.join(output_path, '<input basename>' + self.output_user_suffix.text() + '.mp4 or .jpg')))

    def projection_mode_fixed_zmin_changed(self, value):
        self.projection_mode_fixed_zmax.setMinimum(value)

    def projection_mode_fixed_zmax_changed(self, value):
        self.projection_mode_fixed_zmin.setMaximum(value)

    def eventFilter(self, target, event):
        if target in self.channel_colors and event.type() == QEvent.MouseButtonRelease:
            color = QColorDialog.getColor(initial=target.pixmap().toImage().pixelColor(0, 0))
            if color.isValid():
                target.pixmap().fill(QColor(color))
                target.repaint()
            return True
        return False

    def submit(self):
        projection_type = self.projection_type.currentText()
        if self.projection_mode_bestZ.isChecked():
            projection_zrange = 0
        elif self.projection_mode_around_bestZ.isChecked():
            projection_zrange = self.projection_mode_around_bestZ_zrange.value()
        elif self.projection_mode_fixed.isChecked():
            projection_zrange = (self.projection_mode_fixed_zmin.value(), self.projection_mode_fixed_zmax.value())
        elif self.projection_mode_all.isChecked():
            projection_zrange = None

        colors = [x.pixmap().toImage().pixelColor(0, 0) for x in self.channel_colors]
        colors = [(x.red(), x.green(), x.blue()) for x in colors]

        if self.input_type_mask.isChecked():
            input_is_mask = True
        elif self.input_type_image.isChecked():
            input_is_mask = False
        else:
            input_is_mask = None

        if self.output_format_jpg.isChecked():
            output_format = 'jpg'
        elif self.output_format_mp4.isChecked():
            output_format = 'mp4'
        else:
            output_format = 'auto'

        image_paths = self.image_list.get_file_list()
        user_suffix = self.output_user_suffix.text()
        output_basenames = [gf.splitext(os.path.basename(image_path))[0] + user_suffix for image_path in image_paths]
        if self.use_input_folder.isChecked():
            output_paths = [os.path.dirname(image_path) for image_path in image_paths]
        else:
            output_paths = [self.output_folder.text() for path in image_paths]

        # check input
        if len(image_paths) == 0:
            self.logger.error('Image or mask missing')
            return
        for image_path in image_paths:
            if not os.path.isfile(image_path):
                self.logger.error('Image or mask not found: %s', image_path)
                return
        if self.output_folder.text() == '' and not self.use_input_folder.isChecked():
            self.logger.error('Output folder missing')
            self.output_folder.setFocus()
            return

        output_files = [os.path.join(d, f) for d, f in zip(output_paths, output_basenames)]
        duplicates = [x for x, y in zip(image_paths, output_files) if output_files.count(y) > 1]
        if len(duplicates) > 0:
            self.logger.error('More than one input file will output to the same file (output files will be overwritten).\nEither use input image/mask folder as output folder or avoid processing image or masks from different input folders.\nProblematic input files:\n%s', '\n'.join(duplicates[:4] + (['...'] if len(duplicates) > 4 else [])))
            return

        for path in image_paths:
            try:
                image = gf.Image(path)
            except Exception:
                self.logger.exception('Error loading:\n %s\n\nError message:', path)
                return

        # disable messagebox error handler
        messagebox_error_handler = None
        for h in logging.getLogger().handlers:
            if h.get_name() == 'messagebox_error_handler':
                messagebox_error_handler = h
                logging.getLogger().removeHandler(messagebox_error_handler)
                break

        QApplication.setOverrideCursor(QCursor(Qt.BusyCursor))
        QApplication.processEvents()

        arguments = []
        for image_path, output_path, output_basename in zip(image_paths, output_paths, output_basenames):
            arguments.append((image_path,
                              output_path,
                              output_basename,
                              output_format,
                              projection_type,
                              projection_zrange,
                              input_is_mask,
                              colors,
                              self.autocontrast.isChecked(),
                              self.output_quality.value(),
                              self.output_fps.value()))
        if not arguments:
            return
        nprocesses = min(len(arguments), self.nprocesses.value())

        status_dialog = gf.StatusTableDialog(image_paths)
        status_dialog.ok_button.setEnabled(False)
        status_dialog.setModal(True)
        status_dialog.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.CustomizeWindowHint)
        status_dialog.show()
        QApplication.processEvents()
        time.sleep(0.01)

        with concurrent.futures.ProcessPoolExecutor(max_workers=nprocesses, initializer=process_initializer) as executor:
            future_reg = {executor.submit(f.convert_image_mask_to_lossy_preview, *args): i for i, args in enumerate(arguments)}
            QApplication.processEvents()
            time.sleep(0.01)
            for future in concurrent.futures.as_completed(future_reg):
                try:
                    future.result()
                    status_dialog.set_status(future_reg[future],'Success')
                except Exception as e:
                    self.logger.exception("An exception occurred")
                    status_dialog.set_status(future_reg[future],'Failed',str(e))
                QApplication.processEvents()
                time.sleep(0.01)

        # Restore cursor
        QApplication.restoreOverrideCursor()
        status_dialog.ok_button.setEnabled(True)

        # re-enable messagebox error handler
        if messagebox_error_handler is not None:
            logging.getLogger().addHandler(messagebox_error_handler)

        self.logger.info('Done')
