import sys
from functools import partial
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QApplication, QFrame, QLabel, QPushButton, QVBoxLayout, QWidget
from modules.image_registration_module import image_registration_master
from modules.groundtruth_generator_module import groundtruth_generator_master
from modules.segmentation_module import segmentation_master
from modules.graph_analysis_module import graph_analysis_master


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("VLab Application")
        self.clickParam = ''
        
        self.image_label = QLabel()
        self.image_label.setPixmap(QPixmap("support_files/Vlab_icon_50x50-01.png"))
        self.image_label.setAlignment(Qt.AlignCenter)

        ####### Main Section #######
        self.label_section = QLabel(self) #INSERT HERE THE MAIN LABEL
        self.label_section.setTextFormat(Qt.RichText)
        
        self.buttonA1 = QPushButton("Registration")
        self.buttonA1.clicked.connect(partial(self.registration))
        self.buttonA2 = QPushButton("Ground Truth Generator")
        self.buttonA2.clicked.connect(partial(self.GTgenerator))
        self.buttonA3 = QPushButton("Segmentation")
        self.buttonA3.clicked.connect(partial(self.segmentation))
        self.buttonA4 = QPushButton("Graph Analysis and Filtering")
        self.buttonA4.clicked.connect(partial(self.graph_analizer))
        # Quit button
        self.quit_button = QPushButton("Quit", self)
        self.quit_button.clicked.connect(self.close)
        # Horizontal line
        self.line = QFrame()
        self.line.setFrameShape(QFrame.HLine)    
        
        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.image_label)
        layout.addWidget(self.label_section)
        layout.addWidget(self.buttonA1)
        layout.addWidget(self.buttonA2)
        layout.addWidget(self.buttonA3)
        layout.addWidget(self.buttonA4)
        layout.addWidget(self.line)     
        layout.addWidget(self.quit_button)        
        self.setLayout(layout)
        
        
    def registration(self):
        window = image_registration_master.MainWindow()
        window.show()

    def GTgenerator(self):
        window = groundtruth_generator_master.MainWindow()
        window.show()

    def segmentation(self):
        window = segmentation_master.MainWindow()
        window.show()

    def graph_analizer(self):
        window = graph_analysis_master.MainWindow()
        window.show()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.move(0,0)
    window.showMaximized()
    window.show()
    sys.exit(app.exec_())