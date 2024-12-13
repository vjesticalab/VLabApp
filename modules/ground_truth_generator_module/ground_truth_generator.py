import os
import logging
from PyQt5.QtWidgets import QVBoxLayout, QRadioButton, QGroupBox, QHBoxLayout, QFileDialog, QPushButton, QWidget, QLineEdit, QLabel, QFormLayout, QMessageBox
from PyQt5.QtCore import Qt, QRegExp
from PyQt5.QtGui import QRegExpValidator
from modules.ground_truth_generator_module import ground_truth_generator_functions as f
from general import general_functions as gf


class GroundTruthGenerator(QWidget):
    def __init__(self):
        super().__init__()

        self.output_suffix = gf.output_suffixes['ground_truth_generator']

        # Documentation
        label_documentation = gf.CollapsibleLabel('', collapsed=True)
        label_documentation.setText('Either create a cell mask using thresholding based segmentation of fluorescent image(s) with cell marker(s) or load an existing mask. The mask can then be manually edited. The bright-field image and the mask can be exported in a format that can be directly used as a training set by <a href="https://www.cellpose.org/">cellpose</a> (one pair of bright-field image and mask in tif format per time frame) to fine-tune a segmentation model.<br>'
                                    + 'Bright-field and fluorescent images must have X and Y axes and can optionally have T or Z (in particular, each image must correspond to a unique channel). Bright-field and fluorescent images must have same axes sizes.<br>'
                                    + 'Input segmentation mask must have X and Y axes and can optionally have T. It must have same X, Y and T axes sizes as the bright-field image.')

        # Input widgets
        self.input_image_BF = gf.FileLineEdit(label='Images', filetypes=gf.imagetypes)
        self.input_image_BF.textChanged.connect(self.input_image_BF_changed)
        self.input_image_fluo1 = gf.FileLineEdit(label='Images', filetypes=gf.imagetypes)
        self.input_image_fluo1.textChanged.connect(self.input_image_fluo1_changed)
        self.input_image_fluo2 = gf.FileLineEdit(label='Images', filetypes=gf.imagetypes)
        self.input_image_fluo2.textChanged.connect(self.input_image_fluo2_changed)
        self.input_image_mask = gf.FileLineEdit(label='Images', filetypes=gf.imagetypes)
        self.input_image_mask.textChanged.connect(self.input_image_mask_changed)

        # Output widgets
        self.use_input_folder = QRadioButton("Use input image folder")
        self.use_input_folder.setChecked(True)
        self.use_input_folder.toggled.connect(self.update_output_filename_label)
        self.use_custom_folder = QRadioButton("Use custom folder")
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
        # Submit
        self.submit_button = QPushButton("Submit", self)
        self.submit_button.clicked.connect(self.submit)
        self.submission_num_failed = 0
        self.label_error = None

        # Layout
        layout = QVBoxLayout()
        # Documentation
        groupbox = QGroupBox("Documentation")
        layout2 = QVBoxLayout()
        layout2.addWidget(label_documentation)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
        # Input files
        groupbox = QGroupBox('Input files')
        layout2 = QVBoxLayout()
        layout2.addWidget(QLabel("Bright-field image:"))
        layout2.addWidget(self.input_image_BF)
        layout2.addWidget(QLabel("Fluorescent image with cell marker 1 (optional):"))
        layout2.addWidget(self.input_image_fluo1)
        layout2.addWidget(QLabel("Fluorescent image with cell marker 2 (optional):"))
        layout2.addWidget(self.input_image_fluo2)
        layout2.addWidget(QLabel("Segmentation mask (optional):"))
        layout2.addWidget(self.input_image_mask)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
        # Output infos
        groupbox = QGroupBox("Output")
        layout2 = QVBoxLayout()
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
        suffix.setFixedWidth(suffix.fontMetrics().width(suffix.text() + '  '))
        suffix.setAlignment(Qt.AlignRight)
        layout4.addWidget(suffix)
        layout4.addWidget(self.output_user_suffix)
        layout3.addRow("Suffix:", layout4)
        layout3.addRow("Filename:", self.output_filename_label)
        layout2.addLayout(layout3)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
        layout.addWidget(self.submit_button, alignment=Qt.AlignCenter)
        self.setLayout(layout)

        self.logger = logging.getLogger(__name__)

        self.update_output_filename_label()

    def input_image_BF_changed(self):
        fluo_suffix = 'WL'
        brightfield_suffix = 'BF'
        image_BF_path = self.input_image_BF.text()
        self.input_image_BF.setPlaceholderText('')
        self.input_image_BF.setToolTip('')
        self.input_image_fluo1.setPlaceholderText('')
        self.input_image_fluo1.setToolTip('')
        self.input_image_fluo2.setPlaceholderText('')
        self.input_image_fluo2.setToolTip('')
        self.input_image_mask.setPlaceholderText('')
        self.input_image_mask.setToolTip('')
        if os.path.isfile(image_BF_path):
            image_fluo_paths = [path for path in os.listdir(os.path.dirname(image_BF_path)) if any(path.endswith(imagetype) for imagetype in gf.imagetypes) and os.path.basename(path) != os.path.basename(image_BF_path) and os.path.basename(path).split('_')[0] == os.path.basename(image_BF_path).split('_')[0] and len(os.path.basename(path).split('_')) == 2 and os.path.basename(path).split('_')[1].startswith(fluo_suffix)]
            if len(image_fluo_paths) == 1:
                image_fluo1_path = os.path.join(os.path.dirname(image_BF_path), image_fluo_paths[0])
                self.input_image_fluo1.setPlaceholderText(image_fluo1_path)
                self.input_image_fluo1.setToolTip(image_fluo1_path)
            if len(image_fluo_paths) == 2:
                image_fluo1_path = os.path.join(os.path.dirname(image_BF_path), image_fluo_paths[0])
                self.input_image_fluo1.setPlaceholderText(image_fluo1_path)
                self.input_image_fluo1.setToolTip(image_fluo1_path)
                image_fluo2_path = os.path.join(os.path.dirname(image_BF_path), image_fluo_paths[1])
                self.input_image_fluo2.setPlaceholderText(image_fluo2_path)
                self.input_image_fluo2.setToolTip(image_fluo2_path)
            image_mask_paths = [path for path in os.listdir(os.path.dirname(image_BF_path)) if any(path.endswith(imagetype) for imagetype in gf.imagetypes) and self.output_suffix in os.path.basename(path) and os.path.basename(path).split('_')[0] == os.path.basename(image_BF_path).split('_')[0]]
            if len(image_mask_paths) == 1:
                image_mask_path = os.path.join(os.path.dirname(image_BF_path), image_mask_paths[0])
                self.input_image_mask.setPlaceholderText(image_mask_path)
                self.input_image_mask.setToolTip(image_mask_path)

    def input_image_fluo1_changed(self):
        fluo_suffix = 'WL'
        brightfield_suffix = 'BF'
        image_fluo1_path = self.input_image_fluo1.text()
        self.input_image_BF.setPlaceholderText('')
        self.input_image_BF.setToolTip('')
        self.input_image_fluo1.setPlaceholderText('')
        self.input_image_fluo1.setToolTip('')
        self.input_image_fluo2.setPlaceholderText('')
        self.input_image_fluo2.setToolTip('')
        self.input_image_mask.setPlaceholderText('')
        self.input_image_mask.setToolTip('')
        if os.path.isfile(image_fluo1_path):
            image_BF_paths = [path for path in os.listdir(os.path.dirname(image_fluo1_path)) if any(path.endswith(imagetype) for imagetype in gf.imagetypes) and os.path.basename(path) != os.path.basename(image_fluo1_path) and os.path.basename(path).split('_')[0] == os.path.basename(image_fluo1_path).split('_')[0] and len(os.path.basename(path).split('_')) == 2 and os.path.basename(path).split('_')[1].startswith(brightfield_suffix)]
            if len(image_BF_paths) == 1:
                image_BF_path = os.path.join(os.path.dirname(image_fluo1_path), image_BF_paths[0])
                self.input_image_BF.setPlaceholderText(image_BF_path)
                self.input_image_BF.setToolTip(image_BF_path)
            image_fluo_paths = [path for path in os.listdir(os.path.dirname(image_fluo1_path)) if any(path.endswith(imagetype) for imagetype in gf.imagetypes) and os.path.basename(path) != os.path.basename(image_fluo1_path) and os.path.basename(path).split('_')[0] == os.path.basename(image_fluo1_path).split('_')[0] and len(os.path.basename(path).split('_')) == 2 and os.path.basename(path).split('_')[1].startswith(fluo_suffix)]
            if len(image_fluo_paths) == 1:
                image_fluo2_path = os.path.join(os.path.dirname(image_fluo1_path), image_fluo_paths[0])
                self.input_image_fluo2.setPlaceholderText(image_fluo2_path)
                self.input_image_fluo2.setToolTip(image_fluo2_path)
            image_mask_paths = [path for path in os.listdir(os.path.dirname(image_BF_path)) if any(path.endswith(imagetype) for imagetype in gf.imagetypes) and self.output_suffix in os.path.basename(path) and os.path.basename(path).split('_')[0] == os.path.basename(image_BF_path).split('_')[0]]
            if len(image_mask_paths) == 1:
                image_mask_path = os.path.join(os.path.dirname(image_BF_path), image_mask_paths[0])
                self.input_image_mask.setPlaceholderText(image_mask_path)
                self.input_image_mask.setToolTip(image_mask_path)

    def input_image_fluo2_changed(self):
        fluo_suffix = 'WL'
        brightfield_suffix = 'BF'
        image_fluo2_path = self.input_image_fluo2.text()
        self.input_image_BF.setPlaceholderText('')
        self.input_image_BF.setToolTip('')
        self.input_image_fluo1.setPlaceholderText('')
        self.input_image_fluo1.setToolTip('')
        self.input_image_fluo2.setPlaceholderText('')
        self.input_image_fluo2.setToolTip('')
        self.input_image_mask.setPlaceholderText('')
        self.input_image_mask.setToolTip('')
        if os.path.isfile(image_fluo2_path):
            image_BF_paths = [path for path in os.listdir(os.path.dirname(image_fluo2_path)) if any(path.endswith(imagetype) for imagetype in gf.imagetypes) and os.path.basename(path) != os.path.basename(image_fluo2_path) and os.path.basename(path).split('_')[0] == os.path.basename(image_fluo2_path).split('_')[0] and len(os.path.basename(path).split('_')) == 2 and os.path.basename(path).split('_')[1].startswith(brightfield_suffix)]
            if len(image_BF_paths) == 1:
                image_BF_path = os.path.join(os.path.dirname(image_fluo2_path), image_BF_paths[0])
                self.input_image_BF.setPlaceholderText(image_BF_path)
                self.input_image_BF.setToolTip(image_BF_path)
            image_fluo_paths = [path for path in os.listdir(os.path.dirname(image_fluo2_path)) if any(path.endswith(imagetype) for imagetype in gf.imagetypes) and os.path.basename(path) != os.path.basename(image_fluo2_path) and os.path.basename(path).split('_')[0] == os.path.basename(image_fluo2_path).split('_')[0] and len(os.path.basename(path).split('_')) == 2 and os.path.basename(path).split('_')[1].startswith(fluo_suffix)]
            if len(image_fluo_paths) == 1:
                image_fluo1_path = os.path.join(os.path.dirname(image_fluo2_path), image_fluo_paths[0])
                self.input_image_fluo1.setPlaceholderText(image_fluo1_path)
                self.input_image_fluo1.setToolTip(image_fluo1_path)
            image_mask_paths = [path for path in os.listdir(os.path.dirname(image_BF_path)) if any(path.endswith(imagetype) for imagetype in gf.imagetypes) and self.output_suffix in os.path.basename(path) and os.path.basename(path).split('_')[0] == os.path.basename(image_BF_path).split('_')[0]]
            if len(image_mask_paths) == 1:
                image_mask_path = os.path.join(os.path.dirname(image_BF_path), image_mask_paths[0])
                self.input_image_mask.setPlaceholderText(image_mask_path)
                self.input_image_mask.setToolTip(image_mask_path)

    def input_image_mask_changed(self):
        fluo_suffix = 'WL'
        brightfield_suffix = 'BF'
        image_mask_path = self.input_image_mask.text()
        self.input_image_BF.setPlaceholderText('')
        self.input_image_BF.setToolTip('')
        self.input_image_fluo1.setPlaceholderText('')
        self.input_image_fluo1.setToolTip('')
        self.input_image_fluo2.setPlaceholderText('')
        self.input_image_fluo2.setToolTip('')
        self.input_image_mask.setPlaceholderText('')
        self.input_image_mask.setToolTip('')
        if os.path.isfile(image_mask_path):
            image_BF_paths = [path for path in os.listdir(os.path.dirname(image_mask_path)) if any(path.endswith(imagetype) for imagetype in gf.imagetypes) and os.path.basename(path) != os.path.basename(image_mask_path) and os.path.basename(path).split('_')[0] == os.path.basename(image_mask_path).split('_')[0] and len(os.path.basename(path).split('_')) == 2 and os.path.basename(path).split('_')[1].startswith(brightfield_suffix)]
            if len(image_BF_paths) == 1:
                image_BF_path = os.path.join(os.path.dirname(image_mask_path), image_BF_paths[0])
                self.input_image_BF.setPlaceholderText(image_BF_path)
                self.input_image_BF.setToolTip(image_BF_path)
            image_fluo_paths = [path for path in os.listdir(os.path.dirname(image_mask_path)) if any(path.endswith(imagetype) for imagetype in gf.imagetypes) and os.path.basename(path) != os.path.basename(image_mask_path) and os.path.basename(path).split('_')[0] == os.path.basename(image_mask_path).split('_')[0] and len(os.path.basename(path).split('_')) == 2 and os.path.basename(path).split('_')[1].startswith(fluo_suffix)]
            if len(image_fluo_paths) == 1:
                image_fluo1_path = os.path.join(os.path.dirname(image_mask_path), image_fluo_paths[0])
                self.input_image_fluo1.setPlaceholderText(image_fluo1_path)
                self.input_image_fluo1.setToolTip(image_fluo1_path)
            if len(image_fluo_paths) == 2:
                image_fluo1_path = os.path.join(os.path.dirname(image_mask_path), image_fluo_paths[0])
                self.input_image_fluo1.setPlaceholderText(image_fluo1_path)
                self.input_image_fluo1.setToolTip(image_fluo1_path)
                image_fluo2_path = os.path.join(os.path.dirname(image_mask_path), image_fluo_paths[1])
                self.input_image_fluo2.setPlaceholderText(image_fluo2_path)
                self.input_image_fluo2.setToolTip(image_fluo2_path)

    def update_output_filename_label(self):
        if self.use_input_folder.isChecked():
            output_path = "<input folder>"
        else:
            output_path = os.path.abspath(self.output_folder.text())

        self.output_filename_label.setText(os.path.normpath(os.path.join(output_path, "<input basename>" + self.output_suffix + self.output_user_suffix.text() + ".ome.tif")))

    def submit(self):
        image_BF_path = self.input_image_BF.text()
        if image_BF_path == '':
            image_BF_path = self.input_image_BF.placeholderText()
        image_fluo1_path = self.input_image_fluo1.text()
        if image_fluo1_path == '':
            image_fluo1_path = self.input_image_fluo1.placeholderText()
        image_fluo2_path = self.input_image_fluo2.text()
        if image_fluo2_path == '':
            image_fluo2_path = self.input_image_fluo2.placeholderText()
        image_mask_path = self.input_image_mask.text()
        if image_mask_path == '':
            image_mask_path = self.input_image_mask.placeholderText()

        if image_BF_path == '':
            self.logger.error('Bright-field image missing')
            self.input_image_BF.setFocus()
            return
        if image_fluo1_path == '' and image_mask_path == '':
            self.logger.error('Fluorescent image with cell marker 1 and segmentation mask missing. At least one of them must be specified.')
            self.input_image_fluo1.setFocus()
            return
        if image_BF_path != '' and not os.path.isfile(image_BF_path):
            self.logger.error('Image not found: %s', image_BF_path)
            self.input_image_BF.setFocus()
            return
        if image_fluo1_path != '' and not os.path.isfile(image_fluo1_path):
            self.logger.error('Image not found: %s', image_fluo1_path)
            self.input_image_fluo1.setFocus()
            return
        if image_fluo2_path != '' and not os.path.isfile(image_fluo2_path):
            self.logger.error('Image not found: %s', image_fluo2_path)
            self.input_image_fluo2.setFocus()
            return
        if image_mask_path != '' and not os.path.isfile(image_mask_path):
            self.logger.error('Image not found: %s', image_mask_path)
            self.input_image_mask.setFocus()
            return
        if self.output_folder.text() == '' and not self.use_input_folder.isChecked():
            self.logger.error('Output folder missing')
            self.output_folder.setFocus()
            return

        user_suffix = self.output_user_suffix.text()
        output_basename = gf.splitext(os.path.basename(image_BF_path))[0] + self.output_suffix + user_suffix
        if self.use_input_folder.isChecked():
            output_path = os.path.dirname(image_BF_path)
        else:
            output_path = self.output_folder.text()

        if os.path.normpath(os.path.abspath(image_mask_path)) == os.path.normpath(os.path.join(output_path, output_basename+".ome.tif")):
            res = QMessageBox.information(self, 'Information', 'The segmentation mask used as input will be overwritten by the mask generated in this module.\nOverwrite?', QMessageBox.Yes | QMessageBox.No, defaultButton=QMessageBox.Yes)
            if res == QMessageBox.No:
                return

        # disable messagebox error handler
        messagebox_error_handler = None
        for h in logging.getLogger().handlers:
            if h.get_name() == 'messagebox_error_handler':
                messagebox_error_handler = h
                logging.getLogger().removeHandler(messagebox_error_handler)
                break

        self.logger.info("Ground truth generation (%s, %s, %s, %s)", image_BF_path, image_fluo1_path, image_fluo2_path, image_mask_path)
        try:
            f.main(image_BF_path, image_fluo1_path, image_fluo2_path, image_mask_path, output_path, output_basename)
        except Exception as e:
            QMessageBox.critical(self, 'Error', str(e))
            self.logger.exception("Ground truth generation failed.")

        # re-enable messagebox error handler
        if messagebox_error_handler is not None:
            logging.getLogger().addHandler(messagebox_error_handler)

        self.logger.info("Done")
