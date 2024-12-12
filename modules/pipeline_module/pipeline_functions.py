import os
from PyQt5.QtWidgets import QAbstractItemView, QListView, QStyledItemDelegate, QStyle, QMessageBox, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QRadioButton, QPushButton, QLineEdit, QGroupBox, QFileDialog, QCheckBox, QSpinBox, QDialog, QTableWidget, QTableWidgetItem, QHeaderView
from PyQt5.QtCore import Qt, QSize, QMargins, QMarginsF, QRect, QRectF, QPointF, QItemSelectionModel
from PyQt5.QtGui import QFont, QPainter, QPainterPath, QPen, QFontMetrics, QStandardItemModel, QPalette, QBrush, QColor
from general import general_functions as gf
from cellpose.core import assign_device


class ListView(QListView):
    def __init__(self, parent=None, placeholder_text=None):
        super().__init__(parent)
        self.placeholder_text = placeholder_text
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        # to deal with selection after drag&drop (works only with selection mode QAbstractItemView.SingleSelection)
        self.rows_removed_start = None
        self.rows_removed_end = None
        self.rows_inserted_start = None
        self.rows_inserted_end = None
        self.allowed_drop_positions = None

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.model().rowCount() == 0:
            painter = QPainter(self.viewport())
            brush = self.palette().brush(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text)
            painter.setPen(QPen(brush.color()))
            painter.drawText(event.rect(), Qt.TextWordWrap | Qt.AlignCenter | Qt.AlignVCenter, self.placeholder_text)

    def delete_selection(self):
        if len(self.selectionModel().selectedRows()) == 1:
            # check if the pipeline is still valid after removal
            selected_index = self.selectionModel().selectedRows()[0]
            selected_item_data = self.model().data(selected_index, Qt.UserRole+1)
            next_index = self.model().index(selected_index.row()+1, 0)
            next_item_data = self.model().data(next_index, Qt.UserRole+1)
            previous_index = self.model().index(selected_index.row()-1, 0)
            previous_item_data = self.model().data(previous_index, Qt.UserRole+1)

            remove = True
            if 'is_removable' in selected_item_data and not selected_item_data['is_removable']:
                remove = False
            if previous_item_data is not None and next_item_data is not None and not set(next_item_data['input_types']).issubset(previous_item_data['output_types']):
                remove = False
            if remove:
                ret = QMessageBox.warning(self, 'Warning', 'Remove selected module?', buttons=QMessageBox.Ok | QMessageBox.Cancel, defaultButton=QMessageBox.Ok)
                if ret == QMessageBox.Ok:
                    self.model().removeRow(self.selectionModel().selectedRows()[0].row())
            else:
                QMessageBox.warning(None, 'Warning', 'It is not possible to remove this module without breaking the pipeline.', buttons=QMessageBox.Ok)

    def startDrag(self, supportedActions):
        if self.defaultDropAction() == Qt.MoveAction:
            # check if the pipeline is still valid after the drag
            selected_index = self.selectionModel().selectedRows()[0]
            selected_item_data = self.model().data(selected_index, Qt.UserRole+1)
            if 'is_removable' in selected_item_data and not selected_item_data['is_removable']:
                QMessageBox.warning(None, 'Warning', 'It is not possible to move this module without breaking the pipeline.', buttons=QMessageBox.Ok)
                return
            next_index = self.model().index(selected_index.row()+1, 0)
            next_item_data = self.model().data(next_index, Qt.UserRole+1)
            previous_index = self.model().index(selected_index.row()-1, 0)
            previous_item_data = self.model().data(previous_index, Qt.UserRole+1)
            if previous_item_data is not None and next_item_data is not None and not set(next_item_data['input_types']).issubset(previous_item_data['output_types']):
                QMessageBox.warning(None, 'Warning', 'It is not possible to move this module without breaking the pipeline.', buttons=QMessageBox.Ok)
                return

        # Deal with selection
        self.rows_removed_start = None
        self.rows_removed_end = None
        self.rows_inserted_start = None
        self.rows_inserted_end = None
        super().startDrag(supportedActions)
        if self.rows_removed_start is not None and self.rows_removed_end is not None:
            # drag&drop finished and an item was removed from this list: unselect everything
            self.clearSelection()
        if self.rows_inserted_start is not None and self.rows_inserted_end is not None:
            # drag&drop finished and an item was inserted to this list: select inserted item (but shift item index if an item with lower index was removed)
            shift = 0
            for i in range(self.rows_removed_start, self.rows_removed_end+1):
                if i <= self.rows_inserted_start:
                    shift += 1
            self.selectionModel().clear()
            for i in range(self.rows_inserted_start, self.rows_inserted_end+1):
                index = self.model().index(i-shift, 0)  # (row,column)
                self.selectionModel().select(index, QItemSelectionModel.Select)

        self.rows_removed_start = None
        self.rows_removed_end = None
        self.rows_inserted_start = None
        self.rows_inserted_end = None

    def dragEnterEvent(self, event):
        # check where the drop is allowed
        if event.source() is None:
            # not dragging from a widget inside this application
            super().dragEnterEvent(event)
            return

        source_model = event.source().model()
        dropped_item_text = source_model.data(event.source().selectionModel().selectedRows()[0], Qt.DisplayRole)
        dropped_item_data = source_model.data(event.source().selectionModel().selectedRows()[0], Qt.UserRole+1)
        self.allowed_drop_positions = []  # drop before item i (at the end if i==rowCount())
        if event.source() != self:
            # check that there is no conflicting module
            if 'conflicting_modules' in dropped_item_data:
                if any(self.model().data(self.model().index(i, 0), Qt.UserRole+1)['name'] in dropped_item_data['conflicting_modules'] for i in range(self.model().rowCount())):
                    super().dragEnterEvent(event)
                    return

        for i in range(self.model().rowCount()+1):
            previous_target_index = self.model().index(i-1, 0)
            next_target_index = self.model().index(i, 0)
            previous_item_data = self.model().data(previous_target_index, Qt.UserRole+1)
            next_item_data = self.model().data(next_target_index, Qt.UserRole+1)
            drop = True
            if previous_item_data is not None and len(previous_item_data['output_types']) == 0:
                drop = False
            if previous_item_data is not None and len(dropped_item_data['input_types']) == 0:
                drop = False
            if next_item_data is not None and len(next_item_data['input_types']) == 0:
                drop = False
            if next_item_data is not None and len(dropped_item_data['output_types']) == 0:
                drop = False
            if previous_item_data is not None and not set(dropped_item_data['input_types']).issubset(previous_item_data['output_types']):
                drop = False
            if next_item_data is not None and not set(next_item_data['input_types']).issubset(dropped_item_data['output_types']):
                drop = False
            if drop:
                self.allowed_drop_positions.append(i)

        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        super().dragMoveEvent(event)
        dropped_position = -1
        if self.dropIndicatorPosition() == QAbstractItemView.AboveItem:
            dropped_position = self.indexAt(event.pos()).row()
        if self.dropIndicatorPosition() == QAbstractItemView.BelowItem:
            dropped_position = self.indexAt(event.pos()).row()+1
        if self.dropIndicatorPosition() == QAbstractItemView.OnViewport:
            # dropped after last element
            dropped_position = self.model().rowCount()
        if dropped_position in self.allowed_drop_positions:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        dropped_position = -1
        if self.dropIndicatorPosition() == QAbstractItemView.AboveItem:
            dropped_position = self.indexAt(event.pos()).row()
        if self.dropIndicatorPosition() == QAbstractItemView.BelowItem:
            dropped_position = self.indexAt(event.pos()).row()+1
        if self.dropIndicatorPosition() == QAbstractItemView.OnViewport:
            # dropped after last element
            dropped_position = self.model().rowCount()
        if dropped_position in self.allowed_drop_positions:
            event.acceptProposedAction()
        else:
            event.setDropAction(Qt.IgnoreAction)
            event.ignore()
        super().dropEvent(event)
        # deal with selection
        if event.source() != self:  # i.e. drag initiated in an other list
            if self.rows_inserted_start is not None and self.rows_inserted_end is not None:
                # select inserted item (warning: not for internal move, as it prevents removing the dragged item, i.e. it duplicates)
                self.selectionModel().clear()
                for i in range(self.rows_inserted_start, self.rows_inserted_end+1):
                    index = self.model().index(i, 0)  # (row,column)
                    self.selectionModel().select(index, QItemSelectionModel.Select)
                self.rows_inserted_start = None
                self.rows_inserted_end = None

    def rowsAboutToBeRemoved(self, parent, start, end):
        super().rowsAboutToBeRemoved(parent, start, end)
        self.rows_removed_start = start
        self.rows_removed_end = end

    def rowsInserted(self, parent, start, end):
        super().rowsInserted(parent, start, end)
        self.rows_inserted_start = start
        self.rows_inserted_end = end


class ItemDelegate(QStyledItemDelegate):
    def __init__(self, numbered=False, draw_links=False):
        super().__init__()
        self.numbered = numbered
        self.draw_links = draw_links
        default_font_height = QFontMetrics(QFont()).height()
        self.port_types = ['image', 'mask', 'graph', 'matrix']
        self.w = default_font_height*9
        self.h = default_font_height*7
        self.outer_margin = round(5*default_font_height/18)
        self.inner_margin = round(5*default_font_height/18)
        self.rounding_radius = round(5*default_font_height/18)
        self.port_radius = round(8*default_font_height/18)

    def paint(self, painter, option, index):
        title = index.data()
        if self.numbered:
            title = str(index.row()+1) + ". " + title
        data = index.data(Qt.UserRole+1)
        rect_item = option.rect - QMargins(self.outer_margin+self.port_radius,
                                           self.outer_margin,
                                           self.outer_margin+self.port_radius,
                                           self.outer_margin)
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)

        # background
        path = QPainterPath()
        if option.state & QStyle.State_Selected:
            painter.setBrush(option.palette.base())
            painter.setPen(QPen(option.palette.highlight(), 1, Qt.SolidLine))
        else:
            painter.setBrush(option.palette.base())
            painter.setPen(QPen(option.palette.dark(), 1, Qt.SolidLine))
        # shift by 0.5 pixel to have 1pixel wide line passing exactly on the pixel (sharper results with antialiasing)
        path.addRoundedRect(QRectF(rect_item)+QMarginsF(0.5, 0.5, 0.5, 0.5), self.rounding_radius, self.rounding_radius)
        painter.drawPath(path)

        # Title background
        title_font_size_factor = 1.0
        rect_title = QRect(rect_item.left(),
                           rect_item.top(),
                           rect_item.width(),
                           round(title_font_size_factor*1.6*painter.fontMetrics().height()+2*self.inner_margin))
        if option.state & QStyle.State_Selected:
            painter.setBrush(option.palette.highlight())
            painter.setPen(QPen(option.palette.highlight(), 1, Qt.SolidLine))
        else:
            painter.setBrush(option.palette.dark())
            painter.setPen(QPen(option.palette.dark(), 1, Qt.SolidLine))
        path.clear()
        # shift by 0.5 pixel to have 1pixel wide line passing exactly on the pixel (sharper results with antialiasing)
        rect_title_margin = QRectF(rect_title) + QMarginsF(0.5, 0.5, 0.5, 0.5)
        path.moveTo(rect_title_margin.left(), rect_title_margin.bottom())
        path.arcTo(rect_title_margin.left(), rect_title_margin.top(), 2*self.rounding_radius, 2*self.rounding_radius, 180, -90)
        path.arcTo(rect_title_margin.right()-2*self.rounding_radius, rect_title_margin.top(), 2*self.rounding_radius, 2*self.rounding_radius, 90, -90)
        path.lineTo(rect_title_margin.right(), rect_title_margin.bottom())
        path.closeSubpath()
        painter.drawPath(path)

        # Title text
        font = QFont()
        font.setBold(True)
        font.setPointSize(round(title_font_size_factor*font.pointSize()))
        painter.setFont(font)
        if option.state & QStyle.State_Selected:
            painter.setPen(QPen(option.palette.highlightedText(), 1, Qt.SolidLine))
        else:
            painter.setPen(QPen(option.palette.highlightedText(), 1, Qt.SolidLine))
        painter.drawText(rect_title, Qt.TextWordWrap | Qt.AlignCenter | Qt.AlignVCenter, title)

        # Inputs
        rect_inputs_outputs = QRect(rect_item.left(),
                                    rect_title.bottom()+self.inner_margin,
                                    rect_item.width(),
                                    rect_item.bottom()-(rect_title.bottom()+2*self.inner_margin))

        port_radius = round(min(self.port_radius*2, (rect_inputs_outputs.height()-2*self.inner_margin)/len(self.port_types))/2)
        font = QFont()
        font.setPointSize(round(0.8*font.pointSize()))
        painter.setFont(font)
        painter.setBrush(option.palette.base())
        for i, p in enumerate(self.port_types):
            if p in data['input_types']:
                port_center = QPointF(rect_inputs_outputs.left(),
                                      rect_inputs_outputs.top()+(i+0.5)*rect_inputs_outputs.height()/len(self.port_types))
                painter.setPen(QPen(option.palette.dark(), 3, Qt.SolidLine))
                if self.draw_links and index.row() > 0:
                    painter.drawLine(option.rect.left(), round(port_center.y()), round(port_center.x()), round(port_center.y()))
                painter.drawEllipse(port_center, port_radius, port_radius)
                painter.setPen(QPen(option.palette.text(), 1, Qt.SolidLine))
                painter.drawText(QRect(rect_inputs_outputs.left()+port_radius+self.inner_margin,
                                       round(port_center.y()-rect_inputs_outputs.height()/len(self.port_types)/2),
                                       rect_inputs_outputs.width(),
                                       round(rect_inputs_outputs.height()/len(self.port_types))),
                                 Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignVCenter, p)

        # Outputs
        port_radius = round(min(self.port_radius*2, (rect_inputs_outputs.height()-2*self.inner_margin)/len(self.port_types))/2)
        for i, p in enumerate(self.port_types):
            if p in data['output_types']:
                port_center = QPointF(rect_inputs_outputs.right(),
                                      rect_inputs_outputs.top()+(i+0.5)*rect_inputs_outputs.height()/len(self.port_types))
                painter.setPen(QPen(option.palette.dark(), 3, Qt.SolidLine))
                if self.draw_links and index.row() < index.model().rowCount()-1:
                    painter.drawLine(round(port_center.x()), round(port_center.y()), option.rect.right(), round(port_center.y()))
                painter.drawEllipse(port_center, port_radius, port_radius)
                painter.setPen(QPen(option.palette.text(), 1, Qt.SolidLine))
                painter.drawText(QRect(rect_inputs_outputs.left(),
                                       round(port_center.y()-rect_inputs_outputs.height()/len(self.port_types)/2),
                                       rect_inputs_outputs.width()-port_radius-self.inner_margin,
                                       round(rect_inputs_outputs.height()/len(self.port_types))),
                                 Qt.TextWordWrap | Qt.AlignRight | Qt.AlignVCenter, p)

        painter.restore()

    def sizeHint(self, option, index):
        return QSize(self.w, self.h)


class StandardItemModel(QStandardItemModel):
    def flags(self, index):
        flags = super().flags(index)
        # to prevent overwriting existing item
        if index.isValid():
            flags = flags ^ Qt.ItemIsDropEnabled
        return flags


class GeneralSettings(QWidget):
    def __init__(self, input_type='none'):
        super().__init__()

        layout = QVBoxLayout()
        self.setLayout(layout)

        # Documentation
        label_documentation = gf.CollapsibleLabel('', collapsed=True)
        label_documentation.setText('General settings for the pipeline.<br>' +
                                    'Input files options will change to match the requirements of the connected module.')

        self.input_type = input_type

        # Input images
        self.image_list = gf.FileListWidget(filetypes=gf.imagetypes, filenames_filter='', filenames_exclude_filter=gf.output_suffixes['segmentation'])

        # Input masks
        self.mask_list = gf.FileListWidget(filetypes=gf.imagetypes, filenames_filter=gf.output_suffixes['segmentation'])

        # Input masks & graph
        self.mask_graph_table = gf.FileTableWidget2(header_1="Mask", header_2="Graph", filenames_suffix_1='.ome.tif', filenames_suffix_2='.graphmlz', filenames_filter=gf.output_suffixes['cell_tracking'])

        # Input image & registration matrix
        self.image_matrix_table = gf.ImageMatrixTableWidget2(filetypes=gf.imagetypes, filenames_filter='', filenames_exclude_filter=gf.output_suffixes['registration'], image_label='image')

        # Input mask & registration matrix
        self.mask_matrix_table = gf.ImageMatrixTableWidget2(filetypes=gf.imagetypes, filenames_filter=gf.output_suffixes['segmentation'], filenames_exclude_filter=gf.output_suffixes['registration'], image_label='mask')

        # Output folders
        self.use_input_folder = QRadioButton("Use input file folder")
        self.use_input_folder.setChecked(True)
        self.use_custom_folder = QRadioButton("Use custom folder (same for all the input files)")
        self.use_custom_folder.setChecked(False)
        self.output_folder = gf.FolderLineEdit()
        self.output_folder.setVisible(self.use_custom_folder.isChecked())
        self.use_custom_folder.toggled.connect(self.output_folder.setVisible)
        self.output_filename_label = QLineEdit()
        self.output_filename_label.setFrame(False)
        self.output_filename_label.setEnabled(False)

        # Multi-processing
        self.use_gpu = QCheckBox("Use GPU")
        device, gpu = assign_device(gpu=True)
        self.use_gpu.setChecked(gpu)
        self.use_gpu.setEnabled(gpu)
        self.nprocesses = QSpinBox()
        self.nprocesses.setMinimum(1)
        self.nprocesses.setMaximum(os.cpu_count())
        self.nprocesses.setValue(1)
        self.coarse_grain = QCheckBox("Use coarse-grained parallelization")
        self.coarse_grain.setToolTip("Assign each input file to own process. Use it when there are more input files than processes and enough memory (memory usage increases with the number of processes).")
        self.coarse_grain.setChecked(False)

        # Documentation
        groupbox = QGroupBox("Documentation")
        layout2 = QVBoxLayout()
        layout2.addWidget(label_documentation)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        # Input none
        self.input_none_groupbox = QGroupBox('Input files')
        layout2 = QVBoxLayout()
        label = QLabel('Please add a module')
        label.setEnabled(False)
        layout2.addWidget(label)
        self.input_none_groupbox.setLayout(layout2)
        self.input_none_groupbox.setVisible(self.input_type == 'none')
        layout.addWidget(self.input_none_groupbox)

        # Input images
        self.input_images_groupbox = QGroupBox('Input files (images)')
        layout2 = QVBoxLayout()
        layout2.addWidget(self.image_list)
        self.input_images_groupbox.setLayout(layout2)
        self.input_images_groupbox.setVisible(self.input_type == 'image')
        layout.addWidget(self.input_images_groupbox)

        # Input masks
        self.input_masks_groupbox = QGroupBox('Input files (segmentation masks)')
        layout2 = QVBoxLayout()
        layout2.addWidget(self.mask_list)
        self.input_masks_groupbox.setLayout(layout2)
        self.input_masks_groupbox.setVisible(self.input_type == 'mask')
        layout.addWidget(self.input_masks_groupbox)

        # Input masks & graphs
        self.input_masks_graphs_groupbox = QGroupBox('Input files (segmentation masks and cell tracking graphs)')
        layout2 = QVBoxLayout()
        layout2.addWidget(self.mask_graph_table)
        self.input_masks_graphs_groupbox.setLayout(layout2)
        self.input_masks_graphs_groupbox.setVisible(self.input_type == 'mask_graph')
        layout.addWidget(self.input_masks_graphs_groupbox)

        # Input images & matrices
        self.input_images_matrices_groupbox = QGroupBox('Input files (images and registration matrices)')
        layout2 = QVBoxLayout()
        layout2.addWidget(self.image_matrix_table)
        self.input_images_matrices_groupbox.setLayout(layout2)
        self.input_images_matrices_groupbox.setVisible(self.input_type == 'image_matrix')
        layout.addWidget(self.input_images_matrices_groupbox)

        # Input masks & matrices
        self.input_masks_matrices_groupbox = QGroupBox('Input files (masks and registration matrices)')
        layout2 = QVBoxLayout()
        layout2.addWidget(self.mask_matrix_table)
        self.input_masks_matrices_groupbox.setLayout(layout2)
        self.input_masks_matrices_groupbox.setVisible(self.input_type == 'mask_matrix')
        layout.addWidget(self.input_masks_matrices_groupbox)

        # Output folders
        groupbox = QGroupBox('Output')
        layout2 = QVBoxLayout()
        layout2.addWidget(QLabel("Folder:"))
        layout2.addWidget(self.use_input_folder)
        layout2.addWidget(self.use_custom_folder)
        layout2.addWidget(self.output_folder)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        # Multi-processing
        groupbox = QGroupBox("Multi-processing")
        layout2 = QVBoxLayout()
        layout2.addWidget(self.use_gpu)
        layout3 = QFormLayout()
        layout3.addRow('Number of processes (CPU):', self.nprocesses)
        layout2.addLayout(layout3)
        layout2.addWidget(self.coarse_grain)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

    def set_input_type(self, input_type):
        self.input_type = input_type
        self.input_none_groupbox.setVisible(self.input_type == 'none')
        self.input_images_groupbox.setVisible(self.input_type == 'image')
        self.input_masks_groupbox.setVisible(self.input_type == 'mask')
        self.input_masks_graphs_groupbox.setVisible(self.input_type == 'mask_graph')
        self.input_images_matrices_groupbox.setVisible(self.input_type == 'image_matrix')
        self.input_masks_matrices_groupbox.setVisible(self.input_type == 'mask_matrix')

    def get_widgets_state(self):
        widgets_state = {
            'input_type': self.input_type,
            'use_gpu': self.use_gpu.isChecked(),
            'nprocesses': self.nprocesses.value(),
            'coarse_grain': self.coarse_grain.isChecked(),
            'use_input_folder': self.use_input_folder.isChecked(),
            'use_custom_folder': self.use_custom_folder.isChecked(),
            'output_folder': self.output_folder.text(),
            'image_list': self.image_list.get_file_list() if self.input_type == 'image' else [],
            'mask_list': self.mask_list.get_file_list() if self.input_type == 'mask' else [],
            'mask_graph_table': self.mask_graph_table.get_file_table() if self.input_type == 'mask_graph' else [],
            'image_matrix_table': self.image_matrix_table.get_file_table() if self.input_type == 'image_matrix' else [],
            'mask_matrix_table': self.mask_matrix_table.get_file_table() if self.input_type == 'mask_matrix' else []}
        return widgets_state

    def set_widgets_state(self, widgets_state):
        self.set_input_type(widgets_state['input_type'])
        self.use_gpu.setChecked(widgets_state['use_gpu'])
        self.nprocesses.setValue(widgets_state['nprocesses'])
        self.coarse_grain.setChecked(widgets_state['coarse_grain'])
        self.use_input_folder.setChecked(widgets_state['use_input_folder'])
        self.use_custom_folder.setChecked(widgets_state['use_custom_folder'])
        self.output_folder.setText(widgets_state['output_folder'])
        self.image_list.set_file_list(widgets_state['image_list'])
        self.mask_list.set_file_list(widgets_state['mask_list'])
        self.mask_graph_table.set_file_table(widgets_state['mask_graph_table'])
        self.image_matrix_table.set_file_table(widgets_state['image_matrix_table'])
        self.mask_matrix_table.set_file_table(widgets_state['mask_matrix_table'])


class StatusTableDialog(QDialog):
    """
    a dialog to report job status.

    Examples
    --------
    msg=StatusTableDialog(42,['Registration','Z-Projection','Segmentation'])
    msg.exec_()
    """

    def __init__(self, input_count, module_labels):
        super().__init__()
        self.abort = False
        self.setSizeGripEnabled(True)
        self.setWindowTitle("Status")
        layout = QVBoxLayout()
        self.table = QTableWidget()
        self.table.setColumnCount(len(module_labels))
        self.table.setHorizontalHeaderLabels(module_labels)
        self.table.setRowCount(input_count)
        self.table.setTextElideMode(Qt.ElideLeft)
        self.table.setWordWrap(False)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        for i in range(self.table.rowCount()):
            for j in range(self.table.columnCount()):
                item = QTableWidgetItem()
                item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                item.setBackground(QBrush(QColor("#FFFFFF")))
                self.table.setItem(i, j, item)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.done)
        layout.addWidget(self.ok_button, alignment=Qt.AlignCenter)
        self.abort_button = QPushButton("Abort")
        self.abort_button.clicked.connect(self.abort_clicked)
        layout.addWidget(self.abort_button, alignment=Qt.AlignCenter)
        self.setLayout(layout)

    def abort_clicked(self):
        self.abort = True

    def keyPressEvent(self, event):
        # to disable reject() with escape key
        if event.key() != Qt.Key_Escape:
            super().keyPressEvent(event)
