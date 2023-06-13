import os
from PyQt5.QtWidgets import QFileDialog, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget, QTextEdit, QMessageBox, QMainWindow, QFrame
from PyQt5.QtCore import Qt
from modules.groundtruth_generator_module.generator import generator_functions as f


class MainWindow(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.setWindowTitle("Image folder segmentation")
        self.setFixedWidth(300)
        
        self.display = QLabel("<b>Select folder to process</b>")
        self.display.setTextFormat(Qt.RichText)
        self.selected_folder = QLineEdit()
        
        self.browse_button = QPushButton("Browse", self)
        self.browse_button.clicked.connect(self.browse_folder)

        self.display2 = QLabel("<b>Select folder to save results</b>")
        self.display2.setTextFormat(Qt.RichText)
        self.selected_folder2 = QLineEdit()
        
        self.browse_button2 = QPushButton("Browse", self)
        self.browse_button2.clicked.connect(self.browse_folder2)

        self.submit_button = QPushButton("Submit", self)
        self.submit_button.clicked.connect(self.submit)
        
        self.quit_button = QPushButton("Quit", self)
        self.quit_button.clicked.connect(self.parent.close)
        self.quit_button.setStyleSheet("background: darkred;")
        self.line = QFrame()
        self.line.setFrameShape(QFrame.HLine)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.display)
        layout.addWidget(self.selected_folder)
        layout.addWidget(self.browse_button)
        layout.addWidget(self.display2)
        layout.addWidget(self.selected_folder2)
        layout.addWidget(self.browse_button2)
        layout.addWidget(self.submit_button) 
        layout.addWidget(self.line)
        layout.addWidget(self.quit_button)
        self.setLayout(layout)
        self.setFixedWidth(550)

    def browse_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        self.selected_folder.setText(folder_path)
    
    def browse_folder2(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        self.selected_folder2.setText(folder_path)

    def submit(self):
        path = self.selected_folder.text()
        result_path = self.selected_folder2.text()
        f.main(path, result_path)


class Generator(QMainWindow):
    def __init__(self, parent=None):
        super(Generator, self).__init__(parent)
        form = MainWindow(self)
        self.setCentralWidget(form)