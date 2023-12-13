import logging
import os
from PyQt5.QtWidgets import QFileDialog, QCheckBox, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QGroupBox, QRadioButton, QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCursor
from modules.segmentation_module import segmentation_functions as f
from general import general_functions as gf
import concurrent

class Segmentation(QWidget):
    def __init__(self):
        super().__init__()

        self.imagetypes = ['.nd2', '.tif', '.tiff']
        self.image_list = gf.FileListWidget(filetypes=self.imagetypes, filenames_filter='_BF')
        self.image_list.file_list_changed.connect(self.image_list_changed)

        self.selected_model = gf.DropFileLineEdit()
        default_model_path = '/Volumes/D2c/Lab_VjesticaLabApps/Cellpose_v2/20230704_CellposeModels/models/cellpose_projection_best_nepochs_5000'
        self.selected_model.setText(default_model_path)
        self.browse_button = QPushButton("Browse", self)
        self.browse_button.clicked.connect(self.browse_model)

        self.use_input_folder = QRadioButton("Use input image folder (segmentation_masks sub-folder)")
        self.use_input_folder.setChecked(True)
        self.use_custom_folder = QRadioButton("Use custom folder:")
        self.use_custom_folder.setChecked(False)
        self.output_folder = gf.DropFolderLineEdit()
        self.browse_button2 = QPushButton("Browse", self)
        self.browse_button2.clicked.connect(self.browse_output)
        self.output_folder.setEnabled(self.use_custom_folder.isChecked())
        self.browse_button2.setEnabled(self.use_custom_folder.isChecked())
        self.use_custom_folder.toggled.connect(self.output_folder.setEnabled)
        self.use_custom_folder.toggled.connect(self.browse_button2.setEnabled)

        self.display_results = QCheckBox("Show results in napari")
        self.display_results.setChecked(False)
        self.halfcapacity = QCheckBox("Use half capacity instead of all")
        self.halfcapacity.setChecked(False)
        self.coarse_grain = QCheckBox("Activate coarse grain parallelisation")
        self.coarse_grain.setChecked(False)
        self.use_gpu = QCheckBox("Activate GPU")
        self.use_gpu.setChecked(False)
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
        groupbox = QGroupBox("Output folder")
        layout2 = QVBoxLayout()
        layout2.addWidget(self.use_input_folder)
        layout2.addWidget(self.use_custom_folder)
        layout3 = QHBoxLayout()
        layout3.addWidget(self.output_folder)
        layout3.addWidget(self.browse_button2, alignment=Qt.AlignCenter)
        layout2.addLayout(layout3)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
        layout.addWidget(self.display_results)
        layout.addWidget(self.halfcapacity)
        layout.addWidget(self.coarse_grain)
        layout.addWidget(self.use_gpu)
        layout.addWidget(self.submit_button, alignment=Qt.AlignCenter)
        self.setLayout(layout)

        self.logger = logging.getLogger(__name__)

    def image_list_changed(self):
        if self.image_list.count() > 1:
            self.display_results.setChecked(False)
        self.display_results.setEnabled(self.image_list.count() <= 1)

    def browse_model(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File")
        self.selected_model.setText(file_path)

    def browse_output(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        self.output_folder.setText(folder_path)

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

        image_paths = self.image_list.get_file_list()
        model_path = self.selected_model.text()
        output_basenames = [os.path.splitext(os.path.basename(path))[0] for path in image_paths]
        if self.use_input_folder.isChecked():
            output_paths = [os.path.join(os.path.dirname(path), 'segmentation_masks') for path in image_paths]
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
        n_count = os.cpu_count()
        if self.halfcapacity.isChecked():
            n_count = os.cpu_count() // 2

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
                f.main(*args, run_parallel=run_parallel)

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
