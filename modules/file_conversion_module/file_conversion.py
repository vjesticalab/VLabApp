import logging
import os
from PyQt5.QtWidgets import QPushButton, QVBoxLayout, QWidget, QGroupBox, QRadioButton, QLabel, QFormLayout, QLineEdit, QComboBox, QApplication
from PyQt5.QtCore import Qt, QRegExp
from PyQt5.QtGui import QCursor, QRegExpValidator
from modules.file_conversion_module import file_conversion_functions as f
from general import general_functions as gf


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
        self.output_user_suffix.setValidator(QRegExpValidator(QRegExp('_?[A-Za-z0-9-]*')))
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

        self.output_filename_label_mask.setText(os.path.normpath(os.path.join(output_path, '<input basename>' + self.output_user_suffix.text() + mask_ext)))
        self.output_filename_label_graph.setText(os.path.normpath(os.path.join(output_path, '<input basename>' + self.output_user_suffix.text() + graph_ext)))

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

        # disable messagebox error handler
        messagebox_error_handler = None
        for h in logging.getLogger().handlers:
            if h.get_name() == 'messagebox_error_handler':
                messagebox_error_handler = h
                logging.getLogger().removeHandler(messagebox_error_handler)
                break

        status = []
        error_messages = []
        for mask_path, graph_path, output_path, output_basename in zip(mask_paths, graph_paths, output_paths, output_basenames):
            self.logger.info('File conversion (mask %s, graph %s)', mask_path, graph_path)

            QApplication.setOverrideCursor(QCursor(Qt.BusyCursor))
            QApplication.processEvents()
            try:
                f.convert_mask_and_graph(mask_path, graph_path, output_path, output_basename, output_mask_format, output_graph_format)
                status.append('Success')
                error_messages.append(None)
            except Exception as e:
                status.append('Failed')
                error_messages.append(str(e))
                self.logger.exception('Conversion failed')
            QApplication.restoreOverrideCursor()

        if any(s != 'Success' for s in status):
            msg = gf.StatusTableDialog('Warning', status, error_messages, mask_paths)
            msg.exec_()

        # re-enable messagebox error handler
        if messagebox_error_handler is not None:
            logging.getLogger().addHandler(messagebox_error_handler)

        self.logger.info('Done')

