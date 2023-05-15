import sys
from functools import partial
from PyQt5.QtCore import QProcess, Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget)
from modules.groundtruth_generator_module.generator import generator

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("Ground Truth Generator")
        self.clickParam = ''
        
        self.label_section = QLabel('<b>Generate ground truth masks</b>', self)
        self.label_section.setTextFormat(Qt.RichText)
        
        self.buttonA1 = QPushButton("Individual image")
        self.buttonA1.clicked.connect(partial(self.generateGT, 'singleFile'))

        self.buttonA2 = QPushButton("Folder of images")
        self.buttonA2.clicked.connect(partial(self.generateGT, 'singleFolder'))

        self.buttonA3 = QPushButton("Collection of folders")
        self.buttonA3.clicked.connect(partial(self.generateGT, 'multiFolder'))
        
        self.quit_button = QPushButton("Quit", self)
        self.quit_button.clicked.connect(self.close)
        self.line = QFrame()
        self.line.setFrameShape(QFrame.HLine) 
        
        # Layout
        layout = QVBoxLayout()
        
        layout.addWidget(self.label_section)
        layout.addWidget(self.buttonA1)
        layout.addWidget(self.buttonA2)
        layout.addWidget(self.buttonA3)
        layout.addWidget(self.line)    
        layout.addWidget(self.quit_button)        
        self.setLayout(layout)
        
        
    def generateGT(self, param):
        window = generator.Generator(param, parent=self)
        window.show()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.move(0,0)
    window.show()
    sys.exit(app.exec_())