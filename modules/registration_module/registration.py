import os
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QCheckBox, QComboBox, QFormLayout, QPushButton, QVBoxLayout, QWidget, QGridLayout, QLabel, QLineEdit, QHBoxLayout, QApplication, QSpinBox, QRadioButton, QGroupBox, QFileDialog
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
        # Documentation
        label_documentation = QLabel()
        label_documentation.setOpenExternalLinks(True)
        label_documentation.setText('<a href="file://' + os.path.join(os.path.dirname(__file__), "doc", "METHODS.html") + '">Methods</a>')

        self.imagetypes = ['.nd2', '.tif', '.tiff']

        self.image_listA = gf.FileListWidget(filetypes=self.imagetypes, filenames_filter='_BF')
        self.channel_position = QLineEdit(placeholderText='eg. 0 (default) / 1 / ...')
        self.channel_position.setMinimumWidth(200)
        self.channel_position.setValidator(QIntValidator())

        # Z-Projection range
        # only bestZ
        self.projection_mode_bestZ = QRadioButton("Z section with best focus")
        self.projection_mode_bestZ.setChecked(False)
        self.projection_mode_bestZ.setToolTip('Keep only Z section with best focus.')
        # around bestZ
        self.projection_mode_around_bestZ = QRadioButton("Range around Z section with best focus")
        self.projection_mode_around_bestZ.setChecked(False)
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
        self.projection_mode_all.setChecked(True)
        self.projection_mode_all.setToolTip('Project all Z sections.')
        # Z-Projection type
        self.projection_type = QComboBox(self)
        self.projection_type.addItem("max")
        self.projection_type.addItem("min")
        self.projection_type.addItem("mean")
        self.projection_type.addItem("median")
        self.projection_type.addItem("std")
        self.projection_type.setCurrentText("std")
        self.projection_type.setDisabled(self.projection_mode_bestZ.isChecked())
        self.projection_mode_bestZ.toggled.connect(self.projection_type.setDisabled)
        # registration method
        self.registration_method = QComboBox(self)
        self.registration_method.addItem("stackreg")
        self.registration_method.addItem("phase correlation")
        self.registration_method.addItem("feature matching (ORB)")
        self.registration_method.addItem("feature matching (BRISK)")
        self.registration_method.addItem("feature matching (AKAZE)")
        self.registration_method.addItem("feature matching (SIFT)")
        self.registration_method.setCurrentText("stackreg")
        self.coalignment_yn_A = QCheckBox("Co-align files with the same unique identifier (eg. smp01 for smp01_BF.nd2)")
        self.skip_cropping_yn_A = QCheckBox("Do NOT crop aligned image")
        self.buttonA = QPushButton("Register")
        self.buttonA.clicked.connect(self.register)
        self.n_count = QSpinBox()
        self.n_count.setMinimum(1)
        self.n_count.setMaximum(os.cpu_count())
        self.n_count.setValue(1)
        n_count_label=QLabel("Number of processes:")

        # T-range
        # all
        self.time_mode_all = QRadioButton("All timepoints")
        self.time_mode_all.setChecked(True)
        # fixed range
        self.time_mode_fixed = QRadioButton("Timepoint range")
        self.time_mode_fixed.setChecked(False)
        self.time_mode_fixed_tmin = QSpinBox()
        self.time_mode_fixed_tmin.setMinimum(0)
        self.time_mode_fixed_tmin.valueChanged.connect(self.time_mode_fixed_tmin_changed)
        self.time_mode_fixed_tmax = QSpinBox()
        self.time_mode_fixed_tmax.setMinimum(0)
        self.time_mode_fixed_tmax.valueChanged.connect(self.time_mode_fixed_tmax_changed)
        


        # Layout
        layout = QVBoxLayout()
        # Documentation
        groupbox = QGroupBox("Documentation")
        layout2 = QVBoxLayout()
        layout2.addWidget(label_documentation)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        groupbox = QGroupBox('Images to process')
        layout2 = QVBoxLayout()
        layout2.addWidget(self.image_listA)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        groupbox = QGroupBox("Options for multidimensional files:")
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

        groupbox2 = QGroupBox("If multiple time points:")
        layout8 = QVBoxLayout()
        layout8.addWidget(self.time_mode_all)
        groupbox2.setLayout(layout8)
        layout8.addWidget(self.time_mode_fixed)
        groupboxt1 = QGroupBox()
        groupboxt1.setVisible(self.time_mode_fixed.isChecked())
        self.time_mode_fixed.toggled.connect(groupboxt1.setVisible)
        layout9 = QHBoxLayout()
        layout10 = QFormLayout()
        layout10.addRow("From:",self.time_mode_fixed_tmin)
        layout9.addLayout(layout10)
        layout10 = QFormLayout()
        layout10.addRow("To:",self.time_mode_fixed_tmax)
        layout9.addLayout(layout10)
        groupboxt1.setLayout(layout9)
        layout8.addWidget(groupboxt1)
        layout3.addRow(groupbox2)

        layout3.addRow("Registration method:",self.registration_method)
        layout3.addRow(self.coalignment_yn_A)
        layout3.addRow(self.skip_cropping_yn_A)
        groupbox.setLayout(layout3)

        layout.addWidget(groupbox)
        groupbox = QGroupBox("Multi-processing")
        layout2 = QFormLayout()
        layout2.addRow(n_count_label,self.n_count)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
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
                return False
            for path in image_paths:
                if not os.path.isfile(path):
                    self.logger.error('Image not found\n' + path)
                    return False
            return True

        image_paths = self.image_listA.get_file_list()

        # Arianna 26/07/23: added the three options channel_name, channel_position, projection_type
        # Arianna 06/03/24: added the time points option
        channel_position = self.channel_position.text()
        projection_type = self.projection_type.currentText()
        if self.projection_mode_bestZ.isChecked():
            projection_zrange = 0
        elif self.projection_mode_around_bestZ.isChecked():
            projection_zrange = self.projection_mode_around_bestZ_zrange.value()
        elif self.projection_mode_fixed.isChecked():
            projection_zrange = (self.projection_mode_fixed_zmin.value(), self.projection_mode_fixed_zmax.value())
        elif self.projection_mode_all.isChecked():
            projection_zrange = None
        
        if self.time_mode_fixed.isChecked():
            timepoint_range = (self.time_mode_fixed_tmin.value(), self.time_mode_fixed_tmax.value())
        else:
            timepoint_range = None
        
        registration_method = self.registration_method.currentText()
        coalignment = self.coalignment_yn_A.isChecked()
        skip_crop_decision = self.skip_cropping_yn_A.isChecked()

        if channel_position == '': channel_position = 0
        else: channel_position = int(channel_position)

        if not check_inputs(image_paths):
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

        status = []
        error_messages = []
        arguments = []
        output_path = os.path.join(os.path.dirname(image_paths[0]), 'registration')
        os.makedirs(os.path.join(output_path, 'transf_matrices'), exist_ok=True)
        for image_path in image_paths:
            if os.path.isfile(image_path):
                # Set log and cursor info
                self.logger.info("Image %s", image_path)

                coalignment_images_list = []

                if coalignment:
                    unique_identifier = os.path.basename(image_path).split('_')[0]
                    for im in os.listdir(os.path.dirname(image_path)):
                        if unique_identifier in im and im != image_path:
                            coalignment_images_list.append(os.path.join(os.path.dirname(image_path),im))


                # collect arguments
                arguments.append((image_path, output_path, channel_position, projection_type, projection_zrange, timepoint_range, skip_crop_decision, coalignment_images_list,registration_method))

            else:
                self.logger.error("Unable to locate file %s", image_path)

        n_count = min(len(arguments), self.n_count.value())

        self.logger.info(f"Using: {n_count} cores to perform registration")
        if not arguments:
            return
        # Perform projection
        if len(arguments) == 1:
            try:
                f.registration_main(*arguments[0])
                status.append("Success")
                error_messages.append("")
            except Exception as e:
                status.append("Failed")
                error_messages.append(str(e))
                self.logger.exception("Registration failed")
        else:
            # we go parallel
            with concurrent.futures.ProcessPoolExecutor(max_workers=n_count) as executor:
                future_reg = {
                    executor.submit(f.registration_main, *args): args for args in arguments
                }
                for future in future_reg:
                    try:
                        image_path = future.result()
                        status.append("Success")
                        error_messages.append("")
                    except Exception as e:
                        status.append("Failed")
                        error_messages.append(str(e))
                        self.logger.exception("An exception occurred")
                    else:
                        self.logger.info(f" Image: {image_path} Done")


        # Restore cursor
        QApplication.restoreOverrideCursor()

        if any(s != 'Success' for s in status):
            msg = gf.StatusTableDialog('Warning', status, error_messages, image_paths)
            msg.exec_()

        # re-enable messagebox error handler
        if messagebox_error_handler is not None:
            logging.getLogger().addHandler(messagebox_error_handler)

        self.logger.info("Done")

    def projection_mode_fixed_zmin_changed(self, value):
        if self.projection_mode_fixed_zmax.value() < value:
            self.projection_mode_fixed_zmax.setValue(value)

    def projection_mode_fixed_zmax_changed(self, value):
        if self.projection_mode_fixed_zmin.value() > value:
            self.projection_mode_fixed_zmin.setValue(value)
    
    def time_mode_fixed_tmin_changed(self, value):
        if self.time_mode_fixed_tmax.value() < value:
            self.time_mode_fixed_tmax.setValue(value)

    def time_mode_fixed_tmax_changed(self, value):
        if self.time_mode_fixed_tmin.value() > value:
            self.time_mode_fixed_tmin.setValue(value)


class Align(gf.Page):
    def __init__(self):
        super().__init__()
        ####### Section Alignment #######
        label = QLabel("Input files to align using pre-existing registration matrices:")
        label2 = QLabel('(the corresponding matrices have to be in "image_path/registration/transf_matrices/" folder)')
        font = label2.font()
        font.setItalic(True)
        label2.setFont(font)
        self.imagetypes = ['.nd2', '.tif', '.tiff']
        self.image_listB = gf.FileListWidget(filetypes=self.imagetypes, filenames_filter='')
        self.skip_cropping_yn_B = QCheckBox("Do NOT crop aligned image")
        self.buttonB = QPushButton("Align")
        self.buttonB.clicked.connect(self.align)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(label)
        layout.addWidget(label2)
        groupbox = QGroupBox('')
        layout2 = QVBoxLayout()
        layout2.addWidget(self.image_listB)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
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
                return False
            for path in image_paths:
                if not os.path.isfile(path):
                    self.logger.error('Image not found\n' + path)
                    return False
            return True

        image_paths = self.image_listB.get_file_list()
        skip_crop_decision = self.skip_cropping_yn_B.isChecked()
        if not check_inputs(image_paths):
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
        for image_path in image_paths:
            if os.path.isfile(image_path):
                # Set log and cursor info
                self.logger.info("Image %s", image_path)
                QApplication.setOverrideCursor(QCursor(Qt.BusyCursor))
                QApplication.processEvents()
                # Perform projection
                try:
                    f.alignment_main(image_path, skip_crop_decision)
                    status.append("Success")
                    error_messages.append(None)
                except Exception as e:
                    status.append("Failed")
                    error_messages.append(str(e))
                    self.logger.exception("Alignment failed")
                # Restore cursor
                QApplication.restoreOverrideCursor()
                self.logger.info("Done")
            else:
                self.logger.error("Unable to locate file %s", image_path)

        if any(s != 'Success' for s in status):
            msg = gf.StatusTableDialog('Warning', status, error_messages, image_paths)
            msg.exec_()

        # re-enable messagebox error handler
        if messagebox_error_handler is not None:
            logging.getLogger().addHandler(messagebox_error_handler)


class Edit(gf.Page):
    def __init__(self):
        super().__init__()
        ####### Section Editing #######
        label = QLabel("Matrices to edit")
        label2 = QLabel('(double click on the transformation matrix to visualize it)')
        font = label2.font()
        font.setItalic(True)
        label2.setFont(font)
        self.matricestypes = ['.txt','.csv']
        self.matrices_list = gf.FileListWidget(filetypes=self.matricestypes, filenames_filter='')
        self.matrices_list.file_list_double_clicked.connect(self.display_matrix)
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
        groupbox = QGroupBox('')
        layout2 = QVBoxLayout()
        layout2.addWidget(self.matrices_list)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
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
                return False
            for path in transfmat_paths:
                if not os.path.isfile(path):
                    self.logger.error('Matrix not found\n' + path)
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

        transfmat_paths = self.matrices_list.get_file_list()
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


class ManualEdit(gf.Page):
    def __init__(self):
        super().__init__()

        self.imagetypes = ['.nd2', '.tif', '.tiff']
        self.matricestypes = ['.txt','.csv']

        ####### Section Manual Editing #######
        self.input_image = gf.DropFileLineEdit(filetypes=self.imagetypes)
        browse_image_button = QPushButton("Browse", self)
        browse_image_button.clicked.connect(self.browse_image)
        self.input_matrix = gf.DropFileLineEdit(filetypes=self.matricestypes)
        browse_matrix_button = QPushButton("Browse", self)
        browse_matrix_button.clicked.connect(self.browse_matrix)
        self.button_edit = QPushButton('Edit')
        self.button_edit.clicked.connect(self.edit)

        # Layout
        layout = QVBoxLayout()
        groupbox = QGroupBox("Input image (before registration)")
        layout2 = QHBoxLayout()
        layout2.addWidget(self.input_image)
        layout2.addWidget(browse_image_button, alignment=Qt.AlignCenter)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
        groupbox = QGroupBox("Matrix to edit")
        layout2 = QHBoxLayout()
        layout2.addWidget(self.input_matrix)
        layout2.addWidget(browse_matrix_button, alignment=Qt.AlignCenter)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
        layout.addWidget(self.button_edit, alignment=Qt.AlignCenter)
        self.window = QVBoxLayout(self.container)
        self.window.addLayout(layout)
        self.window.addStretch()

        self.logger = logging.getLogger(__name__)

    def browse_image(self):
        file_path, _ = QFileDialog.getOpenFileName(self, 'Select Files', filter='Images (' + ' '.join(['*' + x for x in self.imagetypes]) + ')')
        if file_path != '':
            self.input_image.setText(file_path)

    def browse_matrix(self):
        file_path, _ = QFileDialog.getOpenFileName(self, 'Select Files', filter='Transformation matrices (' + ' '.join(['*' + x for x in self.matricestypes]) + ')')
        if file_path != '':
            self.input_matrix.setText(file_path)

    def edit(self):
        def check_inputs(image_path, matrix_path):
            """
            Check if the inputs are valid
            Return: True if valid, False otherwise
            """
            if image_path == '':
                self.logger.error('Image missing')
                self.input_image.setFocus()
                return False
            if not os.path.isfile(image_path):
                self.logger.error('Image not found %s', image_path)
                self.input_image.setFocus()
                return False
            if matrix_path == '':
                self.logger.error('Matrix missing')
                self.input_matrix.setFocus()
                return False
            if not os.path.isfile(matrix_path):
                self.logger.error('Matrix not found %s', matrix_path)
                self.input_matrix.setFocus()
                return False
            return True

        image_path = self.input_image.text()
        matrix_path = self.input_matrix.text()

        if not check_inputs(image_path, matrix_path):
            return
        self.logger.info('Manually editing %s (image: %s', matrix_path, image_path)
        try:
            f.manual_edit_main(image_path, matrix_path)
        except Exception as e:
            self.logger.exception('Manual editing failed')

        self.logger.info("Done")


class Registration(QWidget):
    def __init__(self):
        super().__init__()

        window = QVBoxLayout(self)
        tabwizard = gf.TabWizard()

        tabwizard.addPage(Perform(), "Registration")
        tabwizard.addPage(Align(), "Alignment")
        tabwizard.addPage(Edit(), "Editing (batch)")
        tabwizard.addPage(ManualEdit(), "Editing (manual)")

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
