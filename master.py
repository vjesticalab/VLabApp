import sys
import os
from functools import partial
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QPixmap, QIcon, QFont
from PyQt5.QtWidgets import QApplication, QSpacerItem, QSizePolicy, QCheckBox, QFrame, QLabel, QPushButton, QVBoxLayout, QWidget, QTabWidget, QFormLayout, QLineEdit, QFileDialog

from modules.image_registration_module.registration import registration
from modules.image_registration_module.alignment import alignment
from modules.image_registration_module.registrationEditing import editing
from modules.groundtruth_generator_module.generator import generator_functions
from modules.segmentation_module.segmentation import segmentation
from modules.graph_analysis_module.graphAnalysis import analysis
from general import general_functions


class TabWizard(QTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tabBar().installEventFilter(self)

    def addPage(self, page, title):
        if not isinstance(page, Page):
            raise TypeError(f"{page} must be Page object")
        self.addTab(page, title)
        page.completeChanged.connect(self.nextPage)
    
    def addHomePage(self, page):
        tab_index = self.addTab(page, '')
        self.setTabIcon(tab_index, QIcon('support_files/home.svg'))
        self.setIconSize(QSize(12,12))
        page.completeChanged.connect(self.nextPage)

    def nextPage(self):
        next_index = self.currentIndex() + 1
        if next_index < self.count():
            self.setCurrentIndex(next_index)


class Page(QWidget):
    completeChanged = pyqtSignal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self.container = QWidget()
        lay = QVBoxLayout(self)
        lay.addWidget(self.container)


class Home(Page):
    def __init__(self):
        super().__init__()
        self.window = QFormLayout(self.container)
        self.title = QLabel('<b>HOME</b>', self)
        self.title.setFont(QFont('Arial', 18))
        self.title.setAlignment(Qt.AlignCenter)
        self.window.addRow(self.title)
        self.line = QFrame()
        self.line.setFrameShape(QFrame.HLine)
        self.window.addRow(self.line)

        self.text = QLabel('The VLabApplication is created with the aim of automating the cellular image analysis process, from the recording of the movies that come out of the microscope, to the tracking of the events within each time frame.\n\n\nThe application is in fact divided into several sub-sections that can be used consecutively or automatically:\n\n  - Image Registration\n\n  - GroundTruth Dataset Construction\n\n  - Image Segmentation\n\n  - Event Tracking', self)
        self.text.setWordWrap(True)
        self.window.addRow(self.text)

        
class Registration(Page):
    def __init__(self):
        super().__init__()
        self.window = QVBoxLayout(self.container)
        self.title = QLabel('<b>Image Registration</b>', self)
        self.title.setFont(QFont('.AppleSystemUIFont', 18))
        self.title.setAlignment(Qt.AlignCenter)
        self.window.addWidget(self.title)
        self.line = QFrame()
        self.line.setFrameShape(QFrame.HLine)
        self.line.setMinimumWidth(400)
        self.window.addWidget(self.line)

        ####### Section A #######
        self.window.addWidget(QLabel('<b>Calculate & Perform Registration</b>', self))
        self.buttonA1 = QPushButton("Individual image")
        self.buttonA1.setMinimumWidth(200)
        self.buttonA1.clicked.connect(partial(self.registration, 'singleFile'))
        self.window.addWidget(self.buttonA1, alignment=Qt.AlignCenter)
        self.buttonA2 = QPushButton("Folder of images")
        self.buttonA2.setMinimumWidth(200)
        self.buttonA2.clicked.connect(partial(self.registration, 'singleFolder'))
        self.window.addWidget(self.buttonA2, alignment=Qt.AlignCenter)
        self.buttonA3 = QPushButton("Collection of folders")
        self.buttonA3.setMinimumWidth(200)
        self.buttonA3.clicked.connect(partial(self.registration, 'multiFolder'))
        self.window.addWidget(self.buttonA3, alignment=Qt.AlignCenter)
        self.lineA = QFrame()
        self.lineA.setFrameShape(QFrame.HLine)
        self.lineA.setMinimumWidth(400)
        self.window.addWidget(self.lineA)
        
        ####### Section B #######
        self.window.addWidget(QLabel('<b>Align with Transformation Matrices</b>', self))
        self.buttonB1 = QPushButton("View aligned tyx image")
        self.buttonB1.setMinimumWidth(200)
        self.buttonB1.clicked.connect(partial(self.alignment, 'view'))
        self.window.addWidget(self.buttonB1, alignment=Qt.AlignCenter)
        self.buttonB2 = QPushButton("Align image or image set")
        self.buttonB2.setMinimumWidth(200)
        self.buttonB2.clicked.connect(partial(self.alignment, 'singleFile'))
        self.window.addWidget(self.buttonB2, alignment=Qt.AlignCenter)
        self.buttonB3 = QPushButton("Align folder of images")
        self.buttonB3.setMinimumWidth(200)
        self.buttonB3.clicked.connect(partial(self.alignment, 'singleFolder'))
        self.window.addWidget(self.buttonB3, alignment=Qt.AlignCenter)
        self.buttonB4 = QPushButton("Align collection of folders")
        self.buttonB4.setMinimumWidth(200)
        self.buttonB4.clicked.connect(partial(self.alignment, 'multiFolder'))
        self.window.addWidget(self.buttonB4, alignment=Qt.AlignCenter)
        self.lineB = QFrame()
        self.lineB.setFrameShape(QFrame.HLine)
        self.lineB.setMinimumWidth(400)
        self.window.addWidget(self.lineB)

        ####### Section C #######
        self.window.addWidget(QLabel('<b>Edit Transformation Matrices</b>', self))
        self.buttonC1 = QPushButton("Individual image")
        self.buttonC1.setMinimumWidth(200)
        self.buttonC1.clicked.connect(partial(self.editing, 'single'))
        self.window.addWidget(self.buttonC1, alignment=Qt.AlignCenter)
        self.buttonC2 = QPushButton("Folder of images")
        self.buttonC2.setMinimumWidth(200)
        self.buttonC2.clicked.connect(partial(self.editing, 'folder'))
        self.window.addWidget(self.buttonC2, alignment=Qt.AlignCenter)
        
    def registration(self, param):
        window = registration.Registration(param, parent=self)
        window.show()

    def alignment(self, param):
        window = alignment.Alignment(param, parent=self)
        window.show()

    def editing(self, param):
        window = editing.Editing(param, parent=self)
        window.show()


class GTGenerator(Page):
    def __init__(self):
        super().__init__()
        self.window = QFormLayout(self.container)
        self.title = QLabel('<b>Ground Truth Masks Generator</b>')
        self.title.setFont(QFont('Arial', 18))
        self.title.setAlignment(Qt.AlignCenter)
        self.window.addRow(self.title)
        self.line = QFrame()
        self.line.setFrameShape(QFrame.HLine)
        self.window.addRow(self.line)
        
        # Upload
        self.input = QLabel("<b>Step 1: Input path</b>")
        self.input.setFont(QFont('Arial', 16))
        self.window.addRow(self.input)
        self.window.addRow(QLabel("Select folder of images to process"))
        self.selected_folder1 = QLineEdit()
        self.selected_folder1.setMinimumWidth(300)
        self.browse_button1 = QPushButton("Browse", self)
        self.browse_button1.clicked.connect(self.browse_folder1)
        self.window.addRow(self.selected_folder1, self.browse_button1)
        self.line1 = QFrame()
        self.line1.setFrameShape(QFrame.HLine)
        self.window.addRow(self.line1)

        # Define path where to save
        self.output = QLabel("<b>Step 2: Output path</b>")
        self.output.setFont(QFont('Arial', 16))
        self.window.addRow(self.output)
        self.check_resfolder = QCheckBox("Save results into the save directory (new folder)")
        self.window.addRow(self.check_resfolder)
        self.window.addRow(QLabel("\nOR\n\nselect another folder where to save results"))
        self.selected_folder2 = QLineEdit()
        self.selected_folder2.setMinimumWidth(300)
        self.browse_button2 = QPushButton("Browse", self)
        self.browse_button2.clicked.connect(self.browse_folder2)
        self.window.addRow(self.selected_folder2, self.browse_button2)
        self.line2 = QFrame()
        self.line2.setFrameShape(QFrame.HLine)
        self.window.addRow(self.line2)

        # Submit
        self.submit_button = QPushButton("Submit", self)
        self.submit_button.clicked.connect(self.process_input)
        self.window.addWidget(self.submit_button)
        self.submission_num_failed = 0
        self.label_error = None
              
    def browse_folder1(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        self.selected_folder1.setText(folder_path)

    def browse_folder2(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        self.selected_folder2.setText(folder_path)
    
    def process_input(self):
        path = self.selected_folder1.text()
        result_path = self.selected_folder2.text()
        result_path_checked = self.check_resfolder.isChecked()
        # Input path
        if path == '':
            self.submission_num_failed += 1
            self.label_error = general_functions.error_empty(self.submission_num_failed, self.selected_folder1, self.window)
        # Output path
        elif not result_path_checked and result_path == '':
            self.submission_num_failed += 1
            self.label_error = general_functions.error_empty(self.submission_num_failed, self.selected_folder2, self.window)  
        else:
            if self.label_error:
                self.window.removeRow(self.label_error)
            if result_path_checked:
                result_path = path
            result_path = result_path + '/groundtruth_masks_generated/'
            if not os.path.exists(result_path):
                os.makedirs(result_path)
            generator_functions.main(path, result_path)
   

class Segmentation(Page):
    def __init__(self):
        super().__init__()
        self.window = QVBoxLayout(self.container)
        self.title = QLabel('<b>Image Segmentation</b>', self)
        self.title.setFont(QFont('Arial', 18))
        self.title.setAlignment(Qt.AlignCenter)
        self.window.addWidget(self.title)
        self.line = QFrame()
        self.line.setFrameShape(QFrame.HLine)
        self.line.setMinimumWidth(400)
        self.window.addWidget(self.line)
        
        self.buttonA1 = QPushButton("Individual image")
        self.buttonA1.setMinimumWidth(200)
        self.buttonA1.clicked.connect(partial(self.segmentation, 'singleFile'))
        self.window.addWidget(self.buttonA1, alignment=Qt.AlignCenter)

        self.buttonA2 = QPushButton("Folder of images")
        self.buttonA2.setMinimumWidth(200)
        self.buttonA2.clicked.connect(partial(self.segmentation, 'singleFolder'))
        self.window.addWidget(self.buttonA2, alignment=Qt.AlignCenter)

        self.buttonA3 = QPushButton("Collection of folders")
        self.buttonA3.setMinimumWidth(200)
        self.buttonA3.clicked.connect(partial(self.segmentation, 'multiFolder'))
        self.window.addWidget(self.buttonA3, alignment=Qt.AlignCenter)

        self.window.addStretch()

        """
        self.selection_type = ''
        
        # Upload
        self.window.addRow(QLabel("Select individual image"))
        self.selected_file = QLineEdit()
        self.browse_button = QPushButton("Browse", self)
        self.browse_button.clicked.connect(self.browse_file)
        self.window.addRow(self.selected_file, self.browse_button)

        self.window.addRow(QLabel("Folder of images"))
        self.selected_folder1 = QLineEdit()
        self.browse_button1 = QPushButton("Browse", self)
        self.browse_button1.clicked.connect(self.browse_folder1)
        self.window.addRow(self.selected_folder1, self.browse_button1)
        
        self.window.addRow(QLabel("Collection of folders"))
        self.displayA = QLabel("Insert here a list of paths to folders. \nEach folder MUST be written in a new line. \nSpace or slash characters at the end of the folder will confuse the script!")
        self.displayA.setFont(QFont('Arial', 10))
        self.window.addRow(self.displayA)
        self.displayB = QLabel("<i>Example: /Users/admin/Desktop/20220216_P0001_E0008_U002</i>")
        self.window.addRow(self.displayB)
        self.folders_list = QTextEdit()
        self.window.addRow(self.folders_list)
        
        # Tracking graphs
        self.graph = QLabel("<i>Note that the tracking graphs are created by default - check the box to skip this step</i>")
        self.no_graph_generation = QCheckBox("Do NOT create the tracking graphs")

        # Define path where to save
        self.check_resfolder = QCheckBox("Save results into the save directory (new folder)")
        self.window.addRow(self.check_resfolder)
        self.window.addRow(QLabel("OR select another folder where to save results"))
        self.results_folder = QLineEdit()
        self.browse_results = QPushButton("Browse", self)
        self.browse_results.clicked.connect(self.browse_folder_results)
        self.window.addRow(self.results_folder, self.browse_results)
        self.line2 = QFrame()
        self.line2.setFrameShape(QFrame.HLine)
        self.window.addRow(self.line2)

        # Submit
        self.submit_button = QPushButton("Submit", self)
        self.submit_button.clicked.connect(partial(self.segmentation, self.selection_type))
        self.window.addRow(self.submit_button)
        self.submission_num_failed = 0
        self.label_error = None
        
    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File")
        self.selected_file.setText(file_path)
        self.selection_type = 'singleFile'

    def browse_folder1(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        self.selected_folder1.setText(folder_path)
        self.selection_type = 'singleFolder'
    
    def browse_folder_results(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        self.results_folder.setText(folder_path)"""
            
        
    def segmentation(self, param):
        window = segmentation.Segmentation(param, parent=self)
        window.show()     


class Tracking(Page):
    def __init__(self):
        super().__init__()
        self.window = QVBoxLayout(self.container)

        self.title = QLabel('<b>Image Tracking</b>', self)
        self.title.setFont(QFont('Arial', 18))
        self.title.setAlignment(Qt.AlignCenter)
        self.window.addWidget(self.title)
        self.line = QFrame()
        self.line.setFrameShape(QFrame.HLine)
        self.line.setMinimumWidth(400)
        self.window.addWidget(self.line)
        
        self.buttonA1 = QPushButton("Filter")
        self.buttonA1.setMinimumWidth(200)
        self.buttonA1.clicked.connect(partial(self.filter))
        self.window.addWidget(self.buttonA1, alignment=Qt.AlignCenter)

        self.buttonA2 = QPushButton("Fusions")
        self.buttonA2.setMinimumWidth(200)
        self.buttonA2.clicked.connect(partial(self.fusions))
        self.window.addWidget(self.buttonA2, alignment=Qt.AlignCenter)

        self.buttonA3 = QPushButton("Divisions")
        self.buttonA3.setMinimumWidth(200)
        self.buttonA3.clicked.connect(partial(self.divisions))
        self.window.addWidget(self.buttonA3, alignment=Qt.AlignCenter)

        self.window.addStretch()
             
    def filter(self):
        self.filter_window = analysis.Filter()
        self.filter_window.move(700,0)
        self.filter_window.show()

    def fusions(self):
        self.fusion_window = analysis.Fusions()
        self.fusion_window.move(700,0)
        self.fusion_window.show()

    def divisions(self):
        self.division_window = analysis.Divisions()
        self.division_window.move(700,0)
        self.division_window.show()


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        window = QVBoxLayout(self)
        self.image = QLabel()
        self.image.setPixmap(QPixmap("support_files/Vlab_icon_50x50-01.png"))
        self.image.setAlignment(Qt.AlignCenter)
        window.addWidget(self.image)
        tabwizard = TabWizard()
        window.addWidget(tabwizard)
        tabwizard.addHomePage(Home())
        tabwizard.addPage(Registration(), "Registration")
        tabwizard.addPage(GTGenerator(), "GroundTruth")
        tabwizard.addPage(Segmentation(), "Segmentation")
        tabwizard.addPage(Tracking(), "Tracking")
        
        self.quit_button = QPushButton("Quit", self)
        self.quit_button.clicked.connect(self.close)
        self.quit_button.setStyleSheet("background: darkred;")
        window.addWidget(self.quit_button, alignment=Qt.AlignRight)
    

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    w.setFixedWidth(500)
    w.setFixedHeight(720)
    sys.exit(app.exec_())