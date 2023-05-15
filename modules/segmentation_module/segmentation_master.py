import sys
from functools import partial
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QFrame, QLabel, QPushButton, QVBoxLayout, QWidget
from modules.segmentation_module.segmentation import segmentation

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("Segmentation")
        self.clickParam = ''

        self.label_section_A = QLabel('<b>Perform the segmentation on:</b>', self)
        self.label_section_A.setTextFormat(Qt.RichText)
        
        self.buttonA1 = QPushButton("Individual image")
        self.buttonA1.clicked.connect(partial(self.segmentation, 'singleFile'))

        self.buttonA2 = QPushButton("Folder of images")
        self.buttonA2.clicked.connect(partial(self.segmentation, 'singleFolder'))

        self.buttonA3 = QPushButton("Collection of folders")
        self.buttonA3.clicked.connect(partial(self.segmentation, 'multiFolder'))
        
        self.quit_button = QPushButton("Quit", self)
        self.quit_button.clicked.connect(self.close)
        
        self.line = QFrame()
        self.line.setFrameShape(QFrame.HLine)
        
        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.label_section_A)
        layout.addWidget(self.buttonA1)
        layout.addWidget(self.buttonA2)
        layout.addWidget(self.buttonA3)
        layout.addWidget(self.line)   
        layout.addWidget(self.quit_button)        
        self.setLayout(layout)
        
        
    def segmentation(self, param):
        window = segmentation.Segmentation(param, parent=self)
        window.show()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.move(0,0)
    window.show()
    sys.exit(app.exec_())