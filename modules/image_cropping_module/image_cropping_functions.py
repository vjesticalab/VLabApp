import os
import time
import logging
from platform import python_version, platform
import numpy as np
import napari
import re
from general import general_functions as gf
from bioio.writers import OmeTiffWriter
from bioio import PhysicalPixelSizes
from ome_types.model import CommentAnnotation
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox, QLabel, QSpinBox, QPushButton, QScrollArea, QMessageBox, QFileDialog
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCursor
from superqt import QRangeSlider
from version import __version__ as vlabapp_version


def remove_all_log_handlers():
    # remove all handlers for this module
    while len(logging.getLogger(__name__).handlers) > 0:
        logging.getLogger(__name__).removeHandler(logging.getLogger(__name__).handlers[0])


class ImageCroppingWidget(QWidget):
    """
    A widget to use inside napari
    """

    def __init__(self, image, crop_T, crop_C, crop_Z, crop_Y, crop_X, T_range, C_range, Z_range, Y_range, X_range, viewer, output_path, output_basename):
        super().__init__()
        self.logger = logging.getLogger(__name__)

        self.logger = logging.getLogger(__name__)

        layout = QVBoxLayout()

        self.image = image
        self.viewer = viewer
        self.output_path = output_path
        self.output_basename = output_basename

        # load input metadata
        self.image_metadata = []
        if self.image.ome_metadata:
            for x in self.image.ome_metadata.structured_annotations:
                if isinstance(x, CommentAnnotation) and x.namespace == "VLabApp":
                    if len(self.image_metadata) == 0:
                        self.image_metadata.append("Metadata for " + self.image.path + ":\n" + x.value)
                    else:
                        self.image_metadata.append(x.value)

        self.image_modified = True

        # To allow saving mask before closing (__del__ is called too late)
        # TODO: replace by proper napari close event once implemented (https://forum.image.sc/t/handle-of-close-event-in-napari/61039)
        self.viewer.window._qt_window.destroyed.connect(self.on_viewer_close)

        groupbox = QGroupBox('Image cropping')
        layout2 = QVBoxLayout()
        help_label = QLabel('Removed regions are shown in red.')
        help_label.setWordWrap(True)
        help_label.setMinimumWidth(10)
        layout2.addWidget(help_label)

        self.crop_T = QGroupBox('Crop T axis:')
        self.crop_T.setCheckable(True)
        self.crop_T.setChecked(crop_T)
        self.crop_T.toggled.connect(self.update_cropped_image_layer)
        self.crop_T_min = QSpinBox()
        self.crop_T_min.setMinimum(0)
        self.crop_T_min.setMaximum(T_range[1])
        self.crop_T_min.setValue(T_range[0])
        self.crop_T_min.valueChanged.connect(self.crop_T_min_changed)
        self.crop_T_min.valueChanged.connect(self.update_cropped_image_layer)
        self.crop_T_max = QSpinBox()
        self.crop_T_max.setMinimum(T_range[0])
        self.crop_T_max.setMaximum(self.image.sizes['T']-1)
        self.crop_T_max.setValue(T_range[1])
        self.crop_T_max.valueChanged.connect(self.crop_T_max_changed)
        self.crop_T_max.valueChanged.connect(self.update_cropped_image_layer)
        self.crop_T_range = QRangeSlider(Qt.Orientation.Horizontal)
        self.crop_T_range.setMinimum(0)
        self.crop_T_range.setMaximum(self.image.sizes['T']-1)
        self.crop_T_range.setValue(T_range)
        self.crop_T_range.valueChanged.connect(self.crop_T_range_changed)
        layout3 = QVBoxLayout()
        layout4 = QHBoxLayout()
        layout5 = QFormLayout()
        layout5.addRow("From:", self.crop_T_min)
        layout4.addLayout(layout5)
        layout4.addStretch()
        layout5 = QFormLayout()
        layout5.addRow("To:", self.crop_T_max)
        layout4.addLayout(layout5)
        layout3.addLayout(layout4)
        layout3.addWidget(self.crop_T_range)
        self.crop_T.setLayout(layout3)
        layout2.addWidget(self.crop_T)

        self.crop_C = QGroupBox('Crop C axis:')
        self.crop_C.setCheckable(True)
        self.crop_C.setChecked(crop_C)
        self.crop_C.toggled.connect(self.update_cropped_image_layer)
        self.crop_C_min = QSpinBox()
        self.crop_C_min.setMinimum(0)
        self.crop_C_min.setMaximum(C_range[1])
        self.crop_C_min.setValue(C_range[0])
        self.crop_C_min.valueChanged.connect(self.crop_C_min_changed)
        self.crop_C_min.valueChanged.connect(self.update_cropped_image_layer)
        self.crop_C_max = QSpinBox()
        self.crop_C_max.setMinimum(C_range[0])
        self.crop_C_max.setMaximum(self.image.sizes['C']-1)
        self.crop_C_max.setValue(C_range[1])
        self.crop_C_max.valueChanged.connect(self.crop_C_max_changed)
        self.crop_C_max.valueChanged.connect(self.update_cropped_image_layer)
        self.crop_C_range = QRangeSlider(Qt.Orientation.Horizontal)
        self.crop_C_range.setMinimum(0)
        self.crop_C_range.setMaximum(self.image.sizes['C']-1)
        self.crop_C_range.setValue(C_range)
        self.crop_C_range.valueChanged.connect(self.crop_C_range_changed)
        layout3 = QVBoxLayout()
        layout4 = QHBoxLayout()
        layout5 = QFormLayout()
        layout5.addRow("From:", self.crop_C_min)
        layout4.addLayout(layout5)
        layout4.addStretch()
        layout5 = QFormLayout()
        layout5.addRow("To:", self.crop_C_max)
        layout4.addLayout(layout5)
        layout3.addLayout(layout4)
        layout3.addWidget(self.crop_C_range)
        self.crop_C.setLayout(layout3)
        layout2.addWidget(self.crop_C)

        self.crop_Z = QGroupBox('Crop Z axis:')
        self.crop_Z.setCheckable(True)
        self.crop_Z.setChecked(crop_Z)
        self.crop_Z.toggled.connect(self.update_cropped_image_layer)
        self.crop_Z_min = QSpinBox()
        self.crop_Z_min.setMinimum(0)
        self.crop_Z_min.setMaximum(Z_range[1])
        self.crop_Z_min.setValue(Z_range[0])
        self.crop_Z_min.valueChanged.connect(self.crop_Z_min_changed)
        self.crop_Z_min.valueChanged.connect(self.update_cropped_image_layer)
        self.crop_Z_max = QSpinBox()
        self.crop_Z_max.setMinimum(C_range[0])
        self.crop_Z_max.setMaximum(self.image.sizes['Z']-1)
        self.crop_Z_max.setValue(Z_range[1])
        self.crop_Z_max.valueChanged.connect(self.crop_Z_max_changed)
        self.crop_Z_max.valueChanged.connect(self.update_cropped_image_layer)
        self.crop_Z_range = QRangeSlider(Qt.Orientation.Horizontal)
        self.crop_Z_range.setMinimum(0)
        self.crop_Z_range.setMaximum(self.image.sizes['Z']-1)
        self.crop_Z_range.setValue(Z_range)
        self.crop_Z_range.valueChanged.connect(self.crop_Z_range_changed)
        layout3 = QVBoxLayout()
        layout4 = QHBoxLayout()
        layout5 = QFormLayout()
        layout5.addRow("From:", self.crop_Z_min)
        layout4.addLayout(layout5)
        layout4.addStretch()
        layout5 = QFormLayout()
        layout5.addRow("To:", self.crop_Z_max)
        layout4.addLayout(layout5)
        layout3.addLayout(layout4)
        layout3.addWidget(self.crop_Z_range)
        self.crop_Z.setLayout(layout3)
        layout2.addWidget(self.crop_Z)

        self.crop_Y = QGroupBox('Crop Y axis:')
        self.crop_Y.setCheckable(True)
        self.crop_Y.setChecked(crop_Y)
        self.crop_Y.toggled.connect(self.update_cropped_image_layer)
        self.crop_Y_min = QSpinBox()
        self.crop_Y_min.setMinimum(0)
        self.crop_Y_min.setMaximum(Y_range[1])
        self.crop_Y_min.setValue(Y_range[0])
        self.crop_Y_min.valueChanged.connect(self.crop_Y_min_changed)
        self.crop_Y_min.valueChanged.connect(self.update_cropped_image_layer)
        self.crop_Y_max = QSpinBox()
        self.crop_Y_max.setMinimum(Y_range[0])
        self.crop_Y_max.setMaximum(self.image.sizes['Y']-1)
        self.crop_Y_max.setValue(Y_range[1])
        self.crop_Y_max.valueChanged.connect(self.crop_Y_max_changed)
        self.crop_Y_max.valueChanged.connect(self.update_cropped_image_layer)
        self.crop_Y_range = QRangeSlider(Qt.Orientation.Horizontal)
        self.crop_Y_range.setMinimum(0)
        self.crop_Y_range.setMaximum(self.image.sizes['Y']-1)
        self.crop_Y_range.setValue(Y_range)
        self.crop_Y_range.valueChanged.connect(self.crop_Y_range_changed)
        layout3 = QVBoxLayout()
        layout4 = QHBoxLayout()
        layout5 = QFormLayout()
        layout5.addRow("From:", self.crop_Y_min)
        layout4.addLayout(layout5)
        layout4.addStretch()
        layout5 = QFormLayout()
        layout5.addRow("To:", self.crop_Y_max)
        layout4.addLayout(layout5)
        layout3.addLayout(layout4)
        layout3.addWidget(self.crop_Y_range)
        self.crop_Y.setLayout(layout3)
        layout2.addWidget(self.crop_Y)

        self.crop_X = QGroupBox('Crop X axis:')
        self.crop_X.setCheckable(True)
        self.crop_X.setChecked(crop_X)
        self.crop_X.toggled.connect(self.update_cropped_image_layer)
        self.crop_X_min = QSpinBox()
        self.crop_X_min.setMinimum(0)
        self.crop_X_min.setMaximum(X_range[1])
        self.crop_X_min.setValue(X_range[0])
        self.crop_X_min.valueChanged.connect(self.crop_X_min_changed)
        self.crop_X_min.valueChanged.connect(self.update_cropped_image_layer)
        self.crop_X_max = QSpinBox()
        self.crop_X_max.setMinimum(X_range[0])
        self.crop_X_max.setMaximum(self.image.sizes['X']-1)
        self.crop_X_max.setValue(X_range[1])
        self.crop_X_max.valueChanged.connect(self.crop_X_max_changed)
        self.crop_X_max.valueChanged.connect(self.update_cropped_image_layer)
        self.crop_X_range = QRangeSlider(Qt.Orientation.Horizontal)
        self.crop_X_range.setMinimum(0)
        self.crop_X_range.setMaximum(self.image.sizes['X']-1)
        self.crop_X_range.setValue(X_range)
        self.crop_X_range.valueChanged.connect(self.crop_X_range_changed)
        layout3 = QVBoxLayout()
        layout4 = QHBoxLayout()
        layout5 = QFormLayout()
        layout5.addRow("From:", self.crop_X_min)
        layout4.addLayout(layout5)
        layout4.addStretch()
        layout5 = QFormLayout()
        layout5.addRow("To:", self.crop_X_max)
        layout4.addLayout(layout5)
        layout3.addLayout(layout4)
        layout3.addWidget(self.crop_X_range)
        self.crop_X.setLayout(layout3)
        layout2.addWidget(self.crop_X)

        button = QPushButton('Load settings from image...')
        button.setToolTip('Click to select a cropped image and to use the cropping settings found in its metadata.')
        button.clicked.connect(self.load_settings_from_image)
        layout2.addWidget(button, alignment=Qt.AlignCenter)

        layout3 = QHBoxLayout()
        # Save button
        self.save_button = QPushButton("Save cropped image")
        self.save_button.clicked.connect(self.save)
        if self.image_modified:
            self.save_button.setStyleSheet("background: darkred;")
        layout3.addWidget(self.save_button)
        # Create a button to quit
        button = QPushButton("Quit")
        button.clicked.connect(self.quit)
        layout3.addWidget(button)
        layout2.addLayout(layout3)

        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        # Add spacer (to avoid filling whole space when the widget is inside a QScrollArea)
        layout.addStretch(1)
        self.setLayout(layout)

    def load_settings_from_image(self):
        file_path, _ = QFileDialog.getOpenFileName(self, 'Select cropped image/mask', directory=os.path.dirname(self.image.path), filter='*'+gf.output_suffixes['image_cropping']+'*.ome.tif')
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
        if value != self.crop_T_range.value()[0]:
            self.crop_T_range.setValue((value, self.crop_T_range.value()[1]))

    def crop_T_max_changed(self, value):
        self.crop_T_min.setMaximum(value)
        if value != self.crop_T_range.value()[1]:
            self.crop_T_range.setValue((self.crop_T_range.value()[0], value))

    def crop_T_range_changed(self, value):
        self.crop_T_min.setMaximum(value[1])
        self.crop_T_max.setMinimum(value[0])
        self.crop_T_min.setValue(value[0])
        self.crop_T_max.setValue(value[1])

    def crop_C_min_changed(self, value):
        self.crop_C_max.setMinimum(value)
        if value != self.crop_C_range.value()[0]:
            self.crop_C_range.setValue((value, self.crop_C_range.value()[1]))

    def crop_C_max_changed(self, value):
        self.crop_C_min.setMaximum(value)
        if value != self.crop_C_range.value()[1]:
            self.crop_C_range.setValue((self.crop_C_range.value()[0], value))

    def crop_C_range_changed(self, value):
        self.crop_C_min.setMaximum(value[1])
        self.crop_C_max.setMinimum(value[0])
        self.crop_C_min.setValue(value[0])
        self.crop_C_max.setValue(value[1])

    def crop_Z_min_changed(self, value):
        self.crop_Z_max.setMinimum(value)
        if value != self.crop_Z_range.value()[0]:
            self.crop_Z_range.setValue((value, self.crop_Z_range.value()[1]))

    def crop_Z_max_changed(self, value):
        self.crop_Z_min.setMaximum(value)
        if value != self.crop_Z_range.value()[1]:
            self.crop_Z_range.setValue((self.crop_Z_range.value()[0], value))

    def crop_Z_range_changed(self, value):
        self.crop_Z_min.setMaximum(value[1])
        self.crop_Z_max.setMinimum(value[0])
        self.crop_Z_min.setValue(value[0])
        self.crop_Z_max.setValue(value[1])

    def crop_Y_min_changed(self, value):
        self.crop_Y_max.setMinimum(value)
        if value != self.crop_Y_range.value()[0]:
            self.crop_Y_range.setValue((value, self.crop_Y_range.value()[1]))

    def crop_Y_max_changed(self, value):
        self.crop_Y_min.setMaximum(value)
        if value != self.crop_Y_range.value()[1]:
            self.crop_Y_range.setValue((self.crop_Y_range.value()[0], value))

    def crop_Y_range_changed(self, value):
        self.crop_Y_min.setMaximum(value[1])
        self.crop_Y_max.setMinimum(value[0])
        self.crop_Y_min.setValue(value[0])
        self.crop_Y_max.setValue(value[1])

    def crop_X_min_changed(self, value):
        self.crop_X_max.setMinimum(value)
        if value != self.crop_X_range.value()[0]:
            self.crop_X_range.setValue((value, self.crop_X_range.value()[1]))

    def crop_X_max_changed(self, value):
        self.crop_X_min.setMaximum(value)
        if value != self.crop_X_range.value()[1]:
            self.crop_X_range.setValue((self.crop_X_range.value()[0], value))

    def crop_X_range_changed(self, value):
        self.crop_X_min.setMaximum(value[1])
        self.crop_X_max.setMinimum(value[0])
        self.crop_X_min.setValue(value[0])
        self.crop_X_max.setValue(value[1])

    def update_cropped_image_layer(self):
        self.image_modified = True
        self.save_button.setStyleSheet("background: darkred;")
        if self.crop_T.isChecked():
            T_range = self.crop_T_range.value()
            # Logging with DEBUG level is ignored by BufferedHandler (and will not appear in logfile/metadata)
            self.logger.debug("Cropping T axis: from %s to %s", T_range[0], T_range[1])
        else:
            T_range = (0, self.image.sizes['T']-1)
        if self.crop_C.isChecked():
            C_range = self.crop_C_range.value()
            # Logging with DEBUG level is ignored by BufferedHandler (and will not appear in logfile/metadata)
            self.logger.debug("Cropping C axis: from %s to %s", C_range[0], C_range[1])
        else:
            C_range = (0, self.image.sizes['C']-1)
        if self.crop_Z.isChecked():
            Z_range = self.crop_Z_range.value()
            # Logging with DEBUG level is ignored by BufferedHandler (and will not appear in logfile/metadata)
            self.logger.debug("Cropping Z axis: from %s to %s", Z_range[0], Z_range[1])
        else:
            Z_range = (0, self.image.sizes['Z']-1)
        if self.crop_Y.isChecked():
            Y_range = self.crop_Y_range.value()
            # Logging with DEBUG level is ignored by BufferedHandler (and will not appear in logfile/metadata)
            self.logger.debug("Cropping Y axis: from %s to %s", Y_range[0], Y_range[1])
        else:
            Y_range = (0, self.image.sizes['Y']-1)
        if self.crop_X.isChecked():
            X_range = self.crop_X_range.value()
            # Logging with DEBUG level is ignored by BufferedHandler (and will not appear in logfile/metadata)
            self.logger.debug("Cropping X axis: from %s to %s", X_range[0], X_range[1])
        else:
            X_range = (0, self.image.sizes['X']-1)

        self.viewer.layers['Cropped image'].data = self.image.image[:,
                                                                    T_range[0]:(T_range[1]+1),
                                                                    C_range[0]:(C_range[1]+1),
                                                                    Z_range[0]:(Z_range[1]+1),
                                                                    Y_range[0]:(Y_range[1]+1),
                                                                    X_range[0]:(X_range[1]+1)]
        self.viewer.layers['Cropped image'].translate = (0, T_range[0], C_range[0], Z_range[0], Y_range[0], X_range[0])
        self.viewer.layers['Cropped image'].editable = False
        self.viewer.layers['Cropped image'].refresh()

    def save(self, closing=False):
        # Set cursor to BusyCursor
        napari.qt.get_qapp().setOverrideCursor(QCursor(Qt.BusyCursor))
        napari.qt.get_qapp().processEvents()

        if not any([self.crop_T.isChecked(),
                    self.crop_C.isChecked(),
                    self.crop_Z.isChecked(),
                    self.crop_Y.isChecked(),
                    self.crop_X.isChecked()]):
            # Restore cursor
            napari.qt.get_qapp().restoreOverrideCursor()
            QMessageBox.warning(self, 'Warning', 'File not saved.\nPlease select at least one axis to crop.', buttons=QMessageBox.Ok)
            return

        ct = time.time_ns()
        asctime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ct/1e9))
        asctime += f',{(ct % 1000000000) // 1000000:03d}'
        log_messages = buffered_handler.get_messages()
        if self.crop_T.isChecked():
            T_range = self.crop_T_range.value()
            log_messages += f"{asctime} (VLabApp - image cropping module) [INFO] Cropping T axis: from {T_range[0]} to {T_range[1]}\n"
            self.logger.debug("Cropping T axis: from %s to %s", T_range[0], T_range[1])
        else:
            T_range = (0, self.image.sizes['T']-1)
        if self.crop_C.isChecked():
            C_range = self.crop_C_range.value()
            log_messages += f"{asctime} (VLabApp - image cropping module) [INFO] Cropping C axis: from {C_range[0]} to {C_range[1]}\n"
            self.logger.debug("Cropping C axis: from %s to %s", C_range[0], C_range[1])
        else:
            C_range = (0, self.image.sizes['C']-1)
        if self.crop_Z.isChecked():
            Z_range = self.crop_Z_range.value()
            log_messages += f"{asctime} (VLabApp - image cropping module) [INFO] Cropping Z axis: from {Z_range[0]} to {Z_range[1]}\n"
            self.logger.debug("Cropping Z axis: from %s to %s", Z_range[0], Z_range[1])
        else:
            Z_range = (0, self.image.sizes['Z']-1)
        if self.crop_Y.isChecked():
            Y_range = self.crop_Y_range.value()
            log_messages += f"{asctime} (VLabApp - image cropping module) [INFO] Cropping Y axis: from {Y_range[0]} to {Y_range[1]}\n"
            self.logger.debug("Cropping Y axis: from %s to %s", Y_range[0], Y_range[1])
        else:
            Y_range = (0, self.image.sizes['Y']-1)
        if self.crop_X.isChecked():
            X_range = self.crop_X_range.value()
            log_messages += f"{asctime} (VLabApp - image cropping module) [INFO] Cropping X axis: from {X_range[0]} to {X_range[1]}\n"
            self.logger.debug("Cropping X axis: from %s to %s", X_range[0], X_range[1])
        else:
            X_range = (0, self.image.sizes['X']-1)

        output_name = os.path.join(self.output_path, self.output_basename+".ome.tif")
        log_messages += f"{asctime} (VLabApp - image cropping module) [INFO] Saving cropped image to {output_name}\n"
        self.logger.debug("Saving cropped image to %s", output_name)
        cropped_image = self.image.image[:,
                                         T_range[0]:(T_range[1]+1),
                                         C_range[0]:(C_range[1]+1),
                                         Z_range[0]:(Z_range[1]+1),
                                         Y_range[0]:(Y_range[1]+1),
                                         X_range[0]:(X_range[1]+1)]
        ome_metadata = OmeTiffWriter.build_ome(data_shapes=[cropped_image[0, :, :, :, :, :].shape],
                                               data_types=[cropped_image[0, :, :, :, :, :].dtype],
                                               dimension_order=["TCZYX"],
                                               channel_names=[self.image.channel_names[C_range[0]:(C_range[1]+1)]],
                                               physical_pixel_sizes=[PhysicalPixelSizes(X=self.image.physical_pixel_sizes[0], Y=self.image.physical_pixel_sizes[1], Z=self.image.physical_pixel_sizes[2])])
        ome_metadata.structured_annotations.append(CommentAnnotation(value=log_messages, namespace="VLabApp"))
        for x in self.image_metadata:
            ome_metadata.structured_annotations.append(CommentAnnotation(value=x, namespace="VLabApp"))
        OmeTiffWriter.save(cropped_image[0, :, :, :, :, :], output_name, ome_xml=ome_metadata)
        # create logfile
        logfile = os.path.join(self.output_path, self.output_basename+".log")
        with open(logfile, 'w') as f:
            f.write(log_messages)

        if not closing:
            self.image_modified = False
            self.save_button.setStyleSheet("")

        self.logger.debug("Done")
        # Restore cursor
        napari.qt.get_qapp().restoreOverrideCursor()

        QMessageBox.information(self, 'Files saved', 'File saved to\n' + output_name)

    def quit(self):
        self.viewer.close()

    def on_viewer_close(self):
        # Restore cursor
        napari.qt.get_qapp().restoreOverrideCursor()
        if self.image_modified:
            save = QMessageBox.question(self, 'Save changes', "Save cropped image before closing?", QMessageBox.Yes | QMessageBox.No)
            if save == QMessageBox.Yes:
                self.save(closing=True)
        remove_all_log_handlers()

    def __del__(self):
        remove_all_log_handlers()


def main(image_path, output_path, output_basename, T_range, C_range, Z_range, Y_range, X_range, display_results=False):
    """
    Load image or mask (`image_path`), crop and
    save into `output_path` directory using filename `output_basename`.ome.tif.

    Parameters
    ----------
    image_path: str
        input image or mask path. Should be ome-tiff or nd2 image.
    output_path: str
        output directory.
    output_basename: str
        output basename. Output file will be saved as `output_path`/`output_basename`.ome.tif.
    T_range: (int, int) or None
        cropping range (Tmin, Tmax) for T axis (keep Tmin<=T<=Tmax) or None (do not crop T axis).
    C_range: (int, int) or None
        cropping range (Cmin, Cmax) for C axis (keep Cmin<=C<=Cmax) or None (do not crop C axis).
    Z_range: (int, int) or None
        cropping range (Zmin, Zmax) for Z axis (keep Zmin<=Z<=Zmax) or None (do not crop Z axis).
    Y_range: (int, int) or None
        cropping range (Ymin, Ymax) for Y axis (keep Ymin<=Y<=Ymax) or None (do not crop Y axis).
    X_range: (int, int) or None
        cropping range (Xmin, Xmax) for X axis (keep Xmin<=X<=Xmax) or None (do not crop X axis).
    display_results: bool, default False
        display image or mask in napari to perform interactive cropping.
    """

    try:
        # Setup logging to file in output_path
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.DEBUG)
        logger.info('IMAGE CROPPING MODULE')
        if not os.path.isdir(output_path):
            logger.debug('creating: %s', output_path)
            os.makedirs(output_path)

        # Log to file:
        # Output filename depends on the cropping range. When using
        # display_results==True, the final cropping range is only
        # known when saving the cropped image. Therefore the logfile
        # is only created at the end, using the content of the
        # BufferedHandler.

        # Log to memory
        global buffered_handler
        buffered_handler = gf.BufferedHandler()
        buffered_handler.setFormatter(logging.Formatter('%(asctime)s (VLabApp - image cropping module) [%(levelname)s] %(message)s'))
        buffered_handler.setLevel(logging.INFO)
        logger.addHandler(buffered_handler)

        logger.info('System info:')
        logger.info('- platform: %s', platform())
        logger.info('- python version: %s', python_version())
        logger.info('- VLabApp version: %s', vlabapp_version)
        logger.info('- numpy version: %s', np.__version__)
        if display_results:
            logger.info("- napari version: %s", napari.__version__)

        logger.info('Input image/mask path: %s', image_path)

        # Load image
        logger.debug("loading %s", image_path)
        try:
            image = gf.Image(image_path)
            image.imread()
        except Exception:
            logging.getLogger(__name__).exception('Error loading image %s', image_path)
            # Remove all handlers for this module
            remove_all_log_handlers()
            raise

        # load image metadata
        image_metadata = []
        if image.ome_metadata:
            for x in image.ome_metadata.structured_annotations:
                if isinstance(x, CommentAnnotation) and x.namespace == "VLabApp":
                    if len(image_metadata) == 0:
                        image_metadata.append("Metadata for "+image.path+":\n"+x.value)
                    else:
                        image_metadata.append(x.value)

        # Check 'F' axis has size 1
        if image.sizes['F'] != 1:
            logger.error('Image %s has a F axis with size > 1', str(image_path))
            # Remove all handlers for this module
            remove_all_log_handlers()
            raise TypeError(f"Image {image_path} has a F axis with size > 1")

        # adjust range to image size
        crop_T = T_range is not None
        crop_C = C_range is not None
        crop_Z = Z_range is not None
        crop_Y = Y_range is not None
        crop_X = X_range is not None
        if crop_T:
            if T_range[1] < 0 or T_range[0] >= image.sizes['T']:
                logger.error('Invalid T axis cropping range (axis length: %s, cropping range: from %s to %s)', image.sizes['T'], T_range[0], T_range[1])
                # Remove all handlers for this module
                remove_all_log_handlers()
                raise TypeError(f"Invalid cropping range for T axis (axis length: {image.sizes['T']}, cropping range: from {T_range[0]} to {T_range[1]})")
            T_range = (min(T_range[0], image.sizes['T']-1), min(T_range[1], image.sizes['T']-1))
            # Logging with DEBUG level is ignored by BufferedHandler (and will not appear in logfile/metadata)
            logger.debug("Cropping T axis: from %s to %s", T_range[0], T_range[1])
        else:
            T_range = (0, image.sizes['T']-1)
        if crop_C:
            if C_range[1] < 0 or C_range[0] >= image.sizes['C']:
                logger.error('Invalid C axis cropping range (axis length: %s, cropping range: from %s to %s)', image.sizes['C'], C_range[0], C_range[1])
                # Remove all handlers for this module
                remove_all_log_handlers()
                raise TypeError(f"Invalid cropping range for C axis (axis length: {image.sizes['C']}, cropping range: from {C_range[0]} to {C_range[1]})")
            C_range = (min(C_range[0], image.sizes['C']-1), min(C_range[1], image.sizes['C']-1))
            # Logging with DEBUG level is ignored by BufferedHandler (and will not appear in logfile/metadata)
            logger.debug("Cropping C axis: from %s to %s", C_range[0], C_range[1])
        else:
            C_range = (0, image.sizes['C']-1)
        if crop_Z:
            if Z_range[1] < 0 or Z_range[0] >= image.sizes['Z']:
                logger.error('Invalid Z axis cropping range (axis length: %s, cropping range: from %s to %s)', image.sizes['Z'], Z_range[0], Z_range[1])
                # Remove all handlers for this module
                remove_all_log_handlers()
                raise TypeError(f"Invalid cropping range for Z axis (axis length: {image.sizes['Z']}, cropping range: from {Z_range[0]} to {Z_range[1]})")
            Z_range = (min(Z_range[0], image.sizes['Z']-1), min(Z_range[1], image.sizes['Z']-1))
            # Logging with DEBUG level is ignored by BufferedHandler (and will not appear in logfile/metadata)
            logger.debug("Cropping Z axis: from %s to %s", Z_range[0], Z_range[1])
        else:
            Z_range = (0, image.sizes['Z']-1)
        if crop_Y:
            if Y_range[1] < 0 or Y_range[0] >= image.sizes['Y']:
                logger.error('Invalid Y axis cropping range (axis length: %s, cropping range: from %s to %s)', image.sizes['Y'], Y_range[0], Y_range[1])
                # Remove all handlers for this module
                remove_all_log_handlers()
                raise TypeError(f"Invalid cropping range for Y axis (axis length: {image.sizes['Y']}, cropping range: from {Y_range[0]} to {Y_range[1]})")
            Y_range = (min(Y_range[0], image.sizes['Y']-1), min(Y_range[1], image.sizes['Y']-1))
            # Logging with DEBUG level is ignored by BufferedHandler (and will not appear in logfile/metadata)
            logger.debug("Cropping Y axis: from %s to %s", Y_range[0], Y_range[1])
        else:
            Y_range = (0, image.sizes['Y']-1)
        if crop_X:
            if X_range[1] < 0 or X_range[0] >= image.sizes['X']:
                logger.error('Invalid X axis cropping range (axis length: %s, cropping range: from %s to %s)', image.sizes['X'], X_range[0], X_range[1])
                # Remove all handlers for this module
                remove_all_log_handlers()
                raise TypeError(f"Invalid cropping range for X axis (axis length: {image.sizes['X']}, cropping range: from {X_range[0]} to {X_range[1]})")
            X_range = (min(X_range[0], image.sizes['X']-1), min(X_range[1], image.sizes['X']-1))
            # Logging with DEBUG level is ignored by BufferedHandler (and will not appear in logfile/metadata)
            logger.debug("Cropping X axis: from %s to %s", X_range[0], X_range[1])
        else:
            X_range = (0, image.sizes['X']-1)

        # crop image
        cropped_image = image.image
        cropped_image = cropped_image[:,
                                      T_range[0]:(T_range[1]+1),
                                      C_range[0]:(C_range[1]+1),
                                      Z_range[0]:(Z_range[1]+1),
                                      Y_range[0]:(Y_range[1]+1),
                                      X_range[0]:(X_range[1]+1)]

        if display_results:
            # TODO: find a better solution to open a modal napari window.
            global viewer
            viewer = napari.Viewer(show=False, title=image_path)
            viewer.window._qt_window.setWindowModality(Qt.ApplicationModal)
            viewer.show()
            layer1 = viewer.add_image(image.image, name="Input image", opacity=0.5, colormap=napari.utils.Colormap([[1, 0, 0, 1], [1, 0, 0, 1]]))
            layer1.editable = False
            cropped_origin = (0, T_range[0], C_range[0], Z_range[0], Y_range[0], X_range[0])
            layer2 = viewer.add_image(cropped_image, name="Cropped image", translate=cropped_origin, contrast_limits=layer1.contrast_limits)
            layer2.editable = False
            viewer.dims.axis_labels = ('F', 'T', 'C', 'Z', 'Y', 'X')
            # Add CellTrackingWidget to napari
            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setWidget(ImageCroppingWidget(image,
                                                      crop_T,
                                                      crop_C,
                                                      crop_Z,
                                                      crop_Y,
                                                      crop_X,
                                                      T_range,
                                                      C_range,
                                                      Z_range,
                                                      Y_range,
                                                      X_range,
                                                      viewer,
                                                      output_path,
                                                      output_basename))
            viewer.window.add_dock_widget(scroll_area, area='right', name="Image cropping")

        else:
            # Save cropped image (repeat log message with INFO level)
            if crop_T:
                logger.info("Cropping T axis: from %s to %s", T_range[0], T_range[1])
            if crop_C:
                logger.info("Cropping C axis: from %s to %s", C_range[0], C_range[1])
            if crop_Z:
                logger.info("Cropping Z axis: from %s to %s", Z_range[0], Z_range[1])
            if crop_Y:
                logger.info("Cropping Y axis: from %s to %s", Y_range[0], Y_range[1])
            if crop_X:
                logger.info("Cropping X axis: from %s to %s", X_range[0], X_range[1])
            output_name = os.path.join(output_path, output_basename+".ome.tif")
            logger.info("Saving cropped image to %s", output_name)
            ome_metadata = OmeTiffWriter.build_ome(data_shapes=[cropped_image[0, :, :, :, :, :].shape],
                                                   data_types=[cropped_image[0, :, :, :, :, :].dtype],
                                                   dimension_order=["TCZYX"],
                                                   channel_names=[image.channel_names[C_range[0]:(C_range[1]+1)]],
                                                   physical_pixel_sizes=[PhysicalPixelSizes(X=image.physical_pixel_sizes[0], Y=image.physical_pixel_sizes[1], Z=image.physical_pixel_sizes[2])])
            ome_metadata.structured_annotations.append(CommentAnnotation(value=buffered_handler.get_messages(), namespace="VLabApp"))
            for x in image_metadata:
                ome_metadata.structured_annotations.append(CommentAnnotation(value=x, namespace="VLabApp"))
            OmeTiffWriter.save(cropped_image[0, :, :, :, :, :], output_name, ome_xml=ome_metadata)
            # create logfile
            logfile = os.path.join(output_path, output_basename+".log")
            with open(logfile, 'w') as f:
                f.write(buffered_handler.get_messages())

        # Remove all handlers for this module
        remove_all_log_handlers()

    except Exception:
        # Remove all handlers for this module
        remove_all_log_handlers()
        if display_results:
            # Restore cursor
            napari.qt.get_qapp().restoreOverrideCursor()
            try:
                # close napari window
                viewer.close()
            except:
                pass
        raise
