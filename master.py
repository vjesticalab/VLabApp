#!/usr/bin/env python3

import os
import sys
import logging
import multiprocessing as mp
from functools import partial
from PyQt5.QtCore import Qt, QSize, QTimer
from PyQt5.QtGui import QPixmap, QIcon, QFontMetrics, QKeySequence
from PyQt5.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QLineEdit, QTreeWidget, QAbstractItemView, QSplitter, QStackedWidget, QTreeWidgetItem, QTreeWidgetItemIterator, QShortcut

from modules.registration_module import registration
from modules.zprojection_module import zprojection
from modules.ground_truth_generator_module import ground_truth_generator
from modules.segmentation_module import segmentation
from modules.cell_tracking_module import cell_tracking
from modules.graph_filtering_module import graph_filtering
from modules.events_filter_module import events_filter
from modules.viewer_module import viewer
from modules.file_organization_module import file_organization
from modules.file_conversion_module import file_conversion
from modules.image_cropping_module import image_cropping
from modules.pipeline_module import pipeline
from general import general_functions as gf


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        window = QVBoxLayout(self)

        title = "VLabApp"
        self.setWindowTitle(title)

        self.image = QLabel()
        self.image.setPixmap(QPixmap("support_files/logo.png"))
        self.image.setAlignment(Qt.AlignCenter)

        self.status_line = QLineEdit()
        self.status_line.setEnabled(False)
        self.status_line.setFrame(False)
        font = self.status_line.font()
        font.setItalic(True)
        self.status_line.setFont(font)

        self.module_list = QTreeWidget()
        self.module_list.setColumnCount(1)
        self.module_list.setSortingEnabled(False)
        self.module_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.module_list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.module_list.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.module_list.setHeaderHidden(True)

        self.right_panel = QStackedWidget()

        splitter = QSplitter()
        self.left_panel = QWidget()
        self.left_panel.setLayout(QVBoxLayout())
        self.left_panel.layout().setContentsMargins(0, 0, 0, 0)
        if not self.image.pixmap().isNull():
            self.left_panel.layout().addWidget(self.image)
        self.left_panel.layout().addWidget(self.module_list)
        splitter.addWidget(self.left_panel)
        splitter.addWidget(self.right_panel)
        splitter.setCollapsible(1, False)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 5)
        window.addWidget(splitter)

        item = QTreeWidgetItem(self.module_list, ["Registration"])
        item.setData(0, Qt.UserRole, self.right_panel.count())
        item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
        self.right_panel.addWidget(gf.Page(widget=QWidget()))

        subitem = QTreeWidgetItem(item, ["Registration"])
        subitem.setData(0, Qt.UserRole, self.right_panel.count())
        self.right_panel.addWidget(gf.Page(widget=registration.Perform()))

        subitem = QTreeWidgetItem(item, ["Alignment"])
        subitem.setData(0, Qt.UserRole, self.right_panel.count())
        self.right_panel.addWidget(gf.Page(widget=registration.Align()))

        subitem = QTreeWidgetItem(item, ["Editing (batch)"])
        subitem.setData(0, Qt.UserRole, self.right_panel.count())
        self.right_panel.addWidget(gf.Page(widget=registration.Edit()))

        subitem = QTreeWidgetItem(item, ["Editing (manual)"])
        subitem.setData(0, Qt.UserRole, self.right_panel.count())
        self.right_panel.addWidget(gf.Page(widget=registration.ManualEdit()))

        item = QTreeWidgetItem(self.module_list, ["Z-Projection"])
        item.setData(0, Qt.UserRole, self.right_panel.count())
        self.right_panel.addWidget(gf.Page(widget=zprojection.zProjection()))

        item = QTreeWidgetItem(self.module_list, ["Segmentation"])
        item.setData(0, Qt.UserRole, self.right_panel.count())
        self.right_panel.addWidget(gf.Page(widget=segmentation.Segmentation()))

        item = QTreeWidgetItem(self.module_list, ["Cell tracking"])
        item.setData(0, Qt.UserRole, self.right_panel.count())
        self.right_panel.addWidget(gf.Page(widget=cell_tracking.CellTracking()))

        item = QTreeWidgetItem(self.module_list, ["Graph filtering"])
        item.setData(0, Qt.UserRole, self.right_panel.count())
        self.right_panel.addWidget(gf.Page(widget=graph_filtering.GraphFiltering()))

        item = QTreeWidgetItem(self.module_list, ["Events filter"])
        item.setData(0, Qt.UserRole, self.right_panel.count())
        self.right_panel.addWidget(gf.Page(widget=events_filter.GraphEventFilter()))

        item = QTreeWidgetItem(self.module_list, ["Pipeline"])
        item.setData(0, Qt.UserRole, self.right_panel.count())
        self.right_panel.addWidget(gf.Page(widget=pipeline.Pipeline()))

        item = QTreeWidgetItem(self.module_list, ["Tools"])
        item.setData(0, Qt.UserRole, self.right_panel.count())
        item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
        self.right_panel.addWidget(gf.Page(widget=QWidget()))

        subitem = QTreeWidgetItem(item, ["View image, mask and graph"])
        subitem.setData(0, Qt.UserRole, self.right_panel.count())
        self.right_panel.addWidget(gf.Page(widget=viewer.ImageMaskGraphViewer()))

        subitem = QTreeWidgetItem(item, ["View registration matrix"])
        subitem.setData(0, Qt.UserRole, self.right_panel.count())
        self.right_panel.addWidget(gf.Page(widget=viewer.RegistrationViewer()))

        subitem = QTreeWidgetItem(item, ["View metadata"])
        subitem.setData(0, Qt.UserRole, self.right_panel.count())
        self.right_panel.addWidget(gf.Page(widget=viewer.MetadataViewer(), add_stretch=False))

        subitem = QTreeWidgetItem(item, ["File organization"])
        subitem.setData(0, Qt.UserRole, self.right_panel.count())
        self.right_panel.addWidget(gf.Page(widget=file_organization.FileOrganization()))

        subitem = QTreeWidgetItem(item, ["File conversion (masks and graphs)"])
        subitem.setData(0, Qt.UserRole, self.right_panel.count())
        self.right_panel.addWidget(gf.Page(widget=file_conversion.MaskGraphConversion()))

        subitem = QTreeWidgetItem(item, ["File conversion (lossy preview)"])
        subitem.setData(0, Qt.UserRole, self.right_panel.count())
        self.right_panel.addWidget(gf.Page(widget=file_conversion.ImageMaskConversion()))

        subitem = QTreeWidgetItem(item, ["Image cropping"])
        subitem.setData(0, Qt.UserRole, self.right_panel.count())
        self.right_panel.addWidget(gf.Page(widget=image_cropping.ImageCropping()))

        subitem = QTreeWidgetItem(item, ["Ground truth generator"])
        subitem.setData(0, Qt.UserRole, self.right_panel.count())
        self.right_panel.addWidget(gf.Page(widget=ground_truth_generator.GroundTruthGenerator()))

        w = self.module_list.sizeHintForColumn(0)
        h = round(1.5*self.module_list.sizeHintForRow(0))
        font_metric = QFontMetrics(self.module_list.font())
        iterator = QTreeWidgetItemIterator(self.module_list)
        while iterator.value():
            item = iterator.value()
            item.setSizeHint(0, QSize(w, h))
            iterator += 1
        self.module_list.setMinimumWidth(font_metric.width('a')*25)

        self.module_list.currentItemChanged.connect(self.module_list_current_item_changed)
        self.module_list.setCurrentItem(self.module_list.topLevelItem(0))

        layout = QHBoxLayout()
        layout.addWidget(self.status_line)

        shortcut_quit = QShortcut(QKeySequence.Quit,self)
        shortcut_quit.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        shortcut_quit.activated.connect(QApplication.quit)

        self.quit_button = QPushButton("Quit", self)
        self.quit_button.clicked.connect(QApplication.quit)
        self.quit_button.setStyleSheet("background: darkred;")
        layout.addWidget(self.quit_button, alignment=Qt.AlignRight)
        window.addLayout(layout)

        # Setup logging
        logging.basicConfig(level=logging.INFO, format="%(asctime)s (%(name)s) [%(levelname)s] %(message)s", handlers=[logging.StreamHandler(sys.stdout)], force=True)

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

        # Temporary workaround to ensure QGroupBox titles are not cropped
        self.setStyleSheet("QLineEdit:disabled {background: transparent} " +
                           "QGroupBox::title {padding-right: 1px}")

    def module_list_current_item_changed(self, current, previous):
        self.right_panel.setCurrentIndex(current.data(0, Qt.UserRole))
        self.setWindowTitle('VLabApp - '+current.text(0))
        self.status_line.setText('')
        if current.childCount():
            current.setExpanded(True)
            self.module_list.setCurrentItem(current.child(0))
            QTimer.singleShot(0, partial(self.module_list.setCurrentItem, current.child(0)))

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
    app.setWindowIcon(QIcon('support_files/logo.png'))
    w = MainWindow()
    w.show()
    w.resize(1000, 800)
    sys.exit(app.exec_())
