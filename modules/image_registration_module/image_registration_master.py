import sys
from functools import partial
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QFrame, QLabel, QPushButton, QVBoxLayout, QWidget
from modules.image_registration_module.registration import registration
from modules.image_registration_module.alignment import alignment
from modules.image_registration_module.registrationEditing import editing

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Registration")
        self.clickParam = ''

        ####### Section A #######
        ####### Modules for initial registration and calculation of transformation matrices ########
        self.label_section_A = QLabel('<b>Calculate & Perform Registration</b>', self)
        self.label_section_A.setTextFormat(Qt.RichText)
        self.label_section_A.setAlignment(Qt.AlignCenter)
        
        self.buttonA1 = QPushButton("Individual image")
        self.buttonA1.clicked.connect(partial(self.registration, 'singleFile'))

        self.buttonA2 = QPushButton("Folder of images")
        self.buttonA2.clicked.connect(partial(self.registration, 'singleFolder'))

        self.buttonA3 = QPushButton("Collection of folders")
        self.buttonA3.clicked.connect(partial(self.registration, 'multiFolder'))
        
        ####### Section B #######
        ####### Use registration matrices to register images ########
        self.label_section_B = QLabel('<b>Align with Transformation Matrices</b>', self)
        self.label_section_B.setTextFormat(Qt.RichText)
        self.label_section_B.setAlignment(Qt.AlignCenter)
        
        self.buttonB0 = QPushButton("View aligned tyx image")
        self.buttonB0.clicked.connect(partial(self.alignment, 'view'))
        
        self.buttonB1 = QPushButton("Align image or image set")
        self.buttonB1.clicked.connect(partial(self.alignment, 'singleFile'))

        self.buttonB2 = QPushButton("Align folder of images")
        self.buttonB2.clicked.connect(partial(self.alignment, 'singleFolder'))

        self.buttonB3 = QPushButton("Align collection of folders")
        self.buttonB3.clicked.connect(partial(self.alignment, 'multiFolder'))

        ####### Section C #######
        ####### Modules for modifying registration matrices ########
        self.label_section_C = QLabel('<b>Edit Transformation Matrices</b>', self)
        self.label_section_C.setTextFormat(Qt.RichText)
        self.label_section_C.setAlignment(Qt.AlignCenter)
        
        self.buttonC1 = QPushButton("Individual image")
        self.buttonC1.clicked.connect(partial(self.editing, 'single'))

        self.buttonC2 = QPushButton("Folder of images")
        self.buttonC2.clicked.connect(partial(self.editing, 'folder'))

        # Quit button
        self.quit_button = QPushButton("Quit", self)
        self.quit_button.clicked.connect(self.close)
        # Horizontal lines
        self.line1 = QFrame()
        self.line1.setFrameShape(QFrame.HLine)
        self.line2 = QFrame()
        self.line2.setFrameShape(QFrame.HLine)        
        self.line3 = QFrame()
        self.line3.setFrameShape(QFrame.HLine)    
        
        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.label_section_A)
        layout.addWidget(self.buttonA1)
        layout.addWidget(self.buttonA2)
        layout.addWidget(self.buttonA3)
        layout.addWidget(self.line1)
        layout.addWidget(self.label_section_B)
        layout.addWidget(self.buttonB0)
        layout.addWidget(self.buttonB1)
        layout.addWidget(self.buttonB2)
        layout.addWidget(self.buttonB3)
        layout.addWidget(self.line2)        
        layout.addWidget(self.label_section_C)
        layout.addWidget(self.buttonC1)
        layout.addWidget(self.buttonC2)
        layout.addWidget(self.line3)     
        layout.addWidget(self.quit_button)        
        self.setLayout(layout)
        
        
    def registration(self, param):
        window = registration.Registration(param, parent=self)
        window.show()

    def alignment(self, param):
        window = alignment.Alignment(param, parent=self)
        window.show()

    def editing(self, param):
        window = editing.Editing(param, parent=self)
        window.show()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.move(0,0)
    window.show()
    sys.exit(app.exec_())