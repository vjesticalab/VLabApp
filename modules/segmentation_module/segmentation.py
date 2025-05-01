import logging
import os
import sys
import time
import concurrent
from PyQt5.QtWidgets import QCheckBox, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QGroupBox, QRadioButton, QApplication, QSpinBox, QFormLayout, QLabel, QLineEdit, QComboBox
from PyQt5.QtCore import Qt, QRegularExpression
from PyQt5.QtGui import QCursor, QDoubleValidator, QRegularExpressionValidator
from modules.segmentation_module import segmentation_functions as f
from general import general_functions as gf
import torch
from cellpose.core import assign_device
try:
    from micro_sam.automatic_segmentation import get_predictor_and_segmenter, automatic_instance_segmentation
    microsam_available = True
except ImportError:
    microsam_available = False


def process_initializer():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s (%(name)s) [%(levelname)s] %(message)s", handlers=[logging.StreamHandler(sys.stdout)], force=True)


class Segmentation(QWidget):
    def __init__(self, pipeline_layout=False):
        super().__init__()

        self.output_suffix = gf.output_suffixes['segmentation']

        self.pipeline_layout = pipeline_layout

        doc_text = 'For each input image,  perform cell segmentation using <a href="https://www.cellpose.org/">Cellpose</a> '
        if microsam_available:
            doc_text += 'or <a href="https://github.com/computational-cell-analytics/micro-sam">Segment Anything for Microscopy</a> '
        doc_text += 'and save the resulting mask.<br>'
        doc_text += 'Input images must have X and Y axes and can optionally have C, Z and/or T axes (Z axis will be projected and only the chosen channel will be selected before performing segmentation).<br>'
        doc_text += '<br>'
        doc_text += 'Additional information: <a href="' + os.path.join(os.path.dirname(__file__), '..', '..', 'doc', 'site', 'segmentation_module', 'reference.html') + '">Documentation</a>'

        label_documentation = gf.CollapsibleLabel('',  collapsed=True)
        label_documentation.setText(doc_text)

        self.image_list = gf.FileListWidget(filetypes=gf.imagetypes, filenames_filter='_BF')
        self.image_list.file_list_changed.connect(self.image_list_changed)

        self.use_input_folder = QRadioButton("Use input image folder")
        self.use_input_folder.setChecked(True)
        self.use_input_folder.toggled.connect(self.update_output_filename_label)
        self.use_custom_folder = QRadioButton("Use custom folder (same for all the input files)")
        self.use_custom_folder.setChecked(False)
        self.use_custom_folder.toggled.connect(self.update_output_filename_label)
        self.output_folder = gf.FolderLineEdit()
        self.output_folder.textChanged.connect(self.update_output_filename_label)
        self.output_folder.setVisible(self.use_custom_folder.isChecked())
        self.use_custom_folder.toggled.connect(self.output_folder.setVisible)
        self.output_user_suffix = QLineEdit()
        self.output_user_suffix.setToolTip('Allowed characters: A-Z, a-z, 0-9 and -')
        self.output_user_suffix.setValidator(QRegularExpressionValidator(QRegularExpression('[A-Za-z0-9-]*')))
        self.output_user_suffix.textChanged.connect(self.update_output_filename_label)
        self.output_filename_label = QLineEdit()
        self.output_filename_label.setFrame(False)
        self.output_filename_label.setEnabled(False)
        self.output_filename_label.textChanged.connect(self.output_filename_label.setToolTip)

        self.segmentation_method = QComboBox()
        self.segmentation_method.addItem("cellpose")
        if microsam_available:
            self.segmentation_method.addItem("Segment Anything for Microscopy")
        self.segmentation_method.setCurrentText("cellpose")
        self.segmentation_method.currentTextChanged.connect(self.segmentation_method_changed)

        self.cellpose_model_type = QComboBox()
        self.cellpose_model_type.addItem("User trained model")
        self.cellpose_model_type.insertSeparator(self.cellpose_model_type.count())
        self.cellpose_model_type.addItem("cyto3")
        self.cellpose_model_type.addItem("cyto2")
        self.cellpose_model_type.addItem("cyto")
        self.cellpose_model_type.addItem("nuclei")
        self.cellpose_model_type.insertSeparator(self.cellpose_model_type.count())
        self.cellpose_model_type.addItem("tissuenet_cp3")
        self.cellpose_model_type.addItem("livecell_cp3")
        self.cellpose_model_type.addItem("yeast_PhC_cp3")
        self.cellpose_model_type.addItem("yeast_BF_cp3")
        self.cellpose_model_type.addItem("bact_phase_cp3")
        self.cellpose_model_type.addItem("bact_fluor_cp3")
        self.cellpose_model_type.addItem("deepbacs_cp3")
        self.cellpose_model_type.addItem("cyto2_cp3")
        self.cellpose_model_type.setCurrentText("User trained model")
        self.cellpose_model_type.currentTextChanged.connect(self.cellpose_model_type_changed)
        self.cellpose_user_model = gf.FileLineEdit()
        self.cellpose_user_model_label = QLabel("Model:")
        self.cellpose_diameter = QSpinBox()
        self.cellpose_diameter.setMinimum(0)
        self.cellpose_diameter.setMaximum(1000)
        self.cellpose_diameter.setValue(0)
        self.cellpose_diameter.setToolTip('Expected cell diameter (pixel). If 0, use Cellpose built-in model to estimate diameter (available only for cyto, cyto2, cyto3 and nuclei models).')
        self.cellpose_diameter.setVisible(False)
        self.cellpose_diameter_label = QLabel("Diameter:")
        self.cellpose_diameter_label.setVisible(False)
        self.cellpose_cellprob_threshold = QLineEdit(placeholderText='0.0')
        self.cellpose_cellprob_threshold.setValidator(QDoubleValidator(decimals=2))
        self.cellpose_cellprob_threshold.validator().setNotation(QDoubleValidator.StandardNotation)
        self.cellpose_flow_threshold = QLineEdit(placeholderText='0.4')
        self.cellpose_flow_threshold.setValidator(QDoubleValidator(decimals=2))
        self.cellpose_flow_threshold.validator().setNotation(QDoubleValidator.StandardNotation)

        self.microsam_model_type = QComboBox()
        self.microsam_model_type.addItem("vit_h")
        self.microsam_model_type.addItem("vit_l")
        self.microsam_model_type.addItem("vit_b")
        self.microsam_model_type.addItem("vit_l_lm")
        self.microsam_model_type.addItem("vit_b_lm")
        self.microsam_model_type.addItem("vit_l_em_organelles")
        self.microsam_model_type.addItem("vit_b_em_organelles")
        self.microsam_model_type.setCurrentText("vit_l_lm")

        self.channel_position = QSpinBox()
        self.channel_position.setMinimum(0)
        self.channel_position.setMaximum(100)
        self.channel_position.setValue(0)

        # Z-Projection range
        # only bestZ
        self.projection_mode_bestZ = QRadioButton("Z section with best focus")
        self.projection_mode_bestZ.setChecked(False)
        self.projection_mode_bestZ.setToolTip('Keep only Z section with best focus.')
        # around bestZ
        self.projection_mode_around_bestZ = QRadioButton("Range around Z section with best focus")
        self.projection_mode_around_bestZ.setChecked(True)
        self.projection_mode_around_bestZ.setToolTip('Project all Z sections with Z in the interval [bestZ-range,bestZ+range], where bestZ is the Z section with best focus.')
        self.projection_mode_around_bestZ_zrange = QSpinBox()
        self.projection_mode_around_bestZ_zrange.setMinimum(0)
        self.projection_mode_around_bestZ_zrange.setMaximum(20)
        self.projection_mode_around_bestZ_zrange.setValue(3)
        # fixed range
        self.projection_mode_fixed = QRadioButton("Fixed range")
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
        self.projection_mode_all = QRadioButton("All Z sections")
        self.projection_mode_all.setChecked(False)
        self.projection_mode_all.setToolTip('Project all Z sections.')
        # Z-Projection type
        self.projection_type = QComboBox()
        self.projection_type.addItem("max")
        self.projection_type.addItem("min")
        self.projection_type.addItem("mean")
        self.projection_type.addItem("median")
        self.projection_type.addItem("std")
        self.projection_type.setCurrentText("mean")
        self.projection_type.setDisabled(self.projection_mode_bestZ.isChecked())
        self.projection_mode_bestZ.toggled.connect(self.projection_type.setDisabled)

        self.use_gpu = QCheckBox("Use GPU")
        device, gpu = assign_device(gpu=True)
        self.use_gpu.setChecked(gpu)
        self.use_gpu.setEnabled(gpu)
        self.coarse_grain = QCheckBox("Use coarse grain parallelisation")
        self.coarse_grain.setToolTip("Assign each input file to its own process. Use it when there are more input files than processes and enough memory (memory usage increases with the number of processes).")
        self.coarse_grain.setChecked(False)
        self.nprocesses = QSpinBox()
        self.nprocesses.setMinimum(1)
        self.nprocesses.setMaximum(os.cpu_count())
        self.nprocesses.setValue(1)
        nprocesses_label = QLabel("Number of processes:")
        self.use_gpu.toggled.connect(nprocesses_label.setDisabled)
        self.use_gpu.toggled.connect(self.update_coarse_grain_status)
        self.use_gpu.toggled.connect(self.nprocesses.setDisabled)
        if self.use_gpu.isEnabled():
            self.use_gpu.setChecked(torch.cuda.is_available())

        self.display_results = QCheckBox("Show results in napari")
        self.display_results.setChecked(False)
        self.submit_button = QPushButton("Submit")
        self.submit_button.clicked.connect(self.submit)

        # Layout
        layout = QVBoxLayout()
        groupbox = QGroupBox("Documentation")
        layout2 = QVBoxLayout()
        layout2.addWidget(label_documentation)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        if not self.pipeline_layout:
            groupbox = QGroupBox('Input files (images)')
            layout2 = QVBoxLayout()
            layout2.addWidget(self.image_list)
            groupbox.setLayout(layout2)
            layout.addWidget(groupbox)

        groupbox = QGroupBox("Output")
        layout2 = QVBoxLayout()
        if not self.pipeline_layout:
            layout2.addWidget(QLabel("Folder:"))
            layout2.addWidget(self.use_input_folder)
            layout2.addWidget(self.use_custom_folder)
            layout2.addWidget(self.output_folder)
        layout3 = QFormLayout()
        layout3.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        layout4 = QHBoxLayout()
        layout4.setSpacing(0)
        suffix = QLineEdit(self.output_suffix)
        suffix.setDisabled(True)
        suffix.setFixedWidth(suffix.fontMetrics().width(suffix.text()+"  "))
        suffix.setAlignment(Qt.AlignRight)
        layout4.addWidget(suffix)
        layout4.addWidget(self.output_user_suffix)
        layout3.addRow("Suffix:", layout4)
        layout3.addRow("Filename:", self.output_filename_label)
        layout2.addLayout(layout3)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        groupbox = QGroupBox("Options")
        layout3 = QVBoxLayout()

        groupbox2 = QGroupBox("Segmentation method")
        layout4 = QFormLayout()
        layout4.addRow("Method:", self.segmentation_method)

        self.segmentation_settings_cellpose = QWidget()
        layout5 = QFormLayout()
        layout5.setContentsMargins(0, 0, 0, 0)
        layout5.addRow("Model type:", self.cellpose_model_type)
        layout5.addRow(self.cellpose_user_model_label, self.cellpose_user_model)
        layout5.addRow(self.cellpose_diameter_label, self.cellpose_diameter)
        collapsible = gf.CollapsibleWidget("", collapsed_icon="▶ [show more]", expanded_icon="▼ [hide]", expanded=False)
        layout6 = QFormLayout()
        collapsible.content.setLayout(layout6)
        layout6.addRow("Cellprob threshold:", self.cellpose_cellprob_threshold)
        layout6.addRow("Flow threshold:", self.cellpose_flow_threshold)
        layout5.addRow(collapsible)
        self.segmentation_settings_cellpose.setLayout(layout5)
        layout4.addRow(self.segmentation_settings_cellpose)

        self.segmentation_settings_microsam = QWidget()
        self.segmentation_settings_microsam.setVisible(False)
        layout5 = QFormLayout()
        layout5.setContentsMargins(0, 0, 0, 0)
        layout5.addRow("Model type:", self.microsam_model_type)
        self.segmentation_settings_microsam.setLayout(layout5)
        layout4.addRow(self.segmentation_settings_microsam)
        groupbox2.setLayout(layout4)
        layout3.addWidget(groupbox2)

        groupbox2 = QGroupBox("If multiple channels:")
        layout4 = QFormLayout()
        layout4.addRow("Channel position:", self.channel_position)
        groupbox2.setLayout(layout4)
        layout3.addWidget(groupbox2)

        groupbox2 = QGroupBox("If multiple z:")
        layout4 = QFormLayout()
        # Z-Projection range
        widget = QWidget()
        layout5 = QVBoxLayout()
        layout5.addWidget(self.projection_mode_bestZ)
        layout5.addWidget(self.projection_mode_around_bestZ)
        groupbox3 = QGroupBox()
        groupbox3.setToolTip('Project all Z sections with Z in the interval [bestZ-range,bestZ+range], where bestZ is the Z section with best focus.')
        groupbox3.setVisible(self.projection_mode_around_bestZ.isChecked())
        self.projection_mode_around_bestZ.toggled.connect(groupbox3.setVisible)
        layout6 = QFormLayout()
        layout6.addRow("Range:", self.projection_mode_around_bestZ_zrange)
        groupbox3.setLayout(layout6)
        layout5.addWidget(groupbox3)
        layout5.addWidget(self.projection_mode_fixed)
        groupbox3 = QGroupBox()
        groupbox3.setToolTip('Project all Z sections with Z in the interval [from,to].')
        groupbox3.setVisible(self.projection_mode_fixed.isChecked())
        self.projection_mode_fixed.toggled.connect(groupbox3.setVisible)
        layout6 = QHBoxLayout()
        layout7 = QFormLayout()
        layout7.addRow("From:", self.projection_mode_fixed_zmin)
        layout6.addLayout(layout7)
        layout7 = QFormLayout()
        layout7.addRow("To:", self.projection_mode_fixed_zmax)
        layout6.addLayout(layout7)
        groupbox3.setLayout(layout6)
        layout5.addWidget(groupbox3)
        layout5.addWidget(self.projection_mode_all)
        widget.setLayout(layout5)
        layout4.addRow("Projection range:", widget)
        layout4.addRow("Projection type:", self.projection_type)
        groupbox2.setLayout(layout4)
        layout3.addWidget(groupbox2)
        groupbox.setLayout(layout3)
        layout.addWidget(groupbox)

        if not self.pipeline_layout:
            groupbox = QGroupBox("Multi-processing")
            layout2 = QVBoxLayout()
            layout2.addWidget(self.use_gpu)
            layout2.addWidget(self.coarse_grain)
            layout3 = QFormLayout()
            layout3.addRow(nprocesses_label, self.nprocesses)
            layout2.addLayout(layout3)
            groupbox.setLayout(layout2)
            layout.addWidget(groupbox)
            layout.addWidget(self.display_results)
            layout.addWidget(self.submit_button, alignment=Qt.AlignCenter)

        self.setLayout(layout)

        self.logger = logging.getLogger(__name__)

        self.update_output_filename_label()

    def segmentation_method_changed(self, method):
        if method == 'cellpose':
            self.segmentation_settings_cellpose.setVisible(True)
            self.segmentation_settings_microsam.setVisible(False)
        else:
            self.segmentation_settings_cellpose.setVisible(False)
            self.segmentation_settings_microsam.setVisible(True)
        return

    def cellpose_model_type_changed(self, model):
        if model == 'User trained model':
            self.cellpose_user_model_label.setVisible(True)
            self.cellpose_user_model.setVisible(True)
            self.cellpose_diameter_label.setVisible(False)
            self.cellpose_diameter.setVisible(False)
        else:
            self.cellpose_user_model_label.setVisible(False)
            self.cellpose_user_model.setVisible(False)
            self.cellpose_diameter_label.setVisible(True)
            self.cellpose_diameter.setVisible(True)

    def image_list_changed(self):
        if self.image_list.count() > 1:
            self.display_results.setChecked(False)
        self.display_results.setEnabled(self.image_list.count() <= 1)
        self.update_coarse_grain_status()

    def update_coarse_grain_status(self):
        if self.image_list.count() == 1:
            self.coarse_grain.setChecked(False)
        if self.use_gpu.isChecked():
            self.coarse_grain.setChecked(False)
        self.coarse_grain.setEnabled(self.image_list.count() > 1 and not self.use_gpu.isChecked())

    def update_output_filename_label(self):
        if self.pipeline_layout:
            output_path = "<output folder>"
        elif self.use_input_folder.isChecked():
            output_path = "<input folder>"
        else:
            output_path = os.path.abspath(self.output_folder.text())

        self.output_filename_label.setText(os.path.normpath(os.path.join(output_path, "<input basename>" + self.output_suffix + self.output_user_suffix.text() + ".ome.tif")))

    def projection_mode_fixed_zmin_changed(self, value):
        self.projection_mode_fixed_zmax.setMinimum(value)

    def projection_mode_fixed_zmax_changed(self, value):
        self.projection_mode_fixed_zmin.setMaximum(value)

    def get_widgets_state(self):
        widgets_state = {
            'image_list': self.image_list.get_file_list(),
            'use_input_folder': self.use_input_folder.isChecked(),
            'use_custom_folder': self.use_custom_folder.isChecked(),
            'output_folder': self.output_folder.text(),
            'segmentation_method': self.segmentation_method.currentText(),
            'cellpose_model_type': self.cellpose_model_type.currentText(),
            'cellpose_user_model': self.cellpose_user_model.text(),
            'cellpose_diameter': self.cellpose_diameter.value(),
            'cellpose_cellprob_threshold': self.cellpose_cellprob_threshold.text() if self.cellpose_cellprob_threshold.text() != '' else self.cellpose_cellprob_threshold.placeholderText(),
            'cellpose_flow_threshold':  self.cellpose_flow_threshold.text() if self.cellpose_flow_threshold.text() != '' else self.cellpose_flow_threshold.placeholderText(),
            'microsam_model_type': self.microsam_model_type.currentText(),
            'output_user_suffix': self.output_user_suffix.text(),
            'channel_position': self.channel_position.value(),
            'projection_mode_bestZ': self.projection_mode_bestZ.isChecked(),
            'projection_mode_around_bestZ': self.projection_mode_around_bestZ.isChecked(),
            'projection_mode_around_bestZ_zrange': self.projection_mode_around_bestZ_zrange.value(),
            'projection_mode_fixed': self.projection_mode_fixed.isChecked(),
            'projection_mode_fixed_zmin': self.projection_mode_fixed_zmin.value(),
            'projection_mode_fixed_zmax': self.projection_mode_fixed_zmax.value(),
            'projection_mode_all': self.projection_mode_all.isChecked(),
            'projection_type': self.projection_type.currentText(),
            'use_gpu': self.use_gpu.isChecked(),
            'coarse_grain': self.coarse_grain.isChecked(),
            'nprocesses': self.nprocesses.value(),
            'display_results': self.display_results.isChecked()}
        return widgets_state

    def set_widgets_state(self, widgets_state):
        self.image_list.set_file_list(widgets_state['image_list'])
        self.use_input_folder.setChecked(widgets_state['use_input_folder'])
        self.use_custom_folder.setChecked(widgets_state['use_custom_folder'])
        self.output_folder.setText(widgets_state['output_folder'])
        self.segmentation_method.setCurrentText(widgets_state['segmentation_method'])
        self.cellpose_model_type.setCurrentText(widgets_state['cellpose_model_type'])
        self.cellpose_user_model.setText(widgets_state['cellpose_user_model'])
        self.cellpose_diameter.setValue(widgets_state['cellpose_diameter'])
        self.cellpose_cellprob_threshold.setText(widgets_state['cellpose_cellprob_threshold'])
        self.cellpose_flow_threshold.setText(widgets_state['cellpose_flow_threshold'])
        self.microsam_model_type.setCurrentText(widgets_state['microsam_model_type'])
        self.output_user_suffix.setText(widgets_state['output_user_suffix'])
        self.channel_position.setValue(widgets_state['channel_position'])
        self.projection_mode_bestZ.setChecked(widgets_state['projection_mode_bestZ'])
        self.projection_mode_around_bestZ.setChecked(widgets_state['projection_mode_around_bestZ'])
        self.projection_mode_around_bestZ_zrange.setValue(widgets_state['projection_mode_around_bestZ_zrange'])
        self.projection_mode_fixed.setChecked(widgets_state['projection_mode_fixed'])
        self.projection_mode_fixed_zmin.setValue(widgets_state['projection_mode_fixed_zmin'])
        self.projection_mode_fixed_zmax.setValue(widgets_state['projection_mode_fixed_zmax'])
        self.projection_mode_all.setChecked(widgets_state['projection_mode_all'])
        self.projection_type.setCurrentText(widgets_state['projection_type'])
        if self.use_gpu.isEnabled():
            self.use_gpu.setChecked(widgets_state['use_gpu'])
        self.coarse_grain.setChecked(widgets_state['coarse_grain'])
        self.nprocesses.setValue(widgets_state['nprocesses'])
        self.display_results.setChecked(widgets_state['display_results'])
        if widgets_state['segmentation_method'] == "Segment Anything for Microscopy" and not microsam_available:
            self.logger.error('Segment Anything for Microscopy is not available.')

    def submit(self):
        channel_position = self.channel_position.value()
        projection_type = self.projection_type.currentText()
        if self.projection_mode_bestZ.isChecked():
            projection_zrange = 0
        elif self.projection_mode_around_bestZ.isChecked():
            projection_zrange = self.projection_mode_around_bestZ_zrange.value()
        elif self.projection_mode_fixed.isChecked():
            projection_zrange = (self.projection_mode_fixed_zmin.value(), self.projection_mode_fixed_zmax.value())
        elif self.projection_mode_all.isChecked():
            projection_zrange = None

        image_paths = self.image_list.get_file_list()
        segmentation_method = self.segmentation_method.currentText()
        cellpose_model_type = self.cellpose_model_type.currentText()
        cellpose_diameter = self.cellpose_diameter.value()
        cellpose_model_path = self.cellpose_user_model.text()
        cellpose_cellprob_threshold = float(self.cellpose_cellprob_threshold.text()) if self.cellpose_cellprob_threshold.text() != '' else float(self.cellpose_cellprob_threshold.placeholderText())
        cellpose_flow_threshold = float(self.cellpose_flow_threshold.text()) if self.cellpose_flow_threshold.text() != '' else float(self.cellpose_flow_threshold.placeholderText())
        microsam_model_type = self.microsam_model_type.currentText()
        user_suffix = self.output_user_suffix.text()
        output_basenames = [gf.splitext(os.path.basename(path))[0] + self.output_suffix + user_suffix for path in image_paths]
        if self.use_input_folder.isChecked():
            output_paths = [os.path.dirname(path) for path in image_paths]
        else:
            output_paths = [self.output_folder.text() for path in image_paths]

        if len(image_paths) == 0:
            self.logger.error('Image missing')
            return
        for path in image_paths:
            if not os.path.isfile(path):
                self.logger.error('Image not found: %s', path)
                return
        if segmentation_method == "cellpose":
            if cellpose_model_type == "User trained model":
                if cellpose_model_path == '':
                    self.logger.error('Model missing')
                    self.cellpose_user_model.setFocus()
                    return
                if not os.path.isfile(cellpose_model_path):
                    self.logger.error('Model not found: %s', cellpose_model_path)
                    self.cellpose_user_model.setFocus()
                    return
            elif cellpose_model_type not in ['cyto', 'cyto2', 'cyto3', 'nuclei'] and cellpose_diameter == 0:
                self.logger.error('Diameter estimation using Cellpose built-in model (i.e. diameter == 0) is only available for cyto, cyto2, cyto3 and nuclei models')
                self.cellpose_diameter.setFocus()
                return

        if self.output_folder.text() == '' and not self.use_input_folder.isChecked():
            self.logger.error('Output folder missing')
            self.output_folder.setFocus()
            return
        output_files = [os.path.join(d, f) for d, f in zip(output_paths, output_basenames)]
        duplicates = [x for x, y in zip(image_paths, output_files) if output_files.count(y) > 1]
        if len(duplicates) > 0:
            self.logger.error('More than one input file will output to the same file (output files will be overwritten).\nEither use input image folder as output folder or avoid processing images from different input folders.\nProblematic input files:\n%s', '\n'.join(duplicates[:4] + (['...'] if len(duplicates) > 4 else [])))
            return

        # check input files are valid
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

        coarse_grain_parallelism = self.coarse_grain.isChecked()
        arguments = []
        nprocesses = self.nprocesses.value()

        run_parallel = True
        if self.use_gpu.isChecked():
            nprocesses = 1
            run_parallel = False
        QApplication.setOverrideCursor(QCursor(Qt.BusyCursor))
        for image_path, output_path, output_basename in zip(image_paths, output_paths, output_basenames):
            self.logger.info("Segmenting image %s", image_path)

            QApplication.processEvents()
            arguments.append(
                (image_path,
                 segmentation_method,
                 cellpose_model_type,
                 cellpose_model_path,
                 cellpose_diameter,
                 cellpose_cellprob_threshold,
                 cellpose_flow_threshold,
                 microsam_model_type,
                 output_path,
                 output_basename,
                 channel_position,
                 projection_type,
                 projection_zrange,
                 nprocesses,
                 self.display_results.isChecked(),
                 self.use_gpu.isChecked()
                 )
            )

        if not arguments:
            return

        status_dialog = gf.StatusTableDialog(image_paths)
        status_dialog.ok_button.setEnabled(False)
        status_dialog.setModal(True)
        status_dialog.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.CustomizeWindowHint)
        status_dialog.show()
        QApplication.processEvents()
        time.sleep(0.01)

        hide_status_dialog = False
        if len(arguments) == 1 or not coarse_grain_parallelism or self.use_gpu.isChecked():
            QApplication.processEvents()
            time.sleep(0.01)
            hide_status_dialog = True
            for i, args in enumerate(arguments):
                try:
                    f.main(*args, run_parallel=run_parallel)
                    status_dialog.set_status(i,'Success')
                except Exception as e:
                    self.logger.exception("Segmentation failed")
                    status_dialog.set_status(i,'Failed',str(e))
                    hide_status_dialog = False
                QApplication.processEvents()
                time.sleep(0.01)
        else:
            self.logger.info("Using %s cores to perform segmentation", nprocesses)
            with concurrent.futures.ProcessPoolExecutor(max_workers=nprocesses, initializer=process_initializer) as executor:
                QApplication.processEvents()
                time.sleep(0.01)
                future_reg = {executor.submit(f.main, *args, run_parallel=False): i for i, args in enumerate(arguments)}
                for future in concurrent.futures.as_completed(future_reg):
                    try:
                        future.result()
                        status_dialog.set_status(future_reg[future],'Success')
                    except Exception as e:
                        self.logger.exception("Segmentation failed")
                        status_dialog.set_status(future_reg[future],'Failed',str(e))
                    QApplication.processEvents()
                    time.sleep(0.01)

        QApplication.restoreOverrideCursor()
        status_dialog.ok_button.setEnabled(True)
        if hide_status_dialog:
            status_dialog.hide()

        # re-enable messagebox error handler
        if messagebox_error_handler is not None:
            logging.getLogger().addHandler(messagebox_error_handler)

        self.logger.info("Done")
