import sys
import numpy as np
from functools import partial
from PyQt5.QtCore import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt5.QtWidgets import QApplication, QFrame, QLabel, QPushButton, QVBoxLayout, QWidget, QLineEdit, QListWidget, QFileDialog, QMessageBox
from PyQt5 import QtWidgets
from modules.graph_analysis_module.graphAnalysis import analysis_functions as f

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("Graph Analysis")
        self.clickParam = ''
        
        self.label_section = QLabel('<b>Edit transformation matrices</b>', self)
        self.label_section.setTextFormat(Qt.RichText)
        
        self.button1 = QPushButton("Filter")
        self.button1.clicked.connect(partial(self.filter))

        self.button2 = QPushButton("Fusions")
        self.button2.clicked.connect(partial(self.fusions))

        self.button3 = QPushButton("Divisions")
        self.button3.clicked.connect(partial(self.divisions))
        
        self.quit_button = QPushButton("Quit", self)
        self.quit_button.clicked.connect(self.close)
        self.line = QFrame()
        self.line.setFrameShape(QFrame.HLine)
        
        # Layout
        layout = QVBoxLayout()    
        layout.addWidget(self.label_section)
        layout.addWidget(self.button1)
        layout.addWidget(self.button2)
        layout.addWidget(self.button3)
        layout.addWidget(self.line)     
        layout.addWidget(self.quit_button)        
        self.setLayout(layout)
             
    def filter(self):
        self.filter_window = Filter()
        self.filter_window.move(700,0)
        self.filter_window.show()

    def fusions(self):
        self.fusion_window = Fusions()
        self.fusion_window.move(700,0)
        self.fusion_window.show()

    def divisions(self):
        self.division_window = Divisions()
        self.division_window.move(700,0)
        self.division_window.show()

class Filter(QWidget):
    pass

class Fusions(QWidget):
    pass
    """def __init__(self):
        super().__init__()
        self.setWindowTitle("Edit single graph and the corresponding mask")

        # Create the widgets
        self.display1 = QLabel('Step1: \tSelect the graphs to edit')
        self.path_edit = QLineEdit(self)            
        self.browse_button = QPushButton("Browse", clicked=self.browse_graph)

        self.display2 = QLabel('Step2: \tDouble click on the event to visualize and edit it')        
        self.events_list = QListWidget()
        self.events_list.itemDoubleClicked.connect(self.event_viewer)


        self.update_label = QLabel('<b>After double-clicking the event, you can update it<\b>', self)
        self.update_label.setTextFormat(Qt.RichText)
        
        self.start_timepoint_label = QLabel('Set new start point:', self)
        self.start_timepoint_edit = QLineEdit(self)

        self.end_timepoint_label = QLabel('Set new end point:', self)
        self.end_timepoint_edit = QLineEdit(self)

        self.submit_button = QPushButton('Update', self)
        self.submit_button.clicked.connect(self.update_click)
        
        self.quit_button = QPushButton('Quit', self)
        self.quit_button.clicked.connect(self.close)

        # Add a horizontal line to the layout
        self.line1 = QFrame()
        self.line1.setFrameShape(QFrame.HLine)
        self.line2 = QFrame()
        self.line2.setFrameShape(QFrame.HLine)

        # Add the widgets to the layout
        layout = QVBoxLayout()
        layout.addWidget(self.display1)
        layout.addWidget(self.path_edit)
        layout.addWidget(self.browse_button)

        layout.addWidget(self.display2)
        layout.addWidget(self.events_list)
        
        layout.addWidget(self.line1)
        
        layout.addWidget(self.update_label)
        layout.addWidget(self.start_timepoint_label)
        layout.addWidget(self.start_timepoint_edit)
        layout.addWidget(self.end_timepoint_label)
        layout.addWidget(self.end_timepoint_edit)
        layout.addWidget(self.submit_button)

        layout.addWidget(self.line2)
        layout.addWidget(self.quit_button)


        # Set the layout for the window
        self.setLayout(layout)

    def browse_graph(self):
        self.graph_path = QFileDialog.getExistingDirectory()
        self.path_edit.setText(self.graph_path)

        events = []#gf.extract_events(os.listdir(self.graph_path))
        for file in events:
            self.events_list.addItem(file)      
               
    def update_click(self):
        try:
            self.graph_path
        except Exception as e:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Critical)
            msg.setText("Error")
            msg.setInformativeText('No values')
            msg.setWindowTitle("Error")
            msg.show()
            print('\n')
            raise(e)
        else:
            print('\nUpdating event into the graph and the mask')
            self.update()        

    def event_viewer(self, item):
        event_name = item.text()
        self.event_name = event_name
        print('\nEvent shown: ', self.event_name)

        TO DO
        self.display_graph = DisplayGraphWindow(self.transfmat_path)
        self.display_graph.setWindowTitle(self.transfMat_name)
        self.display_graph.move(700,0)
        self.display_graph.show()
        

    def update(self):
        start_timepoint = self.start_timepoint_edit.text()
        end_timepoint = self.end_timepoint_edit.text()        
        
        f.edit_event(self.graph_path, self.event_name, int(start_timepoint), int(start_timepoint), int(end_timepoint))
        
        TO DO
        self.display_graph = DisplayGraphWindow(self.graph_path)
        self.display_graph.setWindowTitle(self.event_name)
        self.display_graph.move(700,0)
        self.display_graph.show()
        """


class Divisions(QWidget):
    pass
   
   
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.move(0,0)
    window.show()
    sys.exit(app.exec_())