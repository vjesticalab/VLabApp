import os
import logging
import re
from PyQt5.QtWidgets import QFileDialog, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QGroupBox, QRadioButton, QApplication, QSpinBox, QFormLayout, QAbstractItemView, QLineEdit
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCursor
from modules.cell_tracking_module import cell_tracking_functions as f
from general import general_functions as gf


class CellTracking(QWidget):
    def __init__(self):
        super().__init__()

        label_documentation=QLabel()
        label_documentation.setOpenExternalLinks(True)
        label_documentation.setText('<a href="file://'+os.path.join(os.path.dirname(__file__),"doc","METHODS.html")+'">Methods</a>')

        self.imagetypes = ['.nd2', '.tif', '.tiff']

        self.mask_filter_name = QLineEdit('_mask',placeholderText='e.g.: _mask')
        self.mask_filter_name.setToolTip('Accept only filenames containing this text')
        self.mask_filter_name.textChanged.connect(self.mask_filter_name_changed)
        self.mask_filter_type = QLineEdit(' '.join(self.imagetypes),placeholderText='e.g.: .nd2 .tif .tiff')
        self.mask_filter_type.setToolTip('Space separated list of accepted file extensions.')
        self.mask_filter_type.textChanged.connect(self.mask_filter_type_changed)
        self.mask_list = gf.DropFilesListWidget(filetypes=self.mask_filter_type.text().split(),filenames_filter=self.mask_filter_name.text())
        self.mask_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.mask_list.model().rowsInserted.connect(self.mask_list_changed)
        self.mask_list.model().rowsRemoved.connect(self.mask_list_changed)
        self.add_mask_button = QPushButton("Add masks", self)
        self.add_mask_button.clicked.connect(self.add_mask)
        self.add_folder_button = QPushButton("Add folder", self)
        self.add_folder_button.clicked.connect(self.add_folder)
        self.remove_button = QPushButton("Remove selected", self)
        self.remove_button.clicked.connect(self.remove)

        self.use_input_folder = QRadioButton("Use input mask folder (cell_tracking sub-folder)")
        self.use_input_folder.setChecked(True)
        self.use_custom_folder = QRadioButton("Use custom folder:")
        self.use_custom_folder.setChecked(False)
        self.output_folder = gf.DropFolderLineEdit()
        browse_button2 = QPushButton("Browse", self)
        browse_button2.clicked.connect(self.browse_output)
        self.output_folder.setEnabled(self.use_custom_folder.isChecked())
        browse_button2.setEnabled(self.use_custom_folder.isChecked())
        self.use_custom_folder.toggled.connect(self.output_folder.setEnabled)
        self.use_custom_folder.toggled.connect(browse_button2.setEnabled)

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
        self.display_results.setChecked(True)

        self.input_image = gf.DropFileLineEdit(filetypes=self.imagetypes)
        browse_button1 = QPushButton("Browse", self)
        browse_button1.clicked.connect(self.add_image)

        self.submit_button = QPushButton("Submit", self)
        self.submit_button.clicked.connect(self.submit)

        layout = QVBoxLayout()
        groupbox = QGroupBox("Documentation")
        layout2 = QVBoxLayout()
        layout2.addWidget(label_documentation)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        groupbox = QGroupBox('Segmentation masks to process')
        layout2 = QVBoxLayout()
        layout2.addWidget(self.mask_list)
        layout3 = QHBoxLayout()
        layout3.addWidget(self.add_mask_button)
        layout3.addWidget(self.add_folder_button)
        layout3.addWidget(self.remove_button)
        layout2.addLayout(layout3)
        layout3 = QHBoxLayout()
        #layout3.addWidget(QLabel("Filters: "))
        layout4 = QFormLayout()
        layout4.addRow("Filter file names:",self.mask_filter_name)
        layout3.addLayout(layout4)
        layout4 = QFormLayout()
        layout4.addRow("file types:",self.mask_filter_type)
        layout3.addLayout(layout4)
        layout2.addLayout(layout3)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        groupbox = QGroupBox("Output folder")
        layout2 = QVBoxLayout()
        layout2.addWidget(self.use_input_folder)
        layout2.addWidget(self.use_custom_folder)
        layout3 = QHBoxLayout()
        layout3.addWidget(self.output_folder)
        layout3.addWidget(browse_button2, alignment=Qt.AlignCenter)
        layout2.addLayout(layout3)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
        groupbox = QGroupBox("Options")
        layout2 = QFormLayout()
        layout2.addRow(QLabel("Cell tracking graph:"))
        layout2.addRow("Min area:", self.min_area)
        layout2.addRow("Max delta frame:", self.max_delta_frame)
        layout2.addRow("Min overlap fraction:", self.min_overlap_fraction)
        self.auto_clean = QGroupBox("Automatic cleaning:")
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

        layout2 = QVBoxLayout()
        layout2.addWidget(QLabel("Input image:"))
        layout3 = QHBoxLayout()
        layout3.addWidget(self.input_image)
        layout3.addWidget(browse_button1, alignment=Qt.AlignCenter)
        layout2.addLayout(layout3)
        self.display_results.setLayout(layout2)
        layout.addWidget(self.display_results)

        layout.addWidget(self.submit_button, alignment=Qt.AlignCenter)
        self.setLayout(layout)

        self.logger = logging.getLogger(__name__)

    def mask_filter_name_changed(self):
        self.mask_list.filenames_filter = self.mask_filter_name.text()

    def mask_filter_type_changed(self):
        self.mask_list.filetypes = self.mask_filter_type.text().split()

    def mask_list_changed(self):
        if self.mask_list.count() > 1:
            self.display_results.setChecked(False)
        self.display_results.setEnabled(self.mask_list.count() <= 1)

    def add_mask(self):
        type_list = ['*'+x for x in self.mask_filter_type.text().split()]
        if len(type_list) == 0:
            type_list = ['*']
        if self.mask_filter_name.text() != '':
            type_list = ['*'+self.mask_filter_name.text()+x for x in type_list]

        file_paths, _ = QFileDialog.getOpenFileNames(self, 'Select Files', filter='Images ('+' '.join(type_list)+')')
        for file_path in file_paths:
            if self.mask_filter_name.text() in os.path.basename(file_path):
                if file_path and len(self.mask_list.findItems(file_path, Qt.MatchExactly)) == 0:
                    self.mask_list.addItem(file_path)

    def add_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder_path:
            masks = [os.path.join(folder_path, i) for i in os.listdir(folder_path) if os.path.splitext(i)[1] in self.mask_filter_type.text().split() and self.mask_filter_name.text() in i]
            self.mask_list.addItems([i for i in masks if len(self.mask_list.findItems(i, Qt.MatchExactly)) == 0])

    def remove(self):
        for item in self.mask_list.selectedItems():
            self.mask_list.takeItem(self.mask_list.row(item))


    def browse_output(self):
        # Browse folders in order to choose the output one
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        self.output_folder.setText(folder_path)

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

    def add_image(self):
        # Add the selected image as input
        file_path, _ = QFileDialog.getOpenFileName(self, 'Select Files', filter='Images ('+' '.join(['*'+x for x in self.imagetypes])+')')
        self.input_image.setText(file_path)

    def submit(self):
        """
        Retrieve the input parameters
        Process the image in f.main()
        """
        def check_inputs(image_path, mask_paths):
            if image_path != '' and not os.path.isfile(image_path):
                self.logger.error('Image: not a valid file')
                self.input_image.setFocus()
                return False
            if len(mask_paths) == 0:
                self.logger.error('Segmentation mask missing')
                self.add_mask_button.setFocus()
                return False
            for path in mask_paths:
                if not os.path.isfile(path):
                    self.logger.error('Segmentation mask not found: %s', path)
                    self.add_mask_button.setFocus()
                    return False
            if self.output_folder.text() == '' and not self.use_input_folder.isChecked():
                self.logger.error('Output folder missing')
                self.output_folder.setFocus()
                return False
            return True

        if self.input_image.isEnabled():
            image_path = self.input_image.text()
        else:
            image_path = ""
        mask_paths = [self.mask_list.item(x).text() for x in range(self.mask_list.count())]

        if not check_inputs(image_path, mask_paths):
            return

        for mask_path in mask_paths:
            if self.use_input_folder.isChecked():
                output_path = os.path.join(os.path.dirname(mask_path), 'cell_tracking')
            else:
                output_path = self.output_folder.text()
            self.logger.info("Cell tracking (image %s, mask %s)", image_path, mask_path)
            QApplication.setOverrideCursor(QCursor(Qt.BusyCursor))
            QApplication.processEvents()

            mask_basename, mask_extension=os.path.splitext(os.path.basename(mask_path))
            output_basename=re.sub("_masks{0,1}$","",mask_basename)
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
            except Exception as e:
                self.logger.error('Tracking failed. %s', str(e))

            QApplication.restoreOverrideCursor()

        self.logger.info("Done")
