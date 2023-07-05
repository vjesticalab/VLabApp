import os
from PyQt5.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget, QFrame, QGroupBox
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt
from functools import partial
import logging
from modules.image_registration_module.registration import registration_functions as f, A_registration, B_alignment, C_editing

class Registration(QWidget):
    def __init__(self):
        super().__init__()
        ####### Section A #######
        self.buttonA1 = QPushButton("Individual image")
        self.buttonA1.setMinimumWidth(200)
        self.buttonA1.clicked.connect(partial(self.registration, 'singleFile'))
        self.buttonA2 = QPushButton("Folder of images")
        self.buttonA2.setMinimumWidth(200)
        self.buttonA2.clicked.connect(partial(self.registration, 'singleFolder'))
        self.buttonA3 = QPushButton("Collection of folders")
        self.buttonA3.setMinimumWidth(200)
        self.buttonA3.clicked.connect(partial(self.registration, 'multiFolder'))
        
        ####### Section B #######
        self.buttonB1 = QPushButton("View aligned tyx image")
        self.buttonB1.setMinimumWidth(200)
        self.buttonB1.clicked.connect(partial(self.alignment, 'view'))
        self.buttonB2 = QPushButton("Align image or image set")
        self.buttonB2.setMinimumWidth(200)
        self.buttonB2.clicked.connect(partial(self.alignment, 'singleFile'))
        self.buttonB3 = QPushButton("Align folder of images")
        self.buttonB3.setMinimumWidth(200)
        self.buttonB3.clicked.connect(partial(self.alignment, 'singleFolder'))
        self.buttonB4 = QPushButton("Align collection of folders")
        self.buttonB4.setMinimumWidth(200)
        self.buttonB4.clicked.connect(partial(self.alignment, 'multiFolder'))

        ####### Section C #######
        self.buttonC1 = QPushButton("Individual image")
        self.buttonC1.setMinimumWidth(200)
        self.buttonC1.clicked.connect(partial(self.editing, 'single'))
        self.buttonC2 = QPushButton("Folder of images")
        self.buttonC2.setMinimumWidth(200)
        self.buttonC2.clicked.connect(partial(self.editing, 'folder'))

        # Layout
        layout = QVBoxLayout()
        groupbox = QGroupBox("Perform Registration")
        layout2 = QVBoxLayout()
        layout2.addWidget(self.buttonA1, alignment=Qt.AlignCenter)
        layout2.addWidget(self.buttonA2, alignment=Qt.AlignCenter)
        layout2.addWidget(self.buttonA3, alignment=Qt.AlignCenter)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
        groupbox = QGroupBox("Align images with transformation matrices")
        layout2 = QVBoxLayout()
        layout2.addWidget(self.buttonB1, alignment=Qt.AlignCenter)
        layout2.addWidget(self.buttonB2, alignment=Qt.AlignCenter)
        layout2.addWidget(self.buttonB3, alignment=Qt.AlignCenter)
        layout2.addWidget(self.buttonB4, alignment=Qt.AlignCenter)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
        groupbox = QGroupBox("Edit transformation matrices")
        layout2 = QVBoxLayout()
        layout2.addWidget(self.buttonC1, alignment=Qt.AlignCenter)
        layout2.addWidget(self.buttonC2, alignment=Qt.AlignCenter)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)
        self.setLayout(layout)

        self.logger = logging.getLogger(__name__)
        
    def registration(self, param):
        window = A_registration.Registration(param, parent=self)
        window.show()

    def alignment(self, param):
        window = B_alignment.Alignment(param, parent=self)
        window.show()

    def editing(self, param):
        window = C_editing.Editing(param, parent=self)
        window.show()
