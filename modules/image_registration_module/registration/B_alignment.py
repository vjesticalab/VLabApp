import os
import logging
from PyQt5.QtWidgets import QTextEdit, QMainWindow, QLabel, QPushButton, QListWidget, QFileDialog, QVBoxLayout, QWidget, QLineEdit, QCheckBox, QMessageBox, QFrame
from PyQt5.QtCore import Qt
import napari
from general import general_functions as gf
from modules.image_registration_module.registration import registration_functions as f

class View(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Files alignment with matrices")
        
        self.display1 = QLabel('<b>Step1:</b> Select folder')    
        self.display1.setTextFormat(Qt.RichText)
        self.selected_folder = QLineEdit()         
        self.browse_button = QPushButton("Browse", clicked=self.browse_folder)

        self.display2 = QLabel('<b>Step2:</b> Double click on the image file to have it registered if matrix is available.')        
        self.display2.setTextFormat(Qt.RichText)
        
        self.images_list = QListWidget()
        self.images_list.itemDoubleClicked.connect(self.click)
        
        self.display3 = QLabel("<i>\nNote that cropping is performed by default. Checkbox to skip cropping.</i>")
        self.skip_cropping_yn = QCheckBox("Do NOT crop aligned image")
        
        self.quit_button = QPushButton("Quit", self)
        self.quit_button.clicked.connect(self.parent.close)
        self.quit_button.setStyleSheet("background: darkred;")
        
        self.line = QFrame()
        self.line.setFrameShape(QFrame.HLine)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.display1)
        layout.addWidget(self.selected_folder)
        layout.addWidget(self.browse_button)
        layout.addWidget(self.display2)
        layout.addWidget(self.images_list)
        layout.addWidget(self.display3)
        layout.addWidget(self.skip_cropping_yn)
        layout.addWidget(self.line) 
        layout.addWidget(self.quit_button)
        self.setLayout(layout)

    def browse_folder(self):
        self.folder_path = QFileDialog.getExistingDirectory()
        self.selected_folder.setText(self.folder_path)
        self.images_list.clear()
        
        files = gf.extract_suitable_files(os.listdir(self.folder_path))
        for file in files:
            self.images_list.addItem(file)

        if self.folder_path.endswith('/'):
            self.folder_path = self.folder_path[:-1]

        self.inventory = f.image_matrix_correspondance(self.folder_path, 'imageFile')


    def click(self, item):
        image_name = item.text()
        skip_crop_decision = self.skip_cropping_yn.isChecked()

        f.view_main(self.folder_path, image_name, self.inventory, skip_crop_decision)


class SingleFile(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Files alignment with matrices")
        
        self.display1 = QLabel('Step1: \tSelect folder')    
        self.selected_folder = QLineEdit()         
        self.browse_button = QPushButton("Browse", clicked=self.browse_folder)

        self.display2 = QLabel('<b>Option A:</b> Double click on the image file to register it if the matrix is available.')        
        self.display2.setTextFormat(Qt.RichText)
        
        self.images_list = QListWidget()
        self.images_list.itemDoubleClicked.connect(self.click_image)

        self.display3 = QLabel('<b>Option B:</b> Double click on transformationMatrix to register all files with the same basename.')        
        self.display3.setTextFormat(Qt.RichText)
        self.transf_mat_list = QListWidget()
        self.transf_mat_list.itemDoubleClicked.connect(self.click_matrix)
        
        self.display4 = QLabel("<i>\nNote that cropping is performed by default. Checkbox to skip cropping.</i>")
        self.skip_cropping_yn = QCheckBox("Do NOT crop aligned image")
        
        self.quit_button = QPushButton("Quit", self)
        self.quit_button.clicked.connect(self.parent.close)
        self.quit_button.setStyleSheet("background: darkred;")
        
        self.line = QFrame()
        self.line.setFrameShape(QFrame.HLine)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.display1)
        layout.addWidget(self.selected_folder)
        layout.addWidget(self.browse_button)
        layout.addWidget(self.display2)
        layout.addWidget(self.images_list)
        layout.addWidget(self.display3)
        layout.addWidget(self.transf_mat_list)
        layout.addWidget(self.display4)
        layout.addWidget(self.skip_cropping_yn)  
        layout.addWidget(self.line)      
        layout.addWidget(self.quit_button)
        self.setLayout(layout)

    def browse_folder(self):
        self.folder_path = QFileDialog.getExistingDirectory()
        self.selected_folder.setText(self.folder_path)
        self.images_list.clear()
        self.transf_mat_list.clear()
        
        imageFiles = gf.extract_suitable_files(os.listdir(self.folder_path))
        for file in imageFiles:
            self.images_list.addItem(file)
        self.imageFile_inventory = f.image_matrix_correspondance(self.folder_path, 'imageFile')

        transfMatFiles = f.extract_transfMat(os.listdir(self.folder_path))
        for file in transfMatFiles:
            self.transf_mat_list.addItem(file) 
        self.transfMat_inventory = f.image_matrix_correspondance(self.folder_path, 'transfMat')


    def click_image(self, item):
        skip_crop_decision = self.skip_cropping_yn.isChecked()
        selected_file = item.text()
        f.alignment_main('imageFile', self.folder_path+'/', self.imageFile_inventory, selected_file, skip_crop_decision)

    def click_matrix(self, item):
        skip_crop_decision = self.skip_cropping_yn.isChecked()
        selected_file = item.text()
        f.alignment_main('transfMat', self.folder_path+'/', self.transfMat_inventory, selected_file, skip_crop_decision)


class SingleFolder(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Input Form")
        
        self.display1 = QLabel("Step1: Select the folder to process")
        self.selected_folder = QLineEdit()
        self.browse_button = QPushButton("Browse", clicked=self.browse_folder)
        self.submit_button = QPushButton("Submit", clicked=self.process_input)
        
        self.display2 = QLabel("<i>\nNote that cropping is performed by default. Checkbox to skip cropping.</i>")
        self.skip_cropping_yn = QCheckBox("Do NOT crop aligned image")
        
        self.quit_button = QPushButton("Quit", self)
        self.quit_button.clicked.connect(self.parent.close)
        self.quit_button.setStyleSheet("background: darkred;")
        
        self.line = QFrame()
        self.line.setFrameShape(QFrame.HLine)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.display1)
        layout.addWidget(self.selected_folder)
        layout.addWidget(self.browse_button)
        layout.addWidget(self.display2)
        layout.addWidget(self.skip_cropping_yn) 
        layout.addWidget(self.submit_button)
        layout.addWidget(self.line) 
        layout.addWidget(self.quit_button)
        self.setLayout(layout)


    def browse_folder(self):
        self.folder_path = QFileDialog.getExistingDirectory()
        self.selected_folder.setText(self.folder_path)


    def process_input(self):
        skip_crop_decision = self.skip_cropping_yn.isChecked()
        folder_path = self.selected_folder.text()
        
        if os.path.isdir(folder_path):
            if folder_path.endswith('/'):
                folder_path = folder_path[:-1]
            imageFile_inventory = f.image_matrix_correspondance(folder_path, 'imageFile')
            for file in imageFile_inventory.keys():
                f.alignment_main('imageFile', folder_path, imageFile_inventory, file, skip_crop_decision)
        else:
            logging.getLogger(__name__).error('Folder not found.\nPlease select an existing folder')


class MultiFolder(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Multiple folders alignment with matrices")
        
        self.display1 = QLabel("Step1: \tInsert a list of paths to folders that need to be aligned. \n\tEach folder MUST be written in a new line. \n\tSpace or slash characters at the end of the folder will confuse the script!")
        self.display1b = QLabel("<i>/Users/admin/Desktop/20220216_P0001_E0008_U002</i>")
        self.display1b.setTextFormat(Qt.RichText)
        self.folders_list = QTextEdit()
        
        self.display2 = QLabel("<i>\nNote that cropping is performed by default. Checkbox to skip cropping.</i>")
        self.skip_cropping_yn = QCheckBox("Do NOT crop aligned image")
        
        self.submit_button = QPushButton("Submit", self)
        self.submit_button.clicked.connect(self.process_input)
        
        self.quit_button = QPushButton("Quit", self)
        self.quit_button.clicked.connect(self.parent.close)
        self.quit_button.setStyleSheet("background: darkred;")
        
        self.line = QFrame()
        self.line.setFrameShape(QFrame.HLine)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.display1)
        layout.addWidget(self.display1b)
        layout.addWidget(self.folders_list)
        layout.addWidget(self.display2)
        layout.addWidget(self.skip_cropping_yn) 
        layout.addWidget(self.submit_button)
        layout.addWidget(self.line) 
        layout.addWidget(self.quit_button)
        self.setLayout(layout)

    def process_input(self):
        skip_crop_decision = self.skip_cropping_yn.isChecked()
        folder_list_text = self.folders_list.toPlainText()
        folder_list = folder_list_text.split('\n')

        for folder_path in folder_list:
            if os.path.isdir(folder_path):
                if folder_path.endswith('/'):
                    folder_path = folder_path[:-1]
                imageFile_inventory = f.image_matrix_correspondance(folder_path, 'imageFile')
                for file in imageFile_inventory.keys():
                    f.alignment_main('imageFile', folder_path, imageFile_inventory, file, skip_crop_decision)
            else:
                logging.getLogger(__name__).error('Folder not found.\nFolder '+folder_path+' does not exist.')


class Alignment(QMainWindow):
    def __init__(self, param, parent=None):
        super(Alignment, self).__init__(parent)
        if param == 'view':
            form = View(self)
            self.setCentralWidget(form)
        elif param == 'singleFile':
            form = SingleFile(self)
            self.setCentralWidget(form)
        elif param == 'singleFolder':
            form = SingleFolder(self)
            self.setCentralWidget(form)
        elif param == 'multiFolder':
            form = MultiFolder(self)
            self.setCentralWidget(form)