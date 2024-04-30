import logging
import os
import re
import shutil
from PyQt5.QtWidgets import QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QGroupBox, QRadioButton, QApplication, QFileDialog, QComboBox, QSpinBox, QLabel, QFormLayout, QLineEdit, QCheckBox, QDialog, QDialogButtonBox, QTableWidget, QAbstractItemView, QTableWidgetItem, QHeaderView, QListWidget, QListWidgetItem
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCursor
from general import general_functions as gf

class ConfirmExportDialog(QDialog):
    """
    a dialog to confirm file export

    Examples
    --------
    msg=ConfirmExportDialog([('filesource1', 'filedest1'), ('filesource2', 'filedest2'), ('filesource3', 'filedest3')],
                            [('logfilesource1', 'logfiledest1'), ('logfilesource2', 'logfiledest2')])
    if msg.exec_():
        print("export")
    """

    def __init__(self, files_to_export,log_files_to_export):
        super().__init__()
        self.setSizeGripEnabled(True)
        self.setWindowTitle('Export')
        layout = QVBoxLayout()
        message = QLabel('Files to move:')
        message.setWordWrap(True)
        layout.addWidget(message)
        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(['Source', 'Destination'])
        table.verticalHeader().hide()
        table.setTextElideMode(Qt.ElideLeft)
        table.setWordWrap(False)
        table.setSelectionMode(QAbstractItemView.NoSelection)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        for src, dst in files_to_export:
            table.insertRow(table.rowCount())
            item = QTableWidgetItem(src)
            item.setToolTip(src)
            item.setFlags(item.flags() ^ Qt.ItemIsEditable)
            table.setItem(table.rowCount()-1, 0, item)
            item = QTableWidgetItem(dst)
            item.setToolTip(dst)
            item.setFlags(item.flags() ^ Qt.ItemIsEditable)
            table.setItem(table.rowCount()-1, 1, item)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(table)
        if len(log_files_to_export)>0:
            message = QLabel('Intermediate log files to copy:')
            message.setWordWrap(True)
            layout.addWidget(message)
            table = QTableWidget()
            table.setColumnCount(2)
            table.setHorizontalHeaderLabels(['Source', 'Destination'])
            table.verticalHeader().hide()
            table.setTextElideMode(Qt.ElideLeft)
            table.setWordWrap(False)
            table.setSelectionMode(QAbstractItemView.NoSelection)
            table.setSelectionBehavior(QAbstractItemView.SelectRows)
            for src, dst in log_files_to_export:
                table.insertRow(table.rowCount())
                item = QTableWidgetItem(src)
                item.setToolTip(src)
                item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                table.setItem(table.rowCount()-1, 0, item)
                item = QTableWidgetItem(dst)
                item.setToolTip(dst)
                item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                table.setItem(table.rowCount()-1, 1, item)
            table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            table.horizontalHeader().setStretchLastSection(True)
            layout.addWidget(table)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setLayout(layout)


class ConfirmRemoveDialog(QDialog):
    """
    a dialog to confirm file removal

    Examples
    --------
    msg=StatusTableDialog(['file', 'file2', 'file3', 'file4'])
    if msg.exec_():
        print("remove")
    """

    def __init__(self, files_to_remove):
        super().__init__()
        self.setSizeGripEnabled(True)
        self.setWindowTitle('Clean')
        layout = QVBoxLayout()
        message = QLabel('Files to remove:')
        message.setWordWrap(True)
        layout.addWidget(message)

        file_list = QListWidget()
        file_list.setTextElideMode(Qt.ElideLeft)
        file_list.setWordWrap(False)
        file_list.setSelectionMode(QAbstractItemView.NoSelection)
        file_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        for f in files_to_remove:
            item = QListWidgetItem(f)
            item.setToolTip(f)
            item.setFlags(item.flags() ^ Qt.ItemIsEditable)
            file_list.addItem(item)
        layout.addWidget(file_list)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setLayout(layout)


class FileOrganization(QWidget):
    def __init__(self):
        super().__init__()

        self.output_suffixes = { 'zprojection': '_vPR',
                                 'groundtruth_generator': '_vGT',
                                 'registration': '_vRG',
                                 'segmentation': '_vSM',
                                 'cell_tracking': '_vTG',
                                 'graph_filtering': '_vGF',
                                 'events_filter': '_vEF'}
        # Input folders
        self.imagetypes = ['.nd2', '.tif', '.tiff', '.ome.tif', '.ome.tiff']
        self.folder_list = gf.DirListWidget()

        # Output folders (export)
        self.use_input_folder = QRadioButton("Use input folder (sub-folder <input folder basename>/)")
        self.use_input_folder.setChecked(True)
        self.use_input_folder.toggled.connect(self.update_output_dirname_label)
        self.use_custom_folder = QRadioButton("Use custom folder (sub-folder <input folder basename>/)")
        self.use_custom_folder.setChecked(False)
        self.use_custom_folder.toggled.connect(self.update_output_dirname_label)
        self.output_folder = gf.DropFolderLineEdit()
        self.output_folder.textChanged.connect(self.update_output_dirname_label)
        self.browse_button2 = QPushButton("Browse", self)
        self.browse_button2.clicked.connect(self.browse_output)
        self.output_folder.setVisible(self.use_custom_folder.isChecked())
        self.browse_button2.setVisible(self.use_custom_folder.isChecked())
        self.use_custom_folder.toggled.connect(self.output_folder.setVisible)
        self.use_custom_folder.toggled.connect(self.browse_button2.setVisible)
        self.output_dirname_label = QLineEdit()
        self.output_dirname_label.setFrame(False)
        self.output_dirname_label.setEnabled(False)

        #files to export
        self.export_image = QCheckBox('Input image')
        self.export_zprojection = QCheckBox('Z-projection module output files (*'+self.output_suffixes['zprojection']+')')
        self.export_groundtruth_generator = QCheckBox('GroundTruth module output files (*'+self.output_suffixes['groundtruth_generator']+')')
        self.export_registration = QCheckBox('Registration module output files (*'+self.output_suffixes['registration']+')')
        self.export_segmentation = QCheckBox('Segmentation module output files (*'+self.output_suffixes['segmentation']+')')
        self.export_cell_tracking = QCheckBox('Cell tracking module output files (*'+self.output_suffixes['cell_tracking']+')')
        self.export_graph_filtering = QCheckBox('Graph filtering module output files (*'+self.output_suffixes['graph_filtering']+')')
        self.export_events_filter = QCheckBox('Events filter module output files (*'+self.output_suffixes['events_filter']+')')
        self.export_intermediate_logs = QCheckBox('Copy intermediate log files')
        self.export_intermediate_logs.setToolTip('Export all log files, including log files corresponding to intermediate files that are not moved')
        self.export_intermediate_logs.setChecked(True)

        # Export
        self.export_button = QPushButton("Export", self)
        self.export_button.clicked.connect(self.export)

        #files to clean
        self.clean_zprojection = QCheckBox('Z-projection module output files (*'+self.output_suffixes['zprojection']+')')
        self.clean_groundtruth_generator = QCheckBox('GroundTruth module output files (*'+self.output_suffixes['groundtruth_generator']+')')
        self.clean_registration = QCheckBox('Registration module output files (*'+self.output_suffixes['registration']+')')
        self.clean_segmentation = QCheckBox('Segmentation module output files (*'+self.output_suffixes['segmentation']+')')
        self.clean_cell_tracking = QCheckBox('Cell tracking module output files (*'+self.output_suffixes['cell_tracking']+')')
        self.clean_graph_filtering = QCheckBox('Graph filtering module output files (*'+self.output_suffixes['graph_filtering']+')')
        self.clean_events_filter = QCheckBox('Events filter module output files (*'+self.output_suffixes['events_filter']+')')
        self.clean_keep_intermediate_logs = QCheckBox('Keep intermediate log files')
        self.clean_keep_intermediate_logs.setToolTip('Kepp all log files, including log files corresponding to intermediate files that are removed.')
        self.clean_keep_intermediate_logs.setChecked(True)

        # clean
        self.clean_button = QPushButton("Clean", self)
        self.clean_button.clicked.connect(self.clean)

        # Layout
        layout = QVBoxLayout()

        # Input folder
        groupbox = QGroupBox('Input folders')
        layout2 = QVBoxLayout()
        layout2.addWidget(self.folder_list)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        ##export
        groupbox = QGroupBox('Export (move files)')
        layout2 = QVBoxLayout()

        # Output folders
        groupbox2 = QGroupBox('Output')
        layout3 = QVBoxLayout()
        layout3.addWidget(QLabel("Folder:"))
        layout3.addWidget(self.use_input_folder)
        layout3.addWidget(self.use_custom_folder)
        layout4 = QHBoxLayout()
        layout4.addWidget(self.output_folder)
        layout4.addWidget(self.browse_button2, alignment=Qt.AlignCenter)
        layout3.addLayout(layout4)
        layout4 = QFormLayout()
        layout4.addRow("Output:", self.output_dirname_label)
        layout3.addLayout(layout4)
        groupbox2.setLayout(layout3)
        layout2.addWidget(groupbox2)

        groupbox2 = QGroupBox("Files to move:")
        layout3 = QVBoxLayout()
        layout3.addWidget(self.export_image)
        layout3.addWidget(self.export_zprojection)
        layout3.addWidget(self.export_groundtruth_generator)
        layout3.addWidget(self.export_registration)
        layout3.addWidget(self.export_segmentation)
        layout3.addWidget(self.export_cell_tracking)
        layout3.addWidget(self.export_graph_filtering)
        layout3.addWidget(self.export_events_filter)
        layout3.addWidget(self.export_intermediate_logs)
        groupbox2.setLayout(layout3)
        layout2.addWidget(groupbox2)

        # Export
        layout2.addWidget(self.export_button, alignment=Qt.AlignCenter)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        ##Clean
        groupbox = QGroupBox('Clean (remove files)')
        layout2 = QVBoxLayout()

        groupbox2 = QGroupBox("Files to remove:")
        layout3 = QVBoxLayout()
        layout3.addWidget(self.clean_zprojection)
        layout3.addWidget(self.clean_groundtruth_generator)
        layout3.addWidget(self.clean_registration)
        layout3.addWidget(self.clean_segmentation)
        layout3.addWidget(self.clean_cell_tracking)
        layout3.addWidget(self.clean_graph_filtering)
        layout3.addWidget(self.clean_events_filter)
        layout3.addWidget(self.clean_keep_intermediate_logs)
        groupbox2.setLayout(layout3)
        layout2.addWidget(groupbox2)

        # Celan
        layout2.addWidget(self.clean_button, alignment=Qt.AlignCenter)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        self.setLayout(layout)


        self.logger = logging.getLogger(__name__)

        self.update_output_dirname_label()

    def browse_output(self):
        # Browse folders in order to choose the output one
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        self.output_folder.setText(folder_path)
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        self.output_folder.setText(folder_path)

    def update_output_dirname_label(self):
        if self.use_input_folder.isChecked():
            output_path = "<input folder>"
        else:
            output_path = self.output_folder.text().rstrip("/")
        self.output_dirname_label.setText(os.path.join(output_path,"<input folder basename>",""))

    def export(self):
        self.logger.info('Exporting')

        input_paths = self.folder_list.get_dir_list()
        if len(input_paths) == 0:
            self.logger.error('Input folder missing')
            return False

        if self.use_input_folder.isChecked():
            output_paths = [os.path.join(os.path.dirname(path), os.path.basename(path.rstrip('/'))) for path in input_paths]
        else:
            output_paths = [os.path.join(self.output_folder.text(), os.path.basename(path.rstrip('/'))) for path in input_paths]

        patterns = []
        if self.export_zprojection.isChecked():
            patterns.append(self.output_suffixes['zprojection']+'[A-Za-z0-9-]*'+'[a-zA-Z.]*$')
        if self.export_groundtruth_generator.isChecked():
            patterns.append(self.output_suffixes['groundtruth_generator']+'[A-Za-z0-9-]*'+'[a-zA-Z.]*$')
        if self.export_registration.isChecked():
            patterns.append(self.output_suffixes['registration']+'[A-Za-z0-9-]*'+'[a-zA-Z.]*$')
        if self.export_segmentation.isChecked():
            patterns.append(self.output_suffixes['segmentation']+'[A-Za-z0-9-]*'+'[a-zA-Z.]*$')
        if self.export_cell_tracking.isChecked():
            patterns.append(self.output_suffixes['cell_tracking']+'[A-Za-z0-9-]*'+'[a-zA-Z.]*$')
        if self.export_graph_filtering.isChecked():
            patterns.append(self.output_suffixes['graph_filtering']+'[A-Za-z0-9-]*'+'[a-zA-Z.]*$')
        if self.export_events_filter.isChecked():
            patterns.append(self.output_suffixes['events_filter']+'[A-Za-z0-9-]*'+'[a-zA-Z.]*$')

        files_to_export = []
        log_files_to_export = []
        for input_path,output_path in zip(input_paths, output_paths):
            files_to_export_tmp = [f for f in os.listdir(input_path) if any(re.search(p, f) for p in patterns)]
            files_to_export.extend([(os.path.join(input_path,f), os.path.join(output_path,f)) for f in files_to_export_tmp ])
            if self.export_intermediate_logs.isChecked():
                log_files_to_export_tmp = [ gf.splitext(f)[0] for f in os.listdir(input_path) if f.endswith('.log') and not f in files_to_export_tmp]
                #keep only log_files with basename corresponding to the beginning of an exported file name
                log_files_to_export_tmp = [ l + '.log' for l in log_files_to_export_tmp if any(f.startswith(l) for f in files_to_export_tmp)]
                log_files_to_export.extend([(os.path.join(input_path,f), os.path.join(output_path,f)) for f in log_files_to_export_tmp ])

        msg = ConfirmExportDialog(files_to_export,log_files_to_export)
        if msg.exec_() == QDialog.Accepted:
            for src, dst in set(files_to_export):
                output_path = os.path.dirname(dst)
                if not os.path.isdir(output_path):
                    self.logger.info("Creating: %s", output_path)
                    os.makedirs(output_path)
                self.logger.info("Moving: %s to %s", src, dst)
                os.replace(src, dst)
            for src, dst in set(log_files_to_export):
                output_path = os.path.dirname(dst)
                if not os.path.isdir(output_path):
                    self.logger.info("Creating: %s", output_path)
                    os.makedirs(output_path)
                self.logger.info("Copying: %s to %s", src, dst)
                shutil.copy(src, dst)

        self.logger.info("Done")

    def clean(self):
        self.logger.info('Cleaning')

        input_paths = self.folder_list.get_dir_list()
        if len(input_paths) == 0:
            self.logger.error('Input folder missing')
            return False

        patterns = []
        if self.clean_zprojection.isChecked():
            patterns.append(self.output_suffixes['zprojection']+'[A-Za-z0-9-]*'+'[a-zA-Z.]*$')
        if self.clean_groundtruth_generator.isChecked():
            patterns.append(self.output_suffixes['groundtruth_generator']+'[A-Za-z0-9-]*'+'[a-zA-Z.]*$')
        if self.clean_registration.isChecked():
            patterns.append(self.output_suffixes['registration']+'[A-Za-z0-9-]*'+'[a-zA-Z.]*$')
        if self.clean_segmentation.isChecked():
            patterns.append(self.output_suffixes['segmentation']+'[A-Za-z0-9-]*'+'[a-zA-Z.]*$')
        if self.clean_cell_tracking.isChecked():
            patterns.append(self.output_suffixes['cell_tracking']+'[A-Za-z0-9-]*'+'[a-zA-Z.]*$')
        if self.clean_graph_filtering.isChecked():
            patterns.append(self.output_suffixes['graph_filtering']+'[A-Za-z0-9-]*'+'[a-zA-Z.]*$')
        if self.clean_events_filter.isChecked():
            patterns.append(self.output_suffixes['events_filter']+'[A-Za-z0-9-]*'+'[a-zA-Z.]*$')

        files_to_remove = []
        for input_path in input_paths:
            files_to_remove_tmp = [f for f in os.listdir(input_path) if any(re.search(p, f) for p in patterns)]
            files_to_keep_tmp = [f for f in os.listdir(input_path) if f not in files_to_remove_tmp]

            if self.clean_keep_intermediate_logs.isChecked():
                log_files_to_keep_tmp = [ gf.splitext(f)[0] for f in os.listdir(input_path) if f.endswith('.log') and not f in files_to_keep_tmp]
                #keep only log_files with basename corresponding to the beginning of an exported file name
                log_files_to_keep_tmp = [ l + '.log' for l in log_files_to_keep_tmp if any(f.startswith(l) for f in files_to_keep_tmp)]
                #remove from files_to_remove_tmp
                files_to_remove_tmp = [ f for f in files_to_remove_tmp if f not in log_files_to_keep_tmp]

            files_to_remove.extend([os.path.join(input_path,f) for f in files_to_remove_tmp ])

        msg = ConfirmRemoveDialog(files_to_remove)
        if msg.exec_() == QDialog.Accepted:
            for f in set(files_to_remove):
                self.logger.info("Removing: %s", f)
                os.remove(f)

        self.logger.info("Done")
