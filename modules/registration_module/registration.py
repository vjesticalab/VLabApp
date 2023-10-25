import os
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QCheckBox, QComboBox, QFileDialog, QFormLayout, QPushButton, QVBoxLayout, QWidget, QAbstractItemView, QGridLayout, QLabel, QLineEdit, QHBoxLayout, QApplication, QSpinBox, QRadioButton, QGroupBox
from PyQt5.QtGui import QCursor, QIntValidator
from functools import partial
import numpy as np
import logging
import matplotlib
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from modules.registration_module import registration_functions as f
from general import general_functions as gf
import concurrent.futures

matplotlib.use("Qt5Agg")

class Perform(gf.Page):
    def __init__(self):
        super().__init__()
        ####### Section Registration #######
        self.imagetypes = ['.nd2', '.tif', '.tiff']
        self.image_listA = gf.DropFilesListWidget(filetypes=self.imagetypes)
        self.image_listA.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.add_image_buttonA = QPushButton("Add images", self)
        self.add_image_buttonA.clicked.connect(partial(self.add_file, self.image_listA, self.imagetypes))
        self.add_folder_buttonA = QPushButton("Add folder", self)
        self.add_folder_buttonA.clicked.connect(partial(self.add_folder, self.image_listA, self.imagetypes))
        self.remove_buttonA = QPushButton("Remove selected", self)
        self.remove_buttonA.clicked.connect(partial(self.remove, self.image_listA))

        label = QLabel("<b>OPTIONS:</b>")
        self.channel_name = QLineEdit(placeholderText='eg. BF (default) / WL508 / ...')
        self.channel_name.setMinimumWidth(200)
        self.channel_position = QLineEdit(placeholderText='eg. 0 (default) / 1 / ...')
        self.channel_position.setMinimumWidth(200)
        self.channel_position.setValidator(QIntValidator())
        # Z-Projection type
        self.projection_type = QComboBox(self)
        self.projection_type.addItem("max")
        self.projection_type.addItem("min")
        self.projection_type.addItem("mean")
        self.projection_type.addItem("median")
        self.projection_type.addItem("std")
        self.projection_type.setCurrentText("std")

        # Z-Projection range
        # all
        self.projection_mode_all = QRadioButton("All Z sections")
        self.projection_mode_all.setChecked(False)
        self.projection_mode_all.setToolTip('Project all Z sections.')
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
        self.coalignment_yn_A = QCheckBox("")
        self.skip_cropping_yn_A = QCheckBox("")
        self.buttonA = QPushButton("Register")
        self.buttonA.clicked.connect(self.register)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Images to process"))
        layout.addWidget(self.image_listA)
        layout2 = QHBoxLayout()
        layout2.addWidget(self.add_image_buttonA)
        layout2.addWidget(self.add_folder_buttonA)
        layout2.addWidget(self.remove_buttonA)
        layout.addLayout(layout2)

        layout.addWidget(label)
        layout3 = QFormLayout()
        layout3.setLabelAlignment(Qt.AlignLeft)
        layout3.setFormAlignment(Qt.AlignLeft)
        layout3.addRow(" - Channel name:",self.channel_name)
        layout3.addRow(" - If needed, channel position into the c-stack:",self.channel_position)
        layout3.addRow(" - If needed, projection type for the z-stack:",self.projection_type)
        # Z-Projection range
        widget = QWidget()
        layout4 = QVBoxLayout()
        layout4.addWidget(self.projection_mode_all)
        layout4.addWidget(self.projection_mode_bestZ)
        layout4.addWidget(self.projection_mode_around_bestZ)
        groupbox = QGroupBox()
        groupbox.setToolTip('Project all Z sections with Z in the interval [bestZ-range,bestZ+range], where bestZ is the Z section with best focus.')
        groupbox.setVisible(self.projection_mode_around_bestZ.isChecked())
        self.projection_mode_around_bestZ.toggled.connect(groupbox.setVisible)
        layout5 = QFormLayout()
        layout5.addRow("Range:",self.projection_mode_around_bestZ_zrange)
        groupbox.setLayout(layout5)
        layout4.addWidget(groupbox)
        layout4.addWidget(self.projection_mode_fixed)
        groupbox = QGroupBox()
        groupbox.setToolTip('Project all Z sections with Z in the interval [from,to].')
        groupbox.setVisible(self.projection_mode_fixed.isChecked())
        self.projection_mode_fixed.toggled.connect(groupbox.setVisible)
        layout5 = QHBoxLayout()
        layout6 = QFormLayout()
        layout6.addRow("From:",self.projection_mode_fixed_zmin)
        layout5.addLayout(layout6)
        layout6 = QFormLayout()
        layout6.addRow("To:",self.projection_mode_fixed_zmax)
        layout5.addLayout(layout6)
        groupbox.setLayout(layout5)
        layout4.addWidget(groupbox)
        widget.setLayout(layout4)
        layout3.addRow(" - If needed, projection range for the z-stack:",widget)
        layout3.addRow(" - Co-align files with the same unique identifier (eg. smp01 for smp01_BF.nd2)", self.coalignment_yn_A)
        layout3.addRow(" - Do NOT crop aligned image", self.skip_cropping_yn_A)
        layout.addLayout(layout3)
        layout.addWidget(self.buttonA, alignment=Qt.AlignCenter)

        self.window = QVBoxLayout(self.container)
        self.window.addLayout(layout)
        self.window.addStretch()

        self.logger = logging.getLogger(__name__)

    def register(self):
        """
        Consider Unique Identifier as split('_')[0]
        """
        def check_inputs(image_paths):
            """
            Check if the inputs are valid
            Return: True if valid, False otherwise
            """
            if len(image_paths) == 0:
                self.logger.error('Image missing')
                self.add_image_buttonA.setFocus()
                return False
            for path in image_paths:
                if not os.path.isfile(path):
                    self.logger.error('Image not found\n' + path)
                    self.add_image_buttonA.setFocus()
                    return False
            return True

        image_paths = [self.image_listA.item(x).text() for x in range(self.image_listA.count())]

        # Arianna 26/07/23: added the three options channel_name, channel_position, projection_type
        channel_name = self.channel_name.text()
        channel_position = self.channel_position.text()
        projection_type = self.projection_type.currentText()
        if self.projection_mode_all.isChecked():
            projection_zrange = None
        elif self.projection_mode_bestZ.isChecked():
            projection_zrange = 0
        elif self.projection_mode_around_bestZ.isChecked():
            projection_zrange = self.projection_mode_around_bestZ_zrange.value()
        elif self.projection_mode_fixed.isChecked():
            projection_zrange = (self.projection_mode_fixed_zmin.value(), self.projection_mode_fixed_zmax.value())
        coalignment = self.coalignment_yn_A.isChecked()
        skip_crop_decision = self.skip_cropping_yn_A.isChecked()

        if channel_name == '': channel_name = 'BF'

        if channel_position == '': channel_position = 0
        else: channel_position = int(channel_position)

        if not check_inputs(image_paths):
            return

        QApplication.setOverrideCursor(QCursor(Qt.BusyCursor))
        QApplication.processEvents()

        arguments = []
        output_path = os.path.join(os.path.dirname(image_paths[0]), 'registration')
        os.makedirs(os.path.join(output_path, 'transf_matrices'), exist_ok=True)
        for image_path in image_paths:
            if os.path.isfile(image_path):
                if '_'+channel_name in image_path or channel_name in image_path:
                    # Set log and cursor info
                    self.logger.info("Image %s", image_path)

                    coalignment_images_list = []

                    if coalignment:
                        unique_identifier = os.path.basename(image_path).split('_')[0]
                        for im in os.listdir(os.path.dirname(image_path)):
                            if unique_identifier in im and im != image_path:
                                coalignment_images_list.append(os.path.join(os.path.dirname(image_path),im))


                    # collect arguments
                    arguments.append((image_path, output_path, channel_position, projection_type, projection_zrange, skip_crop_decision, coalignment_images_list))

            else:
                self.logger.error("Unable to locate file %s", image_path)

        # we use as many cores as images on the list but not more than half of the cores available
        nprocs = min(len(arguments), os.cpu_count()//2)
        self.logger.info(f"Using: {nprocs} cores to perform registration")
        if not arguments:
            return
        # Perform projection
        if len(arguments) == 1:
            f.registration_main(*arguments[0])
        else:
            # we go parallel
            with concurrent.futures.ProcessPoolExecutor(max_workers=nprocs) as executor:
                future_reg = {
                    executor.submit(f.registration_main, *args): args for args in arguments
                }
                for future in concurrent.futures.as_completed(future_reg):
                    try:

                        image_path = future.result()
                    except Exception:
                        self.logger.exception("An exception occurred")
                    else:
                        self.logger.info(f" Image: {image_path} Done")


        # Restore cursor
        QApplication.restoreOverrideCursor()
        self.logger.info("Done")

    def add_file(self, filelist, filetypes):
        # Add the selected file to the input file list
        file_paths, _ = QFileDialog.getOpenFileNames(self, 'Select Files', filter='Files ('+' '.join(['*'+x for x in filetypes])+')')
        for file_path in file_paths:
            if file_path and len(filelist.findItems(file_path, Qt.MatchExactly)) == 0:
                filelist.addItem(file_path)

    def add_folder(self, filelist, filetypes):
        # Add all the images in the selected folder to the input file list
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder_path:
            images = [os.path.join(folder_path, i) for i in os.listdir(folder_path) if os.path.splitext(i)[1] in filetypes]
            filelist.addItems([i for i in images if len(filelist.findItems(i, Qt.MatchExactly)) == 0])

    def remove(self, filelist):
        # Remove the selected file from the file list
        for item in filelist.selectedItems():
            filelist.takeItem(filelist.row(item))

    def projection_mode_fixed_zmin_changed(self, value):
        if self.projection_mode_fixed_zmax.value() < value:
            self.projection_mode_fixed_zmax.setValue(value)

    def projection_mode_fixed_zmax_changed(self, value):
        if self.projection_mode_fixed_zmin.value() > value:
            self.projection_mode_fixed_zmin.setValue(value)


class Align(gf.Page):
    def __init__(self):
        super().__init__()
        ####### Section Alignment #######
        label = QLabel("Images to align")
        label2 = QLabel('(the corresponding matrices have to be in "image_path/registration/transf_matrices/" folder)')
        font = label2.font()
        font.setItalic(True)
        label2.setFont(font)
        self.imagetypes = ['.nd2', '.tif', '.tiff']
        self.image_listB = gf.DropFilesListWidget(filetypes=self.imagetypes)
        self.image_listB.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.add_image_buttonB = QPushButton("Add images", self)
        self.add_image_buttonB.clicked.connect(partial(self.add_file, self.image_listB, self.imagetypes))
        self.add_folder_buttonB = QPushButton("Add folder", self)
        self.add_folder_buttonB.clicked.connect(partial(self.add_folder, self.image_listB, self.imagetypes))
        self.remove_buttonB = QPushButton("Remove selected", self)
        self.remove_buttonB.clicked.connect(partial(self.remove, self.image_listB))
        self.skip_cropping_yn_B = QCheckBox("Do NOT crop aligned image")
        self.buttonB = QPushButton("Align")
        self.buttonB.clicked.connect(self.align)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(label)
        layout.addWidget(label2)
        layout.addWidget(self.image_listB)
        layout3 = QHBoxLayout()
        layout3.addWidget(self.add_image_buttonB)
        layout3.addWidget(self.add_folder_buttonB)
        layout3.addWidget(self.remove_buttonB)
        layout.addLayout(layout3)
        layout.addWidget(self.skip_cropping_yn_B)
        layout.addWidget(self.buttonB, alignment=Qt.AlignCenter)

        self.window = QVBoxLayout(self.container)
        self.window.addLayout(layout)
        self.window.addStretch()

        self.logger = logging.getLogger(__name__)

    def align(self):
        def check_inputs(image_paths):
            """
            Check if the inputs are valid
            Return: True if valid, False otherwise
            """
            if len(image_paths) == 0:
                self.logger.error('Image missing')
                self.add_image_buttonB.setFocus()
                return False
            for path in image_paths:
                if not os.path.isfile(path):
                    self.logger.error('Image not found\n' + path)
                    self.add_image_buttonB.setFocus()
                    return False
            return True

        image_paths = [self.image_listB.item(x).text() for x in range(self.image_listB.count())]
        skip_crop_decision = self.skip_cropping_yn_B.isChecked()
        if not check_inputs(image_paths):
            return
        for image_path in image_paths:
            if os.path.isfile(image_path):
                # Set log and cursor info
                self.logger.info("Image %s", image_path)
                QApplication.setOverrideCursor(QCursor(Qt.BusyCursor))
                QApplication.processEvents()
                # Perform projection
                try:
                    f.alignment_main(image_path, skip_crop_decision)
                except Exception as e:
                    self.logger.error("Alignment failed.\n" + str(e))
                # Restore cursor
                QApplication.restoreOverrideCursor()
                self.logger.info("Done")
            else:
                self.logger.error("Unable to locate file %s", image_path)


    def add_file(self, filelist, filetypes):
        # Add the selected file to the input file list
        file_paths, _ = QFileDialog.getOpenFileNames(self, 'Select Files', filter='Files ('+' '.join(['*'+x for x in filetypes])+')')
        for file_path in file_paths:
            if file_path and len(filelist.findItems(file_path, Qt.MatchExactly)) == 0:
                filelist.addItem(file_path)

    def add_folder(self, filelist, filetypes):
        # Add all the images in the selected folder to the input file list
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder_path:
            images = [os.path.join(folder_path, i) for i in os.listdir(folder_path) if os.path.splitext(i)[1] in filetypes]
            filelist.addItems([i for i in images if len(filelist.findItems(i, Qt.MatchExactly)) == 0])

    def remove(self, filelist):
        # Remove the selected file from the file list
        for item in filelist.selectedItems():
            filelist.takeItem(filelist.row(item))


class Edit(gf.Page):
    def __init__(self):
        super().__init__()
        ####### Section Editing #######
        label = QLabel("Matrices to edit")
        label2 = QLabel('(double click on the transformation matrix to visualize it)')
        font = label2.font()
        font.setItalic(True)
        label2.setFont(font)
        self.matricestypes = ['.txt']
        self.matrices_list = gf.DropFilesListWidget(filetypes=self.matricestypes)
        self.matrices_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.add_file_buttonC = QPushButton("Add matrix", self)
        self.add_file_buttonC.clicked.connect(partial(self.add_file, self.matrices_list, self.matricestypes))
        self.add_folder_buttonC = QPushButton("Add folder", self)
        self.add_folder_buttonC.clicked.connect(partial(self.add_folder, self.matrices_list, self.matricestypes))
        self.remove_buttonC = QPushButton("Remove selected", self)
        self.remove_buttonC.clicked.connect(partial(self.remove, self.matrices_list))
        self.matrices_list.itemDoubleClicked.connect(self.display_matrix)
        #self.update_label = QLabel('After double-clicking the matrix, you can update its range', self)
        self.start_timepoint_label = QLabel('New start point:', self)
        self.start_timepoint_edit = QLineEdit(self)
        self.end_timepoint_label = QLabel('New end point:', self)
        self.end_timepoint_edit = QLineEdit(self)
        self.buttonC = QPushButton('Edit')
        self.buttonC.clicked.connect(self.edit)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(label)
        layout.addWidget(label2)
        layout.addWidget(self.matrices_list)
        layout3 = QHBoxLayout()
        layout3.addWidget(self.add_file_buttonC)
        layout3.addWidget(self.add_folder_buttonC)
        layout3.addWidget(self.remove_buttonC)
        layout.addLayout(layout3)
        layout3 = QGridLayout()
        layout3.addWidget(self.start_timepoint_label, 0, 0)
        layout3.addWidget(self.start_timepoint_edit, 0, 1)
        layout3.addWidget(self.end_timepoint_label, 0, 2)
        layout3.addWidget(self.end_timepoint_edit, 0, 3)
        layout.addLayout(layout3)
        layout.addWidget(self.buttonC, alignment=Qt.AlignCenter)
        self.window = QVBoxLayout(self.container)
        self.window.addLayout(layout)
        self.window.addStretch()

        self.logger = logging.getLogger(__name__)

    def edit(self):
        def check_inputs(transfmat_paths, start_timepoint, end_timepoint):
            """
            Check if the inputs are valid
            Return: True if valid, False otherwise
            """
            if len(transfmat_paths) == 0:
                self.logger.error('Matrix missing')
                self.add_file_buttonC.setFocus()
                return False
            for path in transfmat_paths:
                if not os.path.isfile(path):
                    self.logger.error('Matrix not found\n' + path)
                    self.add_file_buttonC.setFocus()
                    return False
            if len(start_timepoint) == 0:
                self.logger.error('Start timepoint missing')
                self.start_timepoint_edit.setFocus()
                return False
            if len(end_timepoint) == 0:
                self.logger.error('End timepoint missing')
                self.end_timepoint_edit.setFocus()
                return False
            return True

        transfmat_paths = [self.matrices_list.item(x).text() for x in range(self.matrices_list.count())]
        start_timepoint = self.start_timepoint_edit.text()
        end_timepoint = self.end_timepoint_edit.text()

        if not check_inputs(transfmat_paths, start_timepoint, end_timepoint):
            return
        for transfmat_path in transfmat_paths:
            self.transfmat_path = transfmat_path
            # Update the transformation matrix with indicated values
            f.edit_main(self.transfmat_path, int(start_timepoint), int(start_timepoint), int(end_timepoint))
            # Create an instance of the second window
            self.display_graph = DisplayGraphWindow(self.transfmat_path)
            self.display_graph.setWindowTitle(os.path.splitext(os.path.basename(self.transfmat_path))[0])
            self.display_graph.move(700,0)
            self.display_graph.show()


    def display_matrix(self, item):
        self.transfmat_path = item.text()
        # Display the matrix
        self.display_graph = DisplayGraphWindow(self.transfmat_path)
        self.display_graph.setWindowTitle(os.path.splitext(os.path.basename(self.transfmat_path))[0])
        self.display_graph.move(700,0)
        self.display_graph.show()

    def add_file(self, filelist, filetypes):
        # Add the selected file to the input file list
        file_paths, _ = QFileDialog.getOpenFileNames(self, 'Select Files', filter='Files ('+' '.join(['*'+x for x in filetypes])+')')
        for file_path in file_paths:
            if file_path and len(filelist.findItems(file_path, Qt.MatchExactly)) == 0:
                filelist.addItem(file_path)

    def add_folder(self, filelist, filetypes):
        # Add all the images in the selected folder to the input file list
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder_path:
            images = [os.path.join(folder_path, i) for i in os.listdir(folder_path) if os.path.splitext(i)[1] in filetypes]
            filelist.addItems([i for i in images if len(filelist.findItems(i, Qt.MatchExactly)) == 0])

    def remove(self, filelist):
        # Remove the selected file from the file list
        for item in filelist.selectedItems():
            filelist.takeItem(filelist.row(item))


class Registration(QWidget):
    def __init__(self):
        super().__init__()

        window = QVBoxLayout(self)
        tabwizard = gf.TabWizard()

        tabwizard.addPage(Perform(), "Registration")
        tabwizard.addPage(Align(), "Alignment")
        tabwizard.addPage(Edit(), "Editing")

        window.addWidget(tabwizard)


class DisplayGraphWindow(QWidget):
    def __init__(self, transfmat_path):
        super().__init__()

        self.plot_xy(transfmat_path)

        layout = QVBoxLayout()
        widget_graph = QWidget(self)
        widget_graph.setLayout(layout)

    def plot_xy(self, transfmat_path):
        # Read the transformation matrix values
        transformation_matrix = f.read_transfMat(transfmat_path)

        if transformation_matrix is None:
            return

        time = list(transformation_matrix[:,0])
        included_x_shift = transformation_matrix[:,1]
        included_y_shift = transformation_matrix[:,2]
        inclusion = transformation_matrix[:,3]
        x_shift = transformation_matrix[:,4]
        y_shift = transformation_matrix[:,5]
        dim_x = transformation_matrix[:,6]
        dim_y = transformation_matrix[:,7]
        dx = dim_x - abs(x_shift)
        dy = dim_y - abs(y_shift)
        included_dx = dim_x - abs(included_x_shift)
        included_dy = dim_y - abs(included_y_shift)

        included_xy_shift = []
        xy_shift = []
        included_xy_shift = []

        for i in range(len(time)):
            distance = np.sqrt((dim_x[i]**2 - dx[i]**2) + (dim_y[i]**2 - dy[i]**2)) # √(x² - dx²) + (y² - dy²))
            if inclusion[i] == 1:
                included_distance = np.sqrt((dim_x[i]**2 - included_dx[i]**2) + (dim_y[i]**2 - included_dy[i]**2)) # √(x² - dx²) + (y² - dy²))
            else:
                included_distance = float("nan")
            max_distance = np.sqrt((dim_x[i]**2) + (dim_y[i]**2))
            xy_shift.append((max_distance-distance)/max_distance)
            included_xy_shift.append((max_distance-included_distance)/max_distance)

        # Create a figure and a canvas
        figure = Figure()
        canvas = FigureCanvas(figure)

        # Create a subplot and plot the data
        ax = figure.add_subplot(111)
        ax.plot(time, xy_shift, label='All timepoints')
        ax.plot(time, included_xy_shift, label='Selected timepoints')
        ax.legend()
        ax.set_title('Offset')
        ax.set_xlabel('timepoints')
        ax.set_ylabel('offset values')

        # Add the canvas to the layout
        layout = QVBoxLayout(self)
        layout.addWidget(canvas)
