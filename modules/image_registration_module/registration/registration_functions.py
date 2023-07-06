import logging
from general import general_functions as gf
import numpy as np
import os
import tifffile
import time
import napari
from pystackreg import StackReg

def read_transfMat(tmat_path):
    try:
        tmat_string = np.loadtxt(tmat_path, delimiter=",", dtype=str)

    except Warning as e:
        logging.getLogger(__name__).error('Load transformation matrix', str(e))
        return

    else:
        tmat_float = tmat_string.astype(float)
        tmat_int = tmat_float.astype(int)
        return tmat_int

def registration_with_tmat(tmat_int, image, skip_crop, output_path):
    """
    This function uses a transformation matrix to performs registration and eventually cropping of a 3D image
    Input:
        tmat_int - transformation matrix
        image - Image object
        skip_crop - boolean indicating whether to crop or not the registeret image
        output_path - parent image path + /registration/
    Save:
        image - ndarray of the registered and eventually cropped image
    Note: assuming FoV dimension of the image as empty     
    """
    registeredFilepath = output_path + image.name + '_registered.tif'

    registered_image = image.image.copy()
    for c in range(0, image.sizes['C']):
        for z in range(0, image.sizes['Z']):
            for timepoint in range(0, image.sizes['T']):
                xyShift = (tmat_int[timepoint, 1]*-1, tmat_int[timepoint, 2]*-1)
                registered_image[0, timepoint, c, z, :, :] = np.roll(image.image[0, timepoint, c, z, :, :], xyShift, axis=(1,0)) 

    if skip_crop:
        # Save the registered and un-cropped image
        tifffile.imwrite(registeredFilepath, data=registered_image[0,:,:,:,:,:], metadata={'axes': 'TCZYX'})
    
    else:
        # Crop to desired area
        y_start = 0 - min(tmat_int[:,2])
        y_end = image.sizes['Y'] - max(tmat_int[:,2])
        x_start = 0 - min(tmat_int[:,1])
        x_end = image.sizes['X'] - max(tmat_int[:,1])
        # Crop along the y-axis
        image_cropped = registered_image[:, :, :, :, y_start:y_end, x_start:x_end]
        
        # Save the registered and cropped image
        tifffile.imwrite(registeredFilepath, data=image_cropped[0,:,:,:,:,:], metadata={'axes': 'TCZYX'})

def registration_values(image, output_path):
    """
    This function calculates the transformation matrices from brightfield images
    Input:
        image - Image object
        output_path - parent image path + /registration/
    Output:
        tmats - integer pixel values transformation matrix
    Save:
        txt_res - file which contains the values t_x and t_y (x and y pixel shifts) as columns for each time point (rows)
    Note: aligned images are NOT saved since pixels are recalculated by StackReg method
           
    """
    image3D = image.get_TYXarray()
    # Translation = only movements on x and y axis
    sr = StackReg(StackReg.TRANSLATION)
    # Align each frame at the previous one
    z = 0
    tmats_float = sr.register_stack(image3D, reference='previous')    
    # Convert tmats_float into integers
    tmats_int = tmats_float
    translation = [] 
    for i in range(0, tmats_int.shape[0]):
        tmats_int[i, 0, 2] = int(tmats_float[i, 0, 2])
        tmats_int[i, 1, 2] = int(tmats_float[i, 1, 2])
        translation.append([int(i)+1, int(tmats_int[i, 0, 2]), int(tmats_int[i, 1, 2]), 1, int(tmats_int[i, 0, 2]), int(tmats_int[i, 1, 2]), image.sizes['X'], image.sizes['Y']])
    
    # Transformation matrix has 6 columns:
    # timePoint, align_t_x, align_t_y, align_0_1, raw_t_x, raw_t_y (align_ and raw_ values are identical, useful then for the alignment)
    transformation_matrices = np.array(translation)
    # Save the txt file with the translation matrix
    txt_name = output_path + 'tmats/' + image.name.split('_')[0] +'_transformationMatrix.txt'
    np.savetxt(txt_name, transformation_matrices, fmt = '%d, %d, %d, %d, %d, %d, %d, %d', header = 'timePoint, align_t_x, align_t_y, align_0_1, raw_t_x, raw_t_y, x, y', delimiter = '\t')    
    
    return transformation_matrices

################################################################

def registration_main(image_path, skip_crop_decision):
    # Load image
    # Note: by default the image have to be ALWAYS 3D with TYX
    output_path = os.path.dirname(image_path)+'/registration/'
    try:
        image = gf.Image(image_path)
        image.imread()
    except Exception as e:
        logging.getLogger(__name__).error('Error loading image '+image_path+' - '+str(e))
           
    # Calculate transformation matrix
    tmat = registration_values(image, output_path)
    # Align and save
    registration_with_tmat(tmat, image, skip_crop_decision, output_path)

################################################################

def alignment_main(image_path, skip_crop_decision):
    # Load image and matrix
    output_path = os.path.dirname(image_path)+'/registration/'
    try:
        image = gf.Image(image_path)  
        image.imread()
    except Exception as e:
        logging.getLogger(__name__).error('Error loading image '+image_path+' - '+str(e))                       
    try:
        tmat_path = output_path + 'tmats/' + image.name.split('_')[0] + '_transformationMatrix.txt'
        tmat_int = read_transfMat(tmat_path)
    except Exception as e:
        logging.getLogger(__name__).error('Error loading transformation matrix for image '+image_path+' - '+str(e))
    # Align and save - registration works with multidimensional files, as long as the TYX axes are specified
    try:
        registration_with_tmat(tmat_int, image, skip_crop_decision, output_path)
    except Exception as e:
        logging.getLogger(__name__).error('Alignment failed for image '+image_path+' - '+str(e))

################################################################

def edit_main(reference_matrix_path, reference_timepoint, range_start, range_end):
    # Load the transformation matrix 
    tmat_int = read_transfMat(reference_matrix_path)
    # Load the transformation matrix header
    with open(reference_matrix_path) as f:
        headerText = ''
        hashtag = '#'
        while hashtag == '#':
            linecontent = f.readline()
            hashtag = linecontent[0]
            if hashtag == '#':
                headerText += linecontent[2:]
    # Make sure reference point is within range and update transformation matrix
    tmat_updated  = gf.update_transfMat(tmat_int, reference_timepoint-1, range_start-1, range_end-1)
    headerText += time.strftime('Updated on %Y/%m/%d at %H:%M:%S .') + ' Timepoints range: ' + str(range_start) + ' - ' + str(range_end) + ' . Reference timepoint: ' + str(reference_timepoint)
    # Save the new matrix  
    np.savetxt(reference_matrix_path, tmat_updated, fmt = '%d, %d, %d, %d, %d, %d, %d, %d', header=headerText, delimiter='\t')
