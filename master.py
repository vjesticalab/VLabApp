import os
import sys
import logging
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QFont, QIcon
from PyQt5.QtWidgets import QApplication, QFrame, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QFormLayout, QLineEdit

from modules.registration_module import registration
from modules.zprojection_module import zprojection
from modules.groundtruth_generator_module import generator
from modules.segmentation_module import segmentation
from modules.cell_tracking_module import cell_tracking
from modules.graph_filtering_module import graph_filtering
from modules.graph_event_filter_module import graph_event_filter
from modules.viewer_module import viewer
from general import general_functions as gf
import multiprocessing as mp

class Home(gf.Page):
    def __init__(self, page_description):
        super().__init__()
        self.window = QFormLayout(self.container)
        self.title = QLabel('<b>HOME</b>', self)
        self.title.setFont(QFont('Arial', 18))
        self.title.setAlignment(Qt.AlignCenter)
        self.window.addRow(self.title)
        self.line = QFrame()
        self.line.setFrameShape(QFrame.HLine)
        self.window.addRow(self.line)

        self.text = QLabel(page_description, self)
        self.text.setWordWrap(True)
        self.window.addRow(self.text)

        
class Registration(gf.Page):
    def __init__(self):
        super().__init__()
        self.window = QVBoxLayout(self.container)
        self.window.addWidget(registration.Registration())


class zProjection(gf.Page):
    def __init__(self):
        super().__init__()
        self.window = QVBoxLayout(self.container)
        self.window.addWidget(zprojection.zProjection())
        self.window.addStretch()


class GTGenerator(gf.Page):
    def __init__(self):
        super().__init__()
        self.window = QVBoxLayout(self.container)
        self.window.addWidget(generator.Generator())
        self.window.addStretch()
   

class Segmentation(gf.Page):
    def __init__(self):
        super().__init__()
        self.window = QVBoxLayout(self.container)
        self.window.addWidget(segmentation.Segmentation())
        self.window.addStretch()


class CellTracking(gf.Page):
    def __init__(self):
        super().__init__()
        self.window = QVBoxLayout(self.container)
        self.window.addWidget(cell_tracking.CellTracking())
        self.window.addStretch()


class GraphFiltering(gf.Page):
    def __init__(self):
        super().__init__()
        self.window = QVBoxLayout(self.container)
        self.window.addWidget(graph_filtering.GraphFiltering())
        self.window.addStretch()


class GraphEventFilter(gf.Page):
    def __init__(self):
        super().__init__()
        self.window = QVBoxLayout(self.container)
        self.window.addWidget(graph_event_filter.GraphEventFilter())
        self.window.addStretch()


class Viewer(gf.Page):
    def __init__(self):
        super().__init__()
        self.window = QVBoxLayout(self.container)
        self.window.addWidget(viewer.Viewer())
        self.window.addStretch()


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        window = QVBoxLayout(self)

        title = "VLabApp"
        self.setWindowTitle(title)

        self.image = QLabel()
        self.image.setPixmap(QPixmap("support_files/Vlab_icon_50x50-01.png"))
        self.image.setAlignment(Qt.AlignCenter)
        window.addWidget(self.image)
        tabwizard = gf.TabWizard()
        window.addWidget(tabwizard)
        
        #page_description = 'The VLabApp is created with the aim of automating the cellular image analysis process, from the recording of the movies that come out of the microscope, to the tracking of the events within each time frame.\n\n\nThe application is in fact divided into several sub-sections that can be used consecutively or automatically:\n\n  - Image Registration\n\n  - GroundTruth Dataset Construction\n\n  - Image Segmentation\n\n  - Event Tracking'
        
        #tabwizard.addHomePage(Home(page_description))
        tabwizard.addPage(Viewer(), "Viewer")
        tabwizard.addPage(zProjection(), "Z-Projection")
        tabwizard.addPage(GTGenerator(), "GroundTruth")
        tabwizard.addPage(Registration(), "Registration")
        tabwizard.addPage(Segmentation(), "Segmentation")
        tabwizard.addPage(CellTracking(), "Cell tracking")
        tabwizard.addPage(GraphFiltering(), "Graph filtering")
        tabwizard.addPage(GraphEventFilter(), "Graph event filter")

        layout = QHBoxLayout()
        self.status_line = QLineEdit()
        self.status_line.setEnabled(False)
        self.status_line.setFrame(False)
        font = self.status_line.font()
        font.setItalic(True)
        self.status_line.setFont(font)
        layout.addWidget(self.status_line)

        self.quit_button = QPushButton("Quit", self)
        self.quit_button.clicked.connect(QApplication.quit)
        self.quit_button.setStyleSheet("background: darkred;")
        layout.addWidget(self.quit_button, alignment=Qt.AlignRight)
        window.addLayout(layout)

        # Setup logging
        logging.basicConfig(level=logging.INFO, format="%(asctime)s (%(name)s) [%(levelname)s] %(message)s", handlers=[logging.StreamHandler(sys.stdout)],force=True)

        # Add a handler to output messages to self.status_line
        self.qlabel_handler = gf.QLineEditHandler(self.status_line)
        self.qlabel_handler.setFormatter(logging.Formatter('%(message)s'))
        logging.getLogger().addHandler(self.qlabel_handler)

        # Add a handler to output errors to QMessageBox
        self.qmessagebox_handler = gf.QMessageBoxErrorHandler(self)
        self.qmessagebox_handler.setFormatter(logging.Formatter('%(message)s'))
        self.qmessagebox_handler.setLevel(logging.ERROR)
        self.qmessagebox_handler.name = 'messagebox_error_handler'
        logging.getLogger().addHandler(self.qmessagebox_handler)

    def __del__(self):
        # Remove handler to avoid problems after self and self.status_line are destroyed
        logging.getLogger().removeHandler(self.qlabel_handler)
        logging.getLogger().removeHandler(self.qmessagebox_handler)


if __name__ == "__main__":
    # set up some environmental variables
    os.environ['OMP_NUM_THREADS'] = '1'
    os.environ['MKL_NUM_THREADS'] = '1'
    try:
        mp.set_start_method('spawn', force=True)
    except RuntimeError:
        sys.exit(1)
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon('support_files/Vlab_icon_50x50-01.png'))
    w = MainWindow()
    w.show()
    w.resize(900,800)
    sys.exit(app.exec_())
