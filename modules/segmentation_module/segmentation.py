import logging
import os
from PyQt5.QtWidgets import QFileDialog, QCheckBox, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QGroupBox, QRadioButton, QApplication, QSpinBox, QFormLayout, QLabel, QLineEdit, QComboBox
from PyQt5.QtCore import Qt, QRegExp
from PyQt5.QtGui import QCursor, QIntValidator, QRegExpValidator
from modules.segmentation_module import segmentation_functions as f
from general import general_functions as gf
import torch
import concurrent

class Segmentation(QWidget):
    def __init__(self):
        super().__init__()

        self.output_suffix = '_vSM'

        self.imagetypes = ['.nd2', '.tif', '.tiff', '.ome.tif', '.ome.tiff']
        self.image_list = gf.FileListWidget(filetypes=self.imagetypes, filenames_filter='_BF')
        self.image_list.file_list_changed.connect(self.image_list_changed)

        self.selected_model = gf.DropFileLineEdit()
        self.browse_button = QPushButton("Browse", self)
        self.browse_button.clicked.connect(self.browse_model)

        self.use_input_folder = QRadioButton("Use input image folder")
        self.use_input_folder.setChecked(True)
        self.use_input_folder.toggled.connect(self.update_output_filename_label)
        self.use_custom_folder = QRadioButton("Use custom folder")
        self.use_custom_folder.setChecked(False)
        self.use_custom_folder.toggled.connect(self.update_output_filename_label)
        self.output_folder = gf.DropFolderLineEdit()
        self.output_folder.textChanged.connect(self.update_output_filename_label)
        self.browse_button2 = QPushButton("Browse", self)
        self.browse_button2.clicked.connect(self.browse_output)
        self.output_folder.setVisible(self.use_custom_folder.isChecked())
        self.browse_button2.setVisible(self.use_custom_folder.isChecked())
        self.use_custom_folder.toggled.connect(self.output_folder.setVisible)
        self.use_custom_folder.toggled.connect(self.browse_button2.setVisible)
        self.output_user_suffix = QLineEdit()
        self.output_user_suffix.setToolTip('Allowed characters: A-Z, a-z, 0-9 and -')
        self.output_user_suffix.setValidator(QRegExpValidator(QRegExp('[A-Za-z0-9-]*')))
        self.output_user_suffix.textChanged.connect(self.update_output_filename_label)
        self.output_filename_label = QLineEdit()
        self.output_filename_label.setFrame(False)
        self.output_filename_label.setEnabled(False)
        self.output_filename_label.textChanged.connect(self.output_filename_label.setToolTip)

        self.channel_position = QLineEdit(placeholderText='eg. 0 (default) / 1 / ...')
        self.channel_position.setMinimumWidth(200)
        self.channel_position.setValidator(QIntValidator())
        self.channel_position.setText("0")
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
        self.projection_mode_fixed_zmin.setMaximum(20)
        self.projection_mode_fixed_zmin.setValue(4)
        self.projection_mode_fixed_zmin.valueChanged.connect(self.projection_mode_fixed_zmin_changed)
        self.projection_mode_fixed_zmax = QSpinBox()
        self.projection_mode_fixed_zmax.setMinimum(0)
        self.projection_mode_fixed_zmax.setMaximum(20)
        self.projection_mode_fixed_zmax.setValue(6)
        self.projection_mode_fixed_zmax.valueChanged.connect(self.projection_mode_fixed_zmax_changed)
        # all
        self.projection_mode_all = QRadioButton("All Z sections")
        self.projection_mode_all.setChecked(False)
        self.projection_mode_all.setToolTip('Project all Z sections.')
        # Z-Projection type
        self.projection_type = QComboBox(self)
        self.projection_type.addItem("max")
        self.projection_type.addItem("min")
        self.projection_type.addItem("mean")
        self.projection_type.addItem("median")
        self.projection_type.addItem("std")
        self.projection_type.setCurrentText("mean")
        self.projection_type.setDisabled(self.projection_mode_bestZ.isChecked())
        self.projection_mode_bestZ.toggled.connect(self.projection_type.setDisabled)

        self.use_gpu = QCheckBox("Activate GPU")
        self.use_gpu.setChecked(False)
        self.coarse_grain = QCheckBox("Activate coarse grain parallelisation")
        self.coarse_grain.setChecked(False)
        self.n_count = QSpinBox()
        self.n_count.setMinimum(1)
        self.n_count.setMaximum(os.cpu_count())
        self.n_count.setValue(1)
        n_count_label=QLabel("Number of processes:")
        self.use_gpu.toggled.connect(n_count_label.setDisabled)
        self.use_gpu.toggled.connect(self.update_coarse_grain_status)
        self.use_gpu.toggled.connect(self.n_count.setDisabled)
        self.use_gpu.setChecked(torch.cuda.is_available())

        self.display_results = QCheckBox("Show results in napari")
        self.display_results.setChecked(False)
        self.submit_button = QPushButton("Submit", self)
        self.submit_button.clicked.connect(self.submit)

        # Layout
        layout = QVBoxLayout()
        groupbox = QGroupBox('Images to process')
        layout2 = QVBoxLayout()
        layout2.addWidget(self.image_list)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
        
        groupbox = QGroupBox("Cellpose model")
        layout2 = QVBoxLayout()
        layout3 = QHBoxLayout()
        layout3.addWidget(self.selected_model)
        layout3.addWidget(self.browse_button, alignment=Qt.AlignCenter)
        layout2.addLayout(layout3)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
        
        groupbox = QGroupBox("Output")
        layout2 = QVBoxLayout()
        layout2.addWidget(QLabel("Folder:"))
        layout2.addWidget(self.use_input_folder)
        layout2.addWidget(self.use_custom_folder)
        layout3 = QHBoxLayout()
        layout3.addWidget(self.output_folder)
        layout3.addWidget(self.browse_button2, alignment=Qt.AlignCenter)
        layout2.addLayout(layout3)
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
        layout3 = QFormLayout()
        layout3.setLabelAlignment(Qt.AlignLeft)
        layout3.setFormAlignment(Qt.AlignLeft)
        groupbox2 = QGroupBox("If multiple channels:")
        layout4 = QFormLayout()
        layout4.addRow("Channel position:",self.channel_position)
        groupbox2.setLayout(layout4)
        layout3.addRow(groupbox2)

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
        layout6.addRow("Range:",self.projection_mode_around_bestZ_zrange)
        groupbox3.setLayout(layout6)
        layout5.addWidget(groupbox3)
        layout5.addWidget(self.projection_mode_fixed)
        groupbox3 = QGroupBox()
        groupbox3.setToolTip('Project all Z sections with Z in the interval [from,to].')
        groupbox3.setVisible(self.projection_mode_fixed.isChecked())
        self.projection_mode_fixed.toggled.connect(groupbox3.setVisible)
        layout6 = QHBoxLayout()
        layout7 = QFormLayout()
        layout7.addRow("From:",self.projection_mode_fixed_zmin)
        layout6.addLayout(layout7)
        layout7 = QFormLayout()
        layout7.addRow("To:",self.projection_mode_fixed_zmax)
        layout6.addLayout(layout7)
        groupbox3.setLayout(layout6)
        layout5.addWidget(groupbox3)
        layout5.addWidget(self.projection_mode_all)
        widget.setLayout(layout5)
        layout4.addRow("Projection range:",widget)
        layout4.addRow("Projection type:",self.projection_type)
        groupbox2.setLayout(layout4)
        layout3.addRow(groupbox2)
        groupbox.setLayout(layout3)
        layout.addWidget(groupbox)

        groupbox = QGroupBox("Multi-processing")
        layout2 = QVBoxLayout()
        layout2.addWidget(self.use_gpu)
        layout2.addWidget(self.coarse_grain)
        layout3 = QFormLayout()
        layout3.addRow(n_count_label,self.n_count)
        layout2.addLayout(layout3)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
        layout.addWidget(self.display_results)
        layout.addWidget(self.submit_button, alignment=Qt.AlignCenter)
        self.setLayout(layout)

        self.logger = logging.getLogger(__name__)

        self.update_output_filename_label()

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

    def browse_model(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File")
        self.selected_model.setText(file_path)

    def browse_output(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        self.output_folder.setText(folder_path)

    def update_output_filename_label(self):
        if self.use_input_folder.isChecked():
            output_path = "<input folder>"
        else:
            output_path = self.output_folder.text().rstrip("/")

        self.output_filename_label.setText(os.path.join(output_path,"<input basename>" + self.output_suffix + self.output_user_suffix.text() + ".ome.tif"))

    def projection_mode_fixed_zmin_changed(self, value):
        if self.projection_mode_fixed_zmax.value() < value:
            self.projection_mode_fixed_zmax.setValue(value)

    def projection_mode_fixed_zmax_changed(self, value):
        if self.projection_mode_fixed_zmin.value() > value:
            self.projection_mode_fixed_zmin.setValue(value)

    def submit(self):
        """
        Retrieve the input parameters
        Iterate over the image paths given performing f.main() function
        """
        def check_inputs(image_paths, model_path, output_paths, output_basenames):
            if len(image_paths) == 0:
                self.logger.error('Image missing')
                return False
            for path in image_paths:
                if not os.path.isfile(path):
                    self.logger.error('Image not found: %s', path)
                    return False
            if model_path == '':
                self.logger.error('Model missing')
                self.selected_model.setFocus()
                return False
            if not os.path.isfile(model_path):
                self.logger.error('Model not found: %s', model_path)
                self.selected_model.setFocus()
                return False
            if self.output_folder.text() == '' and not self.use_input_folder.isChecked():
                self.logger.error('Output folder missing')
                self.output_folder.setFocus()
                return False
            output_files = [os.path.join(d, f) for d, f in zip(output_paths, output_basenames)]
            duplicates = [x for x, y in zip(image_paths, output_files) if output_files.count(y) > 1]
            if len(duplicates) > 0:
                self.logger.error('More than one input file will output to the same file (output files will be overwritten).\nEither use input image folder as output folder or avoid processing images from different input folders.\nProblematic input files:\n%s', '\n'.join(duplicates[:4] + (['...'] if len(duplicates) > 4 else [])))
                return False
            return True

        if self.channel_position.text() == '':
            channel_position = 0
        else:
            channel_position = int(self.channel_position.text())
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
        model_path = self.selected_model.text()
        user_suffix = self.output_user_suffix.text()
        output_basenames = [gf.splitext(os.path.basename(path))[0] + self.output_suffix + user_suffix for path in image_paths]
        if self.use_input_folder.isChecked():
            output_paths = [os.path.dirname(path) for path in image_paths]
        else:
            output_paths = [self.output_folder.text() for path in image_paths]

        if not check_inputs(image_paths, model_path, output_paths, output_basenames):
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
                 model_path,
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
            self.logger.info(f"NCOUNT {n_count}")
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
