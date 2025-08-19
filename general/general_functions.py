import numpy as np
import os
import tifffile
import nd2
import re
import webbrowser
from aicsimageio.readers import OmeTiffReader
from PyQt5.QtCore import Qt, pyqtSignal, QUrl, QRegularExpression
from PyQt5.QtGui import QBrush, QKeySequence, QPainter, QFontMetrics, QTextDocument, QColor, QRegularExpressionValidator
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QHBoxLayout, QFormLayout, QWidget, QLineEdit, QScrollArea, QListWidget, QMessageBox, QTableWidget, QHeaderView, QTableWidgetItem, QAbstractItemView, QPushButton, QFileDialog, QListWidgetItem, QDialog, QShortcut, QRadioButton, QSpinBox, QComboBox, QGroupBox

import logging
import igraph as ig
import cv2


output_suffixes = {'zprojection': '_vPR',
                   'ground_truth_generator': '_vGT',
                   'registration': '_vRG',
                   'segmentation': '_vSM',
                   'cell_tracking': '_vTG',
                   'graph_filtering': '_vGF',
                   'events_selection': '_vES',
                   'image_cropping': '_vCR'}
imagetypes = ['.nd2', '.tif', '.tiff', '.ome.tif', '.ome.tiff']
graphtypes = ['.graphmlz']
matrixtypes = ['.txt', '.csv']


def splitext(path):
    """
    Quick and dirty hack based on os.path.splitext() but modified to
    deal with .ome.* extensions (e.g. .ome.tif, .ome.tiff, .ome.zarr, ...).
    Split `path` into a pair (root, ext) such that root + ext == path
    and ext is everything from the last dot to the end, except if root
    ends with ".ome", in which case ".ome" is moved to ext.

    Parameters
    ----------
    path: str
        a path name.

    Returns
    -------
    (str, str)
        a tuple (root, ext).

    Examples
    --------
    >>> splitext('bar')
    ('bar', '')

    >>> splitext('foo.bar.exe')
    ('foo.bar', '.exe')

    >>> splitext('foo.ome.tif')
    ('foo', '.ome.tif')

    >>> splitext('.cshrc')
    ('.cshrc', '')

    >>> splitext('/foo/....jpg')
    ('/foo/....jpg', '')

    >>> splitext('project-v0.4.17.zip')
    ('project-v0.4.17', '.zip')
    """
    root, ext = os.path.splitext(path)
    ext2 = '.ome'
    if root.endswith(ext2):
        root, ext2 = os.path.splitext(root)
        ext = ext2 + ext
    return (root, ext)


class CollapsibleWidget(QWidget):
    def __init__(self, text, parent=None, collapsed_icon="▶", expanded_icon="▼", expanded=True):
        super().__init__(parent)

        self.collapsed_icon = collapsed_icon
        self.expanded_icon = expanded_icon

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        layout2 = QHBoxLayout()
        self.button = QPushButton()
        self.button.setCheckable(True)
        self.button.setChecked(expanded)
        self.button.setStyleSheet("border: none;background: none;padding-left: 0px; padding-right: 0px;padding-top: 0px; padding-bottom: 0px;")
        self.content = QWidget()
        layout2.addWidget(self.button, alignment=Qt.AlignLeft)
        layout2.addWidget(QLabel(text))
        layout2.addStretch()
        layout.addLayout(layout2)
        layout.addWidget(self.content)

        self.set_icon(self.button.isChecked())
        self.content.setVisible(self.button.isChecked())
        self.button.clicked.connect(self.content.setVisible)
        self.button.clicked.connect(self.set_icon)

    def set_icon(self, expanded):
        if expanded:
            self.button.setText(self.expanded_icon)
        else:
            self.button.setText(self.collapsed_icon)


class CollapsibleLabel(QLabel):
    def __init__(self, text, parent=None, collapsed=False):
        super().__init__(text, parent)
        self.collapsed = collapsed
        self.raw_text = text
        self.setTextFormat(Qt.RichText)
        self.linkActivated.connect(self.link_activated)
        self.setText(text)
        self.setWordWrap(True)
        super().setOpenExternalLinks(False)

    def setText(self, text):
        self.raw_text = text
        super().setText(self.elide_text(self.raw_text))

    def elide_text(self, text):
        metrics = QFontMetrics(self.font())
        if self.collapsed:
            # keep only first line (we force Rich Text format => split at <br>, <p>, <div>, <h1> ... or <h6>)
            elided = re.split(r'(<br>|<p>|<div>|<h[1-6]>)', text)[0]
            # convert to plain text to avoid problem with text length and html tags
            document = QTextDocument()
            document.setHtml(elided)
            elided = document.toPlainText()
            elided = metrics.elidedText(elided, Qt.ElideRight, self.width()-metrics.boundingRect('... [show more]').width())
            if elided != text:
                elided += ' <a href="_EXPAND_">[show more]</a>'
        else:
            # keep only first line (we force Rich Text format => split at <br>, <p>, <div>, <h1> ... or <h6>)
            elided = re.split(r'(<br>|<p>|<div>|<h[1-6]>)', text)[0]
            elided = metrics.elidedText(elided, Qt.ElideRight, self.width())
            if elided != text:
                elided = text+'<br><a href="_COLLAPSE_">[show less]</a>'
        return elided

    def resizeEvent(self, event):
        super().setText(self.elide_text(self.raw_text))

    def link_activated(self, link):
        if link == '_EXPAND_':
            self.collapsed = False
            super().setText(self.elide_text(self.raw_text))
        elif link == '_COLLAPSE_':
            self.collapsed = True
            super().setText(self.elide_text(self.raw_text))
        else:
            # deal with url fragment
            tmp = link.split('#')
            if len(tmp) == 2:
                url = QUrl.fromUserInput(tmp[0])
                url.setFragment(tmp[1])
            else:
                url = QUrl.fromUserInput(link)
            webbrowser.open(url.toString())


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


class BufferedHandler(logging.Handler):
    """
    Logging handler to store messages.

    Examples
    --------
    handler= BufferedHandler(self)
    handler.setLevel(logging.INFO)
    logging.getLogger().addHandler(handler)
    """

    def __init__(self):
        logging.Handler.__init__(self)
        self.records = []

    def emit(self, record):
        self.records.append(self.format(record))

    def reset(self):
        self.records = []

    def get_messages(self):
        if len(self.records) > 0:
            return "\n".join(self.records)+"\n"
        else:
            return ""


class StatusTableDialog(QDialog):
    """
    a dialog to report job status.

    Examples
    --------
    msg=StatusTableDialog(['image1.tif','image2.tif','image3.tif'])
    msg.exec_()
    """

    def __init__(self, input_files):
        super().__init__()
        self.setSizeGripEnabled(True)
        self.setWindowTitle('Status')
        layout = QVBoxLayout()
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(['Status', 'Input file'])
        self.table.verticalHeader().hide()
        self.table.setTextElideMode(Qt.ElideLeft)
        self.table.setWordWrap(False)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        for f in input_files:
            self.table.insertRow(self.table.rowCount())
            item = QTableWidgetItem('')
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            item.setToolTip('')
            self.table.setItem(self.table.rowCount()-1, 0, item)
            item = QTableWidgetItem(f)
            item.setToolTip(f)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(self.table.rowCount()-1, 1, item)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.done)
        layout.addWidget(self.ok_button, alignment=Qt.AlignCenter)
        self.setLayout(layout)

    def set_status(self, row, status, error_message=''):
        self.table.item(row, 0).setText(status)
        self.table.item(row, 0).setToolTip(error_message)
        if status == 'Success':
            self.table.item(row, 0).setBackground(QBrush(QColor('#00ff00')))
            self.table.item(row, 0).setForeground(QBrush(QColor('#000000')))
        elif status == 'Failed':
            self.table.item(row, 0).setBackground(QBrush(QColor('#ff0000')))
            self.table.item(row, 0).setForeground(QBrush(QColor('#000000')))
        else:
            self.table.item(row, 0).setBackground(self.table.palette().base())
            self.table.item(row, 0).setForeground(self.table.palette().text())

    def keyPressEvent(self, event):
        # to disable reject() with escape key
        if event.key() != Qt.Key_Escape:
            super().keyPressEvent(event)


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


class NapariStatusBarHandler(logging.Handler):
    """
    Logging handler to send message to the status bar of a napari viewer.

    Examples
    --------
    viewer=napari.viewer()
    handler=NapariStatusBarHandler(viewer)
    logging.getLogger().addHandler(handler)
    """

    def __init__(self, viewer):
        logging.Handler.__init__(self)
        self.status_bar = viewer.window._qt_window.statusBar()

    def emit(self, record):
        msg = self.format(record)
        self.status_bar.showMessage(msg, msecs=1000)
        # force repainting to update message even when busy
        self.status_bar.repaint()


class DropFilesTableWidget2(QTableWidget):
    """
    A QTableWidget with drop support for files and folders with 2 columns. If a folder is dropped, all files contained in the folder are added.
    """

    def __init__(self, filter_files_callback, parent=None, header_1=None, header_2=None):
        super().__init__(parent)
        self.setColumnCount(2)
        self.setHorizontalHeaderLabels([header_1, header_2])
        self.verticalHeader().hide()
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.setAcceptDrops(True)
        self.setTextElideMode(Qt.ElideLeft)
        self.setWordWrap(False)
        self.filter_files_callback = filter_files_callback
        shortcut = QShortcut(QKeySequence.Delete, self)
        shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        shortcut.activated.connect(self.remove_selected)

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
                    self.add_files([url.toLocalFile()])
                if os.path.isdir(url.toLocalFile()):
                    d = url.toLocalFile()
                    # keep only files (not folders)
                    self.add_files([os.path.join(d, f) for f in os.listdir(d)])

    def remove_selected(self):
        rows = set()
        for index in self.selectedIndexes():
            rows.add(index.row())
        for row in sorted(rows, reverse=True):
            self.removeRow(row)

    def add_files(self, filenames):
        filenames = self.filter_files_callback(filenames)
        for path_1, path_2 in filenames:
            self.insertRow(self.rowCount())
            item = QTableWidgetItem(os.path.normpath(path_1))
            item.setToolTip(os.path.normpath(path_1))
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.setItem(self.rowCount()-1, 0, item)
            item = QTableWidgetItem(os.path.normpath(path_2))
            item.setToolTip(os.path.normpath(path_2))
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.setItem(self.rowCount()-1, 1, item)


class FileTableWidget2(QWidget):
    """
    A 2 columns table of files with filters, button to add files and folder and drag and drop support.
    Corresponding files in both columns are assumed to share a common base name and only differ in the
    filename suffix.
    """
    file_table_changed = pyqtSignal()

    def __init__(self, parent=None, header_1=None, header_2=None, filenames_suffix_1=None, filenames_suffix_2=None, filenames_filter='', filenames_exclude_filter=''):
        """
        Parameters
        ----------
        header_1: str
            name of the first column.
        header_2: str
            name of the second column.
        filenames_suffix_1: str
            filenames not ending with this text will be ignored (for column 1).
        filenames_suffix_2: str
            filenames not ending with this text will be ignored (for column 2).
        filenames_filter: str
            filenames not containing this text will be ignored.
        filenames_exclude_filter: str
            filenames containing this text will be ignored.
        """
        super().__init__(parent)

        self.header_1 = header_1
        self.header_2 = header_2
        self.filter_name = QLineEdit(filenames_filter, placeholderText='e.g.: _BF')
        self.filter_name.setToolTip('Accept only filenames containing this text. Filtering is done only when populating the table.')
        self.filter_name_exclude = QLineEdit(filenames_exclude_filter, placeholderText='e.g.: _WL508')
        self.filter_name_exclude.setToolTip('Accept only filenames NOT containing this text. Filtering is done only when populating the table.')

        self.suffix_1 = QLineEdit(filenames_suffix_1, placeholderText='e.g.: _vTG.ome.tif')
        self.suffix_1.setToolTip('Accept only filenames ending with this text.')
        self.suffix_2 = QLineEdit(filenames_suffix_2, placeholderText='e.g.: _vTG.graphmlz')
        self.suffix_2.setToolTip('Accept only filenames ending with this text')
        self.file_table = DropFilesTableWidget2(self.filter_files, header_1=header_1, header_2=header_2)
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
        filters = CollapsibleWidget('Filters (applied when populating the table)', expanded=False)
        layout2 = QHBoxLayout()
        filters.content.setLayout(layout2)
        layout3 = QFormLayout()
        layout3.addRow("Filename must include:", self.filter_name)
        layout2.addLayout(layout3)
        layout3 = QFormLayout()
        layout3.addRow("Filename must NOT include:", self.filter_name_exclude)
        layout2.addLayout(layout3)
        layout.addWidget(filters)
        layout.addWidget(self.file_table)
        layout2 = QHBoxLayout()
        layout2.addWidget(self.add_file_button)
        layout2.addWidget(self.add_folder_button)
        layout2.addWidget(self.remove_file_button)
        layout.addLayout(layout2)
        layout2 = QHBoxLayout()
        layout3 = QFormLayout()
        layout3.addRow(header_1 + " suffix:", self.suffix_1)
        layout2.addLayout(layout3)
        layout3 = QFormLayout()
        layout3.addRow(header_2 + " suffix:", self.suffix_2)
        layout2.addLayout(layout3)
        layout.addLayout(layout2)
        help_label = QLabel("Corresponding " + header_1 + " and " + header_2 + " files must be in the same folder. Their filenames must share the same basename and end with the specified suffix (by default <basename>"+self.suffix_1.text()+" and <basename>"+self.suffix_2.text()+")")
        help_label.setWordWrap(True)
        layout.addWidget(help_label)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

    def file_table_rows_inserted(self):
        self.file_table_changed.emit()

    def file_table_rows_removed(self):
        self.file_table_changed.emit()

    def add_file(self):
        type_list = ['*'+self.suffix_1.text(), '*'+self.suffix_2.text()]
        if self.filter_name.text() != '':
            type_list = ['*'+self.filter_name.text()+x for x in type_list]
        file_paths, _ = QFileDialog.getOpenFileNames(self, 'Select Files', filter=self.header_1+' or '+self.header_2+' ('+' '.join(type_list)+')')
        self.file_table.add_files(file_paths)

    def add_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder_path:
            self.file_table.add_files([os.path.join(folder_path, file_path) for file_path in os.listdir(folder_path)])

    def remove_file(self):
        self.file_table.remove_selected()

    def rowCount(self):
        return self.file_table.rowCount()

    def filter_files(self, filenames):
        filtered_filenames = []
        for file_path in filenames:
            path_1 = None
            path_2 = None
            re_pattern = self.suffix_1.text() + '$'
            if re.search(re_pattern, file_path):
                basename = re.sub(re_pattern, '', file_path)
                path_1 = os.path.normpath(file_path)
                if os.path.isfile(basename + self.suffix_2.text()):
                    path_2 = os.path.normpath(basename + self.suffix_2.text())
            re_pattern = self.suffix_2.text() + '$'
            if re.search(re_pattern, file_path):
                basename = re.sub(re_pattern, '', file_path)
                path_2 = os.path.normpath(file_path)
                if os.path.isfile(basename + self.suffix_1.text()):
                    path_1 = os.path.normpath(basename + self.suffix_1.text())
            if path_1 is not None and path_2 is not None:
                if self.filter_name.text() in os.path.basename(path_1) and self.filter_name.text() in os.path.basename(path_2):
                    if self.filter_name_exclude.text() == '' or (not self.filter_name_exclude.text() in os.path.basename(path_1) and self.filter_name_exclude.text() not in os.path.basename(path_2)):
                        if len(self.file_table.findItems(path_2, Qt.MatchExactly)) == 0 and len(self.file_table.findItems(path_1, Qt.MatchExactly)) == 0:
                            if (path_1, path_2) not in filtered_filenames:
                                if os.path.isfile(path_1) and os.path.isfile(path_1):
                                    filtered_filenames.append((path_1, path_2))
        return filtered_filenames

    def get_file_table(self):
        return [(self.file_table.item(row, 0).text(), self.file_table.item(row, 1).text()) for row in range(self.file_table.rowCount())]

    def set_file_table(self, files):
        self.file_table.clearContents()
        self.file_table.setRowCount(0)
        for f1, f2 in files:
            self.file_table.insertRow(self.file_table.rowCount())
            item = QTableWidgetItem(os.path.normpath(f1))
            item.setToolTip(os.path.normpath(f1))
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.file_table.setItem(self.file_table.rowCount()-1, 0, item)
            item = QTableWidgetItem(os.path.normpath(f2))
            item.setToolTip(os.path.normpath(f2))
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.file_table.setItem(self.file_table.rowCount()-1, 1, item)


class ImageMatrixTableWidget2(QWidget):
    """
    A 2 columns table of files with filters, button to add files and folder and drag and drop support.
    This is a special case for pairs of images (or masks) and registration matrices.
    Corresponding image (or mask) and registration matrix in both columns are assumed to share a common unique identifier (part of the filename before the first "_".
    If multiple registration matrices match a given image (or mask), the one with shortest filename is arbitrarily chosen.
    """

    def __init__(self, parent=None, filetypes=None, filenames_filter='', filenames_exclude_filter='', image_label='image'):
        """
        Parameters
        ----------
        filetypes: list of str
            list of allowed file extensions, including the '.'. E.g. ['.tif','.nd2'].
            If empty: allow all extensions.
        filenames_filter: str
            filenames not containing this text will be ignored.
        filenames_exclude_filter: str
            filenames containing this text will be ignored.
        """
        super().__init__(parent)

        self.image_label = image_label
        if filetypes is None:
            filetypes = []
        self.filter_name = QLineEdit(filenames_filter, placeholderText='e.g.: _BF')
        self.filter_name.setToolTip('Accept only filenames containing this text. Filtering is done only when populating the table.')
        self.filter_name_exclude = QLineEdit(filenames_exclude_filter, placeholderText='e.g.: _WL508')
        self.filter_name_exclude.setToolTip('Accept only filenames NOT containing this text. Filtering is done only when populating the table.')
        self.filetypes = QLineEdit(' '.join(filetypes), placeholderText='e.g.: .nd2 .tif .tiff .ome.tif .ome.tiff')
        self.filetypes.setToolTip('Space separated list of accepted '+self.image_label+' file extensions. Filtering is done only when populating the list.')

        self.file_table = DropFilesTableWidget2(self.filter_files, header_1=self.image_label[:1].upper()+self.image_label[1:], header_2='Matrix')
        self.file_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.file_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.add_file_button = QPushButton("Add files", self)
        self.add_file_button.clicked.connect(self.add_file)
        self.add_folder_button = QPushButton("Add folder", self)
        self.add_folder_button.clicked.connect(self.add_folder)
        self.remove_file_button = QPushButton("Remove selected", self)
        self.remove_file_button.clicked.connect(self.remove_file)

        layout = QVBoxLayout()
        filters = CollapsibleWidget('Filters (applied when populating the table)', expanded=False)
        layout2 = QHBoxLayout()
        filters.content.setLayout(layout2)
        layout3 = QFormLayout()
        layout3.addRow("Filename must include:", self.filter_name)
        layout2.addLayout(layout3)
        layout3 = QFormLayout()
        layout3.addRow("Filename must NOT include:", self.filter_name_exclude)
        layout2.addLayout(layout3)
        layout3 = QFormLayout()
        layout3.addRow(self.image_label[:1].upper()+self.image_label[1:]+" types:", self.filetypes)
        layout2.addLayout(layout3)
        layout.addWidget(filters)
        layout.addWidget(self.file_table)
        layout2 = QHBoxLayout()
        layout2.addWidget(self.add_file_button)
        layout2.addWidget(self.add_folder_button)
        layout2.addWidget(self.remove_file_button)
        layout.addLayout(layout2)
        help_label = QLabel("Add "+self.image_label+"s to the list using \"Add files\", \"Add folder\" buttons or drag and drop. The corresponding matrix file must be in the same folder as the "+self.image_label+". Their filenames must share the same unique identifier (part of the filename before the first \"_\"). If multiple matrix files correspond to an "+self.image_label+", the matrix with shortest filename will be selected.")
        help_label.setWordWrap(True)
        layout.addWidget(help_label)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

    def add_file(self):
        type_list = ['*'+x for x in self.filetypes.text().split()]
        if self.filter_name.text() != '':
            type_list = ['*'+self.filter_name.text()+x for x in type_list]
        file_paths, _ = QFileDialog.getOpenFileNames(self, 'Select Files', filter='Images ('+' '.join(type_list)+')')
        self.file_table.add_files(file_paths)

    def add_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder_path:
            self.file_table.add_files([os.path.join(folder_path, file_path) for file_path in os.listdir(folder_path)])

    def remove_file(self):
        self.file_table.remove_selected()

    def rowCount(self):
        return self.file_table.rowCount()

    def filter_files(self, filenames):
        filtered_filenames = []
        multiple_matches_images = []
        multiple_matches_matrix = []
        multiple_matches_candidates = []
        not_found = []
        for image_path in filenames:
            image_path = os.path.normpath(image_path)
            if len(self.filetypes.text().split()) == 0 or splitext(image_path)[1] in self.filetypes.text().split():
                if self.filter_name.text() in os.path.basename(image_path):
                    if self.filter_name_exclude.text() == '' or self.filter_name_exclude.text() not in os.path.basename(image_path):
                        if os.path.isfile(image_path):
                            if len(self.file_table.findItems(image_path, Qt.MatchExactly)) == 0:
                                # search for candidate registration matrix paths
                                candidate_paths = [path for path in os.listdir(os.path.dirname(image_path)) if any(path.endswith(matricestype) for matricestype in matrixtypes) and output_suffixes['registration'] in path and os.path.basename(path).split('_')[0] == splitext(os.path.basename(image_path))[0].split('_')[0]]
                                # sort by path length
                                candidate_paths = [os.path.normpath(os.path.join(os.path.dirname(image_path), path)) for path in sorted(candidate_paths, key=len)]
                                if len(candidate_paths) == 0:
                                    not_found.append(image_path)
                                else:
                                    # keep shortest path length
                                    matrix_path = candidate_paths[0]
                                    if len(candidate_paths) > 1:
                                        multiple_matches_images.append(image_path)
                                        multiple_matches_matrix.append(matrix_path)
                                        multiple_matches_candidates.append(candidate_paths)
                                    if (image_path, matrix_path) not in filtered_filenames:
                                        filtered_filenames.append((image_path, matrix_path))

        if len(not_found) > 0 or len(multiple_matches_images) > 0:
            text = 'Problems when searching matching registration matrices'
            informative_text = ''
            detailed_text = ''
            i = 1
            if len(not_found) > 0:
                informative_text += str(i)+') Registration matrix not found.\n'
                detailed_text += 'Registration matrix not found for the following '+self.image_label+'(s):\n - ' + '\n - '.join(not_found) + '\n\n'
                i += 1
            if len(multiple_matches_images) > 0:
                informative_text += str(i)+') Multiple candidate registration matrices (matrix with shortest filename was selected).\n'
                detailed_text += '\n\n'.join([self.image_label[:1].upper()+self.image_label[1:]+':\n - ' + image + '\nSelected registration matrix:\n - ' + os.path.basename(matrix) + '\nCandidate registration matrices:\n - ' + '\n - '.join([os.path.basename(x) for x in candidates]) for image, matrix, candidates in zip(multiple_matches_images, multiple_matches_matrix, multiple_matches_candidates)])
            msgbox = QMessageBox()
            msgbox.setIcon(QMessageBox.Warning)
            msgbox.setWindowTitle("Warning")
            msgbox.setText(text)
            msgbox.setInformativeText(informative_text)
            msgbox.setDetailedText(detailed_text)
            msgbox.addButton(QMessageBox.Ok)
            msgbox.exec()
        return filtered_filenames

    def get_file_table(self):
        return [(self.file_table.item(row, 0).text(), self.file_table.item(row, 1).text()) for row in range(self.file_table.rowCount())]

    def set_file_table(self, files):
        self.file_table.clearContents()
        self.file_table.setRowCount(0)
        for f1, f2 in files:
            self.file_table.insertRow(self.file_table.rowCount())
            item = QTableWidgetItem(os.path.normpath(f1))
            item.setToolTip(os.path.normpath(f1))
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.file_table.setItem(self.file_table.rowCount()-1, 0, item)
            item = QTableWidgetItem(os.path.normpath(f2))
            item.setToolTip(os.path.normpath(f2))
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.file_table.setItem(self.file_table.rowCount()-1, 1, item)


class DropFilesListWidget(QListWidget):
    """
    A QListWidget with drop support for files and folders. If a folder is dropped, all files contained in the folder are added.
    """

    def __init__(self, filter_files_callback, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.filter_files_callback = filter_files_callback
        shortcut = QShortcut(QKeySequence.Delete, self)
        shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        shortcut.activated.connect(self.remove_selected)

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
                    self.add_files([url.toLocalFile()])
                if os.path.isdir(url.toLocalFile()):
                    d = url.toLocalFile()
                    # keep only files (not folders)
                    self.add_files([os.path.join(d, f) for f in os.listdir(d)])

    def remove_selected(self):
        for item in self.selectedItems():
            self.takeItem(self.row(item))

    def add_files(self, filenames):
        filenames = self.filter_files_callback(filenames)
        self.addItems([os.path.normpath(f) for f in filenames])


class FileListWidget(QWidget):
    """
    A list of files with filters, button to add files and folder and drag and drop support.
    """
    file_list_changed = pyqtSignal()
    file_list_double_clicked = pyqtSignal(QListWidgetItem)

    def __init__(self, parent=None, filetypes=None, filenames_filter='', filenames_exclude_filter=''):
        """
        Parameters
        ----------
        filetypes: list of str
            list of allowed file extensions, including the '.'. E.g. ['.tif','.nd2'].
            If empty: allow all extensions.
        filenames_filter: str
            filenames not containing this text will be ignored.
        filenames_exclude_filter: str
            filenames containing this text will be ignored.
        """
        super().__init__(parent)

        if filetypes is None:
            filetypes = []
        self.filter_name = QLineEdit(filenames_filter, placeholderText='e.g.: _BF')
        self.filter_name.setToolTip('Accept only filenames containing this text. Filtering is done only when populating the list.')
        self.filter_name_exclude = QLineEdit(filenames_exclude_filter, placeholderText='e.g.: _WL508')
        self.filter_name_exclude.setToolTip('Accept only filenames NOT containing this text. Filtering is done only when populating the list.')
        self.filetypes = QLineEdit(' '.join(filetypes), placeholderText='e.g.: .nd2 .tif .tiff .ome.tif .ome.tiff')
        self.filetypes.setToolTip('Space separated list of accepted file extensions. Filtering is done only when populating the list.')
        self.file_list = DropFilesListWidget(self.filter_files)
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

        filters = CollapsibleWidget('Filters (applied when populating the list)', expanded=False)
        layout2 = QHBoxLayout()
        filters.content.setLayout(layout2)
        layout3 = QFormLayout()
        layout3.addRow("Filename must include:", self.filter_name)
        layout2.addLayout(layout3)
        layout3 = QFormLayout()
        layout3.addRow("Filename must NOT include:", self.filter_name_exclude)
        layout2.addLayout(layout3)
        layout3 = QFormLayout()
        layout3.addRow("File types:", self.filetypes)
        layout2.addLayout(layout3)
        layout.addWidget(filters)

        layout.addWidget(self.file_list)
        layout2 = QHBoxLayout()
        layout2.addWidget(self.add_file_button)
        layout2.addWidget(self.add_folder_button)
        layout2.addWidget(self.remove_file_button)
        layout.addLayout(layout2)

        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

    def file_list_rows_inserted(self):
        self.file_list_changed.emit()

    def file_list_rows_removed(self):
        self.file_list_changed.emit()

    def add_file(self):
        type_list = ['*'+x for x in self.filetypes.text().split()]
        if len(type_list) == 0:
            type_list = ['*']
        if self.filter_name.text() != '':
            type_list = ['*'+self.filter_name.text()+x for x in type_list]

        file_paths, _ = QFileDialog.getOpenFileNames(self, 'Select Files', filter='Images ('+' '.join(type_list)+')')
        self.file_list.add_files(file_paths)

    def add_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder_path:
            self.file_list.add_files([os.path.join(folder_path, f) for f in os.listdir(folder_path)])

    def remove_file(self):
        self.file_list.remove_selected()

    def count(self):
        return self.file_list.count()

    def filter_files(self, filenames):
        filtered_filenames = []
        for file_path in filenames:
            file_path = os.path.normpath(file_path)
            if len(self.filetypes.text().split()) == 0 or splitext(file_path)[1] in self.filetypes.text().split():
                if self.filter_name.text() in os.path.basename(file_path):
                    if self.filter_name_exclude.text() == '' or self.filter_name_exclude.text() not in os.path.basename(file_path):
                        if os.path.isfile(file_path):
                            if len(self.file_list.findItems(file_path, Qt.MatchExactly)) == 0:
                                if file_path not in filtered_filenames:
                                    filtered_filenames.append(file_path)
        return filtered_filenames

    def get_file_list(self):
        return [self.file_list.item(x).text() for x in range(self.file_list.count())]

    def set_file_list(self, files):
        self.file_list.clear()
        for f in files:
            self.file_list.addItem(os.path.normpath(f))


class DropFoldersListWidget(QListWidget):
    """
    A QListWidget with drop support for folders.
    """

    def __init__(self, filter_folders_callback, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.filter_folders_callback = filter_folders_callback
        shortcut = QShortcut(QKeySequence.Delete, self)
        shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        shortcut.activated.connect(self.remove_selected)

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
                    self.add_folders([url.toLocalFile()])

    def remove_selected(self):
        for item in self.selectedItems():
            self.takeItem(self.row(item))

    def add_folders(self, foldernames):
        foldernames = self.filter_folders_callback(foldernames)
        self.addItems([os.path.join(os.path.normpath(d), '') for d in foldernames])


class FolderListWidget(QWidget):
    """
    A list of folders with filters, button to add folders and drag and drop support.
    """
    folder_list_changed = pyqtSignal()
    folder_list_double_clicked = pyqtSignal(QListWidgetItem)

    def __init__(self, parent=None, foldernames_filter='', foldernames_exclude_filter=''):
        """
        Parameters
        ----------
        foldernames_filter: str
            Folders with name not containing this text will be ignored.
        foldernames_exclude_filter: str
            Folders with name containing this text will be ignored.
        """
        super().__init__(parent)

        self.filter_name = QLineEdit(foldernames_filter, placeholderText='e.g.: _BF')
        self.filter_name.setToolTip('Accept only folder names containing this text. Filtering is done only when populating the list.')
        self.filter_name_exclude = QLineEdit(foldernames_exclude_filter, placeholderText='e.g.: _WL508')
        self.filter_name_exclude.setToolTip('Accept only folder names NOT containing this text. Filtering is done only when populating the list.')
        self.folder_list = DropFoldersListWidget(self.filter_folders)
        self.folder_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.folder_list.model().rowsInserted.connect(self.folder_list_rows_inserted)
        self.folder_list.model().rowsRemoved.connect(self.folder_list_rows_removed)
        self.folder_list.itemDoubleClicked.connect(self.folder_list_double_clicked)
        self.add_folder_button = QPushButton("Add folder", self)
        self.add_folder_button.clicked.connect(self.add_folder)
        self.remove_folder_button = QPushButton("Remove selected", self)
        self.remove_folder_button.clicked.connect(self.remove_folder)

        layout = QVBoxLayout()

        filters = CollapsibleWidget('Filters (applied when populating the list)', expanded=False)
        layout2 = QHBoxLayout()
        filters.content.setLayout(layout2)
        layout3 = QFormLayout()
        layout3.addRow("Folder name must include:", self.filter_name)
        layout2.addLayout(layout3)
        layout3 = QFormLayout()
        layout3.addRow("Folder name must NOT include:", self.filter_name_exclude)
        layout2.addLayout(layout3)
        layout.addWidget(filters)

        layout.addWidget(self.folder_list)
        layout2 = QHBoxLayout()
        layout2.addWidget(self.add_folder_button)
        layout2.addWidget(self.remove_folder_button)
        layout.addLayout(layout2)

        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

    def folder_list_rows_inserted(self):
        self.folder_list_changed.emit()

    def folder_list_rows_removed(self):
        self.folder_list_changed.emit()

    def add_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder_path:
            self.folder_list.add_folders([folder_path])

    def remove_folder(self):
        self.folder_list.remove_selected()

    def count(self):
        return self.folder_list.count()

    def filter_folders(self, foldernames):
        filtered_foldernames = []
        for folder_path in foldernames:
            folder_path = os.path.join(os.path.normpath(folder_path), '')
            if self.filter_name.text() in os.path.basename(os.path.normpath(folder_path)):
                if self.filter_name_exclude.text() == '' or self.filter_name_exclude.text() not in os.path.basename(os.path.normpath(folder_path)):
                    if os.path.isdir(folder_path):
                        if folder_path and len(self.folder_list.findItems(folder_path, Qt.MatchExactly)) == 0:
                            if folder_path not in filtered_foldernames:
                                filtered_foldernames.append(folder_path)
        return filtered_foldernames

    def get_folder_list(self):
        return [self.folder_list.item(x).text() for x in range(self.folder_list.count())]

    def set_folder_list(self, folders):
        self.folder_list.clear()
        for f in folders:
            self.folder_list.addItem(os.path.join(os.path.normpath(f), ''))


class DropFileLineEdit(QLineEdit):
    """
    A QLineEdit with drop support for files.
    """

    def __init__(self, parent=None, filetypes=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setClearButtonEnabled(True)
        self.filetypes = filetypes
        self.placeholder_text = ''

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
                    if self.filetypes is None or len(self.filetypes) == 0 or splitext(filename)[1] in self.filetypes:
                        self.setText(os.path.normpath(filename))

    def placeholderText(self):
        return self.placeholder_text

    def setPlaceholderText(self, placeholder_text):
        self.placeholder_text = placeholder_text
        self.update()

    def paintEvent(self, event):
        # reimplement paintEvent to elide placeholder text on the left instead of right.
        super().paintEvent(event)
        if not self.text() and self.placeholder_text:
            painter = QPainter(self)
            painter.setPen(self.palette().placeholderText().color())
            font_metrics = QFontMetrics(self.font())
            rect = self.rect()
            elided_text = font_metrics.elidedText(self.placeholder_text, Qt.ElideLeft, rect.width()-2)
            painter.drawText(rect, Qt.AlignLeft | Qt.AlignVCenter, elided_text)
            painter.end()


class FileLineEdit(QWidget):
    """
    A DropFileLineEdit with drag and drop support and a browse button.
    """
    textChanged = pyqtSignal(str)

    def __init__(self, parent=None, label=None, filetypes=None):
        """
        Parameters
        ----------
        label: str
            File type label. E.g. 'Images', 'Cell tracking graphs'.
        filetypes: list of str
            list of allowed file extensions, including the '.'. E.g. ['.tif','.nd2'].
            If empty: allow all extensions.
        """

        super().__init__(parent)

        if filetypes is None:
            filetypes = []
        self.filetypes = filetypes
        self.label = label

        self.line_edit = DropFileLineEdit(filetypes=filetypes)
        self.browse_button = QPushButton("Browse")
        self.browse_button.clicked.connect(self.browse)
        self.line_edit.textChanged.connect(self.textChanged.emit)

        self.setFocusProxy(self.line_edit)

        layout = QHBoxLayout()
        layout.addWidget(self.line_edit)
        layout.addWidget(self.browse_button, alignment=Qt.AlignCenter)

        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

    def browse(self):
        filter = ''
        if len(self.filetypes) > 0:
            if self.label:
                filter = self.label + ' '
            filter += '(' + ' '.join(['*' + x for x in self.filetypes]) + ')'
        file_path, _ = QFileDialog.getOpenFileName(self, 'Select File', filter=filter)
        if file_path != '':
            self.line_edit.setText(os.path.normpath(file_path))

    def setToolTip(self, text):
        self.line_edit.setToolTip(text)

    def toolTip(self):
        return self.line_edit.toolTip()

    def setPlaceholderText(self, text):
        self.line_edit.setPlaceholderText(text)

    def placeholderText(self):
        return self.line_edit.placeholderText()

    def text(self):
        if self.line_edit.text() == '':
            return ''
        return os.path.normpath(self.line_edit.text())

    def setText(self, file):
        if file == '':
            self.line_edit.setText('')
        else:
            self.line_edit.setText(os.path.normpath(file))


class DropFolderLineEdit(QLineEdit):
    """
    A QLineEdit with drop support for folder.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setClearButtonEnabled(True)

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
                    self.setText(os.path.join(os.path.normpath(url.toLocalFile()), ''))

    def paintEvent(self, event):
        # reimplement paintEvent to elide placeholder text on the left instead of right.
        placeholder_text = self.placeholderText()
        self.setPlaceholderText('')
        super().paintEvent(event)
        self.setPlaceholderText(placeholder_text)
        if not self.text() and self.placeholderText():
            painter = QPainter(self)
            painter.setPen(self.palette().placeholderText().color())
            font_metrics = QFontMetrics(self.font())
            rect = self.rect()
            elided_text = font_metrics.elidedText(placeholder_text, Qt.ElideLeft, rect.width()-2)
            painter.drawText(rect, Qt.AlignLeft | Qt.AlignVCenter, elided_text)
            painter.end()


class FolderLineEdit(QWidget):
    """
    A DropFolderLineEdit with drag and drop support and a browse button.
    """
    textChanged = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.line_edit = DropFolderLineEdit()
        self.browse_button = QPushButton("Browse")
        self.browse_button.clicked.connect(self.browse)
        self.line_edit.textChanged.connect(self.textChanged.emit)

        self.setFocusProxy(self.line_edit)

        layout = QHBoxLayout()
        layout.addWidget(self.line_edit)
        layout.addWidget(self.browse_button, alignment=Qt.AlignCenter)

        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

    def browse(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder_path != '':
            self.line_edit.setText(os.path.join(os.path.normpath(folder_path), ''))

    def text(self):
        if self.line_edit.text() == '':
            return ''
        return os.path.join(os.path.normpath(self.line_edit.text()), '')

    def setText(self, folder):
        if folder == '':
            self.line_edit.setText(folder)
        else:
            self.line_edit.setText(os.path.join(os.path.normpath(folder), ''))


class OutputSettings(QWidget):
    """
    A QWidget to enter output settings.
    """

    def __init__(self, parent=None, output_suffix='', extensions=None, pipeline_layout=False):
        """
        Parameters
        ----------
        output_suffix: str
            output suffix.
        extensions: list of str
            list of filename extensions including the '.' (one extension per output file). E.g. ['.csv','.ome.tif'].
            Only used to display output filenames.
        pipeline_layout: bool
            the widget is used in the pipeline module and the choice of folder is not shown.
        """
        super().__init__(parent)

        self.output_suffix = output_suffix
        self.extensions = extensions
        self.pipeline_layout = pipeline_layout

        self.use_input_folder = QRadioButton("Use input folder")
        self.use_input_folder.setChecked(True)
        self.use_input_folder.toggled.connect(self.update_output_filename_labels)
        self.use_custom_folder = QRadioButton("Use custom folder (same for all the input files)")
        self.use_custom_folder.setChecked(False)
        self.use_custom_folder.toggled.connect(self.update_output_filename_labels)
        self.output_folder = FolderLineEdit()
        self.output_folder.textChanged.connect(self.update_output_filename_labels)
        self.output_folder.setVisible(self.use_custom_folder.isChecked())
        self.use_custom_folder.toggled.connect(self.output_folder.setVisible)
        self.output_user_suffix = QLineEdit()
        self.output_user_suffix.setToolTip('Allowed characters: A-Z, a-z, 0-9 and -')
        self.output_user_suffix.setValidator(QRegularExpressionValidator(QRegularExpression('[A-Za-z0-9-]*')))
        self.output_user_suffix.textChanged.connect(self.update_output_filename_labels)
        self.output_filename_labels = []
        for i in range(len(self.extensions)):
            label = QLineEdit()
            label.setFrame(False)
            label.setEnabled(False)
            label.textChanged.connect(label.setToolTip)
            self.output_filename_labels.append(label)

        layout = QVBoxLayout()
        if not self.pipeline_layout:
            layout.addWidget(QLabel("Folder:"))
            layout.addWidget(self.use_input_folder)
            layout.addWidget(self.use_custom_folder)
            layout.addWidget(self.output_folder)
        layout2 = QFormLayout()
        layout2.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        layout3 = QHBoxLayout()
        layout3.setSpacing(0)
        if output_suffix:
            suffix = QLineEdit(self.output_suffix)
            suffix.setDisabled(True)
            suffix.setFixedWidth(suffix.fontMetrics().width(suffix.text()+"  "))
            suffix.setAlignment(Qt.AlignRight)
            layout3.addWidget(suffix)
        layout3.addWidget(self.output_user_suffix)
        layout2.addRow("Suffix:", layout3)
        layout3 = QVBoxLayout()
        layout3.setSpacing(0)
        for label in self.output_filename_labels:
            layout3.addWidget(label)
        layout2.addRow("Filename:", layout3)
        layout.addLayout(layout2)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        self.update_output_filename_labels()

    def update_output_filename_labels(self):
        if self.pipeline_layout:
            output_path = "<output folder>"
        elif self.use_input_folder.isChecked():
            output_path = "<input folder>"
        else:
            output_path = os.path.abspath(self.output_folder.text())

        for label, extension in zip(self.output_filename_labels, self.extensions):
            label.setText(os.path.normpath(os.path.join(output_path, "<input basename>" + self.output_suffix + self.output_user_suffix.text() + extension)))

    def get_basename(self, input_filename):
        return splitext(os.path.basename(input_filename))[0] + self.output_suffix + self.output_user_suffix.text()

    def get_path(self, input_filename):
        if self.use_input_folder.isChecked():
            return os.path.dirname(input_filename)
        else:
            return self.output_folder.text()


class ZProjectionSettings(QWidget):
    """
    A QWidget to enter Z-projection settings.
    """
    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        # only bestZ
        self.projection_mode_bestZ = QRadioButton("Z section with best focus")
        self.projection_mode_bestZ.setChecked(False)
        self.projection_mode_bestZ.setToolTip('Keep only Z section with best focus.')
        # around bestZ
        self.projection_mode_around_bestZ = QRadioButton("Range around Z section with best focus")
        self.projection_mode_around_bestZ.setChecked(True)
        self.projection_mode_around_bestZ.setToolTip('Project all Z sections with Z in the interval [bestZ-range,bestZ+range], where bestZ is the Z section with best focus.')
        self.projection_mode_around_bestZ_zrange = QSpinBox()
        self.projection_mode_around_bestZ_zrange.setMinimum(0)
        self.projection_mode_around_bestZ_zrange.setMaximum(99)
        self.projection_mode_around_bestZ_zrange.setValue(3)
        # fixed range
        self.projection_mode_fixed = QRadioButton("Fixed range")
        self.projection_mode_fixed.setChecked(False)
        self.projection_mode_fixed.setToolTip('Project all Z sections with Z in the interval [from,to].')
        self.projection_mode_fixed_zmin = QSpinBox()
        self.projection_mode_fixed_zmin.setMinimum(0)
        self.projection_mode_fixed_zmin.setMaximum(6)
        self.projection_mode_fixed_zmin.setValue(4)
        self.projection_mode_fixed_zmin.valueChanged.connect(self.projection_mode_fixed_zmin_changed)
        self.projection_mode_fixed_zmax = QSpinBox()
        self.projection_mode_fixed_zmax.setMinimum(4)
        self.projection_mode_fixed_zmax.setMaximum(99)
        self.projection_mode_fixed_zmax.setValue(6)
        self.projection_mode_fixed_zmax.valueChanged.connect(self.projection_mode_fixed_zmax_changed)
        # all
        self.projection_mode_all = QRadioButton("All Z sections")
        self.projection_mode_all.setChecked(False)
        self.projection_mode_all.setToolTip('Project all Z sections.')
        # Z-Projection type
        self.projection_type = QComboBox()
        self.projection_type.addItem("max")
        self.projection_type.addItem("min")
        self.projection_type.addItem("mean")
        self.projection_type.addItem("median")
        self.projection_type.addItem("std")
        self.projection_type.setCurrentText("mean")
        self.projection_type.setDisabled(self.projection_mode_bestZ.isChecked())
        self.projection_mode_bestZ.toggled.connect(self.projection_type.setDisabled)

        self.projection_mode_around_bestZ.toggled.connect(self.changed)
        self.projection_mode_around_bestZ_zrange.valueChanged.connect(self.changed)
        self.projection_mode_fixed.toggled.connect(self.changed)
        self.projection_mode_fixed_zmin.valueChanged.connect(self.changed)
        self.projection_mode_fixed_zmax.valueChanged.connect(self.changed)
        self.projection_mode_all.toggled.connect(self.changed)
        self.projection_type.currentTextChanged.connect(self.changed)

        layout = QFormLayout()
        # Z-Projection range
        widget = QWidget()
        layout2 = QVBoxLayout()
        layout2.addWidget(self.projection_mode_bestZ)
        layout2.addWidget(self.projection_mode_around_bestZ)
        groupbox3 = QGroupBox()
        groupbox3.setToolTip('Project all Z sections with Z in the interval [bestZ-range,bestZ+range], where bestZ is the Z section with best focus.')
        groupbox3.setVisible(self.projection_mode_around_bestZ.isChecked())
        self.projection_mode_around_bestZ.toggled.connect(groupbox3.setVisible)
        layout3 = QFormLayout()
        layout3.addRow("Range:", self.projection_mode_around_bestZ_zrange)
        groupbox3.setLayout(layout3)
        layout2.addWidget(groupbox3)
        layout2.addWidget(self.projection_mode_fixed)
        groupbox3 = QGroupBox()
        groupbox3.setToolTip('Project all Z sections with Z in the interval [from,to].')
        groupbox3.setVisible(self.projection_mode_fixed.isChecked())
        self.projection_mode_fixed.toggled.connect(groupbox3.setVisible)
        layout3 = QHBoxLayout()
        layout4 = QFormLayout()
        layout4.addRow("From:", self.projection_mode_fixed_zmin)
        layout3.addLayout(layout4)
        layout4 = QFormLayout()
        layout4.addRow("To:", self.projection_mode_fixed_zmax)
        layout3.addLayout(layout4)
        groupbox3.setLayout(layout3)
        layout2.addWidget(groupbox3)
        layout2.addWidget(self.projection_mode_all)
        widget.setLayout(layout2)
        layout.addRow("Projection range:", widget)
        layout.addRow("Projection type:", self.projection_type)

        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

    def projection_mode_fixed_zmin_changed(self, value):
        self.projection_mode_fixed_zmax.setMinimum(value)

    def projection_mode_fixed_zmax_changed(self, value):
        self.projection_mode_fixed_zmin.setMaximum(value)

    def get_projection_type(self):
        return self.projection_type.currentText()

    def get_projection_zrange(self):
        if self.projection_mode_bestZ.isChecked():
            projection_zrange = 0
        elif self.projection_mode_around_bestZ.isChecked():
            projection_zrange = self.projection_mode_around_bestZ_zrange.value()
        elif self.projection_mode_fixed.isChecked():
            projection_zrange = (self.projection_mode_fixed_zmin.value(), self.projection_mode_fixed_zmax.value())
        elif self.projection_mode_all.isChecked():
            projection_zrange = None
        return projection_zrange


class Page(QWidget):
    def __init__(self, parent=None, widget=None, add_stretch=True):
        super().__init__(parent)
        self.container = QWidget()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.container)
        lay.addWidget(scroll)

        if widget:
            layout = QVBoxLayout(self.container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(widget)
            if add_stretch:
                layout.addStretch()


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
    dtype: np.dtype
        image data type
    channel_names : list
        list with channel names. None if not available
    physical_pixel_sizes : tuple
        tuple with physical pixel sizes in x, y and z direction (in micrometer). (None,None,None) if not available.
    ome_metadata : ome_types.model.ome.OME
        ome metadata. None if not available.

    Methods
    -------
    __init__()
        Set the 'path' and populate attributes sizes and shape.
    imread()
        Read the image from the already setted 'path'.
        Attribute image is populated here.
    save()
        Empty
    get_TYXarray()
        Return the 3D image with the dimensions T, Y and X.
        When used the other dimensions F,C,Z MUST be empty (with size = 1)
    z_projection(projection_type, zrange,focus_method)
        Return the z-projection of the image using the selected projection type over the range of z values defined by zrange.
        Possible projection types: max, min, std, avg (or mean), median.
        If zrange is None, use all Z values. If zrange is an integer, use z values in [z_best-zrange,z_best+zrange],
        where z_best is the Z corresponding to best focus. If zrange is a tuple of lenght 2 (zmin,zmax), use z values in [zmin,zmax].
        Possible focus_methods: tenengrad_var, laplacian_var, std.
    crop(axis, start, end)
        crop axis ('F', 'T', 'C', 'Z', 'Y' or 'X') to start:end in-place.
    """

    def __init__(self, im_path):
        self.path = im_path
        self.basename = os.path.basename(self.path)
        self.name, self.extension = splitext(self.basename)
        self.sizes = None
        self.image = None
        self.shape = None
        self.dtype = None
        self._axes = 'FTCZYX'
        self.channel_names = None
        self.physical_pixel_sizes = (None, None, None)
        self.ome_metadata = None
        self.read_attr()

    def read_attr(self):
        if self.extension == '.nd2':
            reader = nd2.ND2File(self.path)
            axes_order = str(''.join(list(reader.sizes.keys()))).upper()  # eg. reader.sizes = {'T': 10, 'C': 2, 'Y': 2048, 'X': 2048}
            shape = reader.shape
            self.dtype = reader.dtype
            self.channel_names = [x.channel.name for x in reader.metadata.channels]
            self.physical_pixel_sizes = (reader.voxel_size(channel=0).x, reader.voxel_size(channel=0).y, reader.voxel_size(channel=0).z)
            reader.close()
        elif self.extension in ['.ome.tif', '.ome.tiff']:
            reader = OmeTiffReader(self.path)
            axes_order = reader.dims.order.upper()
            shape = reader.shape
            self.dtype = reader.dtype
            self.channel_names = reader.channel_names
            self.physical_pixel_sizes = (reader.physical_pixel_sizes.X, reader.physical_pixel_sizes.Y, reader.physical_pixel_sizes.Z)
            self.ome_metadata = reader.ome_metadata
        elif self.extension in ['.tif', '.tiff']:
            reader = tifffile.TiffFile(self.path)
            axes_order = str(reader.series[0].axes).upper()
            shape = reader.series[0].shape
            self.dtype = reader.series[0].dtype
            reader.close()
        else:
            logging.getLogger(__name__).error('Image format not supported. Please upload a tiff, ome-tiff or nd2 image file.')
            raise TypeError('Image format not supported. Please upload a tiff, ome-tiff or nd2 image file.')

        self.shape = []
        self.sizes = {}
        for a in self._axes:
            if a in axes_order:
                self.shape.append(shape[axes_order.index(a)])
                self.sizes[a] = shape[axes_order.index(a)]
            else:
                self.shape.append(1)
                self.sizes[a] = 1
        self.shape = tuple(self.shape)

    def imread(self):
        def set_6Dimage(image, axes):
            """
            Return a 6D ndarray of the input image
            """
            dimensions = {k: v for v, k in enumerate(self._axes)}
            # Dictionary with image axes order
            axes_order = {}
            for i, char in enumerate(axes):
                axes_order[char] = i
            # Mapping for the desired order of dimensions
            mapping = [axes_order.get(d, None) for d in self._axes]
            mapping = [i for i in mapping if i is not None]
            # Rearrange the image array based on the desired order
            image = np.transpose(image, axes=mapping)
            # Determine the missing dimensions and reshape the array filling the missing dimensions
            missing_dims = []
            for c in self._axes:
                if c not in axes:
                    missing_dims.append(c)
            for dim in missing_dims:
                position = dimensions[dim]
                image = np.expand_dims(image, axis=position)
            return image

        # axis default order: FTCZYX for 6D - F = FieldofView, T = time, C = channels
        if self.extension == '.nd2':
            reader = nd2.ND2File(self.path)
            axes_order = str(''.join(list(reader.sizes.keys()))).upper()  # eg. reader.sizes = {'T': 10, 'C': 2, 'Y': 2048, 'X': 2048}
            image = reader.asarray()  # nd2.imread(self.path)
            reader.close()
        elif self.extension in ['.ome.tif', '.ome.tiff']:
            reader = OmeTiffReader(self.path)
            axes_order = reader.dims.order.upper()
            image = reader.data
        elif self.extension in ['.tif', '.tiff']:
            reader = tifffile.TiffFile(self.path)
            axes_order = str(reader.series[0].axes).upper()
            image = reader.asarray()
            reader.close()
        else:
            logging.getLogger(__name__).error('Image format not supported. Please upload a tiff, ome-tiff or nd2 image file.')
            raise TypeError('Image format not supported. Please upload a tiff, ome-tiff or nd2 image file.')

        self.image = set_6Dimage(image, axes_order)
        return self.image

    def get_TYXarray(self):
        if self.sizes['F'] > 1 or self.sizes['C'] > 1 or self.sizes['Z'] > 1:
            logging.getLogger(__name__).error('Image format not supported. Please load an image with only TYX dimensions.')
            raise TypeError('Image format not supported. Please load an image with only TYX dimensions')
        return self.image[0, :, 0, 0, :, :]

    def z_projection(self, projection_type, zrange, focus_method="tenengrad_var", z_shift=0):
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
        focus_method: str
            the method used to estimate the Z corresponding to best focus (tenengrad_var, laplacian_var, std)
            tenengrad_var: estimate the sharpness using the variance of sqrt(Gx^2+Gy^2), where Gx and Gy are the gradients in the x and y direction computed using Sobel operators.
            laplacian_var: estimate the sharpness using the variance of the laplacian.
            std: estimate the sharpness using the standard deviation of the image.
        z_shift: int or list of int
            Shift the z sections to use for projection by z_shift (per time frame), e.g. to generate out-of-focus images.
            If `z_shift` is list of integers, it must contain one entry per time frames in the image (axis T).
            If `z_shift` is a single integer, the same shift will be used for all time frames.
            Not relevant when projecting all z sections.

        Returns
        -------
        ndarray
            a 6D array with original image size, except for Z axis which has size 1.
        """
        if focus_method not in ['tenengrad_var', 'laplacian_var', 'std']:
            raise TypeError(f"Invalid focus_method {focus_method}")

        if np.ndim(z_shift) == 0:
            z_shift = [z_shift] * self.sizes['T']

        if zrange is None:
            logging.getLogger(__name__).info('Z-Projection: projection type=%s, zrange=%s (All Z sections)', projection_type, zrange)
        elif isinstance(zrange, int) and zrange == 0:
            logging.getLogger(__name__).info('Z-Projection: projection type=%s, zrange=%s (Z section with best focus), focus method=%s, z shift=%s', projection_type, zrange, focus_method, z_shift)
        elif isinstance(zrange, int):
            logging.getLogger(__name__).info('Z-Projection: projection type=%s, zrange=%s (Range %s around Z section with best focus), focus method=%s, z shift=%s', projection_type, zrange, zrange, focus_method, z_shift)
        elif isinstance(zrange, tuple) and len(zrange) == 2 and zrange[0] <= zrange[1]:
            logging.getLogger(__name__).info('Z-Projection: projection type=%s, zrange=%s (Fixed range from %s to %s), z shift=%s', projection_type, zrange, zrange[0], zrange[1], z_shift)
        else:
            logging.getLogger(__name__).info('Z-Projection: invalid zrange')
        projected_image = np.zeros((self.sizes['F'], self.sizes['T'], self.sizes['C'], 1, self.sizes['Y'], self.sizes['X']), dtype=self.image.dtype)
        sharpness = np.zeros(self.sizes['Z'])
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
                        # estimate sharpness
                        if focus_method == 'tenengrad_var':
                            for z in range(self.sizes['Z']):
                                sharpness[z] = cv2.magnitude(cv2.Sobel(self.image[f, t, c, z, :, :].astype("float64"), cv2.CV_64F, 0, 1, ksize=3),
                                                             cv2.Sobel(self.image[f, t, c, z, :, :].astype("float64"), cv2.CV_64F, 1, 0, ksize=3)).var()
                        elif focus_method == 'laplacian_var':
                            for z in range(self.sizes['Z']):
                                sharpness[z] = cv2.Laplacian(self.image[f, t, c, z, :, :].astype("float64"), cv2.CV_64F, ksize=11).var()
                        elif focus_method == 'std':
                            sharpness = self.image[f, t, c, :, :, :].std(axis=(1, 2))

                        # estimate z_best
                        if focus_method == 'std':
                            # choose z_best as z with maximum sharpness
                            z_best = sharpness.argmax()
                        elif focus_method in ['tenengrad_var', 'laplacian_var']:
                            # smooth sharpness with running mean and choose z_best as z with maximum smoothed sharpness
                            smooth_window = 1
                            sharpness_smoothed = sharpness / max(sharpness)
                            # smooth with running mean:
                            sharpness_smoothed = np.hstack((np.full(smooth_window, sharpness_smoothed[0]),
                                                            sharpness_smoothed,
                                                            np.full(smooth_window, sharpness_smoothed[-1])))
                            sharpness_smoothed = np.convolve(sharpness_smoothed,
                                                             np.ones(2*smooth_window+1)/(2*smooth_window+1),
                                                             mode='valid')
                            z_best = sharpness_smoothed.argmax()

                        # if z_best is too close to min or maz 'Z' => shift best_z so as to keep (2*zrange+1) z values (z_values).
                        z_best_tmp = min(max(z_best+z_shift[t], zrange), self.sizes['Z']-zrange-1)
                        z_values = [z for z in range(z_best_tmp-zrange, z_best_tmp+zrange+1) if z < self.sizes['Z'] and z >= 0]

                        logging.getLogger(__name__).info('Z-Projection (F: %s, T: %s, C: %s): %s over z in %s (Best z=%s, z shift=%s)', f, t, c, projection_type, z_values, z_best, z_shift[t])
                    elif isinstance(zrange, tuple) and len(zrange) == 2 and zrange[0] <= zrange[1]:
                        # use fixed range
                        z_values = [z for z in range(zrange[0]+z_shift[t], zrange[1]+z_shift[t]+1) if z < self.sizes['Z'] and z >= 0]
                        logging.getLogger(__name__).info('Z-Projection (F: %s, T: %s, C: %s): %s over z in %s (fixed range, z shift=%s)', f, t, c, projection_type, z_values, z_shift[t])

                    if len(z_values) == 1:
                        projected_image[f, t, c, 0, :, :] = self.image[f, t, c, z_values[0], :, :].copy()
                    elif projection_type == 'max':
                        projected_image[f, t, c, 0, :, :] = np.max(self.image[f, t, c, z_values, :, :], axis=0)
                    elif projection_type == 'min':
                        projected_image[f, t, c, 0, :, :] = np.min(self.image[f, t, c, z_values, :, :], axis=0)
                    elif projection_type == 'std':
                        projected_image[f, t, c, 0, :, :] = np.std(self.image[f, t, c, z_values, :, :], axis=0, ddof=1)
                    elif projection_type in ['avg', 'mean']:
                        projected_image[f, t, c, 0, :, :] = np.mean(self.image[f, t, c, z_values, :, :], axis=0)
                    elif projection_type == 'median':
                        projected_image[f, t, c, 0, :, :] = np.median(self.image[f, t, c, z_values, :, :], axis=0)
                    else:
                        logging.getLogger(__name__).error('Projection type not recognized')
                        return None

        return projected_image

    def crop(self, axis, start, end):
        """
        Crop axis to start:end in-place.

        Parameters
        ----------
        axis: str
            axis to crop ('F', 'T', 'C', 'Z', 'Y' or 'X').
        start: int
            start indice.
        end: int
            end indice.
        """
        slices = []
        for a in self._axes:
            if a == axis:
                slices.append(slice(start, end))
            else:
                slices.append(slice(None))
        self.image = self.image[tuple(slices)]
        self.shape = self.image.shape
        for i, a in enumerate(self._axes):
            self.sizes[a] = self.shape[i]
        if axis == 'C':
            self.channel_names = self.channel_names[start:end]


def load_cell_tracking_graph(graph_path, mask_dtype):
    graph = ig.Graph().Read_GraphMLz(graph_path)
    # Adjust attibute types
    graph.vs['frame'] = np.array(graph.vs['frame'], dtype='int32')
    graph.vs['mask_id'] = np.array(graph.vs['mask_id'], dtype=mask_dtype)
    graph.vs['area'] = np.array(graph.vs['area'], dtype='int64')
    graph.es['overlap_area'] = np.array(graph.es['overlap_area'], dtype='int64')
    graph.es['frame_source'] = np.array(graph.es['frame_source'], dtype='int32')
    graph.es['frame_target'] = np.array(graph.es['frame_target'], dtype='int32')
    graph.es['mask_id_source'] = np.array(graph.es['mask_id_source'], dtype=mask_dtype)
    graph.es['mask_id_target'] = np.array(graph.es['mask_id_target'], dtype=mask_dtype)
    # Remove useless attribute
    del graph.vs['id']

    return graph


def evaluate_graph_properties(graph):
    """
    Evaluate the properties of the graph

    Parameters
    ---------------------
    graph: igraph.Graph
        cell tracking graph

    Returns
    ---------------------
    cell_tracks
    """
    # Set "stable" subgraph = if source vertex has a unique outgoing edge and target vertex has a unique incoming edge
    graph.es['stable'] = False
    graph.es.select(lambda edge: abs(edge['frame_source']-edge['frame_target']) == 1 and edge['mask_id_source'] == edge['mask_id_target'] and graph.outdegree(edge.source) == 1 and graph.indegree(edge.target) == 1)['stable'] = True
    # Flag edge with low overlap as not stable
    graph.es.select(overlap_fraction_source_lt=0)['stable'] = False
    graph.es.select(overlap_fraction_target_lt=0)['stable'] = False
    # Evaluate length of "stable" subgraph and store it as vertex attribute
    g2 = graph.subgraph_edges(graph.es.select(stable=True), delete_vertices=False)
    components = g2.connected_components(mode='weak')
    for i, n in enumerate(components.sizes()):
        graph.vs[components[i]]['stable_component_size'] = n

    # Evaluation cell tracks (i.e. connected components of the cell tracking graph)
    components = graph.connected_components(mode='weak')
    cell_tracks = []

    for i, cmp in enumerate(components):  # each connected component found is a subgraph
        g2 = graph.subgraph(cmp)
        mask_ids = np.unique(g2.vs['mask_id'])
        frame_min = np.min(g2.vs['frame'])
        frame_max = np.max(g2.vs['frame'])
        # Number of missing labelled regions (edges spanning more than 1 frame)
        n_missing = np.sum([e['frame_target'] - e['frame_source'] - 1 for e in g2.es])
        # Number fusion events with stable neighborhood
        n_fusions = np.sum([1 if v.indegree() > 1 and min(v2['stable_component_size'] for v2 in v.neighbors()) >= 1 else 0 for v in g2.vs])
        fusions_frames = []
        if n_fusions > 0:
            indegree = g2.vs[0].indegree()
            for v in g2.vs:
                if v.indegree() > indegree:
                    indegree = v.indegree()
                    fusions_frames.append(v['frame'])
        # Number division events with stable neighborhood
        n_divisions = np.sum([1 if v.outdegree() > 1 and min(v2['stable_component_size'] for v2 in v.neighbors()) >= 1 else 0 for v in g2.vs])
        divisions_frames = []
        if n_divisions > 0:
            outdegree = g2.vs[0].outdegree()
            for v in g2.vs:
                if v.outdegree() > outdegree:
                    outdegree = v.outdegree()
                    divisions_frames.append(v['frame'])
        min_area = np.min(g2.vs['area'])
        max_area = np.max(g2.vs['area'])
        # Topology
        cell_tracks.append({'graph_vertices': cmp, 'mask_ids': mask_ids, 'frame_min': frame_min,
                            'frame_max': frame_max, 'n_missing': n_missing, 'n_fusions': n_fusions,
                            'n_divisions': n_divisions, 'min_area': min_area, 'max_area': max_area,
                            'fusions_frames': fusions_frames, 'divisions_frames': divisions_frames})
    return cell_tracks


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
            if self.last is None or current != self.last:
                self.last = current
                return True
            return False
        self.last = current
        return True
