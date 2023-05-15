import os
from PyQt5.QtWidgets import QFileDialog, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget, QTextEdit, QMessageBox, QMainWindow, QFrame
from PyQt5.QtCore import Qt
from modules.groundtruth_generator_module.generator import generator_functions as f

class SingleFile(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Single image mask generation")
        
        self.display = QLabel("<b>Select the image to process</b>")
        self.display.setTextFormat(Qt.RichText)
        self.selected_file = QLineEdit()
        
        self.browse_button = QPushButton("Browse", self)
        self.browse_button.clicked.connect(self.browse_file)
        
        self.submit_button = QPushButton("Submit", self)
        self.submit_button.clicked.connect(self.process_input)
        
        self.quit_button = QPushButton("Quit", self)
        self.quit_button.clicked.connect(self.parent.close)
        self.line = QFrame()
        self.line.setFrameShape(QFrame.HLine)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.display)
        layout.addWidget(self.selected_file)
        layout.addWidget(self.browse_button)
        layout.addWidget(self.submit_button)
        layout.addWidget(self.line) 
        layout.addWidget(self.quit_button)
        self.setLayout(layout)
        self.setFixedWidth(300)
        self.setFixedHeight(200)

    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File")
        self.selected_file.setText(file_path)

    def process_input(self):
        path = self.selected_file.text()
        print('\nSelected file is:', path)

        if os.path.isfile(path):
            print('\nFile found. Generating mask...')
            try:
                f.main(path, 'singleFile')
            except Exception as e:
                msg = QMessageBox()
                msg.setIcon(QMessageBox.Critical)
                msg.setText("Error - generator_fuctions failed")
                msg.setInformativeText(str(e))
                msg.setWindowTitle("Error")
                msg.exec_()
                print('\n')
                raise(e)
        else:
            print('\nNo such file found!')

        self.parent.close()


class SingleFolder(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.setWindowTitle("Image folder masks generation")
        
        self.display = QLabel("<b>Select the folder to process</b>")
        self.display.setTextFormat(Qt.RichText)
        self.selected_folder = QLineEdit()
        
        self.browse_button = QPushButton("Browse", self)
        self.browse_button.clicked.connect(self.browse_folder)
        
        self.submit_button = QPushButton("Submit", self)
        self.submit_button.clicked.connect(self.process_input)
        
        self.quit_button = QPushButton("Quit", self)
        self.quit_button.clicked.connect(self.parent.close)
        self.line = QFrame()
        self.line.setFrameShape(QFrame.HLine)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.display)
        layout.addWidget(self.selected_folder)
        layout.addWidget(self.browse_button)
        layout.addWidget(self.submit_button)
        layout.addWidget(self.line) 
        layout.addWidget(self.quit_button)
        self.setLayout(layout)
        self.setFixedWidth(300)
        self.setFixedHeight(200)

    def browse_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        self.selected_folder.setText(folder_path)

    def process_input(self):
        path = self.selected_folder.text() + '/'
        print('\nSelected folder is:', path)

        if os.path.isdir(path):
            print('\nFolder found. Generating masks...')
            try:
                f.main(path, 'singleFolder')
            except Exception as e:
                msg = QMessageBox()
                msg.setIcon(QMessageBox.Critical)
                msg.setText("Error - generator_fuctions failed")
                msg.setInformativeText(str(e))
                msg.setWindowTitle("Error")
                msg.exec_()
                print('\n')
                raise(e)
        else:
            print('\nNo such folder found!')

        self.parent.close()


class MultiFolder(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.setWindowTitle("Multiple folders masks generation")
        
        self.display1 = QLabel("<b>Select the folders to process</b>")
        self.display1.setTextFormat(Qt.RichText)
        self.display1a = QLabel("Insert here a list of paths to folders. \nEach folder MUST be written in a new line. \nSpace or slash characters at the end of the folder will confuse the script!")
        self.display1b = QLabel("<i>Example: /Users/admin/Desktop/20220216_P0001_E0008_U002</i>")
        self.display1b.setTextFormat(Qt.RichText)
        self.folders_list = QTextEdit()
        
        self.submit_button = QPushButton("Submit", self)
        self.submit_button.clicked.connect(self.process_input)
        
        self.quit_button = QPushButton("Quit", self)
        self.quit_button.clicked.connect(self.parent.close)
        self.line = QFrame()
        self.line.setFrameShape(QFrame.HLine)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.display1)
        layout.addWidget(self.display1a)
        layout.addWidget(self.display1b)
        layout.addWidget(self.folders_list)
        layout.addWidget(self.submit_button)
        layout.addWidget(self.line) 
        layout.addWidget(self.quit_button)
        self.setLayout(layout)

    def process_input(self):
        folder_list_text = self.folders_list.toPlainText()
        folder_list = folder_list_text.split('\n')
        print('\nYou selected ', len(folder_list), 'folders. Selected folders are:')
        for folder in folder_list:
            print('\n\t', folder)

        for folder in folder_list:
            if os.path.isdir(folder):
                print('\nFolder ', folder, ' found. Generating masks...')
                path = folder + '/'
                try:
                    f.main(path, 'singleFolder')
                except Exception as e:
                    msg = QMessageBox()
                    msg.setIcon(QMessageBox.Critical)
                    msg.setText("Error - generator_fuctions failed") 
                    msg.setInformativeText(str(e))
                    msg.setWindowTitle("Error")
                    msg.exec_()
                    print('\n')
                    raise(e)
            else:
                print('\nUnable to locate folder ', folder, '\nMoving onto next folder...')

        print('\nAll folders have been registered!')
        self.parent.close()


class Generator(QMainWindow):
    def __init__(self, param, parent=None):
        super(Generator, self).__init__(parent)
        if param == 'singleFile':
            form = SingleFile(self)
            self.setCentralWidget(form)
        elif param == 'singleFolder':
            form = SingleFolder(self)
            self.setCentralWidget(form)
        elif param == 'multiFolder':
            form = MultiFolder(self)
            self.setCentralWidget(form)
