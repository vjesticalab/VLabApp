import numpy as np
import os
import tifffile
import nd2
import re
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QIcon, QPalette, QBrush
from PyQt5.QtWidgets import QFrame, QLabel, QVBoxLayout, QHBoxLayout, QFormLayout, QWidget, QTabWidget, QLineEdit, QScrollArea, QListWidget, QMessageBox, QTableWidget, QHeaderView, QTableWidgetItem, QAbstractItemView, QPushButton, QFileDialog, QListWidgetItem, QDialog

import logging
import igraph as ig
from matplotlib import cm
from scipy.optimize import curve_fit
import cv2 as cv


class QLineEditHandler(logging.Handler):
    """
    logging handler to send message to QLineEdit.

    Examples
    --------
    label=QLineEdit()
    handler=QLineEditHandler(label)
    logging.getLogger().addHandler(handler)
    """

    def __init__(self, qlabel):
        logging.Handler.__init__(self)
        self.label = qlabel

    def emit(self, record):
        msg = self.format(record)
        self.label.setText(msg)
        # to focus on the beginning of the text if too long
        self.label.setCursorPosition(0)
        # force repainting to update message even when busy
        self.label.repaint()


class StatusTableDialog(QDialog):
    """
    a dialog to report job status.

    Examples
    --------
    msg=StatusTableDialog('Warning',['Success','Success','Failed'],[None,None,'invalid file'],['image1.tif','image2.tif','image3.tif'])
    msg.exec_()
    """

    def __init__(self, title, status, error_messages, input_files):
        super().__init__()
        self.setSizeGripEnabled(True)
        self.setWindowTitle(title)
        layout = QVBoxLayout()
        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(['Status', 'Error message', 'Input file'])
        table.verticalHeader().hide()
        table.setTextElideMode(Qt.ElideLeft)
        table.setWordWrap(False)
        table.setSelectionMode(QAbstractItemView.NoSelection)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        for s, m, f in zip(status, error_messages, input_files):
            table.insertRow(table.rowCount())
            item = QTableWidgetItem(s)
            item.setFlags(item.flags() ^ Qt.ItemIsEditable)
            if s != 'Success':
                item.setBackground(QBrush(Qt.red))
            table.setItem(table.rowCount()-1, 0, item)
            item = QTableWidgetItem(m)
            item.setToolTip(m)
            item.setFlags(item.flags() ^ Qt.ItemIsEditable)
            table.setItem(table.rowCount()-1, 1, item)
            item = QTableWidgetItem(f)
            item.setToolTip(f)
            item.setFlags(item.flags() ^ Qt.ItemIsEditable)
            table.setItem(table.rowCount()-1, 2, item)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(table)
        button = QPushButton("OK")
        button.clicked.connect(self.done)
        layout.addWidget(button, alignment=Qt.AlignCenter)
        self.setLayout(layout)


class QMessageBoxErrorHandler(logging.Handler):
    """
    Logging handler to send message to QMessageBox.critical

    Examples
    --------
    handler= QMessageBoxErrorHandler(self)
    handler.setLevel(logging.ERROR)
    logging.getLogger().addHandler(handler)
    """

    def __init__(self, parent):
        logging.Handler.__init__(self)
        self.parent = parent

    def emit(self, record):
        msg = self.format(record)
        QMessageBox.critical(self.parent, 'Error', msg)


class DropFilesTableWidget2(QTableWidget):
    """
    A QTableWidget with drop support for files and folders with 2 columns. If a folder is dropped, all files contained in the folder are added.
    """

    def __init__(self, parent=None, header_1=None, header_2=None, filenames_suffix_1=None, filenames_suffix_2=None):
        super().__init__(parent)
        self.setColumnCount(2)
        self.setHorizontalHeaderLabels([header_1, header_2])
        self.verticalHeader().hide()
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.setAcceptDrops(True)
        self.setTextElideMode(Qt.ElideLeft)
        self.setWordWrap(False)
        self.filenames_suffix_1 = filenames_suffix_1
        self.filenames_suffix_2 = filenames_suffix_2

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls:
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            if url.isLocalFile():
                if os.path.isfile(url.toLocalFile()):
                    filename = url.toLocalFile()
                    path_1 = None
                    path_2 = None
                    re_pattern = self.filenames_suffix_1 + '$'
                    if re.search(re_pattern, filename):
                        basename = re.sub(re_pattern, '', filename)
                        path_1 = filename
                        if os.path.isfile(basename + self.filenames_suffix_2):
                            path_2 = basename + self.filenames_suffix_2
                    re_pattern = self.filenames_suffix_2 + '$'
                    if re.search(re_pattern, filename):
                        basename = re.sub(re_pattern, '', filename)
                        path_2 = filename
                        if os.path.isfile(basename + self.filenames_suffix_1):
                            path_1 = basename + self.filenames_suffix_1
                    if not path_1 is None and not path_2 is None:
                        if len(self.findItems(path_2, Qt.MatchExactly)) == 0 and len(self.findItems(path_1, Qt.MatchExactly)) == 0:
                            self.insertRow(self.rowCount())
                            item = QTableWidgetItem(path_1)
                            item.setToolTip(path_1)
                            item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                            self.setItem(self.rowCount()-1, 0, item)
                            item = QTableWidgetItem(path_2)
                            item.setToolTip(path_2)
                            item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                            self.setItem(self.rowCount()-1, 1, item)
                if os.path.isdir(url.toLocalFile()):
                    d = url.toLocalFile()
                    # keep only files (not folders)
                    for filename in [os.path.join(d, f) for f in os.listdir(d)]:
                        path_1 = None
                        path_2 = None
                        re_pattern = self.filenames_suffix_1 + '$'
                        if re.search(re_pattern, filename):
                            basename = re.sub(re_pattern, '', filename)
                            path_1 = filename
                            if os.path.isfile(basename + self.filenames_suffix_2):
                                path_2 = basename + self.filenames_suffix_2
                        re_pattern = self.filenames_suffix_2 + '$'
                        if re.search(re_pattern, filename):
                            basename = re.sub(re_pattern, '', filename)
                            path_2 = filename
                            if os.path.isfile(basename + self.filenames_suffix_1):
                                path_1 = basename + self.filenames_suffix_1
                        if not path_1 is None and not path_2 is None:
                            if len(self.findItems(path_2, Qt.MatchExactly)) == 0 and len(self.findItems(path_1, Qt.MatchExactly)) == 0:
                                self.insertRow(self.rowCount())
                                item = QTableWidgetItem(path_1)
                                item.setToolTip(path_1)
                                item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                                self.setItem(self.rowCount()-1, 0, item)
                                item = QTableWidgetItem(path_2)
                                item.setToolTip(path_2)
                                item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                                self.setItem(self.rowCount()-1, 1, item)


class FileTableWidget2(QWidget):
    """
    A 2 columns table of files with filters, button to add files and folder and drag and drop support.
    Corresponding files in both columns are assumed to share a common base name and only differ in the
    filename suffix.
    """
    file_table_changed = pyqtSignal()

    def __init__(self, parent=None, header_1=None, header_2=None, filenames_suffix_1=None, filenames_suffix_2=None):
        """
        Parameters
        ----------
        header_1: str
            name of the first column.
        header_2: str
            name of the second column.
        filename_suffix_1: str
            filenames not ending with this text will be ignored (for column 1).
        filename_suffix_2: str
            filenames not ending with this text will be ignored (for column 2).
        """
        super().__init__(parent)

        self.filter_name_1 = QLineEdit(filenames_suffix_1, placeholderText='e.g.: _mask.tif')
        self.filter_name_1.setToolTip('Accept only filenames ending with this text.')
        self.filter_name_1.textChanged.connect(self.filter_name_1_changed)
        self.filter_name_2 = QLineEdit(filenames_suffix_2, placeholderText='e.g.: _graph.graphmlz')
        self.filter_name_2.setToolTip('Accept only filenames ending with this text')
        self.filter_name_2.textChanged.connect(self.filter_name_2_changed)
        self.file_table = DropFilesTableWidget2(header_1=header_1, header_2=header_2, filenames_suffix_1=self.filter_name_1.text(), filenames_suffix_2=self.filter_name_2.text())
        self.file_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.file_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.file_table.model().rowsInserted.connect(self.file_table_rows_inserted)
        self.file_table.model().rowsRemoved.connect(self.file_table_rows_removed)
        self.add_file_button = QPushButton("Add files", self)
        self.add_file_button.clicked.connect(self.add_file)
        self.add_folder_button = QPushButton("Add folder", self)
        self.add_folder_button.clicked.connect(self.add_folder)
        self.remove_file_button = QPushButton("Remove selected", self)
        self.remove_file_button.clicked.connect(self.remove_file)


        layout = QVBoxLayout()
        layout.addWidget(self.file_table)
        layout2 = QHBoxLayout()
        layout2.addWidget(self.add_file_button)
        layout2.addWidget(self.add_folder_button)
        layout2.addWidget(self.remove_file_button)
        layout.addLayout(layout2)
        layout2 = QHBoxLayout()
        layout3 = QFormLayout()
        layout3.addRow(header_1 + " suffix:", self.filter_name_1)
        layout2.addLayout(layout3)
        layout3 = QFormLayout()
        layout3.addRow(header_2 + " suffix:", self.filter_name_2)
        layout2.addLayout(layout3)
        layout.addLayout(layout2)
        help_label = QLabel("Corresponding " + header_1 + " and " + header_2 + " files must be in the same directory. Their filenames must share the same basename and end with the specified suffix (by default <basename>"+self.filter_name_1.text()+" and <basename>"+self.filter_name_2.text()+")")
        help_label.setWordWrap(True)
        layout.addWidget(help_label)
        layout.setContentsMargins(0,0,0,0)
        self.setLayout(layout)

    def file_table_rows_inserted(self):
        self.file_table_changed.emit()

    def file_table_rows_removed(self):
        self.file_table_changed.emit()

    def filter_name_1_changed(self):
        self.file_table.filenames_suffix_1 = self.filter_name_1.text()

    def filter_name_2_changed(self):
        self.file_table.filenames_suffix_2 = self.filter_name_2.text()

    def add_file(self):
        file_paths, _ = QFileDialog.getOpenFileNames(self, 'Select Files', filter='Images ('+'*'+self.filter_name_1.text()+' '+'*'+self.filter_name_2.text()+')')
        for file_path in file_paths:
            path_1 = None
            path_2 = None
            re_pattern = self.filter_name_1.text() + '$'
            if re.search(re_pattern, file_path):
                basename = re.sub(re_pattern, '', file_path)
                path_1 = file_path
                if os.path.isfile(basename + self.filter_name_2.text()):
                    path_2 = basename + self.filter_name_2.text()
            re_pattern = self.filter_name_2.text() + '$'
            if re.search(re_pattern, file_path):
                basename = re.sub(re_pattern, '', file_path)
                path_2 = file_path
                if os.path.isfile(basename + self.filter_name_1.text()):
                    path_1 = basename + self.filter_name_1.text()
            if not path_1 is None and not path_2 is None:
                if len(self.file_table.findItems(path_2, Qt.MatchExactly)) == 0 and len(self.file_table.findItems(path_1, Qt.MatchExactly)) == 0:
                    self.file_table.insertRow(self.file_table.rowCount())
                    item = QTableWidgetItem(path_1)
                    item.setToolTip(path_1)
                    item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                    self.file_table.setItem(self.file_table.rowCount()-1, 0, item)
                    item = QTableWidgetItem(path_2)
                    item.setToolTip(path_2)
                    item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                    self.file_table.setItem(self.file_table.rowCount()-1, 1, item)

    def add_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder_path:
            for fname in os.listdir(folder_path):
                file_path = os.path.join(folder_path, fname)
                path_1 = None
                path_2 = None
                re_pattern = self.filter_name_1.text() + '$'
                if re.search(re_pattern, file_path):
                    basename = re.sub(re_pattern, '', file_path)
                    path_1 = file_path
                    if os.path.isfile(basename + self.filter_name_2.text()):
                        path_2 = basename + self.filter_name_2.text()
                re_pattern = self.filter_name_2.text() + '$'
                if re.search(re_pattern, file_path):
                    basename = re.sub(re_pattern, '', file_path)
                    path_2 = file_path
                    if os.path.isfile(basename + self.filter_name_1.text()):
                        path_1 = basename + self.filter_name_1.text()
                if not path_1 is None and not path_2 is None:
                    if len(self.file_table.findItems(path_2, Qt.MatchExactly)) == 0 and len(self.file_table.findItems(path_1, Qt.MatchExactly)) == 0:
                        self.file_table.insertRow(self.file_table.rowCount())
                        item = QTableWidgetItem(path_1)
                        item.setToolTip(path_1)
                        item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                        self.file_table.setItem(self.file_table.rowCount()-1, 0, item)
                        item = QTableWidgetItem(path_2)
                        item.setToolTip(path_2)
                        item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                        self.file_table.setItem(self.file_table.rowCount()-1, 1, item)

    def remove_file(self):
        rows = set()
        for index in self.file_table.selectedIndexes():
            rows.add(index.row())
        for row in sorted(rows, reverse=True):
            self.file_table.removeRow(row)

    def rowCount(self):
        return self.file_table.rowCount()

    def get_file_table(self):
        return [(self.file_table.item(row, 0).text(), self.file_table.item(row, 1).text()) for row in range(self.file_table.rowCount())]


class DropFilesListWidget(QListWidget):
    """
    A QListWidget with drop support for files and folders. If a folder is dropped, all files contained in the folder are added.
    """

    def __init__(self, parent=None, filetypes=None, filenames_filter=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.filetypes = filetypes
        self.filenames_filter = filenames_filter

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls:
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            if url.isLocalFile():
                if os.path.isfile(url.toLocalFile()):
                    filename = url.toLocalFile()
                    if len(self.findItems(filename, Qt.MatchExactly)) == 0 and (len(self.filetypes) == 0 or self.filetypes is None or os.path.splitext(filename)[1] in self.filetypes) and (self.filenames_filter is None or self.filenames_filter in os.path.basename(filename)):
                        self.addItem(filename)
                if os.path.isdir(url.toLocalFile()):
                    d = url.toLocalFile()
                    # keep only files (not folders)
                    filenames = [os.path.join(d, f)
                                 for f in os.listdir(d)]
                    if not self.filetypes == '' and not self.filetypes is None:
                        # keep only allowed filetypes
                        filenames = [f for f in filenames
                                     if os.path.splitext(f)[1] in self.filetypes]
                    if not self.filenames_filter is None:
                        # keep only filenames containing filenames_filter
                        filenames = [f for f in filenames
                                     if self.filenames_filter in os.path.basename(f)]
                    # keep only existing files (not folders)
                    filenames = [f for f in filenames
                                 if os.path.isfile(f)]
                    # do not add if already in the list
                    filenames = [f for f in filenames
                                 if len(self.findItems(f, Qt.MatchExactly)) == 0]
                    self.addItems(filenames)

class FileListWidget(QWidget):
    """
    A list of files with filters, button to add files and folder and drag and drop support.
    """
    file_list_changed = pyqtSignal()
    file_list_double_clicked = pyqtSignal(QListWidgetItem)

    def __init__(self, parent=None, filetypes=None, filenames_filter=''):
        """
        Parameters
        ----------
        filetypes: list of str
            list of allowed file extensions, including the '.'. E.g. ['.tif','.nd2'].
            If empty: allow all extensions.
        filenames_filter: str
            filenames not containing this text will be ignored.
        """
        super().__init__(parent)

        if filetypes is None:
            filetypes = []
        self.filter_name = QLineEdit(filenames_filter, placeholderText='e.g.: _BF')
        self.filter_name.setToolTip('Accept only filenames containing this text')
        self.filter_name.textChanged.connect(self.filter_name_changed)
        self.filetypes = QLineEdit(' '.join(filetypes), placeholderText='e.g.: .nd2 .tif .tiff')
        self.filetypes.setToolTip('Space separated list of accepted file extensions.')
        self.filetypes.textChanged.connect(self.filetypes_changed)
        self.file_list = DropFilesListWidget(filetypes=self.filetypes.text().split(), filenames_filter=self.filter_name.text())
        self.file_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.file_list.model().rowsInserted.connect(self.file_list_rows_inserted)
        self.file_list.model().rowsRemoved.connect(self.file_list_rows_removed)
        self.file_list.itemDoubleClicked.connect(self.file_list_double_clicked)
        self.add_file_button = QPushButton("Add files", self)
        self.add_file_button.clicked.connect(self.add_file)
        self.add_folder_button = QPushButton("Add folder", self)
        self.add_folder_button.clicked.connect(self.add_folder)
        self.remove_file_button = QPushButton("Remove selected", self)
        self.remove_file_button.clicked.connect(self.remove_file)


        layout = QVBoxLayout()
        layout.addWidget(self.file_list)
        layout2 = QHBoxLayout()
        layout2.addWidget(self.add_file_button)
        layout2.addWidget(self.add_folder_button)
        layout2.addWidget(self.remove_file_button)
        layout.addLayout(layout2)
        layout2 = QHBoxLayout()
        layout3 = QFormLayout()
        layout3.addRow("Filter file names:", self.filter_name)
        layout2.addLayout(layout3)
        layout3 = QFormLayout()
        layout3.addRow("file types:", self.filetypes)
        layout2.addLayout(layout3)
        layout.addLayout(layout2)
        layout.setContentsMargins(0,0,0,0)
        self.setLayout(layout)

    def file_list_rows_inserted(self):
        self.file_list_changed.emit()

    def file_list_rows_removed(self):
        self.file_list_changed.emit()

    def filter_name_changed(self):
        self.file_list.filenames_filter = self.filter_name.text()

    def filetypes_changed(self):
        self.file_list.filetypes = self.filetypes.text().split()

    def add_file(self):
        type_list = ['*'+x for x in self.filetypes.text().split()]
        if len(type_list) == 0:
            type_list = ['*']
        if self.filter_name.text() != '':
            type_list = ['*'+self.filter_name.text()+x for x in type_list]

        file_paths, _ = QFileDialog.getOpenFileNames(self, 'Select Files', filter='Images ('+' '.join(type_list)+')')
        for file_path in file_paths:
            if self.filter_name.text() in os.path.basename(file_path):
                if file_path and len(self.file_list.findItems(file_path, Qt.MatchExactly)) == 0:
                    self.file_list.addItem(file_path)

    def add_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder_path:
            files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if os.path.splitext(f)[1] in self.filetypes.text().split() and self.filter_name.text() in f]
            self.file_list.addItems([f for f in files if len(self.file_list.findItems(f, Qt.MatchExactly)) == 0])

    def remove_file(self):
        for item in self.file_list.selectedItems():
            self.file_list.takeItem(self.file_list.row(item))

    def count(self):
        return self.file_list.count()

    def get_file_list(self):
        return [self.file_list.item(x).text() for x in range(self.file_list.count())]


class DropFileLineEdit(QLineEdit):
    """
    A QLineEdit with drop support for files.
    """

    def __init__(self, parent=None, filetypes=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.filetypes = filetypes

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls:
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            if url.isLocalFile():
                if os.path.isfile(url.toLocalFile()):
                    filename = url.toLocalFile()
                    if self.filetypes is None or len(self.filetypes) == 0 or os.path.splitext(filename)[1] in self.filetypes:
                        self.setText(filename)


class DropFolderLineEdit(QLineEdit):
    """
    A QLineEdit with drop support for folder.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls:
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            if url.isLocalFile():
                if os.path.isdir(url.toLocalFile()):
                    self.setText(url.toLocalFile())


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
        self.setIconSize(QSize(12, 12))
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


class Image:
    """
    Class used to read and elaborate images
    Default dimension positions = {'F': 0, 'T': 1, 'C': 2, 'Z': 3, 'Y': 4, 'X': 5}

    Attributes
    ----------
    path : str
        path to the image
    basename : str
        image name with extension
    name : str
        image name without extension
    extension : str
        extension of the image
    sizes : dict
        dictionary with dimesions names and values
        # eg. {'F': 1, 'T': 1, 'C': 3, 'Z': 11, 'Y': 2048, 'X': 2048}
    image : ndarray
        numpy ndarray with the image
    shape : list
        list with image shapes

    Methods
    -------
    imread()
        Read the image from the already setted 'path'
        Attributes image, sizes and shape are populated here
    save()
        Empty
    get_TYXarray()
        Return the 3D image with the dimensions T, Y and X.
        When used the other dimensions F,C,Z MUST be empty (with size = 1)
    zProjection(projection_type, zrange)
        Return the z-projection of the image using the selected projection type over the range of z values defined by zrange.
        Possible projection types: max, min, std, avg (or mean), median.
        If zrange is None, use all Z values. If zrange is an integer, use z values in [z_best-zrange,z_best+zrange],
        where z_best is the Z corresponding to best focus. If zrange is a tuple of lenght 2 (zmin,zmax), use z values in [zmin,zmax].
    """

    def __init__(self, im_path):
        self.path = im_path
        self.basename = os.path.basename(self.path)
        self.name, self.extension = os.path.splitext(self.basename)
        self.sizes = None
        self.image = None
        self.shape = None

    def imread(self):
        def set_6Dimage(image, axes):
            """
            Return a 6D ndarray of the input image
            """
            dimensions = {'F': 0, 'T': 1, 'C': 2, 'Z': 3, 'Y': 4, 'X': 5}
            # Dictionary with image axes order
            axes_order = {}
            for i, char in enumerate(axes):
                axes_order[char] = i
            # Mapping for the desired order of dimensions
            mapping = [axes_order.get(d, None) for d in 'FTCZYX']
            mapping = [i for i in mapping if i is not None]
            # Rearrange the image array based on the desired order
            image = np.transpose(image, axes=mapping)
            # Determine the missing dimensions and reshape the array filling the missing dimensions
            missing_dims = []
            for c in 'FTCZYX':
                if c not in axes:
                    missing_dims.append(c)
            for dim in missing_dims:
                position = dimensions[dim]
                image = np.expand_dims(image, axis=position)
            return image, image.shape

        # axis default order: FTCZYX for 6D - F = FieldofView, T = time, C = channels
        if self.extension == '.nd2':
            reader = nd2.ND2File(self.path)
            axes_order = str(''.join(list(reader.sizes.keys()))).upper() #eg. reader.sizes = {'T': 10, 'C': 2, 'Y': 2048, 'X': 2048}
            image = reader.asarray() #nd2.imread(self.path)
            reader.close()
            self.sizes = {}
            self.image, self.shape = set_6Dimage(image, axes_order)
            for key, value in zip('FTCZYX', self.shape):
                self.sizes[key] = value # eg. {'F': 1, 'T': 10, 'C': 2, 'Z': 1, 'Y': 2048, 'X': 2048}
            return self.image

        elif (self.extension == '.tiff' or self.extension == '.tif'):
            reader = tifffile.TiffFile(self.path)
            axes_order = str(reader.series[0].axes).upper()
            image = reader.asarray()
            reader.close()
            self.sizes = {}
            self.image, self.shape = set_6Dimage(image, axes_order)
            for key, value in zip('FTCZYX', self.shape):
                self.sizes[key] = value
            return self.image
        else:
            logging.getLogger(__name__).error('Image format not supported. Please upload a tiff or nd2 image file.')

    def save(self):
        pass

    def get_TYXarray(self):
        if self.sizes['F'] > 1 or self.sizes['C'] > 1 or self.sizes['Z'] > 1:
            logging.getLogger(__name__).error('Image format not supported. Please upload an image with only TYX dimesions.')
        return self.image[0,:,0,0,:,:]

    def zProjection(self, projection_type, zrange):
        """
        Return the z-projection of the image using the selected projection type over the range of z values defined by zrange.

        Parameters
        ----------
        projection_type: str
            the projection type (max, min, std, avg, mean or median)
        zrange: int or (int,int) or None
            the range of z sections to use for projection.
            If zrange is None, use all z sections.
            If zrange is an integer, use all z sections in the interval [z_best-zrange,z_best+zrange]
            where z_best is the Z corresponding to best focus.
            If zrange is tuple (zmin,zmax), use all z sections in the interval [zmin,zmax].

        Returns
        -------
        ndarray
            a 6D array with original image size, except for Z axis which has size 1.
        """
        if zrange is None:
            logging.getLogger(__name__).info('Z-Projection: projection type=%s, zrange=%s (All Z sections)', projection_type, zrange)
        elif isinstance(zrange, int) and zrange == 0:
            logging.getLogger(__name__).info('Z-Projection: projection type=%s, zrange=%s (Z section with best focus)', projection_type, zrange)
        elif isinstance(zrange, int):
            logging.getLogger(__name__).info('Z-Projection: projection type=%s, zrange=%s (Range %s around Z section with best focus)', projection_type, zrange, zrange)
        elif isinstance(zrange, tuple) and len(zrange) == 2 and zrange[0] <= zrange[1]:
            logging.getLogger(__name__).info('Z-Projection: projection type=%s, zrange=%s (Fixed range from %s to %s)', projection_type, zrange, zrange[0], zrange[1])
        else:
            logging.getLogger(__name__).info('Z-Projection: invalid zrange')
        projected_image = np.zeros((self.sizes['F'], self.sizes['T'], self.sizes['C'], 1, self.sizes['Y'], self.sizes['X']), dtype=self.image.dtype)
        sharpness = np.zeros(self.sizes['Z'])
        def gaus(x, a, x0, sigma, b):
            return a*np.exp(-(x-x0)**2/(2*sigma**2))+b
        for f in range(self.sizes['F']):
            for t in range(self.sizes['T']):
                for c in range(self.sizes['C']):
                    z_values = None
                    if zrange is None:
                        # use all Z
                        z_values = list(range(self.sizes['Z']))
                        logging.getLogger(__name__).info('Z-Projection (F: %s, T: %s, C: %s): %s over z in %s (all)', f, t, c, projection_type, z_values)
                    elif isinstance(zrange, int):
                        # use zrange around Z with best focus
                        for z in range(self.sizes['Z']):
                            sharpness[z] = cv.Laplacian(self.image[f, t, c, z, :, :].astype("float64"), cv.CV_64F, ksize=11).var()

                        # fit a gaussian and extract position of the max
                        try:
                            popt, pcov = curve_fit(gaus, np.arange(sharpness.shape[0]), sharpness/max(sharpness), p0=[1, 5, 2, 0.1])
                            z_best = round(popt[1])
                            fit_error = False
                        except:
                            z_best = int((self.sizes['Z']-1)/2)
                            fit_error = True

                        # if z_best is too close to min or maz 'Z' => shift best_z so as to keep (2*zrange+1) z values (z_values).
                        z_best_tmp = min(max(z_best, zrange), self.sizes['Z']-zrange-1)
                        z_values = [z for z in range(z_best_tmp-zrange, z_best_tmp+zrange+1) if z < self.sizes['Z'] and z >= 0 ]

                        if fit_error:
                            logging.getLogger(__name__).info('Z-Projection (F: %s, T: %s, C: %s): %s over z in %s (Best z estimation failed, using default value %s)', f, t, c, projection_type, z_values, z_best)
                        else:
                            logging.getLogger(__name__).info('Z-Projection (F: %s, T: %s, C: %s): %s over z in %s (Best z=%s)', f, t, c, projection_type, z_values, z_best)
                    elif isinstance(zrange, tuple) and len(zrange) == 2 and zrange[0] <= zrange[1]:
                        # use fixed range
                        z_values = [z for z in range(zrange[0], zrange[1]+1) if z < self.sizes['Z'] and z >= 0]
                        logging.getLogger(__name__).info('Z-Projection (F: %s, T: %s, C: %s): %s over z in %s (fixed range)', f, t, c, projection_type, z_values)

                    if len(z_values) == 1:
                        projected_image[f, t, c, 0, :, :] = self.image[f, t, c, z_values[0], :, :].copy()
                    elif projection_type == 'max':
                        projected_image[f, t, c, 0, :, :] = np.max(self.image[f, t, c, z_values, :, :], axis=0)
                    elif projection_type == 'min':
                        projected_image[f, t, c, 0, :, :] = np.min(self.image[f, t, c, z_values, :, :], axis=0)
                    elif projection_type == 'std':
                        projected_image[f, t, c, 0, :, :] = np.std(self.image[f, t, c, z_values, :, :], axis=0, ddof=1)
                    elif projection_type == 'avg' or projection_type == 'mean':
                        projected_image[f, t, c, 0, :, :] = np.mean(self.image[f, t, c, z_values, :, :], axis=0)
                    elif projection_type == 'median':
                        projected_image[f, t, c, 0, :, :] = np.median(self.image[f, t, c, z_values, :, :], axis=0)
                    else:
                        logging.getLogger(__name__).error('Projection type not recognized')
                        return None

        return projected_image


def update_transfMat(tmat_int, reference_timepoint_index, range_start_index, range_end_index):
    """
    Update the transformation matrix
    
    Parameters
    ----------
        tmat_int : 
            original matrix
        reference_timepoint_index : 
            index of the new reference point
        range_start_index : 
            index of the starting timepoint (included)
        range_end_index : 
            index of the ending timepoint (included)
    """

    # Step 1:
    # get x- and y- offset values for the reference timepoint
    min_timepoint = min(tmat_int[:,0]) -1
    max_timepoint = max(tmat_int[:,0]) -1

    exc1 = reference_timepoint_index < range_start_index
    exc2 = reference_timepoint_index > range_end_index
    exc3 = range_start_index < min_timepoint
    exc4 = range_end_index > max_timepoint

    if exc1 or exc2 or exc3 or exc4:
        logging.getLogger(__name__).error('Values out of range')
        return tmat_int

    reference_rawXoffset = tmat_int[reference_timepoint_index,4]
    reference_rawYoffset = tmat_int[reference_timepoint_index,5]
    
    # Step 2:
    # subtract reference point offset values from all other timepoints and write them to 2nd and 3rd columns,
    # which will are used for registration from transformation matrices
    tmat_updated = np.copy(tmat_int)
    for counter in range(0,len(tmat_int)):
        tmat_updated[counter,1] = tmat_int[counter,4]-reference_rawXoffset
        tmat_updated[counter,2] = tmat_int[counter,5]-reference_rawYoffset
        tmat_updated[counter,3] = 0        
    
    # Step 3:
    # write in 4th column whether the timepoint is included in the registration (value = 1)
    # or excluded from registration (value = 0)
    for counter in range(range_start_index, range_end_index+1):
        tmat_updated[counter,3] = 1
    return tmat_updated


def error_empty(submission_num, widget, window):
    """
    Add an error line in the main application window when missing input values
    """
    widget.setFocus()
    if submission_num == 1:
        label_error = QLabel('Error : missing value')
        label_error.setAlignment(Qt.AlignCenter)
        label_error.setStyleSheet("color: red;")
        window.addRow(label_error)
        return label_error


def adjust_graph_types(graph, mask_dtype):
    graph.vs['frame'] = np.array(graph.vs['frame'], dtype='int32')
    graph.vs['mask_id'] = np.array(graph.vs['mask_id'], dtype=mask_dtype)
    graph.vs['area'] = np.array(graph.vs['area'], dtype='int64')
    graph.es['overlap_area'] = np.array(graph.es['overlap_area'], dtype='int64')
    graph.es['frame_source'] = np.array(graph.es['frame_source'], dtype='int32')
    graph.es['frame_target'] = np.array(graph.es['frame_target'], dtype='int32')
    graph.es['mask_id_source'] = np.array(graph.es['mask_id_source'], dtype=mask_dtype)
    graph.es['mask_id_target'] = np.array(graph.es['mask_id_target'], dtype=mask_dtype)
    # Remove useless attribute
    return graph


def plot_graph(viewer, graph_path):
    """
    Add two layers (with names 'Edges' and 'Vertices') to the `viewer_graph`
    and plot the cell tracking graph.
    Existing layers  'Edges' and 'Vertices' will be cleared.
    Setup mouse click callbacks to allow vertices selection in `viewer_graph`
    and centering `viewer_images` camera to specific vertex.

    Parameters
    ----------
    viewer_graph: napari.Viewer
        napari viewer in which the graph should be displayed.
    viewer_images: napari.Viewer
        napari viewer with image and mask.
    mask_layer: napari.layer.Labels
        napari layer with segmentation mask.
    graph: igraph.Graph
        cell tracking graph.
    colors: numpy.array
        numpy array with shape (number of colors,4) with one color per
        row (row index i corresponds to to mask id i)
    """
    graph = ig.Graph().Read_GraphMLz(graph_path)
    # Adjust attibute types
    graph = adjust_graph_types(graph, 'uint16')

    mask_ids = [v['mask_id'] for v in graph.vs]

    colors = []
    for i, c in enumerate(cm.hsv(np.linspace(0, 1, max(mask_ids)+1))):
        colors.append(c.tolist())
    colors = np.asarray(colors)

    layout_per_component = True
    if layout_per_component:
        # Layout_sugiyama doesn't always properly split connectected components.
        # This is an attempt to overcome this problem.
        # A better option would probably be to use the algorithm used by graphviz (dot) or graphviz.
        components = graph.connected_components(mode='weak')
        layout = [[0.0, 0.0] for v in graph.vs]
        lastx = 0
        for cmp in components:
            g2 = graph.subgraph(cmp)
            layout_tmp = g2.layout_sugiyama(
                layers=[f+min(graph.vs['frame']) for f in g2.vs['frame']], maxiter=1000)
            # Shift x coord by lastx
            minx = min(x for x, y in layout_tmp.coords)
            maxx = max(x for x, y in layout_tmp.coords)
            for i, j in enumerate(cmp):
                x, y = layout_tmp[i]
                layout[j] = [x-minx+lastx, y]
            lastx = lastx-minx+maxx+1  # max([x+lastx for x,y in layout_tmp.coords])+1
    else:
        # Simple layout_sugiyama
        layout = graph.layout_sugiyama(
            layers=[f+min(graph.vs['frame']) for f in graph.vs['frame']], maxiter=1000)

    vertex_size = 0.4
    edge_w_min = 0.01
    edge_w_max = vertex_size*0.8

    # Edges
    if not 'Edges' in viewer.layers:
        edges_layer = viewer.add_shapes(name='Edges', opacity=1)
    else:
        edges_layer = viewer.layers['Edges']
        edges_layer.data = []

    # Note: (x,y) to reverse horizontal order (left to right)
    edges_coords = [[[layout[e.source][0], layout[e.source][1]], [
        layout[e.target][0], layout[e.target][1]]] for e in graph.es]
    edges_layer.add(edges_coords,
                    edge_width=np.minimum(graph.es['overlap_fraction_target'],
                                          graph.es['overlap_fraction_source']) * (edge_w_max - edge_w_min) + edge_w_min,
                    edge_color="lightgrey",
                    shape_type='line')
    edges_layer.editable = False
    edges_layer.refresh()

    # Add vertices
    if not 'Vertices' in viewer.layers:
        vertices_layer = viewer.add_points(name='Vertices', opacity=1)
        vertices_layer.help = "<left-click> to set view, <right-click> to select, <shift>+<right-click> to extend selection"
        vertices_layer_isnew = True
    else:
        vertices_layer = viewer.layers['Vertices']
        vertices_layer.data = []
        vertices_layer_isnew = False

    vertices_layer.add(np.array(layout[:graph.vcount()]))
    vertices_layer.edge_width_is_relative = True
    vertices_layer.edge_width = 0.0
    vertices_layer.symbol = 'square'
    vertices_layer.size = vertex_size
    vertices_layer.face_color = colors[mask_ids]
    vertices_layer.properties = {'frame': graph.vs['frame'],
                                 'mask_id': graph.vs['mask_id'],
                                 'selected': np.repeat(False, graph.vcount())}
    vertices_layer.selected_data = set()
    vertices_layer.editable = False

    vertices_layer.refresh()

    # Note: it would be probably better to use the already existing option to select points in the Points layer instead of using an additional 'selected' property.
    # However I couldn't manage to allow selecting points without allowing to move, add or delete points (moving, adding, deleting points should not be allowed as it would cause trouble later).

    if vertices_layer_isnew:
        # mouse click on viewer_graph
        @vertices_layer.mouse_drag_callbacks.append
        def click_drag(layer, event):
            dragged = False
            yield
            # on move
            while event.type == 'mouse_move':
                dragged = True
                yield
            # on release
            if not dragged:  # i.e. simple click
                if event.button == 1:  # center view (left-click)
                    # center view on corresponding vertex
                    point_id = layer.get_value(event.position)
                elif event.button == 2:  # selection (right-click)
                    # vertices selection (multple mask_ids, same frame range for all)
                    point_id = layer.get_value(event.position)
                    if not point_id is None:
                        if 'Shift' in event.modifiers:
                            # add to selection
                            layer.properties['selected'][point_id] = True
                            # find frame range
                            v_selected = np.where(layer.properties['selected'])[0]
                            frame_min = np.min(layer.properties['frame'][v_selected])
                            frame_max = np.max(layer.properties['frame'][v_selected])
                            # find selected mask_ids
                            mask_ids = layer.properties['mask_id'][v_selected]
                            # erase previous selection
                            layer.properties['selected'] = False
                            # select all vertice with mask_id in mask_ids and within frame_range
                            layer.properties['selected'][(layer.properties['frame'] >= frame_min) & (layer.properties['frame'] <= frame_max) & (np.isin(layer.properties['mask_id'], mask_ids))] = True
                        else:
                            # replace selection
                            layer.properties['selected'][layer.properties['selected']] = False
                            layer.properties['selected'][point_id] = not layer.properties['selected'][point_id]
                    else:
                        if not 'Control' in event.modifiers and not 'Shift' in event.modifiers:
                            # erase selection
                            layer.properties['selected'][layer.properties['selected']] = False
                    # change style
                    layer.edge_color[layer.properties['selected']] = [1.0, 1.0, 1.0, 1.0]  # white
                    layer.edge_width[~layer.properties['selected']] = 0
                    layer.edge_width[layer.properties['selected']] = 0.4
                    layer.refresh()

        viewer.reset_view()


class IgnoreDuplicate(logging.Filter):
    """
    logging filter to ignore duplicate messages.
    """

    def __init__(self, message=None):
        logging.Filter.__init__(self)
        self.last = None
        self.message = message

    def filter(self, record):
        current = (record.module, record.levelno, record.msg)
        if self.message is None or self.message == record.msg:
            # add other fields if you need more granular comparison, depends on your app
            if self.last is None or current != self.last:
                self.last = current
                return True
            return False
        self.last = current
        return True
