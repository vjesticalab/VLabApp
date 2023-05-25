import os
from PyQt5.QtWidgets import QFileDialog, QLabel, QLineEdit, QCheckBox, QPushButton, QVBoxLayout, QWidget, QTextEdit, QMessageBox, QMainWindow, QFrame
from PyQt5.QtCore import Qt
from modules.segmentation_module.segmentation import segmentation_functions as f
from modules.segmentation_module.graphGenerator import graph_functions

class Segmentation(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Single image segmentation")
        self.setFixedWidth(300)
        self.setFixedHeight(200)
        
        self.display1 = QLabel("<b>Select the image to process</b>")
        self.display1.setTextFormat(Qt.RichText)
        self.selected_file = QLineEdit()
        
        self.browse_button = QPushButton("Browse", self)
        self.browse_button.clicked.connect(self.browse_file)

        self.display2 = QLabel("<i>Note that the tracking graph is created by default - check the box to skip this step</i>")
        self.no_graph_generation = QCheckBox("Do NOT create the tracking graph")
        
        self.submit_button = QPushButton("Submit", self)
        self.submit_button.clicked.connect(self.process_input)
        
        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.display1)
        layout.addWidget(self.selected_file)
        layout.addWidget(self.browse_button)
        layout.addWidget(self.display2)
        layout.addWidget(self.no_graph_generation)
        layout.addWidget(self.submit_button)
        self.setLayout(layout)
        self.setFixedWidth(550)

    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File")
        self.selected_file.setText(file_path)

    def process_input(self):
        skip_graph_generation = self.no_graph_generation.isChecked()
        path = self.selected_file.text()
        print('\nSelected file is:', path)

        if os.path.isfile(path):
            print('\nFile found. Generating mask...')
            try:
                f.main(path)
            except Exception as e:
                msg = QMessageBox()
                msg.setIcon(QMessageBox.Critical)
                msg.setText("Error - segmentation_functions.py failed")
                msg.setInformativeText(str(e))
                msg.setWindowTitle("Error")
                msg.exec_()
                print('\n')
                raise(e)
            if not skip_graph_generation:
                try:
                    graph_functions.main(path)
                except Exception as e:
                    msg = QMessageBox()
                    msg.setIcon(QMessageBox.Critical)
                    msg.setText("Error - graph_functions.py failed")
                    msg.setInformativeText(str(e))
                    msg.setWindowTitle("Error")
                    msg.exec_()
                    print('\n')
                    raise(e)
        else:
            print('\nNo such file found!')

