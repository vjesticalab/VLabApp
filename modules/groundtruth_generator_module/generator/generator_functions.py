import os
import nd2
import napari
import cv2
import numpy as np
import tifffile
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QMessageBox, QSplitter, QWidget, QVBoxLayout, QLabel, QPushButton, QDoubleSpinBox, QTabWidget, QMainWindow,QApplication
import sys
from general import general_functions as gf


"""class Image:
    def __init__(self, path):
        self.basename = os.path.basename(path)
        self.name = self.basename.split('.')[0]
        if path.endswith('.nd2'):
            imagereader = nd2.ND2File(path)
            axes_order = str(''.join(list(imagereader.sizes.keys()))).upper()
            shape = list(imagereader.sizes.values())
            image = nd2.imread(path)
            imagereader.close()
        else:
            # default: TZCXY for 5D, ZCXY for 4D, CXY for 3D, XY for 2D data.
            imagereader = tifffile.TiffFile(path)
            axes_order = str(imagereader.series[0].axes).upper()
            shape = list(imagereader.series[0].shape)
            image = tifffile.imread(path)
        self.image, self.shape, self.axes_order = image, shape, axes_order
        self.image, self.shape, self.axes_order = self.check_axes_order(image, shape, axes_order)

    def check_axes_order(self, image, shape, axes_order):

        def swipe(image, shape, axes_order, dimension):
            expected_pos = len(shape)-i
            actual_pos = self.axes_order.find(dimension)
            image = np.moveaxis(image, actual_pos, expected_pos)
            shape = list(image.shape)
            l = [x for x in axes_order]
            l[actual_pos], l[expected_pos] = l[expected_pos], l[actual_pos]
            axes_order = ''.join(l)
            return image, shape, axes_order

        def error():
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Critical)
            msg.setText("Error - Image "+self.basename)
            msg.setInformativeText('Image MUST have minimin 3 dimensions: X Y C. \nIt is not possible to create the mask without other fluorescent channels.')
            msg.setWindowTitle("Error")
            msg.exec_()

        i = 0
        if 'X' in axes_order:
            i += 1
            if axes_order[-i] != 'X':
                image, shape, axes_order = swipe(image, shape, axes_order, 'X')
        else:
            error()

        if 'Y' in axes_order:
            i += 1
            if axes_order[-i] != 'Y':
                image, shape, axes_order = swipe(image, shape, axes_order, 'Y')
        else:
            error()

        if 'Z' in axes_order:
            i += 1
            if axes_order[-i] != 'Z':
                image, shape, axes_order = swipe(image, shape, axes_order, 'Z')

        if 'C' in axes_order:
            i += 1
            if axes_order[-i] != 'C':
                image, shape, axes_order = swipe(image, shape, axes_order, 'C')
        else:
            error()

        if 'T' in axes_order:
            i += 1
            if axes_order[-i] != 'T':
                image, shape, axes_order = swipe(image, shape, axes_order, 'T')
                
        return image, shape, axes_order

    def get_2D(self, c, t, z):
        if z != -1:
            # x, y, c and z are existing
            if 'T' in self.axes_order: # TCZYX
                return self.image[t,c,z,:,:]
            else: # CZYX
                return self.image[c,z,:,:]
        else:
            if 'T' in self.axes_order: # TCYX
                return self.image[t,c,:,:]
            elif 'T' not in self.axes_order: # CYX
                return self.image[c,:,:]
        return self.image

    def get_shape(self, axis):
        pos = self.axes_order.find(axis)
        if pos == -1:
            return pos
        return self.shape[pos]

"""

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
        treshMasks(norm_channels_image,  self.lowerth.value(), self.upperth.value(), self.viewer)
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
    def __init__(self, viewer: napari.Viewer, result_path):
        super().__init__()
        self.result_path = result_path
        self.viewer = viewer
        self.button = QPushButton('Save layer')
        self.button.clicked.connect(self.save_layer)
        layout = QVBoxLayout()
        layout.addWidget(self.button)
        self.setLayout(layout)
    
    def save_layer(self):
        for layer in self.viewer.layers:
            if layer in self.viewer.layers.selection:
                tifffile.imwrite(self.result_path+'/'+image_name+'.tif', layer.data)
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
    def __init__(self, result_path):
        super().__init__()
        viewer = napari.Viewer()
        viewer.add_image(norm_channels_image.astype('uint32'), name='image')
        viewer.window._qt_window.setWindowState(Qt.WindowMaximized)
        dock_widget = MultipleViewerWidget(viewer)
        viewer.window.add_dock_widget(dock_widget, name="Segment")
        save_button = SaveButton(viewer, result_path)
        viewer.window.add_dock_widget(save_button, name='Save', area='left')
        quit_button = QuitButton(viewer)
        viewer.window.add_dock_widget(quit_button, name='Quit', area='right')
        viewer.show(block=True)


def focal_plane(image: gf.Image):
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



def treshMasks(image, lowerTreshold, upperTreshold, viewer):
   try:
      # Adaptive tresholding method to identify cell boundaries
      image8bit = np.array(image/256, dtype='uint8')
      adaptiveTreshImage = cv2.adaptiveThreshold(image8bit, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 21, 1)
      emptyImage = np.zeros(image.shape, dtype='uint8')
      # Absolute tresholding method to identify regions of cells
      _, thresholdedImage = cv2.threshold(image, lowerTreshold, upperTreshold, cv2.THRESH_BINARY)
      thresholdedImage8bit = np.array(thresholdedImage, dtype='uint8')
      # Combine the two methods to identify individual cells
      multipliedImage = cv2.multiply(thresholdedImage8bit, adaptiveTreshImage)
      # Dilate/erode approach to fill in holes
      kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (4, 4))
      processingImage = cv2.morphologyEx(multipliedImage, cv2.MORPH_CROSS, kernel, iterations=1)
      # Extract contours from thresholded image
      contours, _ = cv2.findContours(image=processingImage, mode=cv2.RETR_EXTERNAL, method=cv2.CHAIN_APPROX_NONE)   
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
   except Exception as e:
      msg = QMessageBox()
      msg.setIcon(QMessageBox.Critical)
      msg.setText("Error in mask generation")
      msg.setInformativeText(str(e))
      msg.setWindowTitle("Error")
      msg.exec_()


def main(path, result_path):
    global norm_channels_image, image_name, min_th_value, max_th_value

    min_th_value = 80
    max_th_value = 200

    images = gf.extract_suitable_files(os.listdir(path))
   
    if not images:
        gf.error("No images", "The folder does not contain .nd2 or .tif files")

    for image_name in images:
        print('Processing image '+image_name)
        
        try:
            image_path = os.path.join(path, image_name)
            image = gf.Image(image_path)
            image_name = image.name
            image.imread()
            
            z_pertime_perchannel = focal_plane(image)

            for t in range(image.sizes['T']):
                channels_image = np.zeros((image.sizes['Y'], image.sizes['X']))
                for c in range(1,image.sizes['C']):
                    z = z_pertime_perchannel[t][c]
                    channel_image = image.image[0,t,c,z,:,:]
                    channels_image += channel_image

                norm_channels_image = cv2.normalize(channels_image, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_32F)  
                nw = NapariWindow(result_path)
                nw.show()

        except Exception as e:
            gf.error("generator crashed", str(e))
      

"""
# To test it:
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        main(path, result_path)


if __name__ == "__main__":
   path = '/Users/aravera/Documents/CIG_Aleks/_AVScript01-Calculating MAsks for AI/Script1_InputSample'
   result_path = '/Users/aravera/Desktop'
   app = QApplication(sys.argv)
   w = MainWindow()
   w.show()
   app.exec()
"""