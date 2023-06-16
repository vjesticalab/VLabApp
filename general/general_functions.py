import numpy as np
import os
import tifffile
import nd2
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel, QMessageBox
import warnings
warnings.filterwarnings(action='ignore', category=DeprecationWarning, message='`np.bool` is a deprecated alias')
#warnings.filterwarnings("error", category=UserWarning)

def error(header, message=None):
    msgbox = QMessageBox()
    msgbox.setText(header)
    msgbox.setIcon(QMessageBox.Warning)
    msgbox.setInformativeText(message)
    msgbox.setWindowTitle("Error")
    msgbox.exec_()

class Image:
    # dimensions = {'F': 0, 'T': 1, 'C': 2, 'Z': 3, 'Y': 4, 'X': 5}
    def __init__(self, im_path):
        self.path = im_path
        self.basename = os.path.basename(self.path)
        self.name, self.extension = os.path.splitext(self.basename)
        self.sizes = None
        self.image = None
        self.shape = None
        
    def imread(self):
        # axis default order: FTCZXY for 6D - F = FieldofView, T = time, C = channels
        if self.extension == '.nd2':
            reader = nd2.ND2File(self.path)
            axes_order = str(''.join(list(reader.sizes.keys()))).upper() #eg. reader.sizes = {'T': 10, 'C': 2, 'Y': 256, 'X': 256}
            image = reader.asarray() #nd2.imread(self.path)
            reader.close()
            self.sizes = {}
            self.image, self.shape = self.set_image(image, axes_order)
            for key, value in zip('FTCZYX', self.shape):
                self.sizes[key] = value # eg. {'F': 1, 'T': 1, 'C': 3, 'Z': 11, 'Y': 2048, 'X': 2048}
            self.shape = self.image.shape
            return self.image

        elif (self.extension == '.tiff' or self.extension == '.tif'):
            reader = tifffile.TiffFile(self.path)
            axes_order = str(reader.series[0].axes).upper()
            image = reader.asarray()
            reader.close()
            self.sizes = {}
            self.image, self.shape = self.set_image(image, axes_order)
            for key, value in zip('FTCZYX', self.shape):
                self.sizes[key] = value
            self.shape = self.image.shape
            return self.image
        else:
            error('Image format.', 'Image format not supported. Please upload a tiff or nd2 image file.')

    def save(self):
        pass

    def get_TZXarray(self):
        return self.image[0,:,0,0,:,:]

    def set_image(self, image, axes):
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
        missing_dims = []
        for c in 'FTCZYX':
            if c not in axes:
                missing_dims.append(c)
        for dim in missing_dims:
            position = dimensions[dim]
            image = np.expand_dims(image, axis=position)
        return image, image.shape


def base_name(fileName):
    #This function uses the underscore symbol to separate the basename from the channel information
    return fileName.split("_")[0]

def file_name_split(fileName):
    #This function splits the full filename into extension and filename
    return fileName.split(".")[0], fileName.split(".")[1]

"""def folder_name(path):
    return path.split('/')[-2]

"""
def extract_suitable_files(content):
    #This function filters and sorts the list of files for those that are opened with openSuitableFiles_ver01_ver01 function
    #this version includes TIF and ND2 file formats
    suitable_files = [i for i in content if i.endswith('.nd2') or i.endswith('.tif')]
    suitable_files = sorted(suitable_files)
    return suitable_files
    
"""def open_suitable_files(filepath):
    #This function opens both TIF and ND2 files and 
    #generates a dictionary with information about image axes
    #Step1: Load the images
    #Step2: Build an axes dictionary where keys are channels (eg. T C Z Y X) 
    #and values contain axis of iteration [0] and size [1]
    #e.g. axes_inventory = {'T': [0, 120], 
    #                       'Z': [1, 3], 
    #                       'C': [2, 2], 
    #                       'Y': [3, 275], 
    #                       'X': [4, 390]}
    
    fileName = os.path.basename(filepath)
    _, fileExtension = file_name_split(fileName)   
    
    if 'tif' in fileExtension:
        #Step1: Load the image
        imageLoad = tifffile.imread(filepath)        
        #Step2: Build an axes dictionary 
        infoFile = tifffile.TiffFile(filepath) #Get file information 
        image_shape =  imageLoad.shape
        image_axes = infoFile.series[0].axes
        axes_inventory = {}
        for channel_position, axis in enumerate(image_axes):
            axes_inventory[axis] = [channel_position, image_shape[channel_position]]      
    
    elif 'nd2' in fileExtension:
        #Step1: Load the image
        imageLoad = nd2.imread(filepath)
        #Step2: Build an axes dictionary
        with nd2.ND2File(filepath) as infoFile:
            image_shape = imageLoad.shape
            image_dimensions = infoFile.sizes
            axes_inventory = {}
            for channel_position, axis in enumerate(image_dimensions.keys()):
                axes_inventory[axis] = [channel_position, image_shape[channel_position]] 
    
    else:
        print('\nThe file', filepath, ' is neither TIF nor ND2. Generating a 5x5x5 random array instead to allow script to run')
        #Write a warning txt file.
        with open(filepath[:-4]+'-!!!WARNING!!!.txt', 'a') as out:
            text = 'This image is not suitable format!'
            out.write(text)       
        imageLoad = [[[0 for i in range(5)] for j in range(5)] for k in range(5)]
        axes_inventory = {'T': [0, 120], 'Z': [1, 3], 'C': [2, 2], 'Y': [3, 275], 'X': [4, 390]}
    
    return imageLoad, axes_inventory"""

def array_slice(a, axis, start, end, step=1):
    return a[(slice(None),) * (axis % a.ndim) + (slice(start, end, step),)]


def update_transfMat(tmat_int, reference_timepoint_index, range_start_index, range_end_index):
    #This function updates the transformation matrix
    #inputs     tmat_int : original matrix
    #           reference_timepoint_index : index of the new reference point
    #           range_start_index : index of the starting timepoint (included)
    #           range_end_index : index of the ending timepoint (included)

    #Step1: Get x- and y- offset values for the reference timepoint

    min_timepoint = min(tmat_int[:,0]) -1 
    max_timepoint = max(tmat_int[:,0]) -1

    exc1 = reference_timepoint_index < range_start_index
    exc2 = reference_timepoint_index > range_end_index
    exc3 = range_start_index < min_timepoint
    exc4 = range_end_index > max_timepoint

    if exc1 or exc2 or exc3 or exc4:
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setText("Error")
        msg.setInformativeText("Values out of range")
        msg.setWindowTitle("Error")
        msg.exec_()
        return tmat_int

    reference_rawXoffset = tmat_int[reference_timepoint_index,4]
    reference_rawYoffset = tmat_int[reference_timepoint_index,5]
    
    #Step2: Subtract reference point offset values from all other timepoints and write them to 2nd and 3rd columns, which will are used for registration from transformation matrices
    tmat_updated = np.copy(tmat_int)
    for counter in range(0,len(tmat_int)):
        tmat_updated[counter,1] = tmat_int[counter,4]-reference_rawXoffset
        tmat_updated[counter,2] = tmat_int[counter,5]-reference_rawYoffset
        tmat_updated[counter,3] = 0        
    
    #Step3: Write in 4th column whether the timepoint is included in the registration (value = 1) or excluded from registration (value = 0)
    for counter in range(range_start_index, range_end_index+1):
        tmat_updated[counter,3] = 1
    return tmat_updated


"""def build_paths_inventory(path):
    pathsInventory={}
    pathsInventory['dataFolder']=path   
    pathsInventory['resultsMasterFolder']=pathsInventory['dataFolder']+folder_name(pathsInventory['dataFolder'])+'_registrationResults/'
    pathsInventory['resultsTransformationMatricesFolder']=pathsInventory['resultsMasterFolder']+folder_name(pathsInventory['dataFolder'])+'_transformationMatrices/'
    pathsInventory['resultsRegisteredImagesFolder']=pathsInventory['resultsMasterFolder']+folder_name(pathsInventory['dataFolder'])+'_registeredImages/'
    pathsInventory['resultsRegistrationAnalysesFolder']=pathsInventory['resultsMasterFolder']+folder_name(pathsInventory['dataFolder'])+'_registrationAnalyses/'
    return pathsInventory"""

def error_empty(submission_num, widget, window):
    widget.setFocus()
    if submission_num == 1:
        label_error = QLabel('Error : missing value')
        label_error.setAlignment(Qt.AlignCenter)
        label_error.setStyleSheet("color: red;")
        window.addRow(label_error)
        return label_error
    