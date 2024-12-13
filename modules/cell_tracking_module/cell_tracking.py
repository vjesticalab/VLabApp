import os
import logging
from PyQt5.QtWidgets import QFileDialog, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QGroupBox, QRadioButton, QApplication, QSpinBox, QFormLayout, QLineEdit
from PyQt5.QtCore import Qt, QRegExp
from PyQt5.QtGui import QCursor, QRegExpValidator
from modules.cell_tracking_module import cell_tracking_functions as f
from general import general_functions as gf


class CellTracking(QWidget):
    def __init__(self, pipeline_layout=False):
        super().__init__()

        self.output_suffix = gf.output_suffixes['cell_tracking']
        self.mask_suffix = gf.output_suffixes['segmentation']

        self.pipeline_layout = pipeline_layout

        label_documentation = gf.CollapsibleLabel('', collapsed=True)
        label_documentation.setText('For each input segmentation mask, perform cell tracking, save the cell tracking graph and segmentation mask with relabelled cells.<br>' +
                                    'Input segmentation mask must have X, Y and T axes. The optional input image must have X, Y and T axes and can optionally have C and/or Z axes.<br><br>' +
                                    'Additional information: <a href="'+os.path.join(os.path.dirname(__file__), "doc", "METHODS.html")+'">Methods</a>')

        self.mask_list = gf.FileListWidget(filetypes=gf.imagetypes, filenames_filter=self.mask_suffix)
        self.mask_list.file_list_changed.connect(self.mask_list_changed)

        self.use_input_folder = QRadioButton("Use input mask folder")
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
        self.output_filename_label1 = QLineEdit()
        self.output_filename_label1.setFrame(False)
        self.output_filename_label1.setEnabled(False)
        self.output_filename_label1.textChanged.connect(self.output_filename_label1.setToolTip)
        self.output_filename_label2 = QLineEdit()
        self.output_filename_label2.setFrame(False)
        self.output_filename_label2.setEnabled(False)
        self.output_filename_label2.textChanged.connect(self.output_filename_label2.setToolTip)

        self.min_area = QSpinBox()
        self.min_area.setMinimum(0)
        self.min_area.setMaximum(10000)
        self.min_area.setValue(300)
        self.min_area.setToolTip('Remove mask regions with area (number of pixels) below this value.')

        self.max_delta_frame = QSpinBox()
        self.max_delta_frame.setMinimum(1)
        self.max_delta_frame.setMaximum(50)
        self.max_delta_frame.setValue(5)
        self.max_delta_frame.setToolTip('Number of previous frames to consider when creating the cell tracking graph.')

        self.min_overlap_fraction = QSpinBox()
        self.min_overlap_fraction.setMinimum(0)
        self.min_overlap_fraction.setMaximum(100)
        self.min_overlap_fraction.setValue(20)
        self.min_overlap_fraction.setSuffix("%")
        self.min_overlap_fraction.setToolTip('minimum overlap fraction (w.r.t mask area) to consider when creating edges in the cell tracking graph.')

        self.stable_overlap_fraction = QSpinBox()
        self.stable_overlap_fraction.setMinimum(0)
        self.stable_overlap_fraction.setMaximum(100)
        self.stable_overlap_fraction.setValue(90)
        self.stable_overlap_fraction.setSuffix("%")
        self.stable_overlap_fraction.setToolTip('Cell tracking graph edges corresponding to an overlap fraction below this value are considered as not stable.')

        self.nframes_defect = QSpinBox()
        self.nframes_defect.setMinimum(1)
        self.nframes_defect.setMaximum(50)
        self.nframes_defect.setValue(2)
        self.nframes_defect.setToolTip('Maximum size of the defect (number of frames).')
        self.nframes_defect.valueChanged.connect(self.nframes_defect_changed)

        self.max_delta_frame_interpolation = QSpinBox()
        self.max_delta_frame_interpolation.setMinimum(1)
        self.max_delta_frame_interpolation.setMaximum(50)
        self.max_delta_frame_interpolation.setValue(3)
        self.max_delta_frame_interpolation.setToolTip('Number of previous and subsequent frames to consider for mask interpolation.')
        self.max_delta_frame_interpolation.valueChanged.connect(self.max_delta_frame_interpolation_changed)

        self.nframes_stable = QSpinBox()
        self.nframes_stable.setMinimum(1)
        self.nframes_stable.setMaximum(50)
        self.nframes_stable.setValue(3)
        self.nframes_stable.setToolTip('Minimum number of stable frames before and after the defect.')
        self.nframes_stable.valueChanged.connect(self.nframes_stable_changed)

        self.display_results = QGroupBox("Show (and edit) results in napari")
        self.display_results.setCheckable(True)
        self.display_results.setChecked(False)

        self.input_image = gf.FileLineEdit(label='Images', filetypes=gf.imagetypes)

        self.submit_button = QPushButton("Submit")
        self.submit_button.clicked.connect(self.submit)

        layout = QVBoxLayout()
        groupbox = QGroupBox("Documentation")
        layout2 = QVBoxLayout()
        layout2.addWidget(label_documentation)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        if not self.pipeline_layout:
            groupbox = QGroupBox('Input files (segmentation masks)')
            layout2 = QVBoxLayout()
            layout2.addWidget(self.mask_list)
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
        layout4 = QVBoxLayout()
        layout4.setSpacing(0)
        layout4.addWidget(self.output_filename_label1)
        layout4.addWidget(self.output_filename_label2)
        layout3.addRow("Filename:", layout4)
        layout2.addLayout(layout3)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
        groupbox = QGroupBox("Options")
        layout2 = QFormLayout()
        layout2.addRow(QLabel("Cell tracking graph:"))
        layout2.addRow("Min area:", self.min_area)
        layout2.addRow("Max delta frame:", self.max_delta_frame)
        layout2.addRow("Min overlap fraction:", self.min_overlap_fraction)
        self.auto_clean = QGroupBox("Automatic cleaning")
        self.auto_clean.setCheckable(True)
        self.auto_clean.setChecked(True)
        layout3 = QFormLayout()
        layout3.addRow("Stable overlap fraction:", self.stable_overlap_fraction)
        layout3.addRow("Max defect size (frames):", self.nframes_defect)
        layout3.addRow("Max delta frame (interpolation):", self.max_delta_frame_interpolation)
        layout3.addRow("Min stable size (frames):", self.nframes_stable)
        self.auto_clean.setLayout(layout3)
        layout2.addRow(self.auto_clean)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        if not self.pipeline_layout:
            layout2 = QVBoxLayout()
            layout2.addWidget(QLabel("Input image:"))
            layout2.addWidget(self.input_image)
            self.display_results.setLayout(layout2)
            layout.addWidget(self.display_results)
            layout.addWidget(self.submit_button, alignment=Qt.AlignCenter)

        self.setLayout(layout)

        self.logger = logging.getLogger(__name__)

        self.update_output_filename_label()

    def mask_list_changed(self):
        if self.mask_list.count() > 1:
            self.display_results.setChecked(False)
        self.display_results.setEnabled(self.mask_list.count() <= 1)

    def nframes_defect_changed(self, value):
        # Set nframes_defect <= max_delta_frame_interpolation <= nframes_stable
        if self.nframes_stable.value() < value:
            self.nframes_stable.setValue(value)
        if self.max_delta_frame_interpolation.value() < value:
            self.max_delta_frame_interpolation.setValue(value)

    def max_delta_frame_interpolation_changed(self, value):
        # Set nframes_defect <= max_delta_frame_interpolation <= nframes_stable
        if self.nframes_stable.value() < value:
            self.nframes_stable.setValue(value)
        if self.nframes_defect.value() > value:
            self.nframes_defect.setValue(value)

    def nframes_stable_changed(self, value):
        # Set nframes_defect <= max_delta_frame_interpolation <= nframes_stable
        if self.nframes_defect.value() > value:
            self.nframes_defect.setValue(value)
        if self.max_delta_frame_interpolation.value() > value:
            self.max_delta_frame_interpolation.setValue(value)

    def update_output_filename_label(self):
        if self.pipeline_layout:
            output_path = "<output folder>"
        elif self.use_input_folder.isChecked():
            output_path = "<input folder>"
        else:
            output_path = os.path.abspath(self.output_folder.text())

        self.output_filename_label1.setText(os.path.normpath(os.path.join(output_path, "<input basename>" + self.output_suffix + self.output_user_suffix.text() + ".ome.tif")))
        self.output_filename_label2.setText(os.path.normpath(os.path.join(output_path, "<input basename>" + self.output_suffix + self.output_user_suffix.text() + ".graphmlz")))

    def get_widgets_state(self):
        widgets_state = {
            'mask_list': self.mask_list.get_file_list(),
            'use_input_folder': self.use_input_folder.isChecked(),
            'use_custom_folder': self.use_custom_folder.isChecked(),
            'output_folder': self.output_folder.text(),
            'output_user_suffix': self.output_user_suffix.text(),
            'min_area': self.min_area.value(),
            'max_delta_frame': self.max_delta_frame.value(),
            'min_overlap_fraction': self.min_overlap_fraction.value(),
            'auto_clean': self.auto_clean.isChecked(),
            'stable_overlap_fraction': self.stable_overlap_fraction.value(),
            'nframes_defect': self.nframes_defect.value(),
            'max_delta_frame_interpolation': self.max_delta_frame_interpolation.value(),
            'nframes_stable': self.nframes_stable.value(),
            'input_image': self.input_image.text(),
            'display_results': self.display_results.isChecked()}
        return widgets_state

    def set_widgets_state(self, widgets_state):
        self.mask_list.set_file_list(widgets_state['mask_list'])
        self.use_input_folder.setChecked(widgets_state['use_input_folder'])
        self.use_custom_folder.setChecked(widgets_state['use_custom_folder'])
        self.output_folder.setText(widgets_state['output_folder'])
        self.output_user_suffix.setText(widgets_state['output_user_suffix'])
        self.min_area.setValue(widgets_state['min_area'])
        self.max_delta_frame.setValue(widgets_state['max_delta_frame'])
        self.min_overlap_fraction.setValue(widgets_state['min_overlap_fraction'])
        self.auto_clean.setChecked(widgets_state['auto_clean'])
        self.stable_overlap_fraction.setValue(widgets_state['stable_overlap_fraction'])
        self.nframes_defect.setValue(widgets_state['nframes_defect'])
        self.max_delta_frame_interpolation.setValue(widgets_state['max_delta_frame_interpolation'])
        self.nframes_stable.setValue(widgets_state['nframes_stable'])
        self.input_image.setText(widgets_state['input_image'])
        self.display_results.setChecked(widgets_state['display_results'])

    def submit(self):
        """
        Retrieve the input parameters
        Process the image in f.main()
        """
        def check_inputs(image_path, mask_paths, output_paths, output_basenames):
            if image_path != '' and not os.path.isfile(image_path):
                self.logger.error('Image: not a valid file')
                self.input_image.setFocus()
                return False
            if len(mask_paths) == 0:
                self.logger.error('Segmentation mask missing')
                return False
            for path in mask_paths:
                if not os.path.isfile(path):
                    self.logger.error('Segmentation mask not found: %s', path)
                    return False
            if self.output_folder.text() == '' and not self.use_input_folder.isChecked():
                self.logger.error('Output folder missing')
                self.output_folder.setFocus()
                return False
            output_files = [os.path.join(d, f) for d, f in zip(output_paths, output_basenames)]
            duplicates = [x for x, y in zip(mask_paths, output_files) if output_files.count(y) > 1]
            if len(duplicates) > 0:
                self.logger.error('More than one input file will output to the same file (output files will be overwritten).\nEither use input mask folder as output folder or avoid processing masks from different input folders.\nProblematic input files:\n%s', '\n'.join(duplicates[:4] + (['...'] if len(duplicates) > 4 else [])))
                return False
            return True

        if self.input_image.isEnabled():
            image_path = self.input_image.text()
        else:
            image_path = ""
        mask_paths = self.mask_list.get_file_list()
        user_suffix = self.output_user_suffix.text()
        output_basenames = [gf.splitext(os.path.basename(path))[0] + self.output_suffix + user_suffix for path in mask_paths]
        if self.use_input_folder.isChecked():
            output_paths = [os.path.dirname(path) for path in mask_paths]
        else:
            output_paths = [self.output_folder.text() for path in mask_paths]

        if not check_inputs(image_path, mask_paths, output_paths, output_basenames):
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
        for mask_path, output_path, output_basename in zip(mask_paths, output_paths, output_basenames):
            self.logger.info("Cell tracking (image %s, mask %s)", image_path, mask_path)
            QApplication.setOverrideCursor(QCursor(Qt.BusyCursor))
            QApplication.processEvents()
            try:
                f.main(image_path, mask_path, output_path=output_path,
                       output_basename=output_basename,
                       min_area=self.min_area.value(),
                       max_delta_frame=self.max_delta_frame.value(),
                       min_overlap_fraction=self.min_overlap_fraction.value()/100.0,
                       clean=self.auto_clean.isChecked(),
                       max_delta_frame_interpolation=self.max_delta_frame_interpolation.value(),
                       nframes_defect=self.nframes_defect.value(),
                       nframes_stable=self.nframes_stable.value(),
                       stable_overlap_fraction=self.stable_overlap_fraction.value()/100.0,
                       display_results=self.display_results.isChecked())
                status.append("Success")
                error_messages.append(None)
            except Exception as e:
                status.append("Failed")
                error_messages.append(str(e))
                self.logger.exception('Tracking failed')
            QApplication.restoreOverrideCursor()

        if any(s != 'Success' for s in status):
            msg = gf.StatusTableDialog('Warning', status, error_messages, mask_paths)
            msg.exec_()

        # re-enable messagebox error handler
        if messagebox_error_handler is not None:
            logging.getLogger().addHandler(messagebox_error_handler)

        self.logger.info("Done")
