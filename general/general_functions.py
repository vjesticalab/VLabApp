import numpy as np
import os
import tifffile
import nd2
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel
import warnings
import logging


class Image:
    """
    Class used to read and elaborate images
    Defualt dimension positions = {'F': 0, 'T': 1, 'C': 2, 'Z': 3, 'Y': 4, 'X': 5}

    Attributes
    ----------
    path : str
        path to the image
    basename : str
        image name with extension
    name : str
        image name without extension
    extension : str
        extension of the image
    sizes : dict
        dictionary with dimesions names and values
        # eg. {'F': 1, 'T': 1, 'C': 3, 'Z': 11, 'Y': 2048, 'X': 2048}
    image : ndarray
        numpy ndarray with the image
    shape : list
        list with image shapes

    Methods
    -------
    imread()
        Read the image from the already setted 'path'
        Attributes image, sizes and shape are populated here
    save()
        Empty
    get_TYXarray()
        Return the 3D image with the dimensions T, Y and X.
        When used the other dimensions F,C,Z MUST be empty (with size = 1)
    zProjection(projection_type)
        Return the z-projection of the image and the selected projection type.
        Possible projection types: max, min, std, avg, median
    """
    def __init__(self, im_path):
        self.path = im_path
        self.basename = os.path.basename(self.path)
        self.name, self.extension = os.path.splitext(self.basename)
        self.sizes = None
        self.image = None
        self.shape = None
        
    def imread(self):

        def set_6Dimage(image, axes):
            """
            Return a 6D ndarray of the input image
            """
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

        # axis default order: FTCZXY for 6D - F = FieldofView, T = time, C = channels
        if self.extension == '.nd2':
            reader = nd2.ND2File(self.path)
            axes_order = str(''.join(list(reader.sizes.keys()))).upper() #eg. reader.sizes = {'T': 10, 'C': 2, 'Y': 2048, 'X': 2048}
            image = reader.asarray() #nd2.imread(self.path)
            reader.close()
            self.sizes = {}
            self.image, self.shape = set_6Dimage(image, axes_order)
            for key, value in zip('FTCZYX', self.shape):
                self.sizes[key] = value # eg. {'F': 1, 'T': 10, 'C': 2, 'Z': 1, 'Y': 2048, 'X': 2048}
            self.shape = self.image.shape
            return self.image

        elif (self.extension == '.tiff' or self.extension == '.tif'):
            reader = tifffile.TiffFile(self.path)
            axes_order = str(reader.series[0].axes).upper()
            image = reader.asarray()
            reader.close()
            self.sizes = {}
            self.image, self.shape = set_6Dimage(image, axes_order)
            for key, value in zip('FTCZYX', self.shape):
                self.sizes[key] = value
            self.shape = self.image.shape
            return self.image
        else:
            logging.getLogger(__name__).error('Image format not supported. Please upload a tiff or nd2 image file.')
    
    def save(self):
        pass

    def get_TYXarray(self):
        if self.sizes['F'] > 1 or self.sizes['C'] > 1 or self.sizes['Z'] > 1:
            logging.getLogger(__name__).error('Image format not supported. Please upload an image with only TYX dimesions.')
        return self.image[0,:,0,0,:,:]

    def zProjection(self, projection_type):
        if projection_type == 'max': projected_image = np.max(self.image, axis=4).astype('uint16')
        elif projection_type == 'min': projected_image = np.min(self.image, axis=4).astype('uint16')
        elif projection_type == 'std': projected_image = np.std(self.image, axis=4, ddof=1).astype('uint16') #float32
        elif projection_type == 'avg': projected_image = np.average(self.image, axis=4).astype('uint16')
        elif projection_type == 'megian': projected_image = np.median(self.image, axis=4).astype('uint16') #float32
        else: logging.error('Projection type not recognized')
        return projected_image


def extract_suitable_files(directory):
    """
    Filter and sort the list of suitable files in the given directory
    In this version suitable files = TIF and ND2 files
    """
    suitable_files = [i for i in directory if i.endswith('.nd2') or i.endswith('.tif')]
    suitable_files = sorted(suitable_files)
    return suitable_files


def update_transfMat(tmat_int, reference_timepoint_index, range_start_index, range_end_index):
    """
    Update the transformation matrix
    Inputs:
        tmat_int : original matrix
        reference_timepoint_index : index of the new reference point
        range_start_index : index of the starting timepoint (included)
        range_end_index : index of the ending timepoint (included)
    """

    # Step 1:
    # get x- and y- offset values for the reference timepoint
    min_timepoint = min(tmat_int[:,0]) -1 
    max_timepoint = max(tmat_int[:,0]) -1

    exc1 = reference_timepoint_index < range_start_index
    exc2 = reference_timepoint_index > range_end_index
    exc3 = range_start_index < min_timepoint
    exc4 = range_end_index > max_timepoint

    if exc1 or exc2 or exc3 or exc4:
        logging.getLogger(__name__).error('Values out of range')
        return tmat_int

    reference_rawXoffset = tmat_int[reference_timepoint_index,4]
    reference_rawYoffset = tmat_int[reference_timepoint_index,5]
    
    # Step 2:
    # subtract reference point offset values from all other timepoints and write them to 2nd and 3rd columns,
    # which will are used for registration from transformation matrices
    tmat_updated = np.copy(tmat_int)
    for counter in range(0,len(tmat_int)):
        tmat_updated[counter,1] = tmat_int[counter,4]-reference_rawXoffset
        tmat_updated[counter,2] = tmat_int[counter,5]-reference_rawYoffset
        tmat_updated[counter,3] = 0        
    
    # Step 3:
    # write in 4th column whether the timepoint is included in the registration (value = 1)
    # or excluded from registration (value = 0)
    for counter in range(range_start_index, range_end_index+1):
        tmat_updated[counter,3] = 1
    return tmat_updated


def error_empty(submission_num, widget, window):
    """
    Add an error line in the main application window when missing input values
    """
    widget.setFocus()
    if submission_num == 1:
        label_error = QLabel('Error : missing value')
        label_error.setAlignment(Qt.AlignCenter)
        label_error.setStyleSheet("color: red;")
        window.addRow(label_error)
        return label_error
    