import logging
import os
import re
import shutil
from PyQt5.QtWidgets import QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QGroupBox, QRadioButton, QFileDialog, QLabel, QFormLayout, QLineEdit, QCheckBox, QDialog, QDialogButtonBox, QTableWidget, QAbstractItemView, QTableWidgetItem, QHeaderView, QListWidget, QListWidgetItem, QMessageBox
from PyQt5.QtCore import Qt
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

    def __init__(self, files_to_export, log_files_to_export, move=False):
        super().__init__()
        self.setSizeGripEnabled(True)
        if move:
            self.setWindowTitle('Move')
        else:
            self.setWindowTitle('Copy')
        layout = QVBoxLayout()
        if move:
            message = QLabel('Files to move')
        else:
            message = QLabel('Files to copy')
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
        if len(log_files_to_export) > 0:
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
        message = QLabel('Files to remove')
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

        # Documentation
        label_documentation = gf.CollapsibleLabel('', collapsed=True)
        label_documentation.setText('For each input folder, selected files types can be exported (i.e. moved or copied) to the specified directory or removed.')

        # Input folders
        self.folder_list = gf.FolderListWidget()

        # Output folders
        self.use_input_folder = QRadioButton("Use input folder (sub-folder <input folder basename>/)")
        self.use_input_folder.setChecked(True)
        self.use_input_folder.toggled.connect(self.update_output_dirname_label)
        self.use_custom_folder = QRadioButton("Use custom folder (sub-folder <input folder basename>/)")
        self.use_custom_folder.setChecked(False)
        self.use_custom_folder.toggled.connect(self.update_output_dirname_label)
        self.output_folder = gf.FolderLineEdit()
        self.output_folder.textChanged.connect(self.update_output_dirname_label)
        self.output_folder.setVisible(self.use_custom_folder.isChecked())
        self.use_custom_folder.toggled.connect(self.output_folder.setVisible)
        self.output_dirname_label = QLineEdit()
        self.output_dirname_label.setFrame(False)
        self.output_dirname_label.setEnabled(False)

        # files
        self.files_image = QCheckBox('Input image')
        self.files_registration = QCheckBox('Registration module output files (*'+gf.output_suffixes['registration']+')')
        self.files_zprojection = QCheckBox('Z-projection module output files (*'+gf.output_suffixes['zprojection']+')')
        self.files_segmentation = QCheckBox('Segmentation module output files (*'+gf.output_suffixes['segmentation']+')')
        self.files_cell_tracking = QCheckBox('Cell tracking module output files (*'+gf.output_suffixes['cell_tracking']+')')
        self.files_graph_filtering = QCheckBox('Graph filtering module output files (*'+gf.output_suffixes['graph_filtering']+')')
        self.files_events_filter = QCheckBox('Events filter module output files (*'+gf.output_suffixes['events_filter']+')')
        self.files_ground_truth_generator = QCheckBox('Ground truth generator module output files (*'+gf.output_suffixes['ground_truth_generator']+')')
        self.files_intermediate_logs = QCheckBox('Preserve intermediate log files')
        self.files_intermediate_logs.setToolTip('Preserve all log files, including log files corresponding to intermediate files')
        self.files_intermediate_logs.setChecked(True)

        self.copy_button = QPushButton("Copy files", self)
        self.copy_button.clicked.connect(self.copy)
        self.move_button = QPushButton("Move files", self)
        self.move_button.clicked.connect(self.move)
        self.clean_button = QPushButton("Remove files", self)
        self.clean_button.clicked.connect(self.clean)

        # Layout
        layout = QVBoxLayout()

        # Documentation
        groupbox = QGroupBox("Documentation")
        layout2 = QVBoxLayout()
        layout2.addWidget(label_documentation)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        # Input folder
        groupbox = QGroupBox('Input folders')
        layout2 = QVBoxLayout()
        layout2.addWidget(self.folder_list)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        # Output folders
        groupbox2 = QGroupBox('Output (when moving or copying files)')
        layout2 = QVBoxLayout()
        layout2.addWidget(QLabel("Folder:"))
        layout2.addWidget(self.use_input_folder)
        layout2.addWidget(self.use_custom_folder)
        layout2.addWidget(self.output_folder)
        layout3 = QFormLayout()
        layout3.addRow("Output:", self.output_dirname_label)
        layout2.addLayout(layout3)
        groupbox2.setLayout(layout2)
        layout.addWidget(groupbox2)

        groupbox2 = QGroupBox("Files selection:")
        layout2 = QVBoxLayout()
        layout2.addWidget(self.files_image)
        layout2.addWidget(self.files_registration)
        layout2.addWidget(self.files_zprojection)
        layout2.addWidget(self.files_segmentation)
        layout2.addWidget(self.files_cell_tracking)
        layout2.addWidget(self.files_graph_filtering)
        layout2.addWidget(self.files_events_filter)
        layout2.addWidget(self.files_ground_truth_generator)
        layout2.addWidget(self.files_intermediate_logs)
        groupbox2.setLayout(layout2)
        layout.addWidget(groupbox2)

        layout2 = QHBoxLayout()
        layout2.addStretch()
        layout2.addWidget(self.copy_button, alignment=Qt.AlignCenter)
        layout2.addWidget(self.move_button, alignment=Qt.AlignCenter)
        layout2.addWidget(self.clean_button, alignment=Qt.AlignCenter)
        layout2.addStretch()
        layout.addLayout(layout2)


        self.setLayout(layout)

        self.logger = logging.getLogger(__name__)

        self.update_output_dirname_label()

    def update_output_dirname_label(self):
        if self.use_input_folder.isChecked():
            output_path = "<input folder>"
        else:
            output_path = self.output_folder.text()
        self.output_dirname_label.setText(os.path.join(os.path.normpath(output_path), "<input folder basename>", ""))

    def copy(self):
        self.export(move=False)

    def move(self):
        self.export(move=True)

    def export(self, move = False):
        if move:
            self.logger.info('Moving files')
        else:
            self.logger.info('Copying files')

        input_paths = self.folder_list.get_folder_list()
        if len(input_paths) == 0:
            self.logger.error('Input folder missing')
            return

        if self.use_input_folder.isChecked():
            output_paths = [os.path.join(os.path.dirname(path), os.path.basename(os.path.normpath(path))) for path in input_paths]
        else:
            output_paths = [os.path.join(self.output_folder.text(), os.path.basename(os.path.normpath(path))) for path in input_paths]

        patterns = []
        if self.files_zprojection.isChecked():
            patterns.append(gf.output_suffixes['zprojection']+'[A-Za-z0-9-]*'+'[a-zA-Z.]*$')
        if self.files_ground_truth_generator.isChecked():
            patterns.append(gf.output_suffixes['ground_truth_generator']+'[A-Za-z0-9-]*'+'[a-zA-Z.]*$')
            # exported directory
            patterns.append(gf.output_suffixes['ground_truth_generator']+'[A-Za-z0-9-]*$')
            patterns.append(gf.output_suffixes['ground_truth_generator']+'[A-Za-z0-9-]*'+gf.output_suffixes['zprojection']+'[A-Za-z0-9-]*$')
        if self.files_registration.isChecked():
            patterns.append(gf.output_suffixes['registration']+'[A-Za-z0-9-]*'+'[a-zA-Z.]*$')
        if self.files_segmentation.isChecked():
            patterns.append(gf.output_suffixes['segmentation']+'[A-Za-z0-9-]*'+'[a-zA-Z.]*$')
        if self.files_cell_tracking.isChecked():
            patterns.append(gf.output_suffixes['cell_tracking']+'[A-Za-z0-9-]*'+'[a-zA-Z.]*$')
        if self.files_graph_filtering.isChecked():
            patterns.append(gf.output_suffixes['graph_filtering']+'[A-Za-z0-9-]*'+'[a-zA-Z.]*$')
        if self.files_events_filter.isChecked():
            patterns.append(gf.output_suffixes['events_filter']+'[A-Za-z0-9-]*'+'[a-zA-Z.]*$')

        if len(patterns) == 0:
            QMessageBox.warning(self, 'Warning', 'Please select at least one file type in the files selection box\n(in addition to log files).', buttons=QMessageBox.Ok)
            return

        files_to_export = []
        log_files_to_export = []
        for input_path, output_path in zip(input_paths, output_paths):
            files_to_export_tmp = [f for f in os.listdir(input_path) if any(re.search(p, f) for p in patterns)]
            files_to_export.extend([(os.path.join(input_path, f), os.path.join(output_path, f)) for f in files_to_export_tmp])
            if self.files_intermediate_logs.isChecked():
                log_files_to_export_tmp = [gf.splitext(f)[0] for f in os.listdir(input_path) if f.endswith('.log') and f not in files_to_export_tmp]
                # keep only log_files with basename corresponding to the beginning of an exported file name
                log_files_to_export_tmp = [l + '.log' for l in log_files_to_export_tmp if any(f.startswith(l) for f in files_to_export_tmp)]
                log_files_to_export.extend([(os.path.join(input_path, f), os.path.join(output_path, f)) for f in log_files_to_export_tmp])

        msg = ConfirmExportDialog(files_to_export, log_files_to_export, move=move)
        if msg.exec_() == QDialog.Accepted:
            for src, dst in set(files_to_export):
                output_path = os.path.dirname(dst)
                if not os.path.isdir(output_path):
                    self.logger.info("Creating: %s", output_path)
                    os.makedirs(output_path)
                self.logger.info("Moving: %s to %s", src, dst)
                if move:
                    shutil.move(src, dst)
                else:
                    if os.path.isdir(src):
                        shutil.copytree(src, dst, dirs_exist_ok=True)
                    else:
                        shutil.copy(src, dst)
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

        input_paths = self.folder_list.get_folder_list()
        if len(input_paths) == 0:
            self.logger.error('Input folder missing')
            return

        patterns = []
        if self.files_zprojection.isChecked():
            patterns.append(gf.output_suffixes['zprojection']+'[A-Za-z0-9-]*'+'[a-zA-Z.]*$')
        if self.files_ground_truth_generator.isChecked():
            patterns.append(gf.output_suffixes['ground_truth_generator']+'[A-Za-z0-9-]*'+'[a-zA-Z.]*$')
            # exported directory
            patterns.append(gf.output_suffixes['ground_truth_generator']+'[A-Za-z0-9-]*$')
            patterns.append(gf.output_suffixes['ground_truth_generator']+'[A-Za-z0-9-]*'+gf.output_suffixes['zprojection']+'[A-Za-z0-9-]*$')
        if self.files_registration.isChecked():
            patterns.append(gf.output_suffixes['registration']+'[A-Za-z0-9-]*'+'[a-zA-Z.]*$')
        if self.files_segmentation.isChecked():
            patterns.append(gf.output_suffixes['segmentation']+'[A-Za-z0-9-]*'+'[a-zA-Z.]*$')
        if self.files_cell_tracking.isChecked():
            patterns.append(gf.output_suffixes['cell_tracking']+'[A-Za-z0-9-]*'+'[a-zA-Z.]*$')
        if self.files_graph_filtering.isChecked():
            patterns.append(gf.output_suffixes['graph_filtering']+'[A-Za-z0-9-]*'+'[a-zA-Z.]*$')
        if self.files_events_filter.isChecked():
            patterns.append(gf.output_suffixes['events_filter']+'[A-Za-z0-9-]*'+'[a-zA-Z.]*$')

        if len(patterns) == 0:
            QMessageBox.warning(self, 'Warning', 'Please select at least one file type in the files selection box\n(in addition to log files).', buttons=QMessageBox.Ok)
            return

        files_to_remove = []
        for input_path in input_paths:
            files_to_remove_tmp = [f for f in os.listdir(input_path) if any(re.search(p, f) for p in patterns)]
            files_to_keep_tmp = [f for f in os.listdir(input_path) if f not in files_to_remove_tmp]

            if self.files_intermediate_logs.isChecked():
                log_files_to_keep_tmp = [gf.splitext(f)[0] for f in os.listdir(input_path) if f.endswith('.log') and f not in files_to_keep_tmp]
                # keep only log_files with basename corresponding to the beginning of an exported file name
                log_files_to_keep_tmp = [l + '.log' for l in log_files_to_keep_tmp if any(f.startswith(l) for f in files_to_keep_tmp)]
                # remove from files_to_remove_tmp
                files_to_remove_tmp = [f for f in files_to_remove_tmp if f not in log_files_to_keep_tmp]

            files_to_remove.extend([os.path.join(input_path, f) for f in files_to_remove_tmp])

        msg = ConfirmRemoveDialog(files_to_remove)
        if msg.exec_() == QDialog.Accepted:
            for f in set(files_to_remove):
                self.logger.info("Removing: %s", f)
                if os.path.isdir(f):
                    shutil.rmtree(f)
                else:
                    os.remove(f)

        self.logger.info("Done")
