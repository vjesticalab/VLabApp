import logging
from general import general_functions as gf
import numpy as np
import os
import tifffile
import time
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
    This function uses a transformation matrix to performs registration and eventually cropping of an image
    Note - always assuming FoV dimension of the image as empty 

    Parameters
    ---------------------
    tmat_int:
        transformation matrix
    image: Image object
    skip_crop: boolean 
        indicates whether to crop or not the registeret image
    output_path: str
        parent image path + /registration/
    
    Saves
    ---------------------
    image : ndarray
        registered and eventually cropped image 
    """
    registeredFilepath = output_path + image.name + '_registered.tif'
    
    # Assuming empty dimension F
    image6D = image.image
    registered_image = image6D.copy()
    for z in range(0, image.sizes['Z']):
        for c in range(0, image.sizes['C']):
            for timepoint in range(0, image.sizes['T']):
                xyShift = (tmat_int[timepoint, 1]*-1, tmat_int[timepoint, 2]*-1)
                registered_image[0, timepoint, c, z, :, :] = np.roll(image6D[0, timepoint, c, z, :, :], xyShift, axis=(1,0)) 

    if skip_crop:
        # Save the registered and un-cropped image
        try:
            tifffile.imwrite(registeredFilepath, data=registered_image[0,:,:,:,:,:], metadata={'axes': 'TCZYX'}, imagej=True, compression='zlib')
        except:
            tifffile.imwrite(registeredFilepath, data=registered_image[0,:,:,:,:,:], metadata={'axes': 'TCZYX'}, compression='zlib')   

    else:
        # Crop to desired area
        y_start = 0 - min(tmat_int[:,2])
        y_end = image.sizes['Y'] - max(tmat_int[:,2])
        x_start = 0 - min(tmat_int[:,1])
        x_end = image.sizes['X'] - max(tmat_int[:,1])
        # Crop along the y-axis
        image_cropped = registered_image[:, :, :, :, y_start:y_end, x_start:x_end]
        
        # Save the registered and cropped image
        try:
            tifffile.imwrite(registeredFilepath, data=image_cropped[0,:,:,:,:,:], metadata={'axes': 'TCZYX'}, imagej=True, compression='zlib')
        except:
            tifffile.imwrite(registeredFilepath, data=image_cropped[0,:,:,:,:,:], metadata={'axes': 'TCZYX'}, compression='zlib')

def registration_projection_with_tmat(tmat_int, image, projection_type, skip_crop, output_path):
    """
    As the previous one but made for the projected image of the z-stack 
    """
    registeredFilepath = output_path + image.name + '_' + projection_type + 'Projection_registered.tif'
    
    # Assuming empty dimension F
    image6D = image.zProjection('std')
    registered_image = image6D.copy()
    for c in range(0, image.sizes['C']):
        for timepoint in range(0, image.sizes['T']):
            xyShift = (tmat_int[timepoint, 1]*-1, tmat_int[timepoint, 2]*-1)
            registered_image[0, timepoint, c, 0, :, :] = np.roll(image6D[0, timepoint, c, 0, :, :], xyShift, axis=(1,0)) 

    if skip_crop:
        # Save the registered and un-cropped image
        try:
            tifffile.imwrite(registeredFilepath, data=registered_image[0,:,:,0,:,:], metadata={'axes': 'TCYX'}, imagej=True, compression='zlib')
        except:
            tifffile.imwrite(registeredFilepath, data=registered_image[0,:,:,0,:,:], metadata={'axes': 'TCYX'}, compression='zlib')   

    else:
        # Crop to desired area
        y_start = 0 - min(tmat_int[:,2])
        y_end = image.sizes['Y'] - max(tmat_int[:,2])
        x_start = 0 - min(tmat_int[:,1])
        x_end = image.sizes['X'] - max(tmat_int[:,1])
        # Crop along the y-axis
        image_cropped = registered_image[:, :, :, :, y_start:y_end, x_start:x_end]
        
        # Save the registered and cropped image
        try:
            tifffile.imwrite(registeredFilepath, data=image_cropped[0,:,:,0,:,:], metadata={'axes': 'TCYX'}, imagej=True, compression='zlib')
        except:
            tifffile.imwrite(registeredFilepath, data=image_cropped[0,:,:,0,:,:], metadata={'axes': 'TCYX'}, compression='zlib')


def registration_values(image, projection_type, channel_position, output_path):
    """
    This function calculates the transformation matrices from brightfield images
    Note: aligned images are NOT saved since pixels are recalculated by StackReg method

    Parameters
    ---------------------
    image : Image object
    projection_type : str
        type of projection to perform if it is a z-stack
    channel_position : int
        posizion of the channel to register if it is a c-stack
    output_path : str
        parent image path + /registration/
    
    Returns
    ---------------------
    tmats :
        integer pixel values transformation matrix
    
    Saves
    ---------------------
    txt_res :
        file which contains the values t_x and t_y (x and y pixel shifts) as columns for each time point (rows)      
    """
    # Assuming empty dimensions F and C defined in channel_position
    # if Z not empty then make z-projection (projection_type)
    if image.sizes['Z'] > 1:
        try:
            projection = image.zProjection(projection_type)
            logging.getLogger(__name__).info('Made z-projection ('+projection_type+') for image '+image.basename)
        except Exception:
            logging.getLogger(__name__).error('Z-projection failed for image '+image.basename)
        if image.sizes['C'] > channel_position:
            image3D = projection[0,:,channel_position,0,:,:]
        else:
            logging.getLogger(__name__).error('Position of the channel given ('+channel_position+') is out of range for image '+image.basename)
    # Otherwise read the 3D image 
    else:
        if image.sizes['C'] > 1:
            if image.sizes['C'] > channel_position:
                image3D = image.image[0,:,channel_position,0,:,:]
            else:
                logging.getLogger(__name__).error('Position of the channel given ('+channel_position+') is out of range for image '+image.basename)            
        else:
            image3D = image.get_TYXarray()
    # Translation = only movements on x and y axis
    sr = StackReg(StackReg.TRANSLATION)
    # Align each frame at the previous one
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
    txt_name = output_path + 'tranf_matrices/' + image.name.split('_')[0] +'_transformationMatrix.txt'
    np.savetxt(txt_name, transformation_matrices, fmt = '%d, %d, %d, %d, %d, %d, %d, %d', header = 'timePoint, align_t_x, align_t_y, align_0_1, raw_t_x, raw_t_y, x, y', delimiter = '\t')    
    
    return transformation_matrices

################################################################

def registration_main(image_path, channel_position, projection_type, skip_crop_decision, coalignment_images_list):
    # Load image
    # Note: by default the image have to be ALWAYS 3D with TYX
    output_path = os.path.dirname(image_path)+'/registration/'
    if not os.path.exists(output_path):
        os.mkdir(output_path)
    if not os.path.exists(output_path + 'tranf_matrices/'):
        os.mkdir(output_path + 'tranf_matrices/')
    try:
        image = gf.Image(image_path)
        image.imread()
    except Exception as e:
        logging.getLogger(__name__).error('Error loading image '+image_path+'\n'+str(e))
           
    # Calculate transformation matrix
    tmat = registration_values(image, projection_type, channel_position, output_path)

    # Align and save
    registration_with_tmat(tmat, image, skip_crop_decision, output_path)

    # If Z not empty it means that in the registration there was a z projection, so save also this
    if image.sizes['Z'] > 1:
        registration_projection_with_tmat(tmat, image, projection_type, skip_crop_decision, output_path)

    for im_coal_path in coalignment_images_list:
        try:
            image_coal = gf.Image(im_coal_path)
            image_coal.imread()
        except Exception as e:
            logging.getLogger(__name__).error('Error loading image '+im_coal_path+'\n'+str(e))
        try:
            registration_with_tmat(tmat, image_coal, skip_crop_decision, output_path)
        except Exception as e:
            logging.getLogger(__name__).error('Alignment failed for image '+im_coal_path+' - '+str(e))

################################################################

def alignment_main(image_path, skip_crop_decision):
    # Load image and matrix
    output_path = os.path.dirname(image_path)+'/registration/'
    try:
        image = gf.Image(image_path)  
        image.imread()
    except Exception as e:
        logging.getLogger(__name__).error('Error loading image '+image_path+'\n'+str(e))                    
    try:
        tmat_path = output_path + 'tranf_matrices/' + image.name.split('_')[0] + '_transformationMatrix.txt'
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
