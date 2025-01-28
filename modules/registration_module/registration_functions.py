import logging
from platform import python_version, platform
from general import general_functions as gf
import numpy as np
import os
from pystackreg import StackReg
from pystackreg import __version__ as StackReg_version
import cv2 as cv
from aicsimageio.writers import OmeTiffWriter
from aicsimageio.types import PhysicalPixelSizes
from ome_types.model import CommentAnnotation
from skimage.measure import ransac
from skimage.transform import ProjectiveTransform
from skimage import __version__ as skimage_version
from PyQt5.QtWidgets import QVBoxLayout, QWidget, QPushButton, QLabel, QScrollArea, QRadioButton, QGroupBox, QFormLayout, QSpinBox, QMessageBox, QCheckBox
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QKeySequence
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvas
from matplotlib.backend_bases import MouseButton
from version import __version__ as vlabapp_version
import napari


def remove_all_log_handlers():
    # remove all handlers for this module
    while len(logging.getLogger(__name__).handlers) > 0:
        logging.getLogger(__name__).removeHandler(logging.getLogger(__name__).handlers[0])
    # remove all handlers for general.general_functions
    while len(logging.getLogger('general.general_functions').handlers) > 0:
        logging.getLogger('general.general_functions').removeHandler(logging.getLogger('general.general_functions').handlers[0])


class EditTransformationMatrix(QWidget):
    """
    A widget to use inside napari
    """

    tmat_changed = pyqtSignal(np.ndarray)

    def __init__(self, viewer, input_filename, read_only=False):
        """
        Parameters
        ----------
        viewer: napari.Viewer
            the napari viewer that contains the image. viewer.dims.axis_labels must contain the actual axis labels (must contain at least 'T', 'Y' and 'X']).
        input_filename: str
            transformation matrix filename
        read_only: bool
            should the matrix be read only?
        """
        super().__init__()

        self.point_alpha_active = 1
        self.point_alpha_inactive = 0.5
        self.point_color_default = [0, 1, 0]
        self.point_color_modified = [1, 0, 0]

        self.viewer = viewer
        self.input_filename = input_filename
        self.read_only = read_only
        self.tmat, self.tmat_metadata = read_transfMat(input_filename)
        self.tmat_saved_version = self.tmat.copy()
        tmat_active_frames = np.nonzero(self.tmat[:, 3])[0]
        if len(tmat_active_frames) > 0:
            tmat_start = tmat_active_frames.min()
            tmat_end = tmat_active_frames.max()
        else:
            tmat_start = 1
            tmat_end = 0

        self.T_axis_index = viewer.dims.axis_labels.index('T')
        self.Y_axis_index = viewer.dims.axis_labels.index('Y')
        self.X_axis_index = viewer.dims.axis_labels.index('X')
        self.other_axis_indices = np.setdiff1d(range(viewer.dims.ndim), [self.T_axis_index, self.Y_axis_index, self.X_axis_index])

        # 3 columns: T, Y, X
        points_TYX = self.tmat[:, (0, 5, 4)]
        # from 1-based indexing to 0-based indexing
        points_TYX[:, 0] = points_TYX[:, 0] - 1
        # center
        shifty = np.round((points_TYX[:, 1].min() + points_TYX[:, 1].max()) / 2 - self.tmat[:, 7].mean() / 2)
        shiftx = np.round((points_TYX[:, 2].min() + points_TYX[:, 2].max()) / 2 - self.tmat[:, 6].mean() / 2)
        points_TYX[:, 1] = points_TYX[:, 1] - shifty
        points_TYX[:, 2] = points_TYX[:, 2] - shiftx

        # add points to all dimensions (viewer.dims)
        points = np.zeros((points_TYX.shape[0], viewer.dims.ndim), dtype=points_TYX.dtype)
        points[:, viewer.dims.axis_labels.index('T')] = points_TYX[:, 0]
        points[:, viewer.dims.axis_labels.index('Y')] = points_TYX[:, 1]
        points[:, viewer.dims.axis_labels.index('X')] = points_TYX[:, 2]
        for i, d in enumerate(viewer.dims.axis_labels):
            if d not in ['T', 'Y', 'X']:
                range_min = np.round(viewer.dims.range[i][0])
                range_max = np.round(viewer.dims.range[i][1])
                values = np.arange(range_min, range_max, 1, dtype=points_TYX.dtype)
                points_nrow = points.shape[0]
                points = np.tile(points, (values.shape[0], 1))
                points[:, i] = np.repeat(values, [points_nrow], axis=0)

        edge_color = np.tile(self.point_color_default+[self.point_alpha_inactive], (points.shape[0], 1))
        edge_color[(tmat_start <= points[:, self.T_axis_index]) & (points[:, self.T_axis_index] <= tmat_end)] = self.point_color_default+[self.point_alpha_active]
        self.layer_points = viewer.add_points(points, name='Alignment points', size=30, face_color="#00000000", edge_color=edge_color, edge_width=0.2)

        layout = QVBoxLayout()

        shift_str = QKeySequence(Qt.ShiftModifier).toString().rstrip('+').upper()
        ctrl_str = QKeySequence(Qt.ControlModifier).toString().rstrip('+').upper()
        if not self.read_only:
            groupbox = QGroupBox("Modify:")
            help_label = QLabel("Use "+shift_str+" + CLICK to define the position of the alignment point (for all frames), without modifying the transformation matrix.\nUse "+ctrl_str+" + CLICK to update the position of the alignment point. When modifying the position of the alignment point, apply the modification to the following frame range:")
        else:
            groupbox = QGroupBox()
            help_label = QLabel("Use "+shift_str+" + CLICK or "+ctrl_str+" + CLICK to define the position of the alignment point.")
        help_label.setWordWrap(True)
        help_label.setMinimumWidth(10)
        self.modify_previous_frames = QRadioButton("from first to current frame")
        self.modify_previous_frames.setChecked(False)
        self.modify_current_frame = QRadioButton("only current frame")
        self.modify_current_frame.setChecked(True)
        self.modify_subsequent_frames = QRadioButton("from current to last frame")
        self.modify_subsequent_frames.setChecked(False)
        self.start_frame = QSpinBox()
        self.start_frame.setMinimum(0)
        self.start_frame.setMaximum(points[:, self.T_axis_index].max() - 1)
        self.start_frame.setValue(tmat_start)
        self.start_frame.valueChanged.connect(self.time_range_changed)
        self.end_frame = QSpinBox()
        self.end_frame.setMinimum(0)
        self.end_frame.setMaximum(points[:, self.T_axis_index].max())
        self.end_frame.setValue(tmat_end)
        self.end_frame.valueChanged.connect(self.time_range_changed)
        self.shift_view = QCheckBox("Move view with alignment point")
        self.shift_view.setChecked(True)
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.save)
        layout2 = QVBoxLayout()
        layout2.addWidget(help_label)
        if not self.read_only:
            layout2.addWidget(self.modify_previous_frames)
            layout2.addWidget(self.modify_current_frame)
            layout2.addWidget(self.modify_subsequent_frames)
            groupbox.setLayout(layout2)
            layout.addWidget(groupbox)

            groupbox = QGroupBox("Transformation range (frames)")
            layout2 = QFormLayout()
            layout2.addRow("From:", self.start_frame)
            layout2.addRow("To:", self.end_frame)
            groupbox.setLayout(layout2)
            layout.addWidget(groupbox)

            groupbox = QGroupBox("View")
            layout2 = QVBoxLayout()
        layout2.addWidget(self.shift_view)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
        if not self.read_only:
            layout.addWidget(self.save_button, alignment=Qt.AlignCenter)

        layout.addStretch()
        self.setLayout(layout)

        layer_points = self.layer_points

        @layer_points.mouse_drag_callbacks.append
        def click_drag(layer, event):
            dragged = False
            yield
            # on move
            while event.type == 'mouse_move':
                dragged = True
                yield
            # on release
            if not dragged:  # i.e. simple click
                if event.button == 1:  # (left-click)
                    if 'Control' in event.modifiers or 'Shift' in event.modifiers:
                        current_frame = round(event.position[self.T_axis_index])
                        sel = np.repeat(True, self.layer_points.data.shape[0])
                        for i in self.other_axis_indices:
                            sel = sel & (self.layer_points.data[:, i] == self.viewer.dims.current_step[i])
                        sel = sel & (np.round(self.layer_points.data[:, self.T_axis_index]) == np.round(current_frame))
                        # note that each frame contains only one point, i.e. sel contains a unique True element
                        delta = np.round(event.position - self.layer_points.data[sel])
                        if 'Shift' in event.modifiers or self.read_only:
                            # move everything
                            sel = np.repeat(True, self.layer_points.data.shape[0])
                        elif self.modify_previous_frames.isChecked():
                            sel = np.round(self.layer_points.data[:, self.T_axis_index]) <= np.round(current_frame)
                        elif self.modify_current_frame.isChecked():
                            sel = np.round(self.layer_points.data[:, self.T_axis_index]) == np.round(current_frame)
                        elif self.modify_subsequent_frames.isChecked():
                            sel = np.round(self.layer_points.data[:, self.T_axis_index]) >= np.round(current_frame)
                        self.layer_points.data[sel,] = self.layer_points.data[sel,] + delta
                        self.update_tmat()
                        #update point color
                        modified_frames = (np.abs(self.tmat_saved_version[:,(4,5)]-self.tmat[:,(4,5)])>0.0001).all(axis=1).nonzero()
                        layer.edge_color[:,0:3] = self.point_color_default
                        layer.edge_color[np.isin(layer.data[:, self.T_axis_index],modified_frames),0:3] = self.point_color_modified

                        layer.refresh()

        self.layer_points.editable = False
        # In the current version of napari (v0.4.17), editable is set to True whenever we change the axis value by clicking on the corresponding slider.
        # This is a quick and dirty hack to force the layer to stay non-editable.
        self.layer_points.events.editable.connect(lambda e: setattr(e.source, 'editable', False))

        # To allow saving transformation matrix before closing (__del__ is called too late)
        # TODO: replace by proper napari close event once implemented (https://forum.image.sc/t/handle-of-close-event-in-napari/61039)
        self.viewer.window._qt_window.destroyed.connect(self.on_close)

        self.viewer.dims.events.current_step.connect(self.dims_current_step_changed)
        self.dims_last_step = self.viewer.dims.current_step

    def dims_current_step_changed(self, event):
        try:
            if self.dims_last_step[self.T_axis_index] != self.viewer.dims.current_step[self.T_axis_index]:
                if self.shift_view.isChecked():
                    last_frame = self.dims_last_step[self.T_axis_index]
                    current_frame = self.viewer.dims.current_step[self.T_axis_index]
                    dx = self.tmat[current_frame, 4] - self.tmat[last_frame, 4]
                    dy = self.tmat[current_frame, 5] - self.tmat[last_frame, 5]
                    self.viewer.camera.center = (0, self.viewer.camera.center[1]+dy, self.viewer.camera.center[2]+dx)
                self.dims_last_step = self.viewer.dims.current_step
        except IndexError:
            pass

    def update_tmat(self):
        # self.layer_points are duplicated along all axes other than T, Y and X.
        # here we keep only subset of data for one value (here the min) of each axis other than T, Y or X
        column_mask = np.zeros(self.layer_points.data.shape[1], dtype=bool)
        column_mask[self.other_axis_indices] = True
        min_values = np.min(self.layer_points.data[:, column_mask], axis=0)
        rows_to_keep = (self.layer_points.data[:, column_mask] == min_values).all(axis=1)
        data_subset = self.layer_points.data[rows_to_keep]

        self.tmat[:, 3] = 0
        self.tmat[self.start_frame.value():self.end_frame.value() + 1, 3] = 1
        # raw transformation
        self.tmat[:, 4] = data_subset[:, self.X_axis_index]
        self.tmat[:, 5] = data_subset[:, self.Y_axis_index]
        self.tmat[:, 4] = self.tmat[:, 4] - self.tmat[0, 4]
        self.tmat[:, 5] = self.tmat[:, 5] - self.tmat[0, 5]
        # final transformation
        self.tmat[:, 1] = self.tmat[:, 4] - self.tmat[self.start_frame.value(), 4]
        self.tmat[:, 2] = self.tmat[:, 5] - self.tmat[self.start_frame.value(), 5]
        self.tmat_changed.emit(self.tmat)

    def time_range_changed(self):
        # adjust point transparency
        self.layer_points.edge_color[:,3] = self.point_alpha_inactive
        self.layer_points.edge_color[(self.start_frame.value() <= self.layer_points.data[:, self.T_axis_index]) & (self.layer_points.data[:, self.T_axis_index] <= self.end_frame.value()),3] = self.point_alpha_active
        self.update_tmat()
        self.layer_points.refresh()

    def on_close(self):
        # Restore cursor
        napari.qt.get_app().restoreOverrideCursor()
        if not np.array_equal(self.tmat, self.tmat_saved_version) and not self.read_only:
            save = QMessageBox.question(self, 'Save changes', "Save transformation matrix before closing?", QMessageBox.Yes | QMessageBox.No)
            if save == QMessageBox.Yes:
                self.save()
        remove_all_log_handlers()
        logging.getLogger(__name__).info('Done')

    def save(self):
        filename = self.input_filename
        if filename != '':
            logging.getLogger(__name__).info('Saving transformation matrix to %s', filename)
            header = buffered_handler.get_messages()
            for x in self.tmat_metadata:
                header += x
            np.savetxt(filename, self.tmat, fmt='%d,%d,%d,%d,%d,%d,%d,%d', header=header+'timePoint,align_t_x,align_t_y,align_0_1,raw_t_x,raw_t_y,x,y', delimiter='\t')
            self.tmat_saved_version = self.tmat.copy()
            #update point color
            self.layer_points.edge_color[:,0:3] = self.point_color_default
            self.layer_points.refresh()

    def __del__(self):
        # Remove all handlers for this module
        remove_all_log_handlers()


class PlotTransformation(QWidget):
    """
    A widget to use inside napari
    """

    def __init__(self, viewer, tmat):
        """
        Parameters
        ----------
        viewer: napari.Viewer
            the napari viewer that contains the image. viewer.dims.axis_labels must contain the actual axis labels (must contain at least 'T', 'Y' and 'X']).
        input_filename: str
            transformation matrix filename
        """
        super().__init__()

        self.viewer = viewer
        self.T_axis_index = self.viewer.dims.axis_labels.index('T')

        self.fig = plt.figure()
        self.ax = self.fig.add_subplot(111)
        self.ax.set(xlabel='Frame', ylabel='Transformation (offset)')
        x = np.arange(0, tmat.shape[0])
        self.vline = self.ax.axvline(x=self.viewer.dims.current_step[self.T_axis_index], ymin=0, ymax=1, color="black", alpha=0.1)
        (self.line_x_all,) = self.ax.plot(x, tmat[:, 4], color="#E41A1C", linestyle=":", label="x (all frames)", alpha=0.8)
        (self.line_y_all,) = self.ax.plot(x, tmat[:, 5], color="#377EB8", linestyle=":", label="y (all frames)", alpha=0.8)
        (self.line_x_active,) = self.ax.plot(x[tmat[:, 3] == 1], tmat[tmat[:, 3] == 1, 1], color="#E41A1C", linestyle="-", label="x (selected frames)")
        (self.line_y_active,) = self.ax.plot(x[tmat[:, 3] == 1], tmat[tmat[:, 3] == 1, 2], color="#377EB8", linestyle="-", label="y (selected frames)")
        self.ax.legend()

        layout = QVBoxLayout()
        layout.addWidget(FigureCanvas(self.fig))
        self.setLayout(layout)

        # connect a callback to update the vertical line (frame) on slider change
        self.viewer.dims.events.current_step.connect(self.update_frame)

    def update_frame(self, event):
        try:
            t = self.viewer.dims.current_step[self.T_axis_index]
            self.vline.set_xdata([t, t])
            self.fig.canvas.draw()
        except IndexError:
            pass

    def update(self, tmat):
        x = np.arange(0, tmat.shape[0])
        self.line_x_all.set_ydata(tmat[:, 4])
        self.line_y_all.set_ydata(tmat[:, 5])
        self.line_x_active.set_xdata(x[tmat[:, 3] == 1])
        self.line_x_active.set_ydata(tmat[tmat[:, 3] == 1, 1])
        self.line_y_active.set_xdata(x[tmat[:, 3] == 1])
        self.line_y_active.set_ydata(tmat[tmat[:, 3] == 1, 2])
        self.ax.relim()
        self.ax.autoscale_view(scalex=False, scaley=True)
        self.fig.canvas.draw()


# create a trivial MoveTransform (only translation) that inherits from skimage.transform.ProjectiveTransform
# the code was adapted from skimage.transform.EuclideanTransform
class MoveTransform(ProjectiveTransform):
    """Move transformation.

    Has the following form in 2D::

        X =  x + a1

        Y =  y + b1

    where the homogeneous transformation matrix is:

        [[1   0  a1]
         [0   1  b1]
         [0   0   1]]

    The Move transformation is a rigid transformation with only
    translation parameters.

    In 2D and 3D, the transformation parameters may be provided either via
    `matrix`, the homogeneous transformation matrix, above, or via the
    implicit parameter `translation` (where `a1` is the
    translation along `x`, `b1` along `y`, etc.).

    Parameters
    ----------
    matrix : (D+1, D+1) array_like, optional
        Homogeneous transformation matrix.
    translation : (x, y[, z, ...]) sequence of float, length D, optional
        Translation parameters for each axis.
    dimensionality : int, optional
        The dimensionality of the transform.

    Attributes
    ----------
    params : (D+1, D+1) array
        Homogeneous transformation matrix.

    References
    ----------
    .. [1] https://en.wikipedia.org/wiki/Rotation_matrix#In_three_dimensions
    """

    def __init__(self, matrix=None, translation=None, *, dimensionality=2):
        params_given = translation is not None

        if params_given and matrix is not None:
            raise ValueError("You cannot specify the transformation matrix and"
                             " the implicit parameters at the same time.")
        elif matrix is not None:
            matrix = np.asarray(matrix)
            if matrix.shape[0] != matrix.shape[1]:
                raise ValueError("Invalid shape of transformation matrix.")
            self.params = matrix
        elif params_given:
            dimensionality = len(translation)
            self.params = np.eye(dimensionality + 1)
            self.params[0:dimensionality, dimensionality] = translation
        else:
            # default to an identity transform
            self.params = np.eye(dimensionality + 1)

    def estimate(self, src, dst):
        """Estimate the transformation from a set of corresponding points.

        You can determine the over-, well- and under-determined parameters
        with the total least-squares method.

        Number of source and destination coordinates must match.

        Parameters
        ----------
        src : (N, 2) array_like
            Source coordinates.
        dst : (N, 2) array_like
            Destination coordinates.

        Returns
        -------
        success : bool
            True, if model estimation succeeds.

        """
        dim = src.shape[1]
        self.params = np.eye(dim + 1)
        self.params[0:dim, dim] = dst.mean(axis=0) - src.mean(axis=0)

        return True

    @property
    def translation(self):
        return self.params[0:self.dimensionality, self.dimensionality]


def read_transfMat(tmat_path):
    try:
        tmat_string = np.loadtxt(tmat_path, delimiter=",", dtype=str)
        # read metadata
        tmat_metadata = []
        metadata_tmp = ''
        with open(tmat_path) as f:
            for line in f:
                if line.startswith('# Metadata for') and not line.startswith("# timePoint,"):
                    if len(tmat_metadata) == 0:
                        tmat_metadata.append("Metadata for matrix "+tmat_path+":\n"+metadata_tmp)
                    else:
                        tmat_metadata.append(metadata_tmp)
                    metadata_tmp = ''
                if line.startswith('# ') and not line.startswith("# timePoint,"):
                    metadata_tmp += line[2:]
        if metadata_tmp:
            if len(tmat_metadata) == 0:
                tmat_metadata.append("Metadata for matrix "+tmat_path+":\n"+metadata_tmp)
            else:
                tmat_metadata.append(metadata_tmp)
    except Exception:
        logging.getLogger(__name__).exception('Load transformation matrix failed')
        raise

    tmat_float = tmat_string.astype(float)
    tmat_int = tmat_float.astype(int)
    return tmat_int, tmat_metadata


def register_stack_phase_correlation(image, blur=5):
    """
    Register an image using phase correlation algorithm implemented in opencv

    Parameters
    ----------
    image: ndarray
        a 3D (TYX) 16bit unsigned integer (uint16) numpy array.
    blur: int
        kernel size for gaussian blue

    Returns
    -------
    list of tuples
        list with one (x,y) tuple per time frame.
        Each (x,y) tuple corresponds to the shift between images at the corresponding time frame and previous time frame.
    """
    # make sure blur is odd
    if blur != 0:
        blur = blur // 2 * 2 + 1

    h = image.shape[1]
    w = image.shape[2]
    shifts = [(0, 0)]
    if blur > 1:
        prev = cv.GaussianBlur(cv.normalize(image[0], None, 0, 1, cv.NORM_MINMAX, dtype=cv.CV_32F), (blur, blur), 0)
    else:
        prev = cv.normalize(image[0], None, 0, 1, cv.NORM_MINMAX, dtype=cv.CV_32F)

    for i in range(1, image.shape[0]):
        if blur > 1:
            curr = cv.GaussianBlur(cv.normalize(image[i], None, 0, 1, cv.NORM_MINMAX, dtype=cv.CV_32F), (blur, blur), 0)
        else:
            curr = cv.normalize(image[i], None, 0, 1, cv.NORM_MINMAX, dtype=cv.CV_32F)

        lastshift = (round(shifts[-1][0]), round(shifts[-1][1]))
        # crop window prev (shifted)
        xmin1 = max(lastshift[0], 0)
        xmax1 = min(w+lastshift[0], w)
        ymin1 = max(lastshift[1], 0)
        ymax1 = min(h+lastshift[1], h)
        # crop window curr
        xmin2 = max(-lastshift[0], 0)
        xmax2 = min(w-lastshift[0], w)
        ymin2 = max(-lastshift[1], 0)
        ymax2 = min(h-lastshift[1], h)

        # register to previous image (shifted and cropped)
        shift, response = cv.phaseCorrelate(curr[ymin2:ymax2, xmin2:xmax2],
                                            prev[ymin1:ymax1, xmin1:xmax1],
                                            cv.createHanningWindow((xmax1-xmin1, ymax1-ymin1), cv.CV_32F))

        shifts.append((lastshift[0]+shift[0], lastshift[1]+shift[1]))

        # store shifted and cropped image as previous image
        prev = cv.warpAffine(curr, M=np.float32([[1, 0, shifts[-1][0]], [0, 1, shifts[-1][1]]]), dsize=(w, h), borderMode=cv.BORDER_CONSTANT, borderValue=curr.max()/2)

    return [(-x, -y) for x, y in shifts]


def register_stack_feature_matching(image, feature_type="ORB", blur=0, seed=76249):
    """
    Register an image using feature matching implemented in opencv followed by parameter estimatimtion with RANSAC.

    Parameters
    ----------
    image: ndarray
        a 3D (TYX) 16bit unsigned integer (uint16) numpy array.
    feature_type: str
        the algorithm use for feature detection.
        Possible feature types: AKAZE, BRISK, KAZE, ORB and SIFT.
    blur: int
        kernel size for gaussian blue
    seed: int
        seed for the random number generator

    Returns
    -------
    list of tuples
        list with one (x,y) tuple per time frame.
        Each (x,y) tuple corresponds to the shift between images at the corresponding time frame and previous time frame.
    """

    # make sure blur is odd
    if blur != 0:
        blur = blur // 2 * 2 + 1

    h = image.shape[1]
    w = image.shape[2]

    if feature_type == "SIFT":
        feature = cv.SIFT_create()
    elif feature_type == "ORB":
        feature = cv.ORB_create()
    elif feature_type == "AKAZE":
        feature = cv.AKAZE_create()
    elif feature_type == "KAZE":
        feature = cv.KAZE_create()
    elif feature_type == "BRISK":
        feature = cv.BRISK_create()
    else:
        logging.getLogger(__name__).error('Error unknown feature type %s', feature_type)
        raise ValueError(f"Error unknown feature type {feature_type}")

    cv.setRNGSeed(seed)
    # taken from https://docs.opencv.org/4.x/dc/dc3/tutorial_py_matcher.html
    if feature_type in ["SIFT", "KAZE"]:
        # for sift, kase
        FLANN_INDEX_KDTREE = 1
        index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=5)
    else:
        # for ORB, brisk, akaze
        FLANN_INDEX_LSH = 6
        index_params = dict(algorithm=FLANN_INDEX_LSH,
                            table_number=6,
                            key_size=12,
                            multi_probe_level=1)
    search_params = dict(checks=50)
    flann = cv.FlannBasedMatcher(index_params, search_params)

    shifts = [(0, 0)]
    if blur > 1:
        prev = cv.GaussianBlur(cv.normalize(image[0], None, 0, np.iinfo('uint8').max, cv.NORM_MINMAX, dtype=cv.CV_8U), (blur, blur), 0)
    else:
        prev = cv.normalize(image[0], None, 0, np.iinfo('uint8').max, cv.NORM_MINMAX, dtype=cv.CV_8U)

    for i in range(1, image.shape[0]):
        if blur > 1:
            curr = cv.GaussianBlur(cv.normalize(image[i], None, 0, np.iinfo('uint8').max, cv.NORM_MINMAX, dtype=cv.CV_8U), (blur, blur), 0)
        else:
            curr = cv.normalize(image[i], None, 0, np.iinfo('uint8').max, cv.NORM_MINMAX, dtype=cv.CV_8U)

        lastshift = (round(shifts[-1][0]), round(shifts[-1][1]))
        # crop window prev (shifted)
        xmin1 = max(lastshift[0], 0)
        xmax1 = min(w+lastshift[0], w)
        ymin1 = max(lastshift[1], 0)
        ymax1 = min(h+lastshift[1], h)
        # crop window curr
        xmin2 = max(-lastshift[0], 0)
        xmax2 = min(w-lastshift[0], w)
        ymin2 = max(-lastshift[1], 0)
        ymax2 = min(h-lastshift[1], h)

        kp1, des1 = feature.detectAndCompute(prev[ymin1:ymax1, xmin1:xmax1], None)
        kp2, des2 = feature.detectAndCompute(curr[ymin2:ymax2, xmin2:xmax2], None)

        matches = flann.knnMatch(des1, des2, k=2)

        # Filter out poor matches (ratio test as per Lowe's paper)
        good_matches = []
        for m in matches:
            if len(m) >= 2 and m[0].distance < 0.75*m[1].distance:
                good_matches.append(m[0])

        matches = good_matches

        points1 = np.float32([kp1[m.queryIdx].pt for m in matches])
        points2 = np.float32([kp2[m.trainIdx].pt for m in matches])

        # ransac
        shift = (0, 0)
        if len(matches) > 3:
            model_robust, inliers = ransac((points1, points2), MoveTransform, min_samples=3,
                                           residual_threshold=2, max_trials=100, rng=seed)
            if model_robust is not None:
                shift = -model_robust.translation

        shifts.append((lastshift[0]+shift[0], lastshift[1]+shift[1]))
        # store shifted image as previous image
        prev = cv.warpAffine(curr, M=np.float32([[1, 0, shifts[-1][0]], [0, 1, shifts[-1][1]]]), dsize=(w, h), borderMode=cv.BORDER_CONSTANT, borderValue=curr.max()/2)

    return [(-x, -y) for x, y in shifts]


def registration_with_tmat(tmat_int, image, skip_crop, output_path, output_basename, metadata):
    """
    This function uses a transformation matrix to performs registration and eventually cropping of an image
    Note - always assuming FoV dimension of the image as empty

    Parameters
    ---------------------
    tmat_int:
        transformation matrix
    image: Image object
    skip_crop: boolean
        indicates whether to crop or not the registered image
    output_path: str
        output directory
    output_basename: str
        output basename. Output file will be saved as `output_path`/`output_basename`.ome.tif
    metadata: list of str
        metadata from input file(s).

    Saves
    ---------------------
    image : ndarray
        registered and eventually cropped image (optional: also save co-aligned images)
    """
    logging.getLogger(__name__).info('Transforming image')
    registeredFilepath = os.path.join(output_path, output_basename+'.ome.tif')

    # Assuming empty dimension F
    image6D = image.image
    registered_image = image6D.copy()
    for z in range(0, image.sizes['Z']):
        for c in range(0, image.sizes['C']):
            for timepoint in range(0, image.sizes['T']):
                if tmat_int[timepoint, 3] == 1:
                    xyShift = (tmat_int[timepoint, 1]*-1, tmat_int[timepoint, 2]*-1)
                    registered_image[0, timepoint, c, z, :, :] = np.roll(image6D[0, timepoint, c, z, :, :], xyShift, axis=(1, 0))

    if skip_crop:
        t_start = min(d[0] for d in tmat_int if d[3] == 1)
        t_end = max(d[0] for d in tmat_int if d[3] == 1)
        registered_image = registered_image[:, t_start:t_end, :, :, :, :]
        # Save the registered and un-cropped image
        logging.getLogger(__name__).info('Saving transformed image to %s', registeredFilepath)
        ome_metadata = OmeTiffWriter.build_ome(data_shapes=[registered_image[0, :, :, :, :, :].shape],
                                               data_types=[registered_image[0, :, :, :, :, :].dtype],
                                               dimension_order=["TCZYX"],
                                               channel_names=[image.channel_names],
                                               physical_pixel_sizes=[PhysicalPixelSizes(X=image.physical_pixel_sizes[0], Y=image.physical_pixel_sizes[1], Z=image.physical_pixel_sizes[2])])
        ome_metadata.structured_annotations.append(CommentAnnotation(value=buffered_handler.get_messages(), namespace="VLabApp"))
        for x in metadata:
            ome_metadata.structured_annotations.append(CommentAnnotation(value=x, namespace="VLabApp"))
        OmeTiffWriter.save(registered_image[0, :, :, :, :, :], registeredFilepath, ome_xml=ome_metadata)
    else:
        logging.getLogger(__name__).info('Cropping image')
        # Crop to desired area
        y_start = 0 - min(d[2] for d in tmat_int if d[3] == 1)
        y_end = image.sizes['Y'] - max(d[2] for d in tmat_int if d[3] == 1)
        x_start = 0 - min([d[1] for d in tmat_int if d[3] == 1])
        x_end = image.sizes['X'] - max(d[1] for d in tmat_int if d[3] == 1)
        t_start = min(d[0] for d in tmat_int if d[3] == 1) - 1
        t_end = max(d[0] for d in tmat_int if d[3] == 1)

        # Crop along the y-axis
        image_cropped = registered_image[:, t_start:t_end, :, :, y_start:y_end, x_start:x_end]

        if image_cropped.shape[4] == 0 or image_cropped.shape[5] == 0:
            raise ValueError('Empty image after cropping (due to registration shift too large). To avoid this error: do not crop or limit the range of time frames.')

        # Save the registered and cropped image
        logging.getLogger(__name__).info('Saving transformed image to %s', registeredFilepath)
        ome_metadata = OmeTiffWriter.build_ome(data_shapes=[image_cropped[0, :, :, :, :, :].shape],
                                               data_types=[image_cropped[0, :, :, :, :, :].dtype],
                                               dimension_order=["TCZYX"],
                                               channel_names=[image.channel_names],
                                               physical_pixel_sizes=[PhysicalPixelSizes(X=image.physical_pixel_sizes[0], Y=image.physical_pixel_sizes[1], Z=image.physical_pixel_sizes[2])])
        ome_metadata.structured_annotations.append(CommentAnnotation(value=buffered_handler.get_messages(), namespace="VLabApp"))
        for x in metadata:
            ome_metadata.structured_annotations.append(CommentAnnotation(value=x, namespace="VLabApp"))
        OmeTiffWriter.save(image_cropped[0, :, :, :, :, :], registeredFilepath, ome_xml=ome_metadata)


def registration_values(image, projection_type, projection_zrange, channel_position, output_path, output_basename, registration_method, metadata, timepoint_range=None):
    """
    This function calculates the transformation matrices.
    Trnasformation matrices are saved  saved as `output_path`/`output_basename`.csv.

    Parameters
    ---------------------
    image : Image object
    projection_type : str
        type of projection to perform if it is a z-stack
    projection_zrange: int or (int,int) or None
        the range of z sections to use for projection.
        If zrange is None, use all z sections.
        If zrange is an integer, use all z sections in the interval [z_best-zrange,z_best+zrange]
        where z_best is the Z corresponding to best focus.
        If zrange is tuple (zmin,zmax), use all z sections in the interval [zmin,zmax].
    channel_position : int
        posizion of the channel to register if it is a c-stack
    output_path: str
        output directory
    output_basename: str
        output basename. Output file will be saved as `output_path`/`output_basename`.csv
    registration_method : str
        method to use for registration. Can be "stackreg", "phase correlation",
        "feature matching (ORB)", "feature matching (BRISK)", "feature matching (AKAZE)"
        or "feature matching (SIFT)".
    metadata: list of str
        metadata from input file(s).
    timepoint_range : tuple (start, end) or None
        If not None, only evaluate the transformation matrix for time frames T such that start <= T <= end.

    Returns
    ---------------------
    tmats :
        integer pixel values transformation matrix

    Saves
    ---------------------
    txt_res :
        file which contains the values t_x and t_y (x and y pixel shifts) as columns for each time point (rows)
    """

    # Assuming empty dimensions F and C defined in channel_position
    # if Z not empty then make z-projection (projection_type,projection_zrange)
    if image.sizes['Z'] > 1:
        try:
            logging.getLogger(__name__).info('Preparing image to evaluate transformation matrix: performing Z-projection')
            projection = image.z_projection(projection_type, projection_zrange)
        except Exception:
            logging.getLogger(__name__).exception('Z-projection failed for image %s', image.basename)
            remove_all_log_handlers()
            raise
        if image.sizes['C'] > channel_position:
            logging.getLogger(__name__).info('Preparing image to evaluate transformation matrix: selecting channel %s', channel_position)
            image3D = projection[0, :, channel_position, 0, :, :]
        else:
            logging.getLogger(__name__).error('Position of the channel given (%s) is out of range for image %s', channel_position, image.basename)
            remove_all_log_handlers()
            raise TypeError(f"Position of the channel given ({channel_position}) is out of range for image {image.basename}")
    # Otherwise read the 3D image
    else:
        if image.sizes['C'] > 1:
            if image.sizes['C'] > channel_position:
                logging.getLogger(__name__).info('Preparing image to evaluate transformation matrix: selecting channel %s', channel_position)
                image3D = image.image[0, :, channel_position, 0, :, :]
            else:
                logging.getLogger(__name__).error('Position of the channel given (%s) is out of range for image %s', channel_position, image.basename)
                remove_all_log_handlers()
                raise TypeError(f"Position of the channel given ({channel_position}) is out of range for image {image.basename}")
        else:
            image3D = image.get_TYXarray()

    if timepoint_range is not None:
        logging.getLogger(__name__).info('Preparing image to evaluate transformation matrix: selecting time frames %s<=T<=%s', timepoint_range[0], timepoint_range[1])
        image3D = image3D[timepoint_range[0]:(timepoint_range[1]+1), :, :]

    if registration_method == "stackreg":
        logging.getLogger(__name__).info('Evaluating transformation matrix with stackreg')
        # Translation = only movements on x and y axis
        sr = StackReg(StackReg.TRANSLATION)
        # Align each frame at the previous one
        tmats = sr.register_stack(image3D, reference='previous')
        shifts = tmats[:, 0:2, 2]
    elif registration_method == "phase correlation":
        logging.getLogger(__name__).info('Evaluating transformation matrix with phase correlation')
        shifts = register_stack_phase_correlation(image3D, blur=5)
        shifts = np.array(shifts)
    elif registration_method.startswith("feature matching"):
        if registration_method == "feature matching (ORB)":
            logging.getLogger(__name__).info('Evaluating transformation matrix with feature matching (ORB)')
            shifts = register_stack_feature_matching(image3D, feature_type="ORB")
        elif registration_method == "feature matching (BRISK)":
            logging.getLogger(__name__).info('Evaluating transformation matrix with feature matching (BRISK)')
            shifts = register_stack_feature_matching(image3D, feature_type="BRISK")
        elif registration_method == "feature matching (AKAZE)":
            logging.getLogger(__name__).info('Evaluating transformation matrix with feature matching (AKAZE)')
            shifts = register_stack_feature_matching(image3D, feature_type="AKAZE")
        elif registration_method == "feature matching (SIFT)":
            logging.getLogger(__name__).info('Evaluating transformation matrix with feature matching (SIFT)')
            shifts = register_stack_feature_matching(image3D, feature_type="SIFT")
        else:
            logging.getLogger(__name__).error('Error unknown registration method %s', registration_method)
            remove_all_log_handlers()
            raise ValueError(f"Error unknown registration method {registration_method}")
        shifts = np.array(shifts)
    else:
        logging.getLogger(__name__).error('Error unknown registration method %s', registration_method)
        remove_all_log_handlers()
        raise ValueError(f"Error unknown registration method {registration_method}")

    # Transformation matrix has 6 columns:
    # timePoint, align_t_x, align_t_y, align_0_1, raw_t_x, raw_t_y (align_ and raw_ values are identical, useful then for the alignment)
    transformation_matrices = np.zeros((image.sizes['T'], 8), dtype=int)
    transformation_matrices[:, 0] = np.arange(1, image.sizes['T']+1)
    if timepoint_range is not None:
        transformation_matrices[timepoint_range[0]:(timepoint_range[1]+1), 1:3] = np.round(shifts).astype(int)
        transformation_matrices[timepoint_range[0]:(timepoint_range[1]+1), 4:6] = np.round(shifts).astype(int)
        transformation_matrices[timepoint_range[0]:(timepoint_range[1]+1), 3] = 1
    else:
        transformation_matrices[:, 1:3] = np.round(shifts).astype(int)
        transformation_matrices[:, 4:6] = np.round(shifts).astype(int)
        transformation_matrices[:, 3] = 1
    transformation_matrices[:, 6] = image.sizes['X']
    transformation_matrices[:, 7] = image.sizes['Y']

    # Save the txt file with the translation matrix
    txt_name = os.path.join(output_path, output_basename+'.csv')
    logging.getLogger(__name__).info("Saving transformation matrix to %s", txt_name)
    header = buffered_handler.get_messages()
    for x in metadata:
        header += x
    np.savetxt(txt_name, transformation_matrices, fmt='%d,%d,%d,%d,%d,%d,%d,%d', header=header+'timePoint,align_t_x,align_t_y,align_0_1,raw_t_x,raw_t_y,x,y', delimiter='\t')

    return transformation_matrices


################################################################


def registration_main(image_path, output_path, output_basename, channel_position, projection_type, projection_zrange, timepoint_range, skip_crop_decision, registration_method, coalign_image_paths=None , coalign_output_basenames=None):

    try:
        # Setup logging to file in output_path
        logger = logging.getLogger(__name__)
        logger.info("REGISTRATION MODULE (registration)")
        if not os.path.isdir(output_path):
            logger.debug("creating: %s", output_path)
            os.makedirs(output_path)

        logfile = os.path.join(output_path, output_basename+".log")
        logger.setLevel(logging.DEBUG)
        logger.debug("writing log output to: %s", logfile)
        logfile_handler = logging.FileHandler(logfile, mode='w')
        logfile_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
        logfile_handler.setLevel(logging.INFO)
        logger.addHandler(logfile_handler)
        # Also save general.general_functions logger to the same file (to log information on z-projection)
        logging.getLogger('general.general_functions').setLevel(logging.DEBUG)
        logging.getLogger('general.general_functions').addHandler(logfile_handler)

        # Log to memory
        global buffered_handler
        buffered_handler = gf.BufferedHandler()
        buffered_handler.setFormatter(logging.Formatter('%(asctime)s (VLabApp - registration module) [%(levelname)s] %(message)s'))
        buffered_handler.setLevel(logging.INFO)
        logger.addHandler(buffered_handler)
        # Also save general.general_functions logger to the same file (to log information on z-projection)
        logging.getLogger('general.general_functions').addHandler(buffered_handler)

        logger.info("System info:")
        logger.info("- platform: %s", platform())
        logger.info("- python version: %s", python_version())
        logger.info("- VLabApp version: %s", vlabapp_version)
        logger.info("- numpy version: %s", np.__version__)
        logger.info("- pystackreg version: %s", StackReg_version)
        logger.info("- opencv version: %s", cv.__version__)
        logger.info("- skimage version: %s", skimage_version)

        logger.info("Input image path: %s", image_path)
        logger.info("Output path: %s", output_path)
        logger.info("Output basename: %s", output_basename)
        logger.info("Registration method: %s", registration_method)

        # Load image
        # Note: by default the image have to be ALWAYS 3D with TYX
        try:
            logger.debug('Loading %s', image_path)
            image = gf.Image(image_path)
            image.imread()
        except Exception:
            logger.exception('Error loading image %s', image_path)
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
            remove_all_log_handlers()
            raise TypeError(f"Image {image_path} has a F axis with size > 1")

        # Calculate transformation matrix
        tmat = registration_values(image, projection_type, projection_zrange, channel_position, output_path, output_basename, registration_method, image_metadata, timepoint_range)

        # Align and save
        try:
            registration_with_tmat(tmat, image, skip_crop_decision, output_path, output_basename, image_metadata)
        except Exception:
            logger.exception('Registration failed for image %s', image_path)
            remove_all_log_handlers()
            raise

        remove_all_log_handlers()

        # Co-alignment
        if coalign_image_paths is not None and coalign_output_basenames is not None:
            tmat_path = os.path.join(output_path, output_basename+'.csv')
            for coalign_image_path, coalign_output_basename in zip(coalign_image_paths, coalign_output_basenames):
                logger.info("Co-aligning image: %s", image_path)
                alignment_main(coalign_image_path, tmat_path, output_path, coalign_output_basename, skip_crop_decision)


        return image_path

    except Exception:
        # Remove all handlers for this module
        remove_all_log_handlers()
        raise

################################################################


def alignment_main(image_path, tmat_path, output_path, output_basename, skip_crop_decision):
    try:
        # Setup logging to file in output_path
        logger = logging.getLogger(__name__)
        logger.info("REGISTRATION MODULE (alignment)")
        if not os.path.isdir(output_path):
            logger.debug("creating: %s", output_path)
            os.makedirs(output_path)

        logfile = os.path.join(output_path, output_basename+".log")
        logger.setLevel(logging.DEBUG)
        logger.debug("writing log output to: %s", logfile)
        logfile_handler = logging.FileHandler(logfile, mode='w')
        logfile_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
        logfile_handler.setLevel(logging.INFO)
        logger.addHandler(logfile_handler)

        # Log to memory
        global buffered_handler
        buffered_handler = gf.BufferedHandler()
        buffered_handler.setFormatter(logging.Formatter('%(asctime)s (VLabApp - registration module) [%(levelname)s] %(message)s'))
        buffered_handler.setLevel(logging.INFO)
        logger.addHandler(buffered_handler)

        logger.info("System info:")
        logger.info("- platform: %s", platform())
        logger.info("- python version: %s", python_version())
        logger.info("- VLabApp version: %s", vlabapp_version)
        logger.info("- numpy version: %s", np.__version__)
        logger.info("- pystackreg version: %s", StackReg_version)
        logger.info("- opencv version: %s", cv.__version__)
        logger.info("- skimage version: %s", skimage_version)

        logger.info("Input image path: %s", image_path)
        logger.info("Input transformation matrix path: %s", tmat_path)
        logger.info("Output path: %s", output_path)
        logger.info("Output basename: %s", output_basename)

        # Load image and matrix
        try:
            logger.debug('loading %s', image_path)
            image = gf.Image(image_path)
            image.imread()
        except Exception:
            logging.getLogger(__name__).exception('Error loading image %s', image_path)
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

        try:
            logger.debug('loading %s', tmat_path)
            tmat_int, tmat_metadata = read_transfMat(tmat_path)
        except Exception:
            logging.getLogger(__name__).exception('Error loading transformation matrix for image %s', image_path)
            remove_all_log_handlers()
            raise
        # Check 'F' axis has size 1
        if image.sizes['F'] != 1:
            logging.getLogger(__name__).error('Image %s has a F axis with size > 1', str(image_path))
            remove_all_log_handlers()
            raise TypeError(f"Image {image_path} has a F axis with size > 1")

        # Align and save - registration works with multidimensional files, as long as the TYX axes are specified
        try:
            registration_with_tmat(tmat_int, image, skip_crop_decision, output_path, output_basename, image_metadata+tmat_metadata)
        except Exception:
            logging.getLogger(__name__).exception('Alignment failed for image %s', image_path)
            remove_all_log_handlers()
            raise

        remove_all_log_handlers()

    except Exception:
        # Remove all handlers for this module
        remove_all_log_handlers()
        raise


################################################################


def edit_main(reference_matrix_path, range_start, range_end):
    try:
        log_path = gf.splitext(reference_matrix_path)[0] + '.log'

        # Setup logging to file in output_path
        logger = logging.getLogger(__name__)
        logger.info("REGISTRATION MODULE (editing)")

        logfile = os.path.join(log_path)
        logger.setLevel(logging.DEBUG)
        logger.debug("writing log output to: %s", logfile)
        logfile_handler = logging.FileHandler(logfile, mode='a')
        logfile_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
        logfile_handler.setLevel(logging.INFO)
        logger.addHandler(logfile_handler)

        # Log to memory
        global buffered_handler
        buffered_handler = gf.BufferedHandler()
        buffered_handler.setFormatter(logging.Formatter('%(asctime)s (VLabApp - registration module) [%(levelname)s] %(message)s'))
        buffered_handler.setLevel(logging.INFO)
        logger.addHandler(buffered_handler)

        logger.info("System info:")
        logger.info("- platform: %s", platform())
        logger.info("- python version: %s", python_version())
        logger.info("- VLabApp version: %s", vlabapp_version)
        logger.info("- numpy version: %s", np.__version__)
        logger.info("- pystackreg version: %s", StackReg_version)
        logger.info("- opencv version: %s", cv.__version__)
        logger.info("- skimage version: %s", skimage_version)

        logger.info("Input transformation matrix path: %s", reference_matrix_path)

        # Load the transformation matrix
        logger.debug("loading: %s", reference_matrix_path)
        tmat, tmat_metadata = read_transfMat(reference_matrix_path)

        # Update transformation matrix
        logger.info("Editing transformation matrix (start=%s, end=%s)", range_start, range_end)
        tmat[:, 3] = 0
        tmat[range_start:(range_end+1), 3] = 1
        tmat[:, 1] = tmat[:, 4] - tmat[range_start, 4]
        tmat[:, 2] = tmat[:, 5] - tmat[range_start, 5]

        # Save the new matrix
        logger.info("Saving transformation matrix to %s", reference_matrix_path)
        header = buffered_handler.get_messages()
        for x in tmat_metadata:
            header += x
        np.savetxt(reference_matrix_path, tmat, fmt='%d,%d,%d,%d,%d,%d,%d,%d', header=header+'timePoint,align_t_x,align_t_y,align_0_1,raw_t_x,raw_t_y,x,y', delimiter='\t')

        remove_all_log_handlers()

    except Exception:
        # Remove all handlers for this module
        remove_all_log_handlers()
        raise



################################################################


def manual_edit_main(image_path, matrix_path):
    try:
        log_path = gf.splitext(matrix_path)[0] + '.log'

        # Setup logging to file in output_path
        logger = logging.getLogger(__name__)
        logger.info("REGISTRATION MODULE (manual editing)")

        logfile = os.path.join(log_path)
        logger.setLevel(logging.DEBUG)
        logger.debug("writing log output to: %s", logfile)
        logfile_handler = logging.FileHandler(logfile, mode='a')
        logfile_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
        logfile_handler.setLevel(logging.INFO)
        logger.addHandler(logfile_handler)

        # Log to memory
        global buffered_handler
        buffered_handler = gf.BufferedHandler()
        buffered_handler.setFormatter(logging.Formatter('%(asctime)s (VLabApp - registration module) [%(levelname)s] %(message)s'))
        buffered_handler.setLevel(logging.INFO)
        logger.addHandler(buffered_handler)

        logger.info("System info:")
        logger.info("- platform: %s", platform())
        logger.info("- python version: %s", python_version())
        logger.info("- VLabApp version: %s", vlabapp_version)
        logger.info("- numpy version: %s", np.__version__)
        logger.info("- pystackreg version: %s", StackReg_version)
        logger.info("- opencv version: %s", cv.__version__)
        logger.info("- skimage version: %s", skimage_version)
        logger.info("- napari version: %s", napari.__version__)

        logger.info("Input image path: %s", image_path)
        logger.info("Input transformation matrix path: %s", matrix_path)

        try:
            image = gf.Image(image_path)
            image.imread()
        except Exception:
            logging.getLogger(__name__).exception('Error loading image %s', image_path)
            raise

        # Check 'F' axis has size 1
        if image.sizes['F'] != 1:
            logging.getLogger(__name__).error('Image %s has a F axis with size > 1', str(image_path))
            raise TypeError(f"Image {image_path} has a F axis with size > 1")

        # open a modal napari window to avoid multiple windows, with competing logging to file.
        # TODO: find a better solution to open a modal napari window.
        global viewer
        viewer = napari.Viewer(show=False)
        viewer.window._qt_window.setWindowModality(Qt.ApplicationModal)
        viewer.show()

        # assuming a FTCZYX image:
        viewer.add_image(image.image, channel_axis=2, name=['Image [' + x + ']' for x in image.channel_names] if image.channel_names else 'Image')
        # channel axis is already used as channel_axis (layers) => it is not in viewer.dims:
        viewer.dims.axis_labels = ('F', 'T', 'Z', 'Y', 'X')

        logger.info("Manually editing the transformation matrix")

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        edit_transformation_matrix = EditTransformationMatrix(viewer, matrix_path)
        scroll_area.setWidget(edit_transformation_matrix)
        viewer.window.add_dock_widget(scroll_area, area='right', name="Edit transformation matrix")

        plot_transformation = PlotTransformation(viewer, edit_transformation_matrix.tmat)
        plot_transformation.fig.canvas.mpl_connect('button_press_event', lambda event: viewer.dims.set_point(1, round(event.xdata)) if event.button is event.button is MouseButton.LEFT and event.inaxes else None)
        plot_transformation.fig.canvas.mpl_connect('motion_notify_event', lambda event: viewer.dims.set_point(1, round(event.xdata)) if event.button is MouseButton.LEFT and event.inaxes else None)
        viewer.window.add_dock_widget(plot_transformation, area="bottom")

        edit_transformation_matrix.tmat_changed.connect(plot_transformation.update)

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

