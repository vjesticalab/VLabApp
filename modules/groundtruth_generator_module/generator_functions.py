import os
import logging
import napari
import cv2
import numpy as np
import tifffile
from qtpy.QtWidgets import QSplitter, QWidget, QVBoxLayout, QLabel, QPushButton, QDoubleSpinBox, QTabWidget
from general import general_functions as gf
from aicsimageio.writers import OmeTiffWriter


class NapariWidget(QWidget):
    def __init__(self, viewer: napari.Viewer):
        super().__init__()
        self.min_th_value = min_th_value
        self.max_th_value = max_th_value

        self.viewer = viewer
        self.lowerth = QDoubleSpinBox()
        self.lowerth.setMinimum(0)
        self.lowerth.setMaximum(1000000)
        self.lowerth.setValue(self.min_th_value)
        self.upperth = QDoubleSpinBox()
        self.upperth.setMinimum(0)
        self.upperth.setMaximum(1000000)
        self.upperth.setValue(self.max_th_value)
        self.label1 = QLabel("min threshold value")
        self.label2 = QLabel("max threshold value")
        self.btn = QPushButton("Segment", self)
        self.btn.clicked.connect(self.button_clicked)

        layout = QVBoxLayout()
        layout.addWidget(self.label1)
        layout.addWidget(self.lowerth)
        layout.addWidget(self.label2)
        layout.addWidget(self.upperth)
        layout.addWidget(self.btn)
        layout.addStretch(1)
        self.setLayout(layout)

    def button_clicked(self):
        tresh_mask(norm_channels_image,  self.lowerth.value(), self.upperth.value(), self.viewer)
        self.min_th_value = self.lowerth.value()
        self.max_th_value = self.upperth.value()

class MultipleViewerWidget(QSplitter):
    def __init__(self, viewer: napari.Viewer):
        super().__init__()
        self.viewer = viewer
        self.tab_widget = QTabWidget()
        widget = NapariWidget(viewer)
        self.tab_widget.addTab(widget, "Thresholding")
        self.addWidget(self.tab_widget)

class SaveButton(QWidget):
    def __init__(self, viewer: napari.Viewer, output_path, output_basename):
        super().__init__()
        self.output_path = output_path
        self.output_basename = output_basename
        self.viewer = viewer
        self.button = QPushButton('Save layer')
        self.button.clicked.connect(self.save_layer)
        layout = QVBoxLayout()
        layout.addWidget(self.button)
        self.setLayout(layout)

    def save_layer(self):
        for layer in self.viewer.layers:
            if layer in self.viewer.layers.selection:
                OmeTiffWriter.save(layer.data, os.path.join(self.output_path, self.output_basename + '.ome.tif'))#, dim_order="TCYX")
        print('Layer saved!')

class QuitButton(QWidget):
    def __init__(self, viewer: napari.Viewer):
        super().__init__()
        self.viewer = viewer
        self.quit_button = QPushButton("Quit")
        self.quit_button.clicked.connect(self.viewer.close)
        self.quit_button.setStyleSheet("background: darkred;")
        layout = QVBoxLayout()
        layout.addWidget(self.quit_button)
        self.setLayout(layout)

class NapariWindow(QWidget):
    def __init__(self, output_path, output_basename):
        super().__init__()
        viewer = napari.Viewer()
        viewer.add_image(norm_channels_image.astype('uint32'), name='image')
        dock_widget = MultipleViewerWidget(viewer)
        viewer.window.add_dock_widget(dock_widget, name="Segment")
        save_button = SaveButton(viewer, output_path, output_basename)
        viewer.window.add_dock_widget(save_button, name='Save', area='left')
        quit_button = QuitButton(viewer)
        viewer.window.add_dock_widget(quit_button, name='Quit', area='right')
        viewer.show()


def focal_plane(image):
    """
    This function checks all the z-sections in the image file to find what is the best focused section.
    It relies on minimum image standard deviation in case of BF images and maximum standard deviation in case of fluorescence images.
    """
    zfocus_per_channel = {}
    for c in range(image.sizes['C']):
        zfocus_per_channel[c] = -1

    zfocus_per_time = {}

    for time in range(image.sizes['T']):
        zfocus_per_time[time] = {}
        for c in range(image.sizes['C']):
            std_list = []
            for z in range(image.sizes['Z']):
                _, [[stDevValue]] = cv2.meanStdDev(image.image[0,time,c,z,:,:])
                std_list.append(stDevValue)
            if c == 0:
                zfocus_per_channel[c] = std_list.index(min(std_list))
            else:
                zfocus_per_channel[c] = std_list.index(max(std_list))
            zfocus_per_time[time][c] = zfocus_per_channel[c]

    return zfocus_per_time

def tresh_mask(image, lowerTreshold, upperTreshold, viewer):
    try:
        # Adaptive tresholding method to identify cell boundaries
        image8bit = np.array(image/256, dtype='uint8')
        adaptiveTreshImage = cv2.adaptiveThreshold(image8bit, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 21, 1)
        # Absolute tresholding method to identify regions of cells
        _, thresholdedImage = cv2.threshold(image, lowerTreshold, upperTreshold, cv2.THRESH_BINARY)
        thresholdedImage8bit = np.array(thresholdedImage, dtype='uint8')

        # Combine the two methods above to identify individual cells
        multipliedImage = cv2.multiply(thresholdedImage8bit, adaptiveTreshImage)

        # Dilate/erode approach to fill in holes
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (4, 4))
        processedImage = cv2.morphologyEx(multipliedImage, cv2.MORPH_CROSS, kernel, iterations=1)

        # Extract contours from thresholded image
        contours, _ = cv2.findContours(image=processedImage, mode=cv2.RETR_EXTERNAL, method=cv2.CHAIN_APPROX_NONE)
        fileteredOutSmallContours = [holder for holder in contours if cv2.contourArea(holder)>1000]

        # Dilate-Erode individual contours
        emptyImage = np.zeros(image.shape, dtype='uint8')
        addingContoursIndividually = np.copy(emptyImage)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        for countContour, singleContour, in enumerate(fileteredOutSmallContours):
            singleContourImage = np.copy(emptyImage)
            cv2.drawContours(image=singleContourImage, contours=fileteredOutSmallContours, contourIdx=countContour, color=(countContour, countContour, countContour), thickness=cv2.FILLED)
            singleContourOpen = cv2.morphologyEx(singleContourImage, cv2.MORPH_CLOSE, kernel, iterations=10)
            addingContoursIndividually = cv2.bitwise_or(addingContoursIndividually, singleContourOpen)

        # Draw all contours from thresholded image
        image16bit = np.zeros(image.shape, dtype='uint16')
        cv2.drawContours(image=image16bit, contours=fileteredOutSmallContours, contourIdx=-1, color=(255, 255, 255), thickness=cv2.FILLED)
        print('Mask created successfully.')
        viewer.add_labels(addingContoursIndividually, name='mask')

    except Exception:
        logging.getLogger(__name__).exception('Error in mask generation.\n%s', image_name)


def main(image_path, output_path, output_basename):
    """
    Generate ground truth masks
    
    Parameters
    ---------------------
    image_path: str
        input image path
    output_path: str
        output directory
    output_basename: str
        output basename. Output file will be saved as `output_path`/`output_basename`.ome.tif

    Saves
    ---------------------
    ground truth image in the output directory

    """
    global norm_channels_image, image_name, min_th_value, max_th_value
    min_th_value = 80
    max_th_value = 200

    # Load image
    try:
        image = gf.Image(image_path)
        image_name = image.name
        image.imread()
    except Exception as e:
        logging.getLogger(__name__).error('Error loading image '+image_path+'\n'+str(e))


    # Check channels existance in the image
    if image.sizes['C'] < 2:
        logging.getLogger(__name__).error('Image format.\n' + image_name + ' - The image must have at least one color channel. The BF will be considered as channel 0 and excluded from the analysis.')
        return

    z_pertime_perchannel = focal_plane(image)

    for t in range(image.sizes['T']):
        channels_image = np.zeros((image.sizes['Y'], image.sizes['X']))
        for c in range(1,image.sizes['C']):
            z = z_pertime_perchannel[t][c]
            channel_image = image.image[0,t,c,z,:,:]
            channels_image += channel_image

        norm_channels_image = cv2.normalize(channels_image, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_32F)
        nw = NapariWindow(output_path,output_basename)

