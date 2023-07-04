import logging
import os
import logging
from PyQt5.QtWidgets import QFileDialog, QLineEdit, QCheckBox, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QMessageBox, QListWidget, QAbstractItemView, QGroupBox, QRadioButton, QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCursor
from modules.zprojection_module.zprojection import zprojection_functions as f
from general import general_functions as gf


class DropFilesListWidget(QListWidget):
    """
    A QListWidget with drop support for files and folders. If a folder is dropped, all files contained in the folder are added.
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
                    if len(self.findItems(filename, Qt.MatchExactly)) == 0 and (self.filetypes is None or os.path.splitext(filename)[1] in self.filetypes):
                        self.addItem(filename)
                if os.path.isdir(url.toLocalFile()):
                    d = url.toLocalFile()
                    # keep only files (not folders)
                    filenames = [os.path.join(d, f)
                                 for f in os.listdir(d)]
                    if not self.filetypes is None:
                        # keep only allowed filetypes
                        filenames = [f for f in filenames
                                     if os.path.splitext(f)[1] in self.filetypes]
                    # keep only existing files (not folders)
                    filenames = [f for f in filenames
                                 if os.path.isfile(f)]
                    # do not add if already in the list
                    filenames = [f for f in filenames
                                 if len(self.findItems(f, Qt.MatchExactly)) == 0]
                    self.addItems(filenames)


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
                    if self.filetypes is None or os.path.splitext(filename)[1] in self.filetypes:
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


class zProjection(QWidget):
    def __init__(self):
        super().__init__()

        self.imagetypes = ['.nd2', '.tif', '.tiff']
        self.image_list = DropFilesListWidget(filetypes=self.imagetypes)
        self.image_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.add_image_button = QPushButton("Add images", self)
        self.add_image_button.clicked.connect(self.add_image)
        self.add_folder_button = QPushButton("Add folder", self)
        self.add_folder_button.clicked.connect(self.add_folder)
        self.remove_button = QPushButton("Remove selected", self)
        self.remove_button.clicked.connect(self.remove)

        self.use_input_folder = QRadioButton("Use input image folder\n(zprojection sub-folder)")
        self.use_input_folder.setChecked(True)
        self.use_custom_folder = QRadioButton("Use custom folder:")
        self.use_custom_folder.setChecked(False)
        self.output_folder = DropFolderLineEdit()
        self.browse_button2 = QPushButton("Browse", self)
        self.browse_button2.clicked.connect(self.browse_output)
        self.output_folder.setEnabled(self.use_custom_folder.isChecked())
        self.browse_button2.setEnabled(self.use_custom_folder.isChecked())
        self.use_custom_folder.toggled.connect(self.output_folder.setEnabled)
        self.use_custom_folder.toggled.connect(self.browse_button2.setEnabled)

        self.b1 = QRadioButton("Max")
        self.b1.setChecked(True)
        self.b1.toggled.connect(lambda:self.btnstate(self.b1))
        self.b2 = QRadioButton("Min")
        self.b2.toggled.connect(lambda:self.btnstate(self.b2))
        self.b3 = QRadioButton("Std")
        self.b3.toggled.connect(lambda:self.btnstate(self.b3))
        self.b4 = QRadioButton("Average")
        self.b4.toggled.connect(lambda:self.btnstate(self.b4))
        self.b5 = QRadioButton("Median")
        self.b5.toggled.connect(lambda:self.btnstate(self.b5))

        self.submit_button = QPushButton("Submit", self)
        self.submit_button.clicked.connect(self.click)

        # Layout
        layout = QVBoxLayout()
        groupbox = QGroupBox("Images to process")
        layout2 = QVBoxLayout()
        layout2.addWidget(self.image_list)
        layout3 = QHBoxLayout()
        layout3.addWidget(self.add_image_button)
        layout3.addWidget(self.add_folder_button)
        layout3.addWidget(self.remove_button)
        layout2.addLayout(layout3)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        groupbox = QGroupBox("Output folder")
        layout2 = QVBoxLayout()
        layout2.addWidget(self.use_input_folder)
        layout2.addWidget(self.use_custom_folder)
        layout3 = QHBoxLayout()
        layout3.addWidget(self.output_folder)
        layout3.addWidget(self.browse_button2, alignment=Qt.AlignCenter)
        layout2.addLayout(layout3)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        groupbox = QGroupBox("Projection type")
        layout2 = QVBoxLayout()
        layout2.addWidget(self.b1)
        layout2.addWidget(self.b2)
        layout2.addWidget(self.b3)
        layout2.addWidget(self.b4)
        layout2.addWidget(self.b5)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        layout.addWidget(self.submit_button, alignment=Qt.AlignCenter)
        self.setLayout(layout)

        self.logger = logging.getLogger(__name__)

    def add_image(self):
        file_paths, _ = QFileDialog.getOpenFileNames(self, 'Select Files', filter='Images ('+' '.join(['*'+x for x in self.imagetypes])+')')
        for file_path in file_paths:
            if file_path and len(self.image_list.findItems(file_path, Qt.MatchExactly)) == 0:
                self.image_list.addItem(file_path)

    def add_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder_path:
            images = [os.path.join(folder_path, i) for i in os.listdir(folder_path) if os.path.splitext(i)[1] in self.imagetypes]
            self.image_list.addItems([i for i in images if len(self.image_list.findItems(i, Qt.MatchExactly)) == 0])

    def remove(self):
        for item in self.image_list.selectedItems():
            self.image_list.takeItem(self.image_list.row(item))

    def browse_model(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File")
        self.selected_model.setText(file_path)

    def browse_output(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        self.output_folder.setText(folder_path)
        
    def btnstate(self,b):
        if b.text() == "Max" and b.isChecked() == True:
            self.projection_type = 'max'
        elif b.text() == "Min" and b.isChecked() == True:
            self.projection_type = 'min'
        elif b.text() == "Std" and b.isChecked() == True:
            self.projection_type = 'std'
        elif b.text() == "Average" and b.isChecked() == True:
            self.projection_type = 'avg'
        elif b.text() == "Median" and b.isChecked() == True:
            self.projection_type = 'median'
				

    def click(self):

        def check_inputs(image_paths):
            if len(image_paths) == 0:
                self.logger.error('Image missing')
                self.add_image_button.setFocus()
                return False
            for path in image_paths:
                if not os.path.isfile(path):
                    self.logger.error('Image not found\n' + path)
                    self.add_image_button.setFocus()
                    return False
            if self.output_folder.text() == '' and not self.use_input_folder.isChecked():
                self.logger.error('Output folder missing')
                self.output_folder.setFocus()
                return False
            return True

        image_paths = [self.image_list.item(x).text() for x in range(self.image_list.count())]

        if not check_inputs(image_paths):
            return
        
        for image_path in image_paths:
            if os.path.isfile(image_path):
                if self.use_input_folder.isChecked():
                    output_path = os.path.join(os.path.dirname(image_path), 'zprojeczion')
                else:
                    output_path = self.output_folder.text()
                self.logger.info("Image %s", image_path)
                QApplication.setOverrideCursor(QCursor(Qt.BusyCursor))
                QApplication.processEvents()
                
                try:
                    f.main(image_path, output_path, self.projection_type)
                except Exception as e:
                    self.logger.error("Projecion failed.\n" + str(e))
                
                QApplication.restoreOverrideCursor()
            else:
                self.logger.error("Unable to locate file %s", image_path)
        

        self.logger.info("Done")
