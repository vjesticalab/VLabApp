import os
from PyQt5.QtWidgets import QTextEdit, QMainWindow, QLabel, QPushButton, QListWidget, QFileDialog, QVBoxLayout, QWidget, QLineEdit, QCheckBox, QMessageBox, QFrame
from PyQt5.QtCore import Qt
from modules.image_registration_module.alignment import alignment_functions as f
import napari
from general import general_functions as gf

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
        self.images_list.itemDoubleClicked.connect(self.image_script)
        
        self.display3 = QLabel("<i>\nNote that cropping is performed by default. Checkbox to skip cropping.</i>")
        self.skip_cropping_yn = QCheckBox("Do NOT crop aligned image")
        
        self.quit_button = QPushButton("Quit", self)
        self.quit_button.clicked.connect(self.parent.close)
        
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
        
        imageFiles = gf.extract_suitable_files(os.listdir(self.folder_path))
        for file in imageFiles:
            self.images_list.addItem(file)

        # !!! TO DO adding folder of the txt files
        # lets do that with pathsInventory then!
        # before:   self.imageFile_inventory = gf.build_dictionary(self.folder_path, 'imageFile')
        self.imageFile_inventory = gf.build_dictionary(self.folder_path, 'imageFile')


    def image_script(self, item):
        imageFile_single = item.text()
        imageFile_single_path = os.path.join(self.folder_path,imageFile_single)
        if len(self.imageFile_inventory[imageFile_single])<1:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Critical)
            msg.setText("Error")
            msg.setInformativeText('No transformation matrix available')
            msg.setWindowTitle("Error")
            msg.show()
            print('\nNo transformation matrix available')
        
        else:
            skip_crop_decision = self.skip_cropping_yn.isChecked()                        
            transfMat_name = self.imageFile_inventory[imageFile_single][0]
            transfMat_single_path=os.path.join(self.folder_path,transfMat_name)

            # Open transformation matrix and imagefile
            transfMat_load = gf.read_transfMat(transfMat_single_path)
            image_load, axes_inventory = gf.open_suitable_files(imageFile_single_path)
            # Example of axes_inventory = {'T': [0, 120], 'Z': [1, 3], 'C': [2, 2], 'Y': [3, 275], 'X': [4, 390]}
            if 'C' in axes_inventory.keys() and 'Z' in axes_inventory.keys():
                for c in range(axes_inventory['C'][1]):
                    for z in range(axes_inventory['Z'][1]):
                        image_registered = gf.register_with_tmat_multiD(transfMat_load, image_load[:,z,c,:,:], 1,2, skip_decision=skip_crop_decision) 
                viewer = napari.Viewer()
                for c in range(axes_inventory['C'][1]):
                    viewer.add_image(image_load[:,:,c,:,:], name="Channel "+str(c), blending="additive")
            elif 'C' in axes_inventory.keys():
                for c in range(axes_inventory['C'][1]):
                    image_registered = gf.register_with_tmat_multiD(transfMat_load, image_load[:,c,:,:], 1,2, skip_decision=skip_crop_decision) 
                viewer = napari.Viewer()
                for c in range(axes_inventory['C'][1]):
                    viewer.add_image(image_load[:,:,c,:,:], name="Channel "+str(c), blending="additive")
            elif 'Z' in axes_inventory.keys():
                for z in range(axes_inventory['Z'][1]):
                    image_registered = gf.register_with_tmat_multiD(transfMat_load, image_load[:,z,:,:], 1,2, skip_decision=skip_crop_decision)    
                viewer = napari.view_image(image_registered)    
            else:
                image_registered = gf.register_with_tmat_multiD(transfMat_load, image_load, 1,2, skip_decision=skip_crop_decision) 
                viewer = napari.view_image(image_registered)


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
        self.images_list.itemDoubleClicked.connect(self.image_script)

        self.display3 = QLabel('<b>Option B:</b> Double click on transformationMatrix to register all files with the same basename.')        
        self.display3.setTextFormat(Qt.RichText)
        self.transf_mat_list = QListWidget()
        self.transf_mat_list.itemDoubleClicked.connect(self.transfMat_script)
        
        self.display4 = QLabel("<i>\nNote that cropping is performed by default. Checkbox to skip cropping.</i>")
        self.skip_cropping_yn = QCheckBox("Do NOT crop aligned image")
        
        self.quit_button = QPushButton("Quit", self)
        self.quit_button.clicked.connect(self.parent.close)
        
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

        transfMatFiles = gf.extract_transfMat(os.listdir(self.folder_path))
        for file in transfMatFiles:
            self.transf_mat_list.addItem(file) 
        
        self.transfMat_inventory = gf.build_dictionary(self.folder_path, 'transfMat')
        
        self.imageFile_inventory = gf.build_dictionary(self.folder_path, 'imageFile')


    def image_script(self, item):
        imageFile_single = item.text()
        if len(self.imageFile_inventory[imageFile_single]) < 1:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Critical)
            msg.setText("Error")
            msg.setInformativeText('No transformation matrix available')
            msg.setWindowTitle("Error")
            msg.show()
            print('\nNo transformation matrix available')

        else:
            skip_crop_decision = self.skip_cropping_yn.isChecked()
            transfMat_name = self.imageFile_inventory[imageFile_single][0]
            current_inventory={}
            current_inventory[transfMat_name]= [imageFile_single]
            print('\nCurrent inventory:', current_inventory, skip_crop_decision)
            f.alignment_main(self.folder_path+'/', current_inventory, skip_crop_decision)

    def transfMat_script(self, item):
        skip_crop_decision = self.skip_cropping_yn.isChecked()
        transfMat_name = item.text()
        imageFiles_list =self.transfMat_inventory[transfMat_name]
        current_inventory={}
        current_inventory[transfMat_name]= imageFiles_list
        print('\nCurrent inventory:', current_inventory, skip_crop_decision)
        f.alignment_main(self.folder_path+'/', current_inventory, skip_crop_decision)


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
        path = self.selected_folder.text() + '/'
        print('\nSelected folder is:', path)
        if os.path.isdir(path):
            print('\nFolder found. Starting registration...')
            f.alignment_main(path, '', skip_crop_decision)
        else:
            print('\nNo such folder found!')


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
        print('\nYou selected ', len(folder_list), 'folders. Selected folders are:')
        for folder in folder_list:
            print('\n\t', folder)

        for folder in folder_list:    
            if os.path.isdir(folder):
                print('\nFound folder ', folder, '\nStarting registration...')
                path = folder + '/'
                f.alignment_main(path, '', skip_crop_decision)
            else:
                print('\nUnable to locate folder ', folder, '\nMoving onto next folder...')

        print('\nAll folders have been aligned!')


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