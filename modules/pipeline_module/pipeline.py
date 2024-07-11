import logging
import os
import sys
import concurrent
import time
from PyQt5.QtWidgets import QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QAbstractItemView, QAction, QListView, QSizePolicy, QGroupBox, QApplication, QFileDialog
from PyQt5.QtCore import Qt, QEvent, QSettings
from PyQt5.QtGui import QKeySequence, QStandardItem, QBrush, QColor, QCursor
from modules.pipeline_module import pipeline_functions as f
from modules.registration_module import registration
from modules.registration_module import registration_functions
from modules.zprojection_module import zprojection
from modules.zprojection_module import zprojection_functions
from modules.segmentation_module import segmentation
from modules.segmentation_module import segmentation_functions
from modules.cell_tracking_module import cell_tracking
from modules.cell_tracking_module import cell_tracking_functions
from modules.graph_filtering_module import graph_filtering
from modules.graph_filtering_module import graph_filtering_functions
from general import general_functions as gf
from version import __version__ as vlabapp_version


def process_initializer():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s (%(name)s) [%(levelname)s] %(message)s", handlers=[logging.StreamHandler(sys.stdout)], force=True)


class Pipeline(QWidget):
    def __init__(self):
        super().__init__()

        label_documentation = QLabel()
        label_documentation.setOpenExternalLinks(True)
        label_documentation.setWordWrap(True)
        label_documentation.setText('Drag and drop modules in the list to create a pipeline.')

        self.pipeline_modules_list = f.ListView(placeholder_text='Drop modules here')
        self.pipeline_modules_list.setModel(f.StandardItemModel(0, 1))
        self.pipeline_modules_list.setDragEnabled(True)
        self.pipeline_modules_list.setDefaultDropAction(Qt.MoveAction)
        self.pipeline_modules_list.setDragDropMode(QAbstractItemView.DragDrop)
        self.pipeline_modules_list.setFlow(QListView.LeftToRight)
        self.pipeline_modules_list.setHorizontalScrollMode(QListView.ScrollPerPixel)
        self.pipeline_modules_list.setWordWrap(True)
        self.pipeline_modules_list.setItemDelegate(f.ItemDelegate(numbered=True, draw_links=True))
        self.pipeline_modules_list.setSizePolicy(QSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Preferred))
        self.pipeline_modules_list.selectionModel().selectionChanged.connect(self.pipeline_modules_selection_changed)
        self.pipeline_modules_list.model().rowsRemoved.connect(self.update_settings_widget_input_types)

        action_delete = QAction('Delete', self.pipeline_modules_list)
        action_delete.setShortcut(QKeySequence.Delete)
        action_delete.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        action_delete.triggered.connect(self.pipeline_modules_list.delete_selection)
        self.pipeline_modules_list.addAction(action_delete)
        self.pipeline_modules_list.setContextMenuPolicy(Qt.ActionsContextMenu)

        self.show_available_modules_button = QPushButton('+')
        self.show_available_modules_button.setStyleSheet('padding-left: 5px; padding-right: 5px;padding-top: 0px; padding-bottom: 0px;')
        self.show_available_modules_button.setToolTip('Add modules')
        self.show_available_modules_button.setCheckable(True)

        self.remove_module_button = QPushButton('-')
        self.remove_module_button.setToolTip('Remove selected module')
        self.remove_module_button.setStyleSheet('padding-left: 5px; padding-right: 5px;padding-top: 0px; padding-bottom: 0px;')
        self.remove_module_button.clicked.connect(self.pipeline_modules_list.delete_selection)

        self.load_settings_button = QPushButton('Load settings...')
        self.load_settings_button.clicked.connect(self.load_settings)

        self.save_settings_button = QPushButton('Save settings...')
        self.save_settings_button.clicked.connect(self.save_settings)

        self.available_modules_list = f.ListView()
        self.available_modules_list.setModel(f.StandardItemModel(0, 1))
        self.available_modules_list.setDragEnabled(True)
        self.available_modules_list.setDefaultDropAction(Qt.IgnoreAction)
        self.available_modules_list.setDragDropMode(QAbstractItemView.DragOnly)
        self.available_modules_list.setFlow(QListView.LeftToRight)
        self.available_modules_list.setHorizontalScrollMode(QListView.ScrollPerPixel)
        self.available_modules_list.setWordWrap(True)
        self.available_modules_list.setItemDelegate(f.ItemDelegate(numbered=False, draw_links=False))
        self.available_modules_list.hide()
        # Prevent immediate reopening when clicking on self.show_available_modules_button
        self.disable_show_available_modules_button = False

        self.submit_button = QPushButton('Submit')
        self.submit_button.clicked.connect(self.submit)

        # Layout
        layout = QVBoxLayout()
        groupbox = QGroupBox('Documentation')
        layout2 = QVBoxLayout()
        layout2.addWidget(label_documentation)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        groupbox = QGroupBox('Modules')
        layout2 = QVBoxLayout()
        layout2.addWidget(self.pipeline_modules_list)
        layout3 = QHBoxLayout()
        layout3.addWidget(self.show_available_modules_button, alignment=Qt.AlignCenter)
        layout3.addWidget(self.remove_module_button, alignment=Qt.AlignCenter)
        layout3.addStretch()
        layout3.addWidget(self.load_settings_button, alignment=Qt.AlignCenter)
        layout3.addWidget(self.save_settings_button, alignment=Qt.AlignCenter)
        layout2.addLayout(layout3)
        layout2.addWidget(self.available_modules_list)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        self.module_settings_groupbox = QGroupBox('Selected module settings')
        layout2 = QVBoxLayout()
        layout2.setContentsMargins(0, 0, 0, 0)
        self.module_settings_groupbox.setLayout(layout2)
        self.module_settings_groupbox.hide()
        self.module_settings_widgets = {}
        self.module_settings_widgets['general_settings'] = f.GeneralSettings()
        self.module_settings_widgets['registration_image'] = registration.Perform(pipeline_layout=True)
        self.module_settings_widgets['registration_alignment_image'] = registration.Align(pipeline_layout=True)
        self.module_settings_widgets['registration_alignment_mask'] = registration.Align(pipeline_layout=True)
        self.module_settings_widgets['zprojection'] = zprojection.zProjection(pipeline_layout=True)
        self.module_settings_widgets['segmentation'] = segmentation.Segmentation(pipeline_layout=True)
        self.module_settings_widgets['cell_tracking'] = cell_tracking.CellTracking(pipeline_layout=True)
        self.module_settings_widgets['graph_filtering'] = graph_filtering.GraphFiltering(pipeline_layout=True)
        for m in self.module_settings_widgets:
            self.module_settings_widgets[m].hide()
            layout2.addWidget(self.module_settings_widgets[m])
        layout.addWidget(self.module_settings_groupbox)

        # quick and dirty hack to disable co-alignment (not yet implemented)
        self.module_settings_widgets['registration_image'].coalignment_yn.setChecked(False)
        self.module_settings_widgets['registration_image'].coalignment_yn.setEnabled(False)

        layout.addWidget(self.submit_button, alignment=Qt.AlignCenter)
        self.setLayout(layout)

        # populate pipeline_modules_list
        item = QStandardItem('Settings')
        description = 'General pipeline settings (input, output, ...)'
        item.setEditable(False)
        item.setData({'name': 'general_settings', 'description': description, 'is_removable': False, 'input_types': [], 'output_types': ['image', 'mask', 'graph', 'matrix']}, Qt.UserRole+1)
        item.setToolTip(description)
        self.pipeline_modules_list.model().appendRow(item)
        self.store_settings_data(item.index())

        # populate available_modules_list
        item = QStandardItem('Registration')
        description = 'Input: image\nOutput: registered image and registration matrix'
        item.setEditable(False)
        item.setData({'name': 'registration_image', 'description': description, 'input_types': ['image'], 'output_types': ['image', 'matrix'], 'conflicting_modules': ['registration_image','registration_alignment_image', 'registration_alignment_mask']}, Qt.UserRole+1)
        item.setToolTip(description)
        self.available_modules_list.model().appendRow(item)
        self.store_settings_data(item.index())
        item = QStandardItem('Registration (alignment)')
        description = 'Input: image and registration matrix\nOutput: registered image'
        item.setEditable(False)
        item.setData({'name': 'registration_alignment_image', 'description': description, 'input_types': ['image', 'matrix'], 'output_types': ['image'], 'conflicting_modules': ['registration_image','registration_alignment_image', 'registration_alignment_mask']}, Qt.UserRole+1)
        item.setToolTip(description)
        self.available_modules_list.model().appendRow(item)
        self.store_settings_data(item.index())
        item = QStandardItem('Registration (alignment)')
        description = 'Input: mask and registration matrix\nOutput: registered mask'
        item.setEditable(False)
        item.setData({'name': 'registration_alignment_mask', 'description': description, 'input_types': ['mask', 'matrix'], 'output_types': ['mask'], 'conflicting_modules': ['registration_image','registration_alignment_image', 'registration_alignment_mask']}, Qt.UserRole+1)
        item.setToolTip(description)
        self.available_modules_list.model().appendRow(item)
        self.store_settings_data(item.index())
        item = QStandardItem('Z-Projection')
        description = 'Input: image\nOutput: projected image'
        item.setEditable(False)
        item.setData({'name': 'zprojection', 'description': description, 'input_types': ['image'], 'output_types': ['image']}, Qt.UserRole+1)
        item.setToolTip(description)
        self.available_modules_list.model().appendRow(item)
        self.store_settings_data(item.index())
        item = QStandardItem('Segmentation')
        description = 'Input: image\nOutput: segmentation mask'
        item.setEditable(False)
        item.setData({'name': 'segmentation', 'description': description, 'input_types': ['image'], 'output_types': ['mask']}, Qt.UserRole+1)
        item.setToolTip(description)
        self.available_modules_list.model().appendRow(item)
        self.store_settings_data(item.index())
        item = QStandardItem('Cell tracking')
        description = 'Input: segmentation mask\nOutput: relabelled segmentation mask and cell tracking graph'
        item.setEditable(False)
        item.setData({'name': 'cell_tracking', 'description': description, 'input_types': ['mask'], 'output_types': ['mask', 'graph']}, Qt.UserRole+1)
        item.setToolTip(description)
        self.available_modules_list.model().appendRow(item)
        self.store_settings_data(item.index())
        item = QStandardItem('Graph filtering')
        description = 'Input: segmentation mask and cell tracking graph\nOutput: filtered segmentation mask and cell tracking graph'
        item.setEditable(False)
        item.setData({'name': 'graph_filtering', 'description': description, 'input_types': ['mask', 'graph'], 'output_types': ['mask', 'graph']}, Qt.UserRole+1)
        item.setToolTip(description)
        self.available_modules_list.model().appendRow(item)
        self.store_settings_data(item.index())

        self.show_available_modules_button.installEventFilter(self)
        self.available_modules_list.installEventFilter(self)

        self.logger = logging.getLogger(__name__)

    def eventFilter(self, target, event):
        if target == self.available_modules_list and event.type() == QEvent.FocusOut:
            # Prevent immediate reopening when clicking on self.show_available_modules_button
            self.startTimer(100)
            self.disable_show_available_modules_button = True
            self.available_modules_list.hide()
            self.show_available_modules_button.setChecked(False)
            return True
        if target == self.show_available_modules_button and event.type() == QEvent.MouseButtonPress:
            # Prevent immediate reopening when clicking on self.show_available_modules_button
            if self.disable_show_available_modules_button:
                return True
            if target.isChecked():
                target.setChecked(False)
            else:
                target.setChecked(True)
                self.available_modules_list.show()
                self.available_modules_list.setFocus()
            return True
        return False

    def timerEvent(self, event):
        # After timeout, kill timer, and reenable showing self.available_modules_list when clicking on self.show_available_modules_button
        self.killTimer(event.timerId())
        self.disable_show_available_modules_button = False

    def pipeline_modules_selection_changed(self, selected, deselected):
        if deselected.count() > 0:
            # at most one item can be selected: QAbstractItemView.SingleSelection
            module_name = deselected.indexes()[0].data(Qt.UserRole+1)['name']
            self.store_settings_data(deselected.indexes()[0])
            self.module_settings_widgets[module_name].hide()
            self.module_settings_groupbox.hide()

        if selected.count() > 0:
            # at most one item can be selected: QAbstractItemView.SingleSelection
            module_name = selected.indexes()[0].data(Qt.UserRole+1)['name']
            if module_name == 'general_settings':
                self.update_settings_widget_input_types()
            self.restore_settings_data(selected.indexes()[0])
            self.module_settings_widgets[module_name].show()
            self.module_settings_groupbox.show()

    def restore_settings_data(self, model_index):
        '''
        Update `self.module_settings_widget` with data stored in item with index `model_index`.
        '''
        # at most one item can be selected: QAbstractItemView.SingleSelection
        module_name = model_index.data(Qt.UserRole+1)['name']
        data = model_index.data(Qt.UserRole+1)
        module_widget = self.module_settings_widgets[module_name]
        if 'settings' in data:
            module_widget.set_widgets_state(data['settings'])

    def store_settings_data(self, model_index):
        '''
        Update the item with index `model_index` using data from `self.module_settings_widget`.
        '''
        module_name = model_index.data(Qt.UserRole+1)['name']
        data = model_index.data(Qt.UserRole+1)
        module_widget = self.module_settings_widgets[module_name]
        # modify data
        data['settings'] = module_widget.get_widgets_state()
        model_index.model().setData(model_index, data, Qt.UserRole+1)

    def update_settings_widget_input_types(self):
        # assuming Settings in first position in the list
        module_name = 'general_settings'
        next_index = self.pipeline_modules_list.model().index(1, 0)
        next_item_data = self.pipeline_modules_list.model().data(next_index, Qt.UserRole+1)
        if not next_index.isValid():
            self.module_settings_widgets[module_name].set_input_type('none')
        elif set(next_item_data['input_types']) == {'image'}:
            self.module_settings_widgets[module_name].set_input_type('image')
        elif set(next_item_data['input_types']) == {'mask'}:
            self.module_settings_widgets[module_name].set_input_type('mask')
        elif set(next_item_data['input_types']) == {'mask', 'graph'}:
            self.module_settings_widgets[module_name].set_input_type('mask_graph')
        elif set(next_item_data['input_types']) == {'image', 'matrix'}:
            self.module_settings_widgets[module_name].set_input_type('image_matrix')
        elif set(next_item_data['input_types']) == {'mask', 'matrix'}:
            self.module_settings_widgets[module_name].set_input_type('mask_matrix')
        # update model
        self.store_settings_data(self.pipeline_modules_list.model().index(0, 0))

    def save_settings(self):
        '''
        Save pipeline settings to file.
        '''
        if len(self.pipeline_modules_list.selectionModel().selectedRows()) == 1:
            # update data for currently selected module
            self.store_settings_data(self.pipeline_modules_list.selectionModel().selectedRows()[0])
            # update settings widget
            self.update_settings_widget_input_types()

        file_path, _ = QFileDialog.getSaveFileName(self, 'Save pipeline settings', 'pipeline_settings.ini', 'ini file (*.ini)')
        if file_path != '':
            settings = QSettings(file_path, QSettings.IniFormat)
            settings.clear()
            settings.setValue('version', vlabapp_version)
            settings.setValue('module_count', self.pipeline_modules_list.model().rowCount())

            for module_idx in range(self.pipeline_modules_list.model().rowCount()):
                item = self.pipeline_modules_list.model().item(module_idx)
                settings.beginGroup('module_'+str(module_idx))
                settings.setValue('module_label', item.data(Qt.DisplayRole))
                settings.setValue('data', item.data(Qt.UserRole+1))
                settings.endGroup()

    def load_settings(self):
        '''
        Load pipeline settings from file.
        '''
        file_path, _ = QFileDialog.getOpenFileName(self, 'Load pipeline settings', filter='ini file (*.ini)')
        if file_path != '' and os.path.exists(file_path):
            settings = QSettings(file_path, QSettings.IniFormat)
            version = settings.value('version')
            # TODO: check version compatibility
            module_count = settings.value('module_count', type=int)

            # remove all modules from self.pipeline_modules_list
            self.pipeline_modules_list.model().clear()

            # hide all module settings widgets
            for module_name in self.module_settings_widgets:
                self.module_settings_widgets[module_name].hide()
            self.module_settings_groupbox.hide()

            for module_idx in range(module_count):
                settings.beginGroup('module_'+str(module_idx))
                item = QStandardItem(settings.value('module_label', type=str))
                item.setEditable(False)
                item.setData(settings.value('data'), Qt.UserRole+1)
                item.setToolTip(item.data(Qt.UserRole+1)['description'])
                self.pipeline_modules_list.model().appendRow(item)
                self.restore_settings_data(item.index())
                settings.endGroup()

    def submit(self):
        if len(self.pipeline_modules_list.selectionModel().selectedRows()) == 1:
            # update data for currently selected module
            self.store_settings_data(self.pipeline_modules_list.selectionModel().selectedRows()[0])
            # update settings widget
            self.update_settings_widget_input_types()

        # Settings (it is always the first module)
        item = self.pipeline_modules_list.model().item(0)
        module_name = item.data(Qt.UserRole+1)['name']
        module_widget = self.module_settings_widgets[module_name]
        settings = item.data(Qt.UserRole+1)['settings']

        use_gpu = settings['use_gpu']
        nprocesses = settings['nprocesses']

        input_image_paths = None
        input_mask_paths = None
        input_graph_paths = None
        input_matrix_paths = None
        input_count = 0
        if settings['input_type'] == 'image':
            input_image_paths = settings['image_list']
            input_count = len(input_image_paths)
            if settings['use_input_folder']:
                output_paths = [os.path.dirname(path) for path in input_image_paths]
            else:
                output_paths = [settings['output_folder'] for path in input_image_paths]
            # check input
            for path in input_image_paths:
                if not os.path.isfile(path):
                    self.logger.error('File not found: %s (module "Settings")', path)
                    return
        elif settings['input_type'] == 'mask':
            input_mask_paths = settings['mask_list']
            input_count = len(input_mask_paths)
            if settings['use_input_folder']:
                output_paths = [os.path.dirname(path) for path in input_mask_paths]
            else:
                output_paths = [settings['output_folder'] for path in input_mask_paths]
            # check input
            for path in input_mask_paths:
                if not os.path.isfile(path):
                    self.logger.error('File not found: %s (module "Settings")', path)
                    return
        elif settings['input_type'] == 'mask_graph':
            input_mask_graph_paths = settings['mask_graph_table']
            input_mask_paths = [mask_path for mask_path, graph_path in input_mask_graph_paths]
            input_graph_paths = [graph_path for mask_path, graph_path in input_mask_graph_paths]
            input_count = len(input_mask_paths)
            if settings['use_input_folder']:
                output_paths = [os.path.dirname(path) for path in input_mask_paths]
            else:
                output_paths = [settings['output_folder'] for path in input_mask_paths]
            # check input exists
            for path in input_mask_paths:
                if not os.path.isfile(path):
                    self.logger.error('File not found: %s (module "Settings")', path)
                    return
            # check input
            for path in input_graph_paths:
                if not os.path.isfile(path):
                    self.logger.error('File not found: %s (module "Settings")', path)
                    return
        elif settings['input_type'] == 'image_matrix':
            input_image_matrix_paths = settings['image_matrix_table']
            input_image_paths = [image_path for image_path, matrix_path in input_image_matrix_paths]
            input_matrix_paths = [matrix_path for image_path, matrix_path in input_image_matrix_paths]
            input_count = len(input_image_paths)
            if settings['use_input_folder']:
                output_paths = [os.path.dirname(path) for path in input_image_paths]
            else:
                output_paths = [settings['output_folder'] for path in input_image_paths]
            # check input exists
            for path in input_image_paths:
                if not os.path.isfile(path):
                    self.logger.error('File not found: %s (module "Settings")', path)
                    return
            # check input
            for path in input_matrix_paths:
                if not os.path.isfile(path):
                    self.logger.error('File not found: %s (module "Settings")', path)
                    return
        elif settings['input_type'] == 'mask_matrix':
            input_mask_matrix_paths = settings['mask_matrix_table']
            input_mask_paths = [mask_path for mask_path, matrix_path in input_mask_matrix_paths]
            input_matrix_paths = [matrix_path for mask_path, matrix_path in input_mask_matrix_paths]
            input_count = len(input_mask_paths)
            if settings['use_input_folder']:
                output_paths = [os.path.dirname(path) for path in input_mask_paths]
            else:
                output_paths = [settings['output_folder'] for path in input_mask_paths]
            # check input exists
            for path in input_mask_paths:
                if not os.path.isfile(path):
                    self.logger.error('File not found: %s (module "Settings")', path)
                    return
            # check input
            for path in input_matrix_paths:
                if not os.path.isfile(path):
                    self.logger.error('File not found: %s (module "Settings")', path)
                    return

        # check input
        if self.pipeline_modules_list.model().rowCount() < 2:
            self.logger.error('No module except "Settings".')
            return
        if not settings['use_input_folder'] and settings['output_folder'] == '':
            self.logger.error('Output folder missing (module "Settings")')
            return
        if input_count == 0:
            self.logger.error('Input files missing (module "Settings")')
            return
        if settings['input_type'] in ['image', 'image_matrix']:
            output_files = [os.path.join(d, f) for d, f in zip(output_paths, [gf.splitext(os.path.basename(path))[0] for path in input_image_paths])]
            duplicates = [x for x, y in zip(input_image_paths, output_files) if output_files.count(y) > 1]
            if len(duplicates) > 0:
                self.logger.error('More than one input file will output to the same file (output files will be overwritten).\nEither use input file folder as output folder or avoid processing files from different input folders.\nProblematic input files:\n%s', '\n'.join(duplicates[:4] + (['...'] if len(duplicates) > 4 else [])))
                return
        elif settings['input_type'] in ['mask', 'mask_graph', 'mask_matrix']:
            output_files = [os.path.join(d, f) for d, f in zip(output_paths, [gf.splitext(os.path.basename(path))[0] for path in input_mask_paths])]
            duplicates = [x for x, y in zip(input_mask_paths, output_files) if output_files.count(y) > 1]
            if len(duplicates) > 0:
                self.logger.error('More than one input file will output to the same file (output files will be overwritten).\nEither use input file folder as output folder or avoid processing files from different input folders.\nProblematic input files:\n%s', '\n'.join(duplicates[:4] + (['...'] if len(duplicates) > 4 else [])))
                return
        # check input images/masks axes
        first_module_name = self.pipeline_modules_list.model().item(1).data(Qt.UserRole+1)['name']
        if first_module_name in ['registration_image', 'registration_alignment_image']:
            for path in input_image_paths:
                try:
                    image = gf.Image(path)
                except Exception:
                    self.logger.exception('Error loading image:\n %s\n\nError message:', path)
                    return
                if not (image.sizes['F'] == 1 and image.sizes['T'] > 1 and image.sizes['Y'] > 1 and image.sizes['X'] > 1):
                    self.logger.error('Invalid image:\n %s\n\nImage must have X, Y and T axes and can optionally have Z or C axes.', path)
                    return
        if first_module_name == 'registration_alignment_mask':
            for path in input_mask_paths:
                try:
                    mask = gf.Image(path)
                except Exception:
                    self.logger.exception('Error loading mask:\n %s\n\nError message:', path)
                    return
                if not (mask.sizes['F'] == 1 and mask.sizes['C'] == 1 and mask.sizes['T'] > 1 and mask.sizes['Y'] > 1 and mask.sizes['X'] > 1):
                    self.logger.error('Invalid mask:\n %s\n\nMask must have X, Y and T axes and can optionally have Z axis.', path)
                    return
        if first_module_name == 'zprojection':
            for path in input_image_paths:
                try:
                    image = gf.Image(path)
                except Exception:
                    self.logger.exception('Error loading image:\n %s\n\nError message:', path)
                    return
                if not (image.sizes['F'] == 1 and image.sizes['Y'] > 1 and image.sizes['X'] > 1):
                    # although it does not make sense to z-project an image without z axis, the module does not crash if it is the case.
                    self.logger.error('Invalid image:\n %s\n\nImage must have X, Y axes and can optionally have T, C or Z axes.', path)
                    return
        if first_module_name == 'segmentation':
            for path in input_image_paths:
                try:
                    image = gf.Image(path)
                except Exception:
                    self.logger.exception('Error loading image:\n %s\n\nError message:', path)
                    return
                if not (image.sizes['F'] == 1 and image.sizes['Y'] > 1 and image.sizes['X'] > 1):
                    self.logger.error('Invalid image:\n %s\n\nImage must have X and Y axes and can optionally have T, C or Z axes.', path)
                    return
        if first_module_name in ['cell_tracking', 'graph_filtering']:
            for path in input_mask_paths:
                try:
                    mask = gf.Image(path)
                except Exception:
                    self.logger.exception('Error loading mask:\n %s\n\nError message:', path)
                    return
                if not (mask.sizes['F'] == 1 and mask.sizes['T'] > 1 and mask.sizes['C'] == 1 and mask.sizes['Z'] == 1 and mask.sizes['Y'] > 1 and mask.sizes['X'] > 1):
                    self.logger.error('Invalid mask:\n %s\n\nMask must have X, Y and T axes.', path)
                    return

        jobs = []
        for input_idx in range(input_count):
            next_image_path = input_image_paths[input_idx] if input_image_paths else None
            next_mask_path = input_mask_paths[input_idx] if input_mask_paths else None
            next_graph_path = input_graph_paths[input_idx] if input_graph_paths else None
            next_matrix_path = input_matrix_paths[input_idx] if input_matrix_paths else None
            output_path = output_paths[input_idx]
            last_job_with_same_input_idx = None
            for module_idx in range(1, self.pipeline_modules_list.model().rowCount()):
                item = self.pipeline_modules_list.model().item(module_idx)
                module_label = item.data(Qt.DisplayRole)
                module_name = item.data(Qt.UserRole+1)['name']
                module_widget = self.module_settings_widgets[module_name]
                settings = item.data(Qt.UserRole+1)['settings']
                if module_name == 'registration_image':
                    image_path = next_image_path
                    output_suffix = gf.output_suffixes['registration']
                    user_suffix = settings['output_user_suffix']
                    output_basename = gf.splitext(os.path.basename(image_path))[0] + output_suffix + user_suffix
                    channel_position = int(settings['channel_position'] if settings['channel_position'] != '' else '0')
                    projection_type = settings['projection_type']
                    if settings['projection_mode_bestZ']:
                        projection_zrange = 0
                    elif settings['projection_mode_around_bestZ']:
                        projection_zrange = settings['projection_mode_around_bestZ_zrange']
                    elif settings['projection_mode_fixed']:
                        projection_zrange = (settings['projection_mode_fixed_zmin'], settings['projection_mode_fixed_zmax'])
                    elif settings['projection_mode_all']:
                        projection_zrange = None
                    if settings['time_mode_fixed']:
                        timepoint_range = (settings['time_mode_fixed_tmin'], settings['time_mode_fixed_tmax'])
                    else:
                        timepoint_range = None
                    skip_crop_decision = settings['skip_cropping_yn']
                    registration_method = settings['registration_method']
                    jobs.append({'function': registration_functions.registration_main,
                                 'arguments': (image_path,
                                               output_path,
                                               output_basename,
                                               channel_position,
                                               projection_type,
                                               projection_zrange,
                                               timepoint_range,
                                               skip_crop_decision,
                                               registration_method),
                                 'depends': [last_job_with_same_input_idx] if last_job_with_same_input_idx is not None else [],
                                 'module_label': module_label,
                                 'module_idx': module_idx,
                                 'input_idx': input_idx,
                                 'use_gpu': False})
                    # to be used by next module
                    next_image_path = os.path.join(output_path, output_basename+'.ome.tif')
                    next_mask_path = None
                    next_graph_path = None
                    next_matrix_path = os.path.join(output_path, output_basename+'.csv')
                    last_job_with_same_input_idx = len(jobs) - 1
                    # TODO: deal with coalignment
                if module_name == 'registration_alignment_image':
                    image_path = next_image_path
                    matrix_path = next_matrix_path
                    output_suffix = gf.output_suffixes['registration']
                    user_suffix = settings['output_user_suffix']
                    output_basename = gf.splitext(os.path.basename(image_path))[0] + output_suffix + user_suffix
                    skip_crop_decision = settings['skip_cropping_yn']
                    jobs.append({'function': registration_functions.alignment_main,
                                 'arguments': (image_path,
                                               matrix_path,
                                               output_path,
                                               output_basename,
                                               skip_crop_decision),
                                 'depends': [last_job_with_same_input_idx] if last_job_with_same_input_idx is not None else [],
                                 'module_label': module_label,
                                 'module_idx': module_idx,
                                 'input_idx': input_idx,
                                 'use_gpu': False})
                    # to be used by next module
                    next_image_path = os.path.join(output_path, output_basename+'.ome.tif')
                    next_mask_path = None
                    next_graph_path = None
                    next_matrix_path = None
                    last_job_with_same_input_idx = len(jobs) - 1
                if module_name == 'registration_alignment_mask':
                    mask_path = next_mask_path
                    matrix_path = next_matrix_path
                    output_suffix = gf.output_suffixes['registration']
                    user_suffix = settings['output_user_suffix']
                    output_basename = gf.splitext(os.path.basename(mask_path))[0] + output_suffix + user_suffix
                    skip_crop_decision = settings['skip_cropping_yn']
                    jobs.append({'function': registration_functions.alignment_main,
                                 'arguments': (mask_path,
                                               matrix_path,
                                               output_path,
                                               output_basename,
                                               skip_crop_decision),
                                 'depends': [last_job_with_same_input_idx] if last_job_with_same_input_idx is not None else [],
                                 'module_label': module_label,
                                 'module_idx': module_idx,
                                 'input_idx': input_idx,
                                 'use_gpu': False})
                    # to be used by next module
                    next_image_path = None
                    next_mask_path = os.path.join(output_path, output_basename+'.ome.tif')
                    next_graph_path = None
                    next_matrix_path = None
                    last_job_with_same_input_idx = len(jobs) - 1
                elif module_name == 'zprojection':
                    image_path = next_image_path
                    output_suffix = gf.output_suffixes['zprojection']
                    projection_type = settings['projection_type']
                    if settings['projection_mode_bestZ']:
                        projection_zrange = 0
                    elif settings['projection_mode_around_bestZ']:
                        projection_zrange = settings['projection_mode_around_bestZ_zrange']
                    elif settings['projection_mode_fixed']:
                        projection_zrange = (settings['projection_mode_fixed_zmin'], settings['projection_mode_fixed_zmax'])
                    elif settings['projection_mode_all']:
                        projection_zrange = None
                    output_basename = gf.splitext(os.path.basename(image_path))[0] + output_suffix + module_widget.get_projection_suffix(image_path, projection_zrange, projection_type)
                    jobs.append({'function': zprojection_functions.main,
                                 'arguments': (image_path,
                                               output_path,
                                               output_basename,
                                               projection_type,
                                               projection_zrange),
                                 'depends': [last_job_with_same_input_idx] if last_job_with_same_input_idx is not None else [],
                                 'module_label': module_label,
                                 'module_idx': module_idx,
                                 'input_idx': input_idx,
                                 'use_gpu': False})
                    # to be used by next module
                    next_image_path = os.path.join(output_path, output_basename+'.ome.tif')
                    next_mask_path = None
                    next_graph_path = None
                    next_matrix_path = None
                    last_job_with_same_input_idx = len(jobs) - 1
                elif module_name == 'segmentation':
                    image_path = next_image_path
                    model_path = settings['selected_model']
                    output_suffix = gf.output_suffixes['segmentation']
                    user_suffix = settings['output_user_suffix']
                    output_basename = gf.splitext(os.path.basename(image_path))[0] + output_suffix + user_suffix
                    channel_position = int(settings['channel_position'] if settings['channel_position'] != '' else '0')
                    projection_type = settings['projection_type']
                    if settings['projection_mode_bestZ']:
                        projection_zrange = 0
                    elif settings['projection_mode_around_bestZ']:
                        projection_zrange = settings['projection_mode_around_bestZ_zrange']
                    elif settings['projection_mode_fixed']:
                        projection_zrange = (settings['projection_mode_fixed_zmin'], settings['projection_mode_fixed_zmax'])
                    elif settings['projection_mode_all']:
                        projection_zrange = None
                    n_count = 1
                    run_parallel = False
                    display_results = False
                    # check input
                    if model_path == '':
                        self.logger.error('Model missing (module "%s")', module_label)
                        return
                    if not os.path.isfile(model_path):
                        self.logger.error('Model not found: %s (module "%s")', model_path, module_label)
                        return
                    jobs.append({'function': segmentation_functions.main,
                                 'arguments': (image_path,
                                               model_path,
                                               output_path,
                                               output_basename,
                                               channel_position,
                                               projection_type,
                                               projection_zrange,
                                               n_count,
                                               display_results,
                                               use_gpu,
                                               run_parallel),
                                 'depends': [last_job_with_same_input_idx] if last_job_with_same_input_idx is not None else [],
                                 'module_label': module_label,
                                 'module_idx': module_idx,
                                 'input_idx': input_idx,
                                 'use_gpu': use_gpu})
                    # to be used by next module
                    next_image_path = None
                    next_mask_path = os.path.join(output_path, output_basename+'.ome.tif')
                    next_graph_path = None
                    next_matrix_path = None
                    last_job_with_same_input_idx = len(jobs) - 1
                elif module_name == 'cell_tracking':
                    image_path = ''
                    mask_path = next_mask_path
                    output_suffix = gf.output_suffixes['cell_tracking']
                    user_suffix = settings['output_user_suffix']
                    output_basename = gf.splitext(os.path.basename(mask_path))[0] + output_suffix + user_suffix
                    min_area = settings['min_area']
                    max_delta_frame = settings['max_delta_frame']
                    min_overlap_fraction = settings['min_overlap_fraction']/100.0
                    clean = settings['auto_clean']
                    max_delta_frame_interpolation = settings['max_delta_frame_interpolation']
                    nframes_defect = settings['nframes_defect']
                    nframes_stable = settings['nframes_stable']
                    stable_overlap_fraction = settings['stable_overlap_fraction']/100.0
                    display_results = False
                    jobs.append({'function': cell_tracking_functions.main,
                                 'arguments': (image_path,
                                               mask_path,
                                               output_path,
                                               output_basename,
                                               min_area,
                                               max_delta_frame,
                                               min_overlap_fraction,
                                               clean,
                                               max_delta_frame_interpolation,
                                               nframes_defect,
                                               nframes_stable,
                                               stable_overlap_fraction,
                                               display_results),
                                 'depends': [last_job_with_same_input_idx] if last_job_with_same_input_idx is not None else [],
                                 'module_label': module_label,
                                 'module_idx': module_idx,
                                 'input_idx': input_idx,
                                 'use_gpu': False})
                    # to be used by next module
                    next_image_path = None
                    next_mask_path = os.path.join(output_path, output_basename+'.ome.tif')
                    next_graph_path = os.path.join(output_path, output_basename+'.graphmlz')
                    next_matrix_path = None
                    last_job_with_same_input_idx = len(jobs) - 1
                elif module_name == 'graph_filtering':
                    image_path = ''
                    mask_path = next_mask_path
                    graph_path = next_graph_path
                    output_suffix = gf.output_suffixes['graph_filtering']
                    user_suffix = settings['output_user_suffix']
                    output_basename = gf.splitext(os.path.basename(mask_path))[0] + output_suffix + user_suffix
                    display_results = False
                    filters = []
                    graph_topologies = None
                    if settings['filter_border_yn']:
                        filters.append(('filter_border', settings['border_width']))
                    if settings['filter_all_cells_area_yn']:
                        filters.append(('filter_all_cells_area', settings['all_cells_min_area'], settings['all_cells_max_area']))
                    if settings['filter_one_cell_area_yn']:
                        filters.append(('filter_one_cell_area', settings['one_cell_min_area'], settings['one_cell_max_area']))
                    if settings['filter_track_length_yn']:
                        filters.append(('filter_track_length', settings['nframes']))
                    if settings['filter_n_missing_yn']:
                        filters.append(('filter_n_missing', settings['nmissing']))
                    if settings['filter_n_divisions_yn']:
                        stable_overlap_fraction = 0
                        filters.append(('filter_n_divisions', settings['min_ndivisions'], settings['max_ndivisions'], settings['nframes_stable_division'], stable_overlap_fraction))
                    if settings['filter_n_fusions_yn']:
                        stable_overlap_fraction = 0
                        filters.append(('filter_n_fusions', settings['min_nfusions'], settings['max_nfusions'], settings['nframes_stable_fusion'], stable_overlap_fraction))
                    if settings['filter_topology_yn']:
                        graph_topologies = module_widget.graph_topologies
                        topology_ids = [i for i, checked in enumerate(settings['topologies']) if checked]
                        filters.append(('filter_topology', topology_ids))
                    jobs.append({'function': graph_filtering_functions.main,
                                 'arguments': (image_path,
                                               mask_path,
                                               graph_path,
                                               output_path,
                                               output_basename,
                                               filters,
                                               display_results,
                                               graph_topologies),
                                 'depends': [last_job_with_same_input_idx] if last_job_with_same_input_idx is not None else [],
                                 'module_label': module_label,
                                 'module_idx': module_idx,
                                 'input_idx': input_idx,
                                 'use_gpu': False})
                    # to be used by next module
                    next_image_path = None
                    next_mask_path = os.path.join(output_path, output_basename+'.ome.tif')
                    next_graph_path = os.path.join(output_path, output_basename+'.graphmlz')
                    next_matrix_path = None
                    last_job_with_same_input_idx = len(jobs) - 1

        status_dialog = f.StatusTableDialog(input_count,
                                            [self.pipeline_modules_list.model().item(i).data(Qt.DisplayRole) for i in range(1, self.pipeline_modules_list.model().rowCount())])
        status_dialog.ok_button.hide()
        status_dialog.abort_button.show()
        status_dialog.setModal(True)
        status_dialog.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.CustomizeWindowHint)
        status_dialog.show()
        QApplication.processEvents()
        time.sleep(0.05)

        # disable messagebox error handler
        messagebox_error_handler = None
        for h in logging.getLogger().handlers:
            if h.get_name() == 'messagebox_error_handler':
                messagebox_error_handler = h
                logging.getLogger().removeHandler(messagebox_error_handler)
                break
        QApplication.setOverrideCursor(QCursor(Qt.BusyCursor))

        # start jobs multi-process
        max_gpu_job_count = 1
        if nprocesses > 1:
            with concurrent.futures.ProcessPoolExecutor(max_workers=nprocesses, initializer=process_initializer) as executor:
                jobs_to_submit = list(range(len(jobs)))
                jobs_submitted = []
                while len(jobs_to_submit) + len(jobs_submitted) > 0:
                    QApplication.processEvents()
                    time.sleep(0.05)
                    if status_dialog.abort:
                        executor.shutdown(wait=False, cancel_futures=True)
                    for n in jobs_to_submit.copy():
                        submit_job = True
                        cancel_job = False
                        for m in jobs[n]['depends']:
                            if 'status' not in jobs[m] or not jobs[m]['status'] == 'Success':
                                submit_job = False
                            if status_dialog.abort or 'status' in jobs[m] and jobs[m]['status'] != 'Success':
                                cancel_job = True
                        if cancel_job:
                            jobs[n]['status'] = 'Cancelled'
                            status_dialog.table.item(jobs[n]['input_idx'], jobs[n]['module_idx']-1).setText('Cancelled')
                            status_dialog.table.item(jobs[n]['input_idx'], jobs[n]['module_idx']-1).setBackground(QBrush(QColor('#ffc8c8')))
                            status_dialog.table.item(jobs[n]['input_idx'], jobs[n]['module_idx']-1).setForeground(QBrush(QColor('#000000')))
                            jobs_to_submit.remove(n)
                            break
                        if jobs[n]['use_gpu']:
                            gpu_job_count = 0
                            for m in jobs_submitted:
                                if jobs[m]['use_gpu']:
                                    gpu_job_count += 1
                            if gpu_job_count > max_gpu_job_count - 1:
                                submit_job = False
                        if submit_job:
                            status_dialog.table.item(jobs[n]['input_idx'], jobs[n]['module_idx']-1).setText('Waiting')
                            status_dialog.table.item(jobs[n]['input_idx'], jobs[n]['module_idx']-1).setBackground(QBrush(QColor('#c8c8ff')))
                            status_dialog.table.item(jobs[n]['input_idx'], jobs[n]['module_idx']-1).setForeground(QBrush(QColor('#000000')))
                            jobs[n]['future'] = executor.submit(jobs[n]['function'], *jobs[n]['arguments'])
                            jobs_to_submit.remove(n)
                            jobs_submitted.append(n)
                            break
                    QApplication.processEvents()
                    time.sleep(0.05)
                    for n in jobs_submitted.copy():
                        if jobs[n]['future'].running():
                            status_dialog.table.item(jobs[n]['input_idx'], jobs[n]['module_idx']-1).setText('Running')
                            status_dialog.table.item(jobs[n]['input_idx'], jobs[n]['module_idx']-1).setBackground(QBrush(QColor('#0000ff')))
                            status_dialog.table.item(jobs[n]['input_idx'], jobs[n]['module_idx']-1).setForeground(QBrush(QColor('#ffffff')))
                        elif jobs[n]['future'].cancelled():
                            jobs[n]['status'] = 'Cancelled'
                            status_dialog.table.item(jobs[n]['input_idx'], jobs[n]['module_idx']-1).setText('Cancelled')
                            status_dialog.table.item(jobs[n]['input_idx'], jobs[n]['module_idx']-1).setBackground(QBrush(QColor('#ffc8c8')))
                            status_dialog.table.item(jobs[n]['input_idx'], jobs[n]['module_idx']-1).setForeground(QBrush(QColor('#000000')))
                            jobs_submitted.remove(n)
                            break
                        elif jobs[n]['future'].done():
                            jobs_submitted.remove(n)
                            try:
                                jobs[n]['future'].result()
                                jobs[n]['status'] = 'Success'
                                jobs[n]['error_message'] = ''
                                status_dialog.table.item(jobs[n]['input_idx'], jobs[n]['module_idx']-1).setText('Success')
                                status_dialog.table.item(jobs[n]['input_idx'], jobs[n]['module_idx']-1).setBackground(QBrush(QColor('#00ff00')))
                                status_dialog.table.item(jobs[n]['input_idx'], jobs[n]['module_idx']-1).setForeground(QBrush(QColor('#000000')))
                            except Exception as e:
                                jobs[n]['status'] = 'Failed'
                                jobs[n]['error_message'] = str(e)
                                status_dialog.table.item(jobs[n]['input_idx'], jobs[n]['module_idx']-1).setText('Failed')
                                status_dialog.table.item(jobs[n]['input_idx'], jobs[n]['module_idx']-1).setBackground(QBrush(QColor('#ff0000')))
                                status_dialog.table.item(jobs[n]['input_idx'], jobs[n]['module_idx']-1).setForeground(QBrush(QColor('#000000')))
                                status_dialog.table.item(jobs[n]['input_idx'], jobs[n]['module_idx']-1).setToolTip(jobs[n]['error_message'])
                            break

        else:
            for job in jobs:
                status_dialog.table.item(job['input_idx'], job['module_idx']-1).setText('Waiting')
                status_dialog.table.item(job['input_idx'], job['module_idx']-1).setBackground(QBrush(QColor('#c8c8ff')))
                status_dialog.table.item(job['input_idx'], job['module_idx']-1).setForeground(QBrush(QColor('#000000')))
                QApplication.processEvents()
                status_dialog.table.item(job['input_idx'], job['module_idx']-1).setText('Running')
                status_dialog.table.item(job['input_idx'], job['module_idx']-1).setBackground(QBrush(QColor('#0000ff')))
                status_dialog.table.item(job['input_idx'], job['module_idx']-1).setForeground(QBrush(QColor('#ffffff')))
                QApplication.processEvents()
                try:
                    job['function'](*job['arguments'])
                    job['status'] = 'Success'
                    job['error_message'] = ''
                    status_dialog.table.item(job['input_idx'], job['module_idx']-1).setText('Success')
                    status_dialog.table.item(job['input_idx'], job['module_idx']-1).setBackground(QBrush(QColor('#00ff00')))
                    status_dialog.table.item(job['input_idx'], job['module_idx']-1).setForeground(QBrush(QColor('#000000')))
                    QApplication.processEvents()
                except Exception as e:
                    job['status'] = 'Failed'
                    job['error_message'] = str(e)
                    status_dialog.table.item(job['input_idx'], job['module_idx']-1).setText('Failed')
                    status_dialog.table.item(job['input_idx'], job['module_idx']-1).setBackground(QBrush(QColor('#ff0000')))
                    status_dialog.table.item(job['input_idx'], job['module_idx']-1).setForeground(QBrush(QColor('#000000')))
                    status_dialog.table.item(job['input_idx'], job['module_idx']-1).setToolTip(job['error_message'])
                    QApplication.processEvents()

        status_dialog.ok_button.show()
        status_dialog.abort_button.hide()

        while QApplication.overrideCursor() is not None:
            QApplication.restoreOverrideCursor()
        # re-enable messagebox error handler
        if messagebox_error_handler is not None:
            logging.getLogger().addHandler(messagebox_error_handler)

        self.logger.info("Done")
