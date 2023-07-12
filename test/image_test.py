import numpy as np
import os
import tifffile
import nd2
from pystackreg import StackReg
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel, QMessageBox
import warnings
import matplotlib.pyplot as plt
warnings.filterwarnings(action='ignore', category=DeprecationWarning, message='`np.bool` is a deprecated alias')
#warnings.filterwarnings("error", category=UserWarning)

def error(header, message):
    print()

class Image:
    def __init__(self, im_path):
        self.path = im_path
        self.basename = os.path.basename(self.path)
        self.name, self.extension = os.path.splitext(self.basename)
        
    def imread(self):
        # axis default order: FTCZXY for 6D - F = FieldofView, T = time, C = channels
        if self.extension == '.nd2':
            reader = nd2.ND2File(self.path)
            axes_order = str(''.join(list(reader.sizes.keys()))).upper() #eg. reader.sizes = {'T': 10, 'C': 2, 'Y': 256, 'X': 256}
            shape = reader.shape #eg. (10, 2, 256, 256)
            image = reader.asarray() #nd2.imread(self.path)
            reader.close()
            self.sizes = {}
            self.image, self.shape = self.set_image(image, shape, axes_order)
            for key, value in zip('FTCZYX', self.shape):
                self.sizes[key] = value
            return self.image

        elif (self.extension == '.tiff' or self.extension == '.tif'):
            reader = tifffile.TiffFile(self.path)
            axes_order = str(reader.series[0].axes).upper()
            shape = list(reader.series[0].shape)
            image = reader.asarray()
            reader.close()
            self.sizes = {}
            self.image, self.shape = self.set_image(image, shape, axes_order)
            for key, value in zip('FTCZYX', self.shape):
                self.sizes[key] = value
            return self.image
        else:
            error('Image', 'Image format not supported. Please upload a tiff or nd2 image file.')
            
    def set_image(self, image, shape, axes):
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
        missing_dims = 'FTCZYX'.strip(axes)
        for dim in missing_dims:
            position = dimensions[dim]
            image = np.expand_dims(image, axis=position)
        return image, image.shape


for file in os.listdir('/Users/aravera/Documents/CIG_Aleks/Application/test/test_data/'):
    if file != '.DS_Store':
        image_file = Image('/Users/aravera/Documents/CIG_Aleks/Application/test/test_data/'+file)
        print(image_file.name)
        image = image_file.imread()
        print(image_file.sizes)