import logging
import os
import sys
import time
import concurrent.futures
import re
from PyQt5.QtWidgets import QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QGroupBox, QRadioButton, QLabel, QFormLayout, QLineEdit, QApplication, QCheckBox, QSpinBox, QMessageBox, QFileDialog
from PyQt5.QtCore import Qt, QRegularExpression
from PyQt5.QtGui import QCursor, QRegularExpressionValidator
from modules.image_cropping_module import image_cropping_functions as f
from general import general_functions as gf
from ome_types.model import CommentAnnotation


def process_initializer():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s (%(name)s) [%(levelname)s] %(message)s", handlers=[logging.StreamHandler(sys.stdout)], force=True)


class ImageCropping(QWidget):
    def __init__(self):
        super().__init__()

        self.output_suffix = gf.output_suffixes['image_cropping']

        layout = QVBoxLayout()

        # Documentation
        label_documentation = gf.CollapsibleLabel('', collapsed=True)
        label_documentation.setText('Crop images and masks.<br>' +
                                    'Input images can have any compbination of T, C, Z, Y and X axes.<br>' +
                                    'Cropping ranges are inclusive, e.g. when cropping axis T from 2 to 10, all time frames T=2, 3, ..., 10 are kept.<br>' +
                                    'Cropping ranges are clipped to axis range, e.g. cropping range from 2 to 10 for a T axis of size 4 (i.e. T=0, 1, 2 or 3) will be clipped to cropping range from 2 to 3.<br>' +
                                    'Cropping ranges must overlap axis ranges, e.g. cropping range from 2 to 10 for a T axis of size 2 (i.e. T=0 or 1) will generate an error.')
        groupbox = QGroupBox('Documentation')
        layout2 = QVBoxLayout()
        layout2.addWidget(label_documentation)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        self.image_list = gf.FileListWidget(filetypes=gf.imagetypes, filenames_exclude_filter=self.output_suffix)
        self.image_list.file_list_changed.connect(self.image_list_changed)
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
        self.output_user_suffix.setValidator(QRegularExpressionValidator(QRegularExpression('[A-Za-z0-9-]*')))
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

        groupbox = QGroupBox('Options')
        layout2 = QVBoxLayout()
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        self.crop_T = QGroupBox('Crop T axis:')
        self.crop_T.setCheckable(True)
        self.crop_T.setChecked(False)
        self.crop_T_min = QSpinBox()
        self.crop_T_min.setMinimum(0)
        self.crop_T_min.setMaximum(10000)
        self.crop_T_min.setValue(0)
        self.crop_T_min.valueChanged.connect(self.crop_T_min_changed)
        self.crop_T_max = QSpinBox()
        self.crop_T_max.setMinimum(0)
        self.crop_T_max.setMaximum(10000)
        self.crop_T_max.setValue(10000)
        self.crop_T_max.valueChanged.connect(self.crop_T_max_changed)
        layout3 = QHBoxLayout()
        layout4 = QFormLayout()
        layout4.addRow("From:", self.crop_T_min)
        layout3.addLayout(layout4)
        layout4 = QFormLayout()
        layout4.addRow("To:", self.crop_T_max)
        layout3.addLayout(layout4)
        self.crop_T.setLayout(layout3)
        layout2.addWidget(self.crop_T)

        self.crop_C = QGroupBox('Crop C axis:')
        self.crop_C.setCheckable(True)
        self.crop_C.setChecked(False)
        self.crop_C_min = QSpinBox()
        self.crop_C_min.setMinimum(0)
        self.crop_C_min.setMaximum(10000)
        self.crop_C_min.setValue(0)
        self.crop_C_min.valueChanged.connect(self.crop_C_min_changed)
        self.crop_C_max = QSpinBox()
        self.crop_C_max.setMinimum(0)
        self.crop_C_max.setMaximum(10000)
        self.crop_C_max.setValue(10000)
        self.crop_C_max.valueChanged.connect(self.crop_C_max_changed)
        layout3 = QHBoxLayout()
        layout4 = QFormLayout()
        layout4.addRow("From:", self.crop_C_min)
        layout3.addLayout(layout4)
        layout4 = QFormLayout()
        layout4.addRow("To:", self.crop_C_max)
        layout3.addLayout(layout4)
        self.crop_C.setLayout(layout3)
        layout2.addWidget(self.crop_C)

        self.crop_Z = QGroupBox('Crop Z axis:')
        self.crop_Z.setCheckable(True)
        self.crop_Z.setChecked(False)
        self.crop_Z_min = QSpinBox()
        self.crop_Z_min.setMinimum(0)
        self.crop_Z_min.setMaximum(10000)
        self.crop_Z_min.setValue(0)
        self.crop_Z_min.valueChanged.connect(self.crop_Z_min_changed)
        self.crop_Z_max = QSpinBox()
        self.crop_Z_max.setMinimum(0)
        self.crop_Z_max.setMaximum(10000)
        self.crop_Z_max.setValue(10000)
        self.crop_Z_max.valueChanged.connect(self.crop_Z_max_changed)
        layout3 = QHBoxLayout()
        layout4 = QFormLayout()
        layout4.addRow("From:", self.crop_Z_min)
        layout3.addLayout(layout4)
        layout4 = QFormLayout()
        layout4.addRow("To:", self.crop_Z_max)
        layout3.addLayout(layout4)
        self.crop_Z.setLayout(layout3)
        layout2.addWidget(self.crop_Z)

        self.crop_Y = QGroupBox('Crop Y axis:')
        self.crop_Y.setCheckable(True)
        self.crop_Y.setChecked(False)
        self.crop_Y_min = QSpinBox()
        self.crop_Y_min.setMinimum(0)
        self.crop_Y_min.setMaximum(10000)
        self.crop_Y_min.setValue(0)
        self.crop_Y_min.valueChanged.connect(self.crop_Y_min_changed)
        self.crop_Y_max = QSpinBox()
        self.crop_Y_max.setMinimum(0)
        self.crop_Y_max.setMaximum(10000)
        self.crop_Y_max.setValue(10000)
        self.crop_Y_max.valueChanged.connect(self.crop_Y_max_changed)
        layout3 = QHBoxLayout()
        layout4 = QFormLayout()
        layout4.addRow("From:", self.crop_Y_min)
        layout3.addLayout(layout4)
        layout4 = QFormLayout()
        layout4.addRow("To:", self.crop_Y_max)
        layout3.addLayout(layout4)
        self.crop_Y.setLayout(layout3)
        layout2.addWidget(self.crop_Y)

        self.crop_X = QGroupBox('Crop X axis:')
        self.crop_X.setCheckable(True)
        self.crop_X.setChecked(False)
        self.crop_X_min = QSpinBox()
        self.crop_X_min.setMinimum(0)
        self.crop_X_min.setMaximum(10000)
        self.crop_X_min.setValue(0)
        self.crop_X_min.valueChanged.connect(self.crop_X_min_changed)
        self.crop_X_max = QSpinBox()
        self.crop_X_max.setMinimum(0)
        self.crop_X_max.setMaximum(10000)
        self.crop_X_max.setValue(10000)
        self.crop_X_max.valueChanged.connect(self.crop_X_max_changed)
        layout3 = QHBoxLayout()
        layout4 = QFormLayout()
        layout4.addRow("From:", self.crop_X_min)
        layout3.addLayout(layout4)
        layout4 = QFormLayout()
        layout4.addRow("To:", self.crop_X_max)
        layout3.addLayout(layout4)
        self.crop_X.setLayout(layout3)
        layout2.addWidget(self.crop_X)

        button = QPushButton('Load settings from image...')
        button.setToolTip('Click to select a cropped image and to use the cropping settings found in its metadata.')
        button.clicked.connect(self.load_settings_from_image)
        layout2.addWidget(button, alignment=Qt.AlignCenter)

        groupbox = QGroupBox("Multi-processing")
        layout2 = QFormLayout()
        self.nprocesses = QSpinBox()
        self.nprocesses.setMinimum(1)
        self.nprocesses.setMaximum(os.cpu_count())
        self.nprocesses.setValue(1)
        layout2.addRow("Number of processes:", self.nprocesses)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        self.display_results = QCheckBox("Show (and edit) results in napari")
        self.display_results.setChecked(False)
        layout.addWidget(self.display_results)

        self.submit_button = QPushButton('Submit')
        self.submit_button.clicked.connect(self.submit)
        layout.addWidget(self.submit_button, alignment=Qt.AlignCenter)

        self.setLayout(layout)

        self.logger = logging.getLogger(__name__)

        self.update_output_filename_label()

    def image_list_changed(self):
        if self.image_list.count() > 1:
            self.display_results.setChecked(False)
        self.display_results.setEnabled(self.image_list.count() <= 1)

        # add tooltip with image size
        for i in range(self.image_list.file_list.count()):
            if self.image_list.file_list.item(i).toolTip() == '':
                image_path = self.image_list.file_list.item(i).text()
                try:
                    image = gf.Image(image_path)
                    self.image_list.file_list.item(i).setToolTip('Image size: (' + ', '.join([k+': '+str(v) for (k, v) in image.sizes.items() if v > 1]) + ')')
                except:
                    self.image_list.file_list.item(i).setToolTip('')

    def load_settings_from_image(self):
        file_path, _ = QFileDialog.getOpenFileName(self, 'Select cropped image/mask', filter='*'+self.output_suffix+'*.ome.tif')
        if file_path != '':
            # load image metadata
            image = gf.Image(file_path)
            operations = []
            n = 0
            if image.ome_metadata:
                for x in image.ome_metadata.structured_annotations:
                    if isinstance(x, CommentAnnotation) and x.namespace == "VLabApp":
                        n += 1
                        for line in x.value.split('\n'):
                            res = re.search('] Cropping ([TCZYX]) axis: from ([0-9]+) to ([0-9]+)$', line)
                            if res:
                                operations.append((n, res.group(1), int(res.group(2)), int(res.group(3))))

            n_distinct_crop = len(set(x[0] for x in operations))
            if n_distinct_crop == 0:
                QMessageBox.warning(self, 'Warning', 'The selected file does not contain cropping information.', buttons=QMessageBox.Ok)
                return
            if n_distinct_crop > 1:
                QMessageBox.information(self, 'Information', 'The selected file contain multiple cropping settings. Merging all cropping settings.', buttons=QMessageBox.Ok)

            if n_distinct_crop > 0:
                crop_settings = dict()
                for _, axis, vmin, vmax in reversed(operations):
                    if axis in crop_settings:
                        crop_settings[axis] = (crop_settings[axis][0]+vmin, crop_settings[axis][0]+vmax)
                    else:
                        crop_settings[axis] = (vmin, vmax)

                if 'T' in crop_settings:
                    self.crop_T.setChecked(True)
                    self.crop_T_min.setValue(crop_settings['T'][0])
                    self.crop_T_max.setValue(crop_settings['T'][1])
                else:
                    self.crop_T.setChecked(False)
                    self.crop_T_min.setValue(0)
                    self.crop_T_max.setValue(10000)
                if 'C' in crop_settings:
                    self.crop_C.setChecked(True)
                    self.crop_C_min.setValue(crop_settings['C'][0])
                    self.crop_C_max.setValue(crop_settings['C'][1])
                else:
                    self.crop_C.setChecked(False)
                    self.crop_C_min.setValue(0)
                    self.crop_C_max.setValue(10000)
                if 'Z' in crop_settings:
                    self.crop_Z.setChecked(True)
                    self.crop_Z_min.setValue(crop_settings['Z'][0])
                    self.crop_Z_max.setValue(crop_settings['Z'][1])
                else:
                    self.crop_Z.setChecked(False)
                    self.crop_Z_min.setValue(0)
                    self.crop_Z_max.setValue(10000)
                if 'Y' in crop_settings:
                    self.crop_Y.setChecked(True)
                    self.crop_Y_min.setValue(crop_settings['Y'][0])
                    self.crop_Y_max.setValue(crop_settings['Y'][1])
                else:
                    self.crop_Y.setChecked(False)
                    self.crop_Y_min.setValue(0)
                    self.crop_Y_max.setValue(10000)
                if 'X' in crop_settings:
                    self.crop_X.setChecked(True)
                    self.crop_X_min.setValue(crop_settings['X'][0])
                    self.crop_X_max.setValue(crop_settings['X'][1])
                else:
                    self.crop_X.setChecked(False)
                    self.crop_X_min.setValue(0)
                    self.crop_X_max.setValue(10000)

    def crop_T_min_changed(self, value):
        self.crop_T_max.setMinimum(value)

    def crop_T_max_changed(self, value):
        self.crop_T_min.setMaximum(value)

    def crop_C_min_changed(self, value):
        self.crop_C_max.setMinimum(value)

    def crop_C_max_changed(self, value):
        self.crop_C_min.setMaximum(value)

    def crop_Z_min_changed(self, value):
        self.crop_Z_max.setMinimum(value)

    def crop_Z_max_changed(self, value):
        self.crop_Z_min.setMaximum(value)

    def crop_Y_min_changed(self, value):
        self.crop_Y_max.setMinimum(value)

    def crop_Y_max_changed(self, value):
        self.crop_Y_min.setMaximum(value)

    def crop_X_min_changed(self, value):
        self.crop_X_max.setMinimum(value)

    def crop_X_max_changed(self, value):
        self.crop_X_min.setMaximum(value)

    def update_output_filename_label(self):
        if self.use_input_folder.isChecked():
            output_path = '<input folder>'
        else:
            output_path = os.path.abspath(self.output_folder.text())

        self.output_filename_label.setText(os.path.normpath(os.path.join(output_path, "<input basename>" + self.output_suffix + self.output_user_suffix.text() + ".ome.tif")))

    def submit(self):
        image_paths = self.image_list.get_file_list()
        user_suffix = self.output_user_suffix.text()
        output_basenames = [gf.splitext(os.path.basename(image_path))[0] + self.output_suffix + user_suffix for image_path in image_paths]
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
        if not any([self.crop_T.isChecked(),
                    self.crop_C.isChecked(),
                    self.crop_Z.isChecked(),
                    self.crop_Y.isChecked(),
                    self.crop_X.isChecked(),
                    self.display_results.isChecked()]):
            self.logger.error('No axis to crop')
            return

        T_range = (self.crop_T_min.value(), self.crop_T_max.value()) if self.crop_T.isChecked() else None
        C_range = (self.crop_C_min.value(), self.crop_C_max.value()) if self.crop_C.isChecked() else None
        Z_range = (self.crop_Z_min.value(), self.crop_Z_max.value()) if self.crop_Z.isChecked() else None
        Y_range = (self.crop_Y_min.value(), self.crop_Y_max.value()) if self.crop_Y.isChecked() else None
        X_range = (self.crop_X_min.value(), self.crop_X_max.value()) if self.crop_X.isChecked() else None

        output_files = [os.path.join(d, f) for d, f in zip(output_paths, output_basenames)]
        duplicates = [x for x, y in zip(image_paths, output_files) if output_files.count(y) > 1]
        if len(duplicates) > 0:
            self.logger.error('More than one input file will output to the same file (output files will be overwritten).\nEither use input image/mask folder as output folder or avoid processing image or masks from different input folders.\nProblematic input files:\n%s', '\n'.join(duplicates[:4] + (['...'] if len(duplicates) > 4 else [])))
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

        QApplication.setOverrideCursor(QCursor(Qt.BusyCursor))
        QApplication.processEvents()

        arguments = []
        for image_path, output_path, output_basename in zip(image_paths, output_paths, output_basenames):
            arguments.append((image_path,
                              output_path,
                              output_basename,
                              T_range,
                              C_range,
                              Z_range,
                              Y_range,
                              X_range,
                              self.display_results.isChecked()))
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

        hide_status_dialog = False
        if self.display_results.isChecked():
            QApplication.processEvents()
            time.sleep(0.01)
            hide_status_dialog = True
            for i, args in enumerate(arguments):
                try:
                    f.main(*args)
                    status_dialog.set_status(i,'Success')
                except Exception as e:
                    self.logger.exception("An exception occurred")
                    status_dialog.set_status(i,'Failed',str(e))
                    hide_status_dialog = False
                QApplication.processEvents()
                time.sleep(0.01)
        else:
            with concurrent.futures.ProcessPoolExecutor(max_workers=nprocesses, initializer=process_initializer) as executor:
                future_reg = {executor.submit(f.main, *args): i for i, args in enumerate(arguments)}
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
        if hide_status_dialog:
            status_dialog.hide()

        # re-enable messagebox error handler
        if messagebox_error_handler is not None:
            logging.getLogger().addHandler(messagebox_error_handler)

        self.logger.info('Done')
