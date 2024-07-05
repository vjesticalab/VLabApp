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
from modules.events_filter_module import events_filter
from modules.viewer_module import viewer
from modules.file_organization_module import file_organization
from modules.pipeline_module import pipeline
from general import general_functions as gf
import multiprocessing as mp


class Tools(gf.Page):
    def __init__(self):
        super().__init__()

        self.window = QVBoxLayout(self.container)
        tabwizard = gf.TabWizard()
        self.window.addWidget(tabwizard)
        tabwizard.addPage(gf.Page(widget=viewer.ImageMaskGraphViewer()), "View image, masks and/or graph")
        tabwizard.addPage(gf.Page(widget=viewer.RegistrationViewer()), "View registration matrix")
        tabwizard.addPage(gf.Page(widget=viewer.MetadataViewer(), add_stretch=False), "View metadata")
        tabwizard.addPage(gf.Page(widget=file_organization.FileOrganization()), "File organization")
        tabwizard.addPage(gf.Page(widget=generator.Generator()), "GroundTruth")


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

        tabwizard.addPage(gf.Page(widget=registration.Registration(), add_stretch=False), "Registration")
        tabwizard.addPage(gf.Page(widget=zprojection.zProjection()), "Z-Projection")
        tabwizard.addPage(gf.Page(widget=segmentation.Segmentation()), "Segmentation")
        tabwizard.addPage(gf.Page(widget=cell_tracking.CellTracking()), "Cell tracking")
        tabwizard.addPage(gf.Page(widget=graph_filtering.GraphFiltering()), "Graph filtering")
        tabwizard.addPage(gf.Page(widget=events_filter.GraphEventFilter()), "Events filter")
        tabwizard.addPage(gf.Page(widget=pipeline.Pipeline()), "Pipeline")
        tabwizard.addPage(gf.Page(widget=Tools(), add_stretch=False), "Tools")

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
