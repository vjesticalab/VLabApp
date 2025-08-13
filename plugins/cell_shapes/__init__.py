"""
A plugin to evaluate shape properties of segmented cells.
"""

import os
import logging
import pandas as pd
from skimage.measure import regionprops_table
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QFormLayout, QLabel, QGroupBox, QRadioButton, QPushButton, QLineEdit
from PyQt5.QtCore import Qt
from general import general_functions as gf

# Name of the plugin (used in the left panel of the GUI)
NAME = 'Cell shapes'


# The widget (shown in the right panel of the GUI)
class Widget(QWidget):
    def __init__(self, parent=None, pipeline_layout=False):
        super().__init__(parent)

        self.output_suffix = '_vCS'
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Short documentation with a collapsible label
        groupbox = QGroupBox("Documentation")
        layout2 = QVBoxLayout()
        label_documentation = gf.CollapsibleLabel('', collapsed=True)
        label_documentation.setText('For each input segmentation mask, evaluate shape properties for all segmented cells and save the resulting table.<br>' +
                                    'Input segmentation mask must have X and Y axes and can optionally have a T axis.<br><br>' +
                                    '<b>Output format</b><br>' +
                                    'Tab-separated values format (.tsv) with a header in first row, one row per segmented cell and the following columns:<br>' +
                                    '* frame<br>' +
                                    '* mask_id<br>' +
                                    '* centroid_y<br>' +
                                    '* centroid_x<br>' +
                                    '* area<br>' +
                                    '* perimeter<br>' +
                                    '* axis_major_length<br>' +
                                    '* axis_minor_length<br>' +
                                    '* eccentricity<br>' +
                                    '* orientation<br>' +
                                    'Columns "frame" and "mask_id" correspond to time frame and cell ID respectively. See the scikit-image documentation (<a href="https://scikit-image.org/docs/stable/api/skimage.measure.html#skimage.measure.regionprops">https://scikit-image.org/docs/stable/api/skimage.measure.html#skimage.measure.regionprops</a>) for more information on the shape properties, '
                                    )
        layout2.addWidget(label_documentation)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        # List of input masks (accept only segmentation masks, i.e. files containing the suffix used by the Segmentation module)
        groupbox = QGroupBox('Input files (segmentation masks)')
        layout2 = QVBoxLayout()
        self.mask_list = gf.FileListWidget(filetypes=gf.imagetypes,
                                           filenames_filter=gf.output_suffixes['segmentation'])
        layout2.addWidget(self.mask_list)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        # Output settings
        groupbox = QGroupBox("Output")
        layout2 = QVBoxLayout()
        self.output_settings = gf.OutputSettings(extensions=['.tsv'], output_suffix=self.output_suffix)
        layout2.addWidget(self.output_settings)
        groupbox.setLayout(layout2)
        layout.addWidget(groupbox)

        # Submit button
        self.submit_button = QPushButton("Submit")
        self.submit_button.clicked.connect(self.submit)
        layout.addWidget(self.submit_button, alignment=Qt.AlignCenter)

    def submit(self):
        mask_paths = self.mask_list.get_file_list()

        for input_path in mask_paths:
            logging.getLogger(__name__).info("Processing mask %s", input_path)
            try:
                output_filename = os.path.join(self.output_settings.get_path(input_path),
                                               self.output_settings.get_basename(input_path) + '.tsv')

                # Load mask
                mask = gf.Image(input_path)
                mask.imread()
                # get the mask data as a numpy ndarray with T, Y and X axes (alternatively, mask.image returns a numpy ndarray with F, T, C, Z, Y and X axes)
                mask_TYX = mask.get_TYXarray()

                # Evaluate shape properties
                properties = []
                for t in range(mask.sizes['T']):
                    props = regionprops_table(mask_TYX[t, :, :],
                                              properties=('label',
                                                          'centroid',
                                                          'area',
                                                          'perimeter',
                                                          'axis_major_length',
                                                          'axis_minor_length',
                                                          'eccentricity',
                                                          'orientation'))
                    df = pd.DataFrame(props)
                    # add a column 'frame' (time frame)
                    df.insert(0, 'frame', t)
                    # rename columns
                    df.rename(columns={'label': 'mask_id',
                                       'centroid-0': 'centroid_y',
                                       'centroid-1': 'centroid_x'},
                              inplace=True)
                    properties.append(df)

                # Save table
                logging.getLogger(__name__).info('Creating: %s', output_filename)
                pd.concat(properties, ignore_index=True).to_csv(output_filename, sep='\t', na_rep='nan', index=False)

            except Exception:
                logging.getLogger(__name__).exception("Processing failed for mask:\n%s\n\nError message:", input_path)

        logging.getLogger(__name__).info("Done")
