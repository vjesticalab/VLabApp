import os
import logging
import napari
import cv2 as cv
import numpy as np
import tifffile
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton, QSpinBox, QScrollArea, QGroupBox, QMessageBox, QRadioButton, QComboBox
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCursor
from aicsimageio.writers import OmeTiffWriter
from aicsimageio.types import PhysicalPixelSizes
from ome_types.model import CommentAnnotation
from platform import python_version, platform
from version import __version__ as vlabapp_version
from general import general_functions as gf


def remove_all_log_handlers():
    # remove all handlers for this module
    while len(logging.getLogger(__name__).handlers) > 0:
        logging.getLogger(__name__).removeHandler(logging.getLogger(__name__).handlers[0])
    # remove all handlers for general.general_functions
    while len(logging.getLogger('general.general_functions').handlers) > 0:
        logging.getLogger('general.general_functions').removeHandler(logging.getLogger('general.general_functions').handlers[0])


def split_regions(mask):
    """
    Split disconnected regions by assigning different mask ids to connected components with same mask id
    Note : 'mask' is modified in-place

    Parameters
    ----------
    mask: ndarray
        a 3D (TYX) 16bit unsigned integer (uint16) numpy array, modified in-place
    """
    logging.getLogger(__name__).debug("Splitting disconnected regions")
    for t in range(mask.shape[0]):
        for n in range(mask[t].max()):
            xmin, ymin, w, h = cv.boundingRect((mask[t] == n+1).astype('uint8'))
            if w > 0 and h > 0:
                nlabels, tmp = cv.connectedComponents((mask[t, (ymin):(ymin+h), (xmin):(xmin+w)] == n+1).astype('uint8'))
                # nlabels: number of labels, including 0 (background)
                if nlabels > 2:
                    logging.getLogger(__name__).debug(" Splitting: frame %s, mask id %s", t, n+1)
                    mask[t, (ymin):(ymin+h), (xmin):(xmin+w)][tmp > 1] = (tmp[tmp > 1]-1)+mask[t].max()


def relabel(mask):
    """
    For each time frame, relabel mask ids using consecutive integer numbers from 1 to number of labels.
    Note : `mask` is modified in-place

    Parameters
    ----------
    mask: ndarray
        a 3D (TYX) 16bit unsigned integer (uint16) numpy array, modified in-place
    """
    # Relabel mask and graph (mask_ids)
    logging.getLogger(__name__).debug("Relabelling mask")
    for t in range(mask.shape[0]):
        mask_ids1 = np.sort(np.unique(mask[t][mask[t]>0]))
        max_mask_ids1 = mask_ids1.max() if len(mask_ids1) > 0 else 0
        map_id = np.repeat(-1, max_mask_ids1+1)
        # Relabel with consecutiv mask_ids
        n_ids = 1
        for mask_id in mask_ids1:
            if mask_id > 0:
                map_id[mask_id] = n_ids
                n_ids += 1
        # Map 0 to 0
        map_id[0] = 0
        # Relabel
        mask[t] = map_id[mask[t]]


def segment_image(image, threshold=20):
    """
    Segment image using a thresholding based method.

    Parameters
    ----------
    image: ndarray
        a 2D (YX) numpy array.
    threshold: int
        threshold used for binary segmentation of cell regions (should be in the interval [0,255])
    """

    # convert to 8 bit
    image = (image*(np.iinfo('uint8').max/(np.iinfo(image.dtype).max))).astype('uint8')

    # adaptive thresholding to identify cell boundaries
    image_boundaries = cv.adaptiveThreshold(image, 255, cv.ADAPTIVE_THRESH_MEAN_C, cv.THRESH_BINARY, 21, 1)

    # Absolute tresholding to identify cells
    _, image_cells = cv.threshold(image, threshold, 255, cv.THRESH_BINARY)

    # Combine the two methods above to identify individual cells
    image = cv.multiply(image_cells, image_boundaries)

    # Dilate/erode approach to fill in holes
    kernel = cv.getStructuringElement(cv.MORPH_ELLIPSE, (4, 4))
    image = cv.morphologyEx(image, cv.MORPH_CROSS, kernel, iterations=1)

    # Extract contours
    contours, _ = cv.findContours(image=image, mode=cv.RETR_EXTERNAL, method=cv.CHAIN_APPROX_NONE)
    # filter out small contours
    contours = [holder for holder in contours if cv.contourArea(holder)>1000]

    # Dilate-Erode individual contours
    mask = np.zeros(image.shape, dtype='uint16')
    image_single_contour = np.zeros(image.shape, dtype='uint16')
    kernel = cv.getStructuringElement(cv.MORPH_ELLIPSE, (3, 3))
    for count_contour, _ in enumerate(contours):
        cv.drawContours(image=image_single_contour, contours=contours, contourIdx=count_contour, color=(count_contour, count_contour, count_contour), thickness=cv.FILLED)
        image_single_contour = cv.morphologyEx(image_single_contour, cv.MORPH_CLOSE, kernel, iterations=10)
        mask = cv.bitwise_or(mask, image_single_contour)
        image_single_contour[image_single_contour!=0] = 0

    return mask


class GroundTruthWidget(QWidget):
    """
    A widget to use inside napari
    """

    def __init__(self, image_BF, image_fluo1, image_fluo2, image_mask, viewer, output_path, output_basename):
        super().__init__()
        self.logger = logging.getLogger(__name__)

        self.logger = logging.getLogger(__name__)

        layout = QVBoxLayout()

        self.image_BF = image_BF
        self.image_fluo1 = image_fluo1
        self.image_fluo2 = image_fluo2
        self.image_mask = image_mask
        self.viewer = viewer
        self.output_path = output_path
        self.output_basename = output_basename

        if 'Mask' in self.viewer.layers:
            # To detect image modifications
            self.mask = self.viewer.layers['Mask'].data[0, :, 0, :, :]
        else:
            self.mask = None

        # load input metadata
        self.image_BF_metadata = []
        if self.image_BF.ome_metadata:
            for x in self.image_BF.ome_metadata.structured_annotations:
                if isinstance(x, CommentAnnotation) and x.namespace == "VLabApp":
                    if len(self.image_BF_metadata) == 0:
                        self.image_BF_metadata.append("Metadata for " + self.image_BF.path + ":\n" + x.value)
                    else:
                        self.image_BF_metadata.append(x.value)
        self.image_fluo1_metadata = []
        if self.image_fluo1 is not None:
            if self.image_fluo1.ome_metadata:
                for x in self.image_fluo1.ome_metadata.structured_annotations:
                    if isinstance(x, CommentAnnotation) and x.namespace == "VLabApp":
                        if len(self.image_fluo1_metadata) == 0:
                            self.image_fluo1_metadata.append("Metadata for " + self.image_fluo1.path + ":\n" + x.value)
                        else:
                            self.image_fluo1_metadata.append(x.value)
        self.image_fluo2_metadata = []
        if self.image_fluo2 is not None:
            if self.image_fluo2.ome_metadata:
                for x in self.image_fluo2.ome_metadata.structured_annotations:
                    if isinstance(x, CommentAnnotation) and x.namespace == "VLabApp":
                        if len(self.image_fluo2_metadata) == 0:
                            self.image_fluo2_metadata.append("Metadata for " + self.image_fluo2.path + ":\n" + x.value)
                        else:
                            self.image_fluo2_metadata.append(x.value)
        self.image_mask_metadata = []
        if self.image_mask is not None:
            if self.image_mask.ome_metadata:
                for x in self.image_mask.ome_metadata.structured_annotations:
                    if isinstance(x, CommentAnnotation) and x.namespace == "VLabApp":
                        if len(self.image_mask_metadata) == 0:
                            self.image_mask_metadata.append("Metadata for " + self.image_mask.path + ":\n" + x.value)
                        else:
                            self.image_mask_metadata.append(x.value)

        if 'Mask' in self.viewer.layers:
            # To detect image modifications
            self.viewer.layers['Mask'].events.paint.connect(self.paint_callback)
            self.mask_modified = True
        else:
            self.mask_modified = False

        # To allow saving mask before closing (__del__ is called too late)
        # TODO: replace by proper napari close event once implemented (https://forum.image.sc/t/handle-of-close-event-in-napari/61039)
        self.viewer.window._qt_window.destroyed.connect(self.on_viewer_close)

        if self.image_fluo1 is not None:
            groupbox = QGroupBox('Segmentation')
            layout2 = QVBoxLayout()
            if self.image_fluo2 is None:
                help_label = QLabel("Perform thresholding based segmentation on the fluorescent image in layer \"Cell marker 1\". Note that the image is normalized to the contrast limits of the layer before performing segmentation.")
            else:
                help_label = QLabel("Perform thresholding based segmentation on the fluorescent images in layers \"Cell marker 1\" and  \"Cell marker 2\". Note that images are normalized to the contrast limits of the layers and merged (mean) before performing segmentation.")
            help_label.setWordWrap(True)
            help_label.setMinimumWidth(10)
            layout2.addWidget(help_label)

            self.threshold = QSpinBox()
            self.threshold.setMinimum(0)
            self.threshold.setMaximum(255)
            self.threshold.setValue(40)
            layout3 = QFormLayout()
            layout3.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
            layout3.addRow('Threshold:', self.threshold)
            layout2.addLayout(layout3)

            button = QPushButton('Segment')
            button.clicked.connect(self.segment)
            layout2.addWidget(button, alignment=Qt.AlignCenter)

            groupbox.setLayout(layout2)
            layout.addWidget(groupbox)

        groupbox = QGroupBox('Edit mask')
        layout2 = QVBoxLayout()
        help_label = QLabel("The mask (layer 'Mask') can be manually edited using tools in the 'layer controls' panel. Press key 'm' to select a new label value.\nNote: when exporting or saving, disconnected regions will get different labels and the mask will be relabelled with consecutive numbers from 1 to the tnumber of labels (per time frame).")
        help_label.setWordWrap(True)
        help_label.setMinimumWidth(10)
        layout2.addWidget(help_label)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        groupbox = QGroupBox('Export')
        layout2 = QFormLayout()
        if self.image_BF.sizes['Z'] > 1:
            help_label = QLabel("Export bright-field image and segmentation mask in a format that can be directly used as a training set by cellpose (one pair of image and mask in tif format per time frame). The Z axis of the bright-field image is projected using the following parameters:")
        else:
            help_label = QLabel("Export bright-field image and segmentation mask in a format that can be directly used as a training set by cellpose (one pair of image and mask in tif format per time frame).")
        help_label.setWordWrap(True)
        help_label.setMinimumWidth(10)
        layout2.addRow(help_label)
        if self.image_BF.sizes['Z'] > 1:
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
            self.projection_mode_around_bestZ_zrange.setMaximum(self.image_BF.sizes['Z']-1)
            self.projection_mode_around_bestZ_zrange.setValue(3)
            # fixed range
            self.projection_mode_fixed = QRadioButton("Fixed range")
            self.projection_mode_fixed.setChecked(False)
            self.projection_mode_fixed.setToolTip('Project all Z sections with Z in the interval [from,to].')
            self.projection_mode_fixed_zmin = QSpinBox()
            self.projection_mode_fixed_zmin.setMinimum(0)
            self.projection_mode_fixed_zmin.setMaximum(self.image_BF.sizes['Z']-1)
            self.projection_mode_fixed_zmin.setValue(4)
            self.projection_mode_fixed_zmin.valueChanged.connect(self.projection_mode_fixed_zmin_changed)
            self.projection_mode_fixed_zmax = QSpinBox()
            self.projection_mode_fixed_zmax.setMinimum(0)
            self.projection_mode_fixed_zmax.setMaximum(self.image_BF.sizes['Z']-1)
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
            # Z-Projection range
            widget = QWidget()
            layout3 = QVBoxLayout()
            layout3.addWidget(self.projection_mode_bestZ)
            layout3.addWidget(self.projection_mode_around_bestZ)
            groupbox3 = QGroupBox()
            groupbox3.setToolTip('Project all Z sections with Z in the interval [bestZ-range,bestZ+range], where bestZ is the Z section with best focus.')
            groupbox3.setVisible(self.projection_mode_around_bestZ.isChecked())
            self.projection_mode_around_bestZ.toggled.connect(groupbox3.setVisible)
            layout4 = QFormLayout()
            layout4.addRow("Range:", self.projection_mode_around_bestZ_zrange)
            groupbox3.setLayout(layout4)
            layout3.addWidget(groupbox3)
            layout3.addWidget(self.projection_mode_fixed)
            groupbox3 = QGroupBox()
            groupbox3.setToolTip('Project all Z sections with Z in the interval [from,to].')
            groupbox3.setVisible(self.projection_mode_fixed.isChecked())
            self.projection_mode_fixed.toggled.connect(groupbox3.setVisible)
            layout4 = QHBoxLayout()
            layout5 = QFormLayout()
            layout5.addRow("From:", self.projection_mode_fixed_zmin)
            layout4.addLayout(layout5)
            layout5 = QFormLayout()
            layout5.addRow("To:", self.projection_mode_fixed_zmax)
            layout4.addLayout(layout5)
            groupbox3.setLayout(layout4)
            layout3.addWidget(groupbox3)
            layout3.addWidget(self.projection_mode_all)
            widget.setLayout(layout3)
            layout2.addRow("Projection range:", widget)
            layout2.addRow("Projection type:", self.projection_type)
            # Z-shift
            help_label = QLabel('Using slightly out-of-focus bright-field images in the training set used to fine-tune a cellpose model can improve the robustness of the resulting model. Out-of-focus images are generated by randomly shifting along the Z axis the Z sections to be projected by a random integer value in the interval [-z_shift,z_shift]  (for each time frame). To generate out-of-focus images, set \"Max Z shift\" below to a non-zero value.\nNote: this option is ignored when projecting all Z sections.')
            help_label.setWordWrap(True)
            help_label.setMinimumWidth(10)
            layout2.addRow(help_label)
            self.zshift_max = QSpinBox()
            self.zshift_max.setMinimum(0)
            self.zshift_max.setMaximum(self.image_BF.sizes['Z']-1)
            self.zshift_max.setValue(0)
            self.zshift_max.setToolTip('.')
            layout2.addRow("Max Z shift:", self.zshift_max)

        self.export_button = QPushButton("Export")
        self.export_button.clicked.connect(self.export)
        layout3 = QHBoxLayout()
        if 'Mask' not in self.viewer.layers:
            self.export_button.setEnabled(False)
        layout3.addWidget(self.export_button, alignment=Qt.AlignCenter)
        layout2.addRow(layout3)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        groupbox = QGroupBox("Save && quit")
        layout2 = QVBoxLayout()
        help_label = QLabel("Save the mask in the same format as masks created with the segmentation module (ome-tif). Saved masks can later be loaded in this module to be manually edited and/or exported to cellpose.")
        help_label.setWordWrap(True)
        help_label.setMinimumWidth(10)
        layout2.addWidget(help_label)
        layout3 = QHBoxLayout()
        # Save button
        self.save_button = QPushButton("Save mask")
        self.save_button.clicked.connect(self.save)
        if 'Mask' not in self.viewer.layers:
            self.save_button.setEnabled(False)
        if self.mask_modified:
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

    def paint_callback(self, event):
        self.logger.info("Manually editing mask")
        self.mask_modified = True
        if 'Mask' in self.viewer.layers:
            self.save_button.setStyleSheet("background: darkred;")

    def projection_mode_fixed_zmin_changed(self, value):
        if self.projection_mode_fixed_zmax.value() < value:
            self.projection_mode_fixed_zmax.setValue(value)

    def projection_mode_fixed_zmax_changed(self, value):
        if self.projection_mode_fixed_zmin.value() > value:
            self.projection_mode_fixed_zmin.setValue(value)

    def get_projection_suffix(self, maxZ, projection_zrange, projection_type):
        if projection_zrange is None:
            output_suffix_reference = 'f'
            output_suffix_range = '0-'+str(maxZ)
            output_suffix_projection_type = projection_type
        elif isinstance(projection_zrange, int):
            output_suffix_reference = 'b'
            output_suffix_range = str(projection_zrange)
            if projection_zrange > 0:
                output_suffix_projection_type = projection_type
            else:
                output_suffix_projection_type = 'none'
        elif isinstance(projection_zrange, tuple) and len(projection_zrange):
            output_suffix_reference = 'f'
            output_suffix_range = str(min(projection_zrange)) + '-' + str(max(projection_zrange))
            if max(projection_zrange) > min(projection_zrange):
                output_suffix_projection_type = projection_type
            else:
                output_suffix_projection_type = 'none'
        else:
            self.logger.error('Invalid projection_zrange: %s', str(projection_zrange))
            raise TypeError(f"Invalid projection_zrange: {projection_zrange}")
        return output_suffix_reference + output_suffix_range + output_suffix_projection_type

    def export(self):
        # Set cursor to BusyCursor
        napari.qt.get_app().setOverrideCursor(QCursor(Qt.BusyCursor))
        napari.qt.get_app().processEvents()

        # Show activity dock & add napari progress bar
        self.viewer.window._status_bar._toggle_activity_dock(True)
        pbr = napari.utils.progress(total=self.image_BF.sizes['T'])

        pbr.set_description('Pre-processing')
        split_regions(self.mask)
        relabel(self.mask)

        # output filenames
        if self.image_BF.sizes['Z'] > 1:
            projection_type = self.projection_type.currentText()
            if self.projection_mode_bestZ.isChecked():
                projection_zrange = 0
            elif self.projection_mode_around_bestZ.isChecked():
                projection_zrange = self.projection_mode_around_bestZ_zrange.value()
            elif self.projection_mode_fixed.isChecked():
                projection_zrange = (self.projection_mode_fixed_zmin.value(), self.projection_mode_fixed_zmax.value())
            elif self.projection_mode_all.isChecked():
                projection_zrange = None
            suffix = gf.output_suffixes['zprojection'] + self.get_projection_suffix(self.image_BF.sizes['Z'], projection_zrange, projection_type)
            output_path = os.path.join(self.output_path, self.output_basename+suffix)
            output_basename = self.output_basename + suffix
        else:
            output_path = os.path.join(self.output_path, self.output_basename)
            output_basename = self.output_basename

        if not os.path.isdir(output_path):
            self.logger.debug("creating: %s", output_path)
            os.makedirs(output_path)

        if self.image_BF.sizes['Z'] > 1:
            # Z-projection
            self.logger.info('Bright-field image: performing Z-projection')
            if self.zshift_max.value() == 0:
                z_shift = 0
            else:
                m = self.zshift_max.value()
                weights = np.array([0.5**np.abs(k) for k in range(-m, m+1)])
                z_shift = np.random.choice(np.arange(-m, m+1), size=self.image_BF.sizes['T'], p=weights / weights.sum())
            image_BF = self.image_BF.z_projection(projection_type, projection_zrange, z_shift=z_shift)
        else:
            image_BF = self.image_BF.image

        for t in range(self.image_BF.sizes['T']):
            pbr.set_description(f"Exporting {t+1}/{self.image_BF.sizes['T']}")
            pbr.update(1)
            # save image
            output_file = os.path.join(output_path, output_basename+f"_vT{t:03d}.tif")
            self.logger.info("Exporting bright-field image (time frame %s) to %s", t, output_file)
            tifffile.imwrite(output_file, image_BF[0, t, 0, 0, :, :], imagej=True, compression='zlib')
            # save mask
            output_file = os.path.join(output_path, output_basename+f"_vT{t:03d}_masks.tif")
            self.logger.info("Exporting segmentation mask (time frame %s) to %s", t, output_file)
            tifffile.imwrite(output_file, self.mask[t, :, :], imagej=True, compression='zlib')

        # log file
        output_file = os.path.join(output_path, output_basename+'.log')
        with open(output_file, 'w') as f:
            f.write(buffered_handler.get_messages())

        # Restore cursor
        napari.qt.get_app().restoreOverrideCursor()
        self.viewer.window._status_bar._toggle_activity_dock(False)
        pbr.close()

        self.logger.debug("Done")
        QMessageBox.information(self, 'Files exported', 'Image(s) and mask(s) saved to\n' + os.path.join(output_path, ''))

    def save(self, closing=False):
        # Set cursor to BusyCursor
        napari.qt.get_app().setOverrideCursor(QCursor(Qt.BusyCursor))
        napari.qt.get_app().processEvents()

        split_regions(self.mask)
        relabel(self.mask)

        output_file = os.path.join(self.output_path, self.output_basename+".ome.tif")
        self.logger.info("Saving segmentation mask to %s", output_file)
        ome_metadata = OmeTiffWriter.build_ome(data_shapes=[self.mask.shape],
                                               data_types=[self.mask.dtype],
                                               dimension_order=["TYX"],
                                               channel_names=[['Segmentation mask']],
                                               physical_pixel_sizes=[PhysicalPixelSizes(X=self.image_BF.physical_pixel_sizes[0], Y=self.image_BF.physical_pixel_sizes[1], Z=self.image_BF.physical_pixel_sizes[2])])
        ome_metadata.structured_annotations.append(CommentAnnotation(value=buffered_handler.get_messages(), namespace="VLabApp"))
        for x in self.image_BF_metadata:
            ome_metadata.structured_annotations.append(CommentAnnotation(value=x, namespace="VLabApp"))
        for x in self.image_fluo1_metadata:
            ome_metadata.structured_annotations.append(CommentAnnotation(value=x, namespace="VLabApp"))
        for x in self.image_fluo2_metadata:
            ome_metadata.structured_annotations.append(CommentAnnotation(value=x, namespace="VLabApp"))
        for x in self.image_mask_metadata:
            ome_metadata.structured_annotations.append(CommentAnnotation(value=x, namespace="VLabApp"))
        OmeTiffWriter.save(self.mask, output_file, ome_xml=ome_metadata)

        if not closing:
            self.mask_modified = False
            self.save_button.setStyleSheet("")
            self.viewer.layers['Mask'].refresh()

        self.logger.debug("Done")
        # Restore cursor
        napari.qt.get_app().restoreOverrideCursor()

        QMessageBox.information(self, 'Files saved', 'Mask saved to\n' + output_file)

    def quit(self):
        self.viewer.close()

    def on_viewer_close(self):
        # Restore cursor
        napari.qt.get_app().restoreOverrideCursor()
        if self.mask_modified:
            save = QMessageBox.question(self, 'Save changes', "Save mask before closing?", QMessageBox.Yes | QMessageBox.No)
            if save == QMessageBox.Yes:
                self.save(closing=True)
        remove_all_log_handlers()

    def __del__(self):
        remove_all_log_handlers()

    def segment(self):

        if self.image_fluo1 is None:
            self.logger.debug("Segmentation: fluorescent image missing")
            return

        # Set cursor to BusyCursor
        napari.qt.get_app().setOverrideCursor(QCursor(Qt.BusyCursor))
        napari.qt.get_app().processEvents()

        # Show activity dock & add napari progress bar
        self.viewer.window._status_bar._toggle_activity_dock(True)
        pbr = napari.utils.progress(total=self.image_fluo1.sizes['T'])

        threshold = self.threshold.value()
        pbr.set_description('Pre-processing')

        if self.image_fluo1.sizes['Z'] > 1:
            # Extract the Z section with best focus
            self.logger.info('Preparing fluorescent image 1 for segmentation: performing Z-projection')
            image1 = self.image_fluo1.z_projection('max', 0)
        else:
            image1 = self.image_fluo1.image.copy()
        # normalize to contrast limits
        limits = [round(x) for x in self.viewer.layers['Cell marker 1'].contrast_limits]
        self.logger.info('Preparing fluorescent image 1 for segmentation: normalizing with contrast limits [%s,%s]', limits[0], limits[1])
        image1[image1<limits[0]] = limits[0]
        image1[image1>limits[1]] = limits[1]
        image1 = ((image1-limits[0])*(np.iinfo(image1.dtype).max/(limits[1]-limits[0]))).astype(self.image_fluo1.dtype)
        image = image1

        if self.image_fluo2 is not None:
            threshold = threshold / 2
            if self.image_fluo2.sizes['Z'] > 1:
                # Extract the Z section with best focus
                self.logger.info('Preparing fluorescent image 2 for segmentation: performing Z-projection')
                image2 = self.image_fluo2.z_projection('max', 0)
            else:
                image2 = self.image_fluo2.image
            # normalize to contrast limits
            limits = [round(x) for x in self.viewer.layers['Cell marker 2'].contrast_limits]
            self.logger.info('Preparing fluorescent image 2 for segmentation: normalizing with contrast limits [%s,%s]', limits[0], limits[1])
            image2[image2<limits[0]] = limits[0]
            image2[image2>limits[1]] = limits[1]
            image2 = ((image2-limits[0])*(np.iinfo(image2.dtype).max/(limits[1]-limits[0]))).astype(self.image_fluo2.dtype)
            # average:
            self.logger.info('Merging fluorescent images 1 and 2 (mean)')
            image = (image1/2).astype(self.image_fluo1.dtype) + (image2/2).astype(self.image_fluo1.dtype)

        self.logger.info("Thresholding based segmentation of fluorescent image(s) (threshold %s)", threshold)
        self.mask = np.zeros((self.image_fluo1.sizes['T'], self.image_fluo1.sizes['Y'], self.image_fluo1.sizes['X']), dtype='uint16')
        for t in range(self.image_fluo1.sizes['T']):
            pbr.set_description(f"Segmentation {t+1}/{self.image_fluo1.sizes['T']}")
            pbr.update(1)
            self.logger.debug("segmenting frame %s", t)
            self.mask[t, :, :] = segment_image(image[0, t, 0, 0, :, :], threshold)

        # broadcast TYX mask to FTZYX, with broadcastedd axis containing shallow copies (C axis is used as channel_axis)
        tmp = np.broadcast_to(self.mask[np.newaxis, :, np.newaxis, :, :], (self.image_fluo1.shape[0], self.image_fluo1.shape[1], self.image_fluo1.shape[3], self.image_fluo1.shape[4], self.image_fluo1.shape[5]))
        # the resulting tmp is read only. To make it writeable:
        tmp.flags['WRITEABLE'] = True
        if 'Mask' in self.viewer.layers:
            self.viewer.layers['Mask'].data = tmp
            self.viewer.layers['Mask'].refresh()
        else:
            self.viewer.add_labels(tmp, name='Mask')
            # To detect image modifications
            self.viewer.layers['Mask'].events.paint.connect(self.paint_callback)

        self.mask_modified = True
        self.save_button.setEnabled(True)
        self.export_button.setEnabled(True)
        self.save_button.setStyleSheet("background: darkred;")

        # Restore cursor
        napari.qt.get_app().restoreOverrideCursor()
        self.viewer.window._status_bar._toggle_activity_dock(False)
        pbr.close()

        self.logger.debug("Done")


def main(image_BF_path, image_fluo1_path, image_fluo2_path, image_mask_path, output_path, output_basename):
    """
    Generate ground truth masks

    Parameters
    ---------------------
    image_BF_path: str
        input image path (bright-field).
    image_fluo1_path: str
        input image path (fluorescent image with cell marker 1).
    image_fluo2_path: str
        input image path (fluorescent image with cell marker 2).
    image_mask_path: str
        Segmentation mask path.
    output_path: str
        output directory
    output_basename: str
        output basename. Output file will be saved as `output_path`/`output_basename`.ome.tif

    Saves
    ---------------------
    ground truth image in the output directory

    """

    try:
        # Setup logging to file in output_path
        logger = logging.getLogger(__name__)
        logger.info("GROUND TRUTH MODULE")
        if not os.path.isdir(output_path):
            logger.debug("creating: %s", output_path)
            os.makedirs(output_path)

        # Log to file
        logfile = os.path.join(output_path, output_basename+".log")
        logger.setLevel(logging.DEBUG)
        logger.debug("writing log output to: %s", logfile)
        logfile_handler = logging.FileHandler(logfile, mode='w')
        logfile_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
        logfile_handler.setLevel(logging.INFO)
        logfile_handler.addFilter(gf.IgnoreDuplicate("Manually editing mask"))
        logger.addHandler(logfile_handler)
        # Also save general.general_functions logger to the same file (to log information on z-projection)
        logging.getLogger('general.general_functions').setLevel(logging.DEBUG)
        logging.getLogger('general.general_functions').addHandler(logfile_handler)

        # Log to memory
        global buffered_handler
        buffered_handler = gf.BufferedHandler()
        buffered_handler.setFormatter(logging.Formatter('%(asctime)s (VLabApp - segmentation module) [%(levelname)s] %(message)s'))
        buffered_handler.setLevel(logging.INFO)
        buffered_handler.addFilter(gf.IgnoreDuplicate("Manually editing mask"))
        logger.addHandler(buffered_handler)
        # Also save general.general_functions logger to the same file (to log information on z-projection)
        logging.getLogger('general.general_functions').addHandler(buffered_handler)

        logger.info("System info:")
        logger.info("- platform: %s", platform())
        logger.info("- python version: %s", python_version())
        logger.info("- VLabApp version: %s", vlabapp_version)
        logger.info("- numpy version: %s", np.__version__)
        logger.info("- opencv version: %s", cv.__version__)
        logger.info("- napari version: %s", napari.__version__)

        logger.info("Input bright-field image path: %s", image_BF_path)
        if image_fluo1_path is not None and image_fluo1_path != '':
            logger.info("Input fluorescent image 1 path: %s", image_fluo1_path)
        if image_fluo2_path is not None and image_fluo2_path != '':
            logger.info("Input fluorescent image 2 path: %s", image_fluo2_path)
        if image_mask_path is not None and image_mask_path != '':
            logger.info("Input segmentation mask path: %s", image_mask_path)

        # Load image
        logger.debug("loading %s", image_BF_path)
        try:
            image_BF = gf.Image(image_BF_path)
            image_BF.imread()
        except Exception:
            logging.getLogger(__name__).exception('Error loading image %s', image_BF_path)
            # stop using logfile
            remove_all_log_handlers()
            raise

        if image_fluo1_path is not None and image_fluo1_path != '':
            logger.debug("loading %s", image_fluo1_path)
            try:
                image_fluo1 = gf.Image(image_fluo1_path)
                image_fluo1.imread()
            except Exception:
                logging.getLogger(__name__).exception('Error loading image %s', image_fluo1_path)
                # stop using logfile
                remove_all_log_handlers()
                raise
        else:
            image_fluo1 = None

        if image_fluo2_path is not None and image_fluo2_path != '':
            logger.debug("loading %s", image_fluo2_path)
            try:
                image_fluo2 = gf.Image(image_fluo2_path)
                image_fluo2.imread()
            except Exception:
                logging.getLogger(__name__).exception('Error loading image %s', image_fluo2_path)
                # stop using logfile
                remove_all_log_handlers()
                raise
        else:
            image_fluo2 = None

        if image_mask_path is not None and image_mask_path != '':
            logger.debug("loading %s", image_mask_path)
            try:
                image_mask = gf.Image(image_mask_path)
                image_mask.imread()
            except Exception:
                logging.getLogger(__name__).exception('Error loading image %s', image_mask_path)
                # stop using logfile
                remove_all_log_handlers()
                raise
        else:
            image_mask = None

        # Check images sizes
        if not (image_BF.sizes['F'] == 1 and image_BF.sizes['C'] == 1 and image_BF.sizes['Y'] > 1 and image_BF.sizes['X'] > 1):
            logger.error('Invalid image:\n %s\n\nImage must have X and Y axes and can optionally have T or Z axis.', image_BF_path)
            # Close logfile
            remove_all_log_handlers()
            raise TypeError(f"Invalid image:\n {image_BF_path}\nImage must have X and Y axes and can optionally have T or Z axis.")
        if image_fluo1 is not None:
            if not (image_fluo1.sizes['F'] == 1 and image_fluo1.sizes['C'] == 1 and image_fluo1.sizes['Y'] > 1 and image_fluo1.sizes['X'] > 1):
                logger.error('Invalid image:\n %s\n\nImage must have X and Y axes and can optionally have T or Z axis.', image_fluo1_path)
                # Close logfile
                remove_all_log_handlers()
                raise TypeError(f"Invalid image:\n {image_fluo1_path}\nImage must have X and Y axes and can optionally have T or Z axis.")
            if not (image_fluo1.sizes['T'] == image_BF.sizes['T'] and image_fluo1.sizes['Z'] == image_BF.sizes['Z'] and image_fluo1.sizes['Y'] == image_BF.sizes['Y'] and image_fluo1.sizes['X'] == image_BF.sizes['X']):
                logger.error('Images must have same X, Y, Z and T axis sizes:\n %s\n %s', image_BF_path, image_fluo1_path)
                # Close logfile
                remove_all_log_handlers()
                raise TypeError(f"Images must have same X, Y, Z and T axis sizes:\n {image_BF_path}\n{image_fluo1_path}")
        if image_fluo2 is not None:
            if not (image_fluo2.sizes['F'] == 1 and image_fluo2.sizes['C'] == 1 and image_fluo2.sizes['Y'] > 1 and image_fluo2.sizes['X'] > 1):
                logger.error('Invalid image:\n %s\n\nImage must have X and Y axes and can optionally have T or Z axis.', image_fluo2_path)
                # Close logfile
                remove_all_log_handlers()
                raise TypeError(f"Invalid image:\n {image_fluo2_path}\nImage must have X and Y axes and can optionally have T or Z axis.")
            if not (image_fluo2.sizes['T'] == image_BF.sizes['T'] and image_fluo2.sizes['Z'] == image_BF.sizes['Z'] and image_fluo2.sizes['Y'] == image_BF.sizes['Y'] and image_fluo2.sizes['X'] == image_BF.sizes['X']):
                logger.error('Images must have same X, Y, Z and T axis sizes:\n %s\n %s', image_BF_path, image_fluo2_path)
                # Close logfile
                remove_all_log_handlers()
                raise TypeError(f"Images must have same X, Y, Z and T axis sizes:\n {image_BF_path}\n{image_fluo2_path}")
        if image_mask is not None:
            if not (image_mask.sizes['F'] == 1 and image_mask.sizes['C'] == 1 and image_mask.sizes['Z'] == 1 and image_mask.sizes['Y'] > 1 and image_mask.sizes['X'] > 1):
                logger.error('Invalid image:\n %s\n\nSegmentation mask must have X and Y axes and can optionally have T axis.', image_mask_path)
                # Close logfile
                remove_all_log_handlers()
                raise TypeError(f"Invalid image:\n {image_mask_path}\nImage must have X and Y axes and can optionally have T or Z axis.")
            if not (image_mask.sizes['T'] == image_BF.sizes['T'] and image_mask.sizes['Y'] == image_BF.sizes['Y'] and image_mask.sizes['X'] == image_BF.sizes['X']):
                logger.error('Segmentation mask and bright-field image must have same X, Y and T axis sizes:\n %s\n %s', image_BF_path, image_mask_path)
                # Close logfile
                remove_all_log_handlers()
                raise TypeError(f"Segmentation mask and bright-field image must have same X, Y and T axis sizes:\n {image_BF_path}\n{image_mask_path}")

        # open a modal napari window to avoid multiple windows, with competing logging to file.
        # TODO: find a better solution to open a modal napari window.
        global viewer
        viewer = napari.Viewer(show=False, title=image_BF_path)
        viewer.window._qt_window.setWindowModality(Qt.ApplicationModal)
        viewer.show()

        viewer.add_image(image_BF.image, channel_axis=2, name='Bright-field', colormap='gray')
        if image_fluo1 is not None:
            viewer.add_image(image_fluo1.image, channel_axis=2, name='Cell marker 1', colormap='magenta', blending='additive')
        if image_fluo2 is not None:
            viewer.add_image(image_fluo2.image, channel_axis=2, name='Cell marker 2', colormap='yellow', blending='additive')
        if image_mask is not None:
            mask = image_mask.get_TYXarray()
            # broadcast mask to FTZYX, with broadcastedd axis containing shallow copies (C axis is used as channel_axis)
            tmp = np.broadcast_to(mask[np.newaxis, :, np.newaxis, :, :], (image_BF.shape[0], image_BF.shape[1], image_BF.shape[3], image_BF.shape[4], image_BF.shape[5]))
            # the resulting tmp is read only. To make it writeable:
            tmp.flags['WRITEABLE'] = True
            viewer.add_labels(tmp, name='Mask')
        viewer.dims.axis_labels = ('F', 'T', 'Z', 'Y', 'X')

        # Add CellTrackingWidget to napari
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(GroundTruthWidget(image_BF, image_fluo1, image_fluo2, image_mask, viewer, output_path, output_basename))
        viewer.window.add_dock_widget(scroll_area, area='right', name="Ground truth")

    except Exception:
        # Remove all handlers for this module
        remove_all_log_handlers()
        # Restore cursor
        napari.qt.get_app().restoreOverrideCursor()
        try:
            # close napari window
            viewer.close()
        except:
            pass
        raise
