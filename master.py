import sys
import logging
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QPixmap, QIcon, QFont, QPalette
from PyQt5.QtWidgets import QApplication, QFrame, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QTabWidget, QFormLayout, QLineEdit, QScrollArea

from modules.image_registration_module.registration import registration
from modules.zprojection_module.zprojection import zprojection
from modules.groundtruth_generator_module.generator import generator
from modules.segmentation_module.segmentation import segmentation
from modules.cell_tracking_module.cell_tracking import cell_tracking
from modules.graph_filtering_module.graph_filtering import graph_filtering
from modules.graph_event_filter_module.graph_event_filter import graph_event_filter
from modules.viewer_module.viewer import viewer
from general import general_functions as gf


class TabWizard(QTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tabBar().installEventFilter(self)

    def addPage(self, page, title):
        if not isinstance(page, Page):
            raise TypeError(f"{page} must be Page object")
        self.addTab(page, title)
        page.completeChanged.connect(self.nextPage)
    
    def addHomePage(self, page):
        tab_index = self.addTab(page, '')
        self.setTabIcon(tab_index, QIcon('support_files/home.svg'))
        self.setIconSize(QSize(12,12))
        page.completeChanged.connect(self.nextPage)

    def nextPage(self):
        next_index = self.currentIndex() + 1
        if next_index < self.count():
            self.setCurrentIndex(next_index)


class Page(QWidget):
    completeChanged = pyqtSignal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self.container = QWidget()
        lay = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.container)
        scroll.setBackgroundRole(QPalette.Base)
        scroll.setFrameShape(QFrame.NoFrame)
        lay.addWidget(scroll)


class Home(Page):
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

        
class Registration(Page):
    def __init__(self):
        super().__init__()
        self.window = QVBoxLayout(self.container)
        self.window.addWidget(registration.Registration())
        self.window.addStretch()


class zProjection(Page):
    def __init__(self):
        super().__init__()
        self.window = QVBoxLayout(self.container)
        self.window.addWidget(zprojection.zProjection())
        self.window.addStretch()


class GTGenerator(Page):
    def __init__(self):
        super().__init__()
        self.window = QVBoxLayout(self.container)
        self.window.addWidget(generator.Generator())
        self.window.addStretch()
   

class Segmentation(Page):
    def __init__(self):
        super().__init__()
        self.window = QVBoxLayout(self.container)
        self.window.addWidget(segmentation.Segmentation())
        self.window.addStretch()


class CellTracking(Page):
    def __init__(self):
        super().__init__()
        self.window = QVBoxLayout(self.container)
        self.window.addWidget(cell_tracking.CellTracking())
        self.window.addStretch()


class GraphFiltering(Page):
    def __init__(self):
        super().__init__()
        self.window = QVBoxLayout(self.container)
        self.window.addWidget(graph_filtering.GraphFiltering())
        self.window.addStretch()


class GraphEventFilter(Page):
    def __init__(self):
        super().__init__()
        self.window = QVBoxLayout(self.container)
        self.window.addWidget(graph_event_filter.GraphEventFilter())
        self.window.addStretch()


class Viewer(Page):
    def __init__(self):
        super().__init__()
        self.window = QVBoxLayout(self.container)
        self.window.addWidget(viewer.Viewer())
        self.window.addStretch()


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        window = QVBoxLayout(self)
        self.image = QLabel()
        self.image.setPixmap(QPixmap("support_files/Vlab_icon_50x50-01.png"))
        self.image.setAlignment(Qt.AlignCenter)
        window.addWidget(self.image)
        tabwizard = TabWizard()
        window.addWidget(tabwizard)
        
        page_description = 'The VLabApplication is created with the aim of automating the cellular image analysis process, from the recording of the movies that come out of the microscope, to the tracking of the events within each time frame.\n\n\nThe application is in fact divided into several sub-sections that can be used consecutively or automatically:\n\n  - Image Registration\n\n  - GroundTruth Dataset Construction\n\n  - Image Segmentation\n\n  - Event Tracking'
        
        tabwizard.addHomePage(Home(page_description))
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
        logging.basicConfig(level=logging.INFO, format="%(asctime)s (%(name)s) [%(levelname)s] %(message)s", handlers=[logging.StreamHandler(sys.stdout)])

        # Add a handler to output messages to self.status_line
        self.qlabel_handler = gf.QLineEditHandler(self.status_line)
        self.qlabel_handler.setFormatter(logging.Formatter('%(message)s'))
        logging.getLogger().addHandler(self.qlabel_handler)

        # Add a handler to output errors to QMessageBox
        self.qmessagebox_handler = gf.QMessageBoxErrorHandler(self)
        self.qmessagebox_handler.setFormatter(logging.Formatter('%(message)s'))
        self.qmessagebox_handler.setLevel(logging.ERROR)
        logging.getLogger().addHandler(self.qmessagebox_handler)

    def __del__(self):
        # Remove handler to avoid problems after self and self.status_line are destroyed
        logging.getLogger().removeHandler(self.qlabel_handler)
        logging.getLogger().removeHandler(self.qmessagebox_handler)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    #w.resize(500,720)
    sys.exit(app.exec_())
