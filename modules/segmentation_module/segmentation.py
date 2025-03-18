import logging
import os
import concurrent
from PyQt5.QtWidgets import QCheckBox, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QGroupBox, QRadioButton, QApplication, QSpinBox, QFormLayout, QLabel, QLineEdit, QComboBox
from PyQt5.QtCore import Qt, QRegExp
from PyQt5.QtGui import QCursor, QDoubleValidator, QRegExpValidator
from modules.segmentation_module import segmentation_functions as f
from general import general_functions as gf
import torch
from cellpose.core import assign_device


class Segmentation(QWidget):
    def __init__(self, pipeline_layout=False):
        super().__init__()

        self.output_suffix = gf.output_suffixes['segmentation']

        self.pipeline_layout = pipeline_layout

        label_documentation = gf.CollapsibleLabel('',  collapsed=True)
        label_documentation.setText('For each input image,  perform cell segmentation using <a href="https://www.cellpose.org/">cellpose</a> and save the resulting mask.<br>' +
                                    'Input images must have X and Y axes and can optionally have C, Z and/or T axes (Z axis will be projected and only the chosen channel will be selected before performing segmentation).<br>' +
                                    '<h3>Cellpose model types</h3>' +
                                    '<b>Built-in models</b><br>' +
                                    'Built-in models cyto, cyto2, nuclei, tissuenet and livecell are available. These models require a parameter "diameter", which should correspond to the expected diameter of the objects to segment. With cyto, cyto2 or nuclei model types, the diameter can be estimated using cellpose built-in model by setting the parameter "diameter" to 0. For more information, see section "Models" in cellpose documentation <a href="https://cellpose.readthedocs.io">https://cellpose.readthedocs.io</a>' +
                                    '<br>' +
                                    '<b>User trained model</b><br>' +
                                    'A user trained model can be obtained by finetuning a pretrained cellpose model on a collection of annotated images similar to the input images (see section "Training" in cellpose documentation <a href="https://cellpose.readthedocs.io">https://cellpose.readthedocs.io</a>). When using a user trained model it is not possible to choose the diameter, which is set to the median diameter estimated on the training set.')

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
        self.output_user_suffix.setValidator(QRegExpValidator(QRegExp('[A-Za-z0-9-]*')))
        self.output_user_suffix.textChanged.connect(self.update_output_filename_label)
        self.output_filename_label = QLineEdit()
        self.output_filename_label.setFrame(False)
        self.output_filename_label.setEnabled(False)
        self.output_filename_label.textChanged.connect(self.output_filename_label.setToolTip)

        self.cellpose_model_type = QComboBox()
        self.cellpose_model_type.addItem("User trained model")
        self.cellpose_model_type.addItem("cyto")
        self.cellpose_model_type.addItem("cyto2")
        self.cellpose_model_type.addItem("nuclei")
        self.cellpose_model_type.addItem("tissuenet")
        self.cellpose_model_type.addItem("livecell")
        self.cellpose_model_type.setCurrentText("User trained model")
        self.cellpose_model_type.currentTextChanged.connect(self.cellpose_model_type_changed)
        self.cellpose_user_model = gf.FileLineEdit()
        self.cellpose_user_model_label = QLabel("Model:")
        self.cellpose_diameter = QSpinBox()
        self.cellpose_diameter.setMinimum(0)
        self.cellpose_diameter.setMaximum(1000)
        self.cellpose_diameter.setValue(0)
        self.cellpose_diameter.setToolTip('Expected cell diameter (pixel). If 0, use cellpose built-in model to estimate diameter (available only for cyto, cyto2 and nuclei models).')
        self.cellpose_diameter.setVisible(False)
        self.cellpose_diameter_label = QLabel("Diameter:")
        self.cellpose_diameter_label.setVisible(False)
        self.cellpose_cellprob_threshold = QLineEdit(placeholderText='0.0')
        self.cellpose_cellprob_threshold.setValidator(QDoubleValidator(decimals=2))
        self.cellpose_cellprob_threshold.validator().setNotation(QDoubleValidator.StandardNotation)
        self.cellpose_flow_threshold = QLineEdit(placeholderText='0.4')
        self.cellpose_flow_threshold.setValidator(QDoubleValidator(decimals=2))
        self.cellpose_flow_threshold.validator().setNotation(QDoubleValidator.StandardNotation)

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

        self.use_gpu = QCheckBox("Activate GPU")
        device, gpu = assign_device(gpu=True)
        self.use_gpu.setChecked(gpu)
        self.use_gpu.setEnabled(gpu)
        self.coarse_grain = QCheckBox("Activate coarse grain parallelisation")
        self.coarse_grain.setChecked(False)
        self.n_count = QSpinBox()
        self.n_count.setMinimum(1)
        self.n_count.setMaximum(os.cpu_count())
        self.n_count.setValue(1)
        n_count_label = QLabel("Number of processes:")
        self.use_gpu.toggled.connect(n_count_label.setDisabled)
        self.use_gpu.toggled.connect(self.update_coarse_grain_status)
        self.use_gpu.toggled.connect(self.n_count.setDisabled)
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
        layout4.addRow("Model type:", self.cellpose_model_type)
        layout4.addRow(self.cellpose_user_model_label, self.cellpose_user_model)
        layout4.addRow(self.cellpose_diameter_label, self.cellpose_diameter)
        collapsible = gf.CollapsibleWidget("", collapsed_icon="▶ [show more]", expanded_icon="▼ [hide]", expanded=False)
        layout5 = QFormLayout()
        collapsible.content.setLayout(layout5)
        layout5.addRow("Cellprob threshold:", self.cellpose_cellprob_threshold)
        layout5.addRow("Flow threshold:", self.cellpose_flow_threshold)
        layout4.addRow(collapsible)
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
            layout3.addRow(n_count_label, self.n_count)
            layout2.addLayout(layout3)
            groupbox.setLayout(layout2)
            layout.addWidget(groupbox)
            layout.addWidget(self.display_results)
            layout.addWidget(self.submit_button, alignment=Qt.AlignCenter)

        self.setLayout(layout)

        self.logger = logging.getLogger(__name__)

        self.update_output_filename_label()

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
            'cellpose_model_type': self.cellpose_model_type.currentText(),
            'cellpose_user_model': self.cellpose_user_model.text(),
            'cellpose_diameter': self.cellpose_diameter.value(),
            'cellpose_cellprob_threshold': self.cellpose_cellprob_threshold.text() if self.cellpose_cellprob_threshold.text() != '' else self.cellpose_cellprob_threshold.placeholderText(),
            'cellpose_flow_threshold':  self.cellpose_flow_threshold.text() if self.cellpose_flow_threshold.text() != '' else self.cellpose_flow_threshold.placeholderText(),
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
            'n_count': self.n_count.value(),
            'display_results': self.display_results.isChecked()}
        return widgets_state

    def set_widgets_state(self, widgets_state):
        self.image_list.set_file_list(widgets_state['image_list'])
        self.use_input_folder.setChecked(widgets_state['use_input_folder'])
        self.use_custom_folder.setChecked(widgets_state['use_custom_folder'])
        self.output_folder.setText(widgets_state['output_folder'])
        self.cellpose_model_type.setCurrentText(widgets_state['cellpose_model_type'])
        self.cellpose_user_model.setText(widgets_state['cellpose_user_model'])
        self.cellpose_diameter.setValue(widgets_state['cellpose_diameter'])
        self.cellpose_cellprob_threshold.setText(widgets_state['cellpose_cellprob_threshold'])
        self.cellpose_flow_threshold.setText(widgets_state['cellpose_flow_threshold'])
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
        self.use_gpu.setChecked(widgets_state['use_gpu'])
        self.coarse_grain.setChecked(widgets_state['coarse_grain'])
        self.n_count.setValue(widgets_state['n_count'])
        self.display_results.setChecked(widgets_state['display_results'])

    def submit(self):
        """
        Retrieve the input parameters
        Iterate over the image paths given performing f.main() function
        """

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
        model_type = self.cellpose_model_type.currentText()
        diameter = self.cellpose_diameter.value()
        model_path = self.cellpose_user_model.text()
        cellprob_threshold = float(self.cellpose_cellprob_threshold.text()) if self.cellpose_cellprob_threshold.text() != '' else float(self.cellpose_cellprob_threshold.placeholderText())
        flow_threshold = float(self.cellpose_flow_threshold.text()) if self.cellpose_flow_threshold.text() != '' else float(self.cellpose_flow_threshold.placeholderText())
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
        if model_type == "User trained model":
            if model_path == '':
                self.logger.error('Model missing')
                self.cellpose_user_model.setFocus()
                return
            if not os.path.isfile(model_path):
                self.logger.error('Model not found: %s', model_path)
                self.cellpose_user_model.setFocus()
                return
        elif model_type not in ['cyto', 'cyto2', 'nuclei'] and diameter == 0:
            self.logger.error('Diameter estimation using cellpose built-in model (i.e. diameter == 0) is only available for cyto, cyto2 and nuclei models')
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

        # disable messagebox error handler
        messagebox_error_handler = None
        for h in logging.getLogger().handlers:
            if h.get_name() == 'messagebox_error_handler':
                messagebox_error_handler = h
                logging.getLogger().removeHandler(messagebox_error_handler)
                break

        status = []
        error_messages = []
        coarse_grain_parallelism = self.coarse_grain.isChecked()
        arguments = []
        n_count = self.n_count.value()

        run_parallel = True
        if self.use_gpu.isChecked():
            n_count = 1
            run_parallel = False
        QApplication.setOverrideCursor(QCursor(Qt.BusyCursor))
        for image_path, output_path, output_basename in zip(image_paths, output_paths, output_basenames):
            self.logger.info("Segmenting image %s", image_path)

            QApplication.processEvents()
            arguments.append(
                (image_path,
                 model_type,
                 model_path,
                 diameter,
                 cellprob_threshold,
                 flow_threshold,
                 output_path,
                 output_basename,
                 channel_position,
                 projection_type,
                 projection_zrange,
                 n_count,
                 self.display_results.isChecked(),
                 self.use_gpu.isChecked()
                 )
            )

        if not arguments:
            return

        # Perform segmentation
        if len(arguments) == 1 or not coarse_grain_parallelism or self.use_gpu.isChecked():
            for args in arguments:
                try:
                    f.main(*args, run_parallel=run_parallel)
                    status.append("Success")
                    error_messages.append("")
                except Exception as e:
                    status.append("Failed")
                    error_messages.append(str(e))
                    self.logger.exception("Segmentation failed")
        elif coarse_grain_parallelism:
            # we launch a process per video
            self.logger.info("NCOUNT %s", n_count)
            with concurrent.futures.ProcessPoolExecutor(n_count) as executor:
                future_reg = {
                    executor.submit(f.main, *args, run_parallel=False): args for args in arguments
                }
                for future in future_reg:
                    try:

                        future.result()
                        status.append("Success")
                        error_messages.append("")
                    except Exception as e:
                        status.append("Failed")
                        error_messages.append(str(e))
                        self.logger.exception("Segmentation failed")

        QApplication.restoreOverrideCursor()

        if any(s != 'Success' for s in status):
            msg = gf.StatusTableDialog('Warning', status, error_messages, image_paths)
            msg.exec_()

        # re-enable messagebox error handler
        if messagebox_error_handler is not None:
            logging.getLogger().addHandler(messagebox_error_handler)

        self.logger.info("Done")
