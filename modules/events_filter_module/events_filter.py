import os
import logging
from PyQt5.QtWidgets import QGridLayout, QCheckBox, QLabel, QSpinBox, QFileDialog, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QGroupBox, QRadioButton, QApplication, QLineEdit, QFormLayout
from PyQt5.QtCore import Qt, QRegExp
from PyQt5.QtGui import QCursor, QRegExpValidator
from modules.events_filter_module import events_filter_functions as f
from general import general_functions as gf


class GraphEventFilter(QWidget):
    def __init__(self):
        super().__init__()

        self.output_suffix = 'gf.output_suffixes['events_filter']


        # Browse segmentation mask
        self.input_mask = gf.DropFileLineEdit(filetypes=gf.imagetypes)
        browse_button1 = QPushButton("Browse", self)
        browse_button1.clicked.connect(self.add_mask)

        # Browse cell graph
        self.input_graph = gf.DropFileLineEdit(filetypes=gf.graphtypes)
        browse_button2 = QPushButton("Browse", self)
        browse_button2.clicked.connect(self.add_graph)

        # output folder
        self.use_input_folder = QRadioButton("Use input mask and graph folder")
        self.use_input_folder.setChecked(True)
        self.use_input_folder.toggled.connect(self.update_output_filename_label)
        self.use_custom_folder = QRadioButton("Use custom folder")
        self.use_custom_folder.setChecked(False)
        self.use_custom_folder.toggled.connect(self.update_output_filename_label)
        self.output_folder = gf.DropFolderLineEdit()
        self.output_folder.textChanged.connect(self.update_output_filename_label)
        browse_button3 = QPushButton("Browse", self)
        browse_button3.clicked.connect(self.browse_output)
        self.output_folder.setVisible(self.use_custom_folder.isChecked())
        browse_button3.setVisible(self.use_custom_folder.isChecked())
        self.use_custom_folder.toggled.connect(self.output_folder.setVisible)
        self.use_custom_folder.toggled.connect(browse_button3.setVisible)
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
        self.output_filename_label3 = QLineEdit()
        self.output_filename_label3.setFrame(False)
        self.output_filename_label3.setEnabled(False)
        self.output_filename_label3.textChanged.connect(self.output_filename_label3.setToolTip)

        # Browse type of event
        self.button_fusion = QRadioButton("Fusion")
        self.button_fusion.setChecked(True)
        self.button_division = QRadioButton("Division")

        # Event time correction
        self.time_correction = QCheckBox("Correct fusion time")
        self.time_correction.setEnabled(self.button_fusion.isChecked())
        self.button_fusion.toggled.connect(self.time_correction.setEnabled)
        # Browse channel image
        self.input_chimage = gf.DropFileLineEdit(filetypes=gf.imagetypes)
        browse_button4 = QPushButton("Browse", self)
        browse_button4.clicked.connect(self.add_chimage)
        self.input_chimage.setEnabled(self.time_correction.isChecked())
        browse_button4.setEnabled(self.time_correction.isChecked())
        self.time_correction.toggled.connect(self.input_chimage.setEnabled)
        self.time_correction.toggled.connect(browse_button4.setEnabled)

        # Save single crops
        self.cropsave = QCheckBox("Save")
        self.cropsave.setEnabled(self.button_fusion.isChecked())
        self.button_fusion.toggled.connect(self.cropsave.setEnabled)
        # Browse channel image to crop and BF, not mandatories
        self.input_chcropimage = gf.DropFileLineEdit(filetypes=gf.imagetypes)
        browse_button5 = QPushButton("Browse", self)
        browse_button5.clicked.connect(self.add_chimage)
        self.input_chcropimage.setEnabled(self.cropsave.isChecked())
        browse_button5.setEnabled(self.cropsave.isChecked())
        self.cropsave.toggled.connect(self.input_chcropimage.setEnabled)
        self.cropsave.toggled.connect(browse_button5.setEnabled)
        self.input_BFimage = gf.DropFileLineEdit(filetypes=gf.imagetypes)
        browse_button6 = QPushButton("Browse", self)
        browse_button6.clicked.connect(self.add_chimage)
        self.input_BFimage.setEnabled(self.cropsave.isChecked())
        browse_button6.setEnabled(self.cropsave.isChecked())
        self.cropsave.toggled.connect(self.input_BFimage.setEnabled)
        self.cropsave.toggled.connect(browse_button6.setEnabled)
        
        # Number timepoints before and after event
        label_before = QLabel("Number of timepoints before event")
        self.spinBox_before = QSpinBox(self)
        self.spinBox_before.setRange(0, 40)
        self.spinBox_before.setValue(5)
        label_after = QLabel("Number of timepoints after event")
        self.spinBox_after = QSpinBox(self)
        self.spinBox_after.setRange(0, 40)
        self.spinBox_after.setValue(5)

        self.submit_button = QPushButton("Submit", self)
        self.submit_button.clicked.connect(self.submit)

        # Layout
        layout = QVBoxLayout()
        groupbox = QGroupBox("Input files")
        layout2 = QVBoxLayout()
        layout2.addWidget(QLabel("Segmentation mask:"))
        layout3 = QHBoxLayout()
        layout3.addWidget(self.input_mask)
        layout3.addWidget(browse_button1, alignment=Qt.AlignCenter)
        layout2.addLayout(layout3)
        layout2.addWidget(QLabel("Cell tracking graph:"))
        layout3 = QHBoxLayout()
        layout3.addWidget(self.input_graph)
        layout3.addWidget(browse_button2, alignment=Qt.AlignCenter)
        layout2.addLayout(layout3)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
        groupbox = QGroupBox("Output")
        layout2 = QVBoxLayout()
        layout2.addWidget(QLabel("Folder:"))
        layout2.addWidget(self.use_input_folder)
        layout2.addWidget(self.use_custom_folder)
        layout3 = QHBoxLayout()
        layout3.addWidget(self.output_folder)
        layout3.addWidget(browse_button3, alignment=Qt.AlignCenter)
        layout2.addLayout(layout3)
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
        layout4.addWidget(self.output_filename_label3)
        layout3.addRow("Filename:", layout4)
        layout2.addLayout(layout3)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        groupbox_options = QGroupBox("Options")
        layout_options = QVBoxLayout()
        groupbox = QGroupBox("Type of event")
        layout2 = QGridLayout()
        layout2.addWidget(self.button_fusion, 0, 0)
        layout2.addWidget(self.button_division, 0, 1)
        groupbox.setLayout(layout2)
        layout_options.addWidget(groupbox)

        groupbox = QGroupBox("Fusion time correction")
        layout2 = QVBoxLayout()
        layout2.addWidget(self.time_correction)
        layout3 = QHBoxLayout()
        layout3.addWidget(QLabel("Fusion marker image :"))
        layout3.addWidget(self.input_chimage)
        layout3.addWidget(browse_button4, alignment=Qt.AlignCenter)
        layout2.addLayout(layout3)
        groupbox.setLayout(layout2)
        layout_options.addWidget(groupbox)

        groupbox = QGroupBox("Timepoints")
        layout2 = QGridLayout()
        layout2.addWidget(label_before, 0, 0, 1, 2)
        layout2.addWidget(self.spinBox_before, 0, 2, 1, 1)
        layout2.addWidget(label_after, 1, 0, 1, 2)
        layout2.addWidget(self.spinBox_after, 1, 2, 1, 1)
        groupbox.setLayout(layout2)
        layout_options.addWidget(groupbox)

        groupbox = QGroupBox("Save single-cropped fusion images")
        layout2 = QVBoxLayout()
        layout2.addWidget(self.cropsave)
        layout3 = QHBoxLayout()
        layout3.addWidget(QLabel("Channel to crop :"))
        layout3.addWidget(self.input_chcropimage)
        layout3.addWidget(browse_button5, alignment=Qt.AlignCenter)
        layout3.addWidget(QLabel("BF :"))
        layout3.addWidget(self.input_BFimage)
        layout3.addWidget(browse_button6, alignment=Qt.AlignCenter)
        layout2.addLayout(layout3)
        groupbox.setLayout(layout2)
        layout_options.addWidget(groupbox)

        groupbox_options.setLayout(layout_options)
        layout.addWidget(groupbox_options)

        layout.addWidget(self.submit_button, alignment=Qt.AlignCenter)
        self.setLayout(layout)

        self.logger = logging.getLogger(__name__)

        self.update_output_filename_label()

    def add_mask(self):
        # Add the selected mask as input
        file_path, _ = QFileDialog.getOpenFileName(self, 'Select Files', filter='Images ('+' '.join(['*'+x for x in gf.imagetypes])+')')
        self.input_mask.setText(file_path)

    def add_graph(self):
        # Add the selected graph as input
        file_path, _ = QFileDialog.getOpenFileName(self, 'Select Files', filter='Cell tracking graphs ('+' '.join(['*'+x for x in gf.graphtypes])+')')
        self.input_graph.setText(file_path)

    def add_chimage(self):
        # Add the selected mask as input
        file_path, _ = QFileDialog.getOpenFileName(self, 'Select Files', filter='Images ('+' '.join(['*'+x for x in gf.imagetypes])+')')
        self.input_chimage.setText(file_path)

    def update_output_filename_label(self):
        if self.use_input_folder.isChecked():
            output_path = "<input folder>"
        else:
            output_path = self.output_folder.text().rstrip("/")

        self.output_filename_label1.setText(os.path.join(output_path,"<input basename>" + self.output_suffix + self.output_user_suffix.text() + ".csv"))
        self.output_filename_label2.setText(os.path.join(output_path,"<input basename>" + self.output_suffix + self.output_user_suffix.text() + ".ome.tif"))
        self.output_filename_label3.setText(os.path.join(output_path,"<input basename>" + self.output_suffix + self.output_user_suffix.text() + ".graphmlz"))

    def browse_output(self):
        # Browse folders in order to choose the output one
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        self.output_folder.setText(folder_path)

    def submit(self):
        """
        Retrieve the input parameters and process them in f.main()
        """
        mask_path = self.input_mask.text()
        graph_path = self.input_graph.text()
        if self.time_correction.isChecked():
            chimage_path = self.input_chimage.text()
        else:
            chimage_path = None
        tp_before = int(self.spinBox_before.text())
        tp_after = int(self.spinBox_after.text())

        # Check inputs
        if mask_path == '':
            self.logger.error('Segmentation mask missing')
            self.input_mask.setFocus()
            return
        if not os.path.isfile(mask_path):
            self.logger.error('Segmentation mask: not a valid file')
            self.input_mask.setFocus()
            return
        if graph_path == '':
            self.logger.error('Cell tracking graph missing')
            self.input_graph.setFocus()
            return
        if not os.path.isfile(graph_path):
            self.logger.error('Cell tracking graph: not a valid file')
            self.input_graph.setFocus()
            return
        if self.time_correction.isChecked():
            if chimage_path == '':
                self.logger.error('Magnified image missing')
                self.input_mask.setFocus()
                return
            if not os.path.isfile(chimage_path):
                self.logger.error('Magnified image: not a valid file')
                self.input_mask.setFocus()
                return
        if self.output_folder.text() == '' and not self.use_input_folder.isChecked():
            self.logger.error('Output folder missing')
            self.output_folder.setFocus()
            return

        # Set output_path
        if self.use_input_folder.isChecked():
            output_path = os.path.dirname(mask_path)
        else:
            output_path = self.output_folder.text()
        user_suffix = self.output_user_suffix.text()
        output_basename = gf.splitext(os.path.basename(mask_path))[0] + self.output_suffix + user_suffix
        self.logger.info("Event filtering (mask %s, graph %s)", mask_path, graph_path)

        # Set event
        if self.button_fusion.isChecked():
            event = 'fusion'
        elif self.button_division.isChecked():
            event = 'division'
            

        QApplication.setOverrideCursor(QCursor(Qt.BusyCursor))
        QApplication.processEvents()
        try:
            f.main(mask_path, graph_path, event, self.time_correction.isChecked(), chimage_path, tp_before, tp_after, self.cropsave.isChecked(), self.input_chcropimage.text(), self.input_BFimage.text(), output_path, output_basename)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            self.logger.error(str(e))
            raise e
        QApplication.restoreOverrideCursor()

        self.logger.info("Done")
