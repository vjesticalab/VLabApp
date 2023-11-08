import logging
from general import general_functions as gf
import numpy as np
import os
import tifffile
import time
from pystackreg import StackReg
import cv2 as cv


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

def register_stack_phase_correlation(image,blur=5):
    """
    Register an image using phase correlation algorithm implemented in opencv

    Parameters
    ----------
    image: ndarray
        a 3D (TYX) 16bit unsigned integer (uint16) numpy array.
    blur: int
        kernel size for gaussian blue

    Returns
    -------
    list of tuples
        list with one (x,y) tuple per time frame.
        Each (x,y) tuple corresponds to the shift between images at the corresponding time frame and previous time frame.
    """

    h = image.shape[1]
    w = image.shape[2]
    shifts = [(0, 0)]
    if blur>1:
        prev = cv.GaussianBlur(cv.normalize(image[0], None, 0, 1, cv.NORM_MINMAX, dtype=cv.CV_32F), (blur, blur), 0)
    else:
        prev = cv.normalize(image[0], None, 0, 1, cv.NORM_MINMAX, dtype=cv.CV_32F)

    for i in range(1, image.shape[0]):
        if blur > 1:
            curr = cv.GaussianBlur(cv.normalize(image[i], None, 0, 1, cv.NORM_MINMAX, dtype=cv.CV_32F), (blur, blur), 0)
        else:
            curr = cv.normalize(image[i], None, 0, 1, cv.NORM_MINMAX, dtype=cv.CV_32F)

        lastshift = (round(shifts[-1][0]), round(shifts[-1][1]))
        #crop window prev (shifted)
        xmin1 = max(lastshift[0], 0)
        xmax1 = min(w+lastshift[0], w)
        ymin1 = max(lastshift[1], 0)
        ymax1 = min(h+lastshift[1], h)
        #crop window curr
        xmin2 = max(-lastshift[0], 0)
        xmax2 = min(w-lastshift[0], w)
        ymin2 = max(-lastshift[1], 0)
        ymax2 = min(h-lastshift[1], h)

        ##register to previous image (shifted and cropped)
        shift, response = cv.phaseCorrelate(curr[ymin2:ymax2, xmin2:xmax2],
                                            prev[ymin1:ymax1, xmin1:xmax1],
                                            cv.createHanningWindow((xmax1-xmin1, ymax1-ymin1), cv.CV_32F))

        shifts.append((lastshift[0]+shift[0], lastshift[1]+shift[1]))

        ## store shifted and cropped image as previous image
        prev = cv.warpAffine(curr, M=np.float32([[1, 0, shifts[-1][0]], [0, 1, shifts[-1][1]]]), dsize=(w, h), borderMode=cv.BORDER_CONSTANT, borderValue=curr.max()/2)
        #i = i+1

    return [(-x,-y) for x, y in shifts]

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
    registeredFilepath = os.path.join(output_path, image.name + '_registered.tif')

    # Assuming empty dimension F
    image6D = image.image
    registered_image = image6D.copy()
    for z in range(0, image.sizes['Z']):
        for c in range(0, image.sizes['C']):
            for timepoint in range(0, image.sizes['T']):
                if tmat_int[timepoint, 3] == 1:
                    xyShift = (tmat_int[timepoint, 1]*-1, tmat_int[timepoint, 2]*-1)
                    registered_image[0, timepoint, c, z, :, :] = np.roll(image6D[0, timepoint, c, z, :, :], xyShift, axis=(1,0))
    
    if skip_crop:
        t_start = min([d[0] for d in tmat_int if d[3] == 1])
        t_end = max([d[0] for d in tmat_int if d[3] == 1])
        registered_image = registered_image[:, t_start:t_end, :, :, :, :]
        # Save the registered and un-cropped image
        if image.sizes['C'] == 1:
            try:
                tifffile.imwrite(registeredFilepath, data=registered_image[0,:,0,:,:,:], metadata={'axes': 'TZYX'}, imagej=True, compression='zlib')
            except:
                tifffile.imwrite(registeredFilepath, data=registered_image[0,:,0,:,:,:], metadata={'axes': 'TZYX'}, compression='zlib')
        else:
            tifffile.imwrite(registeredFilepath, data=registered_image[0,:,:,:,:,:], metadata={'axes': 'TCZYX'}, compression='zlib') #XYCZT

    else:
        # Crop to desired area
        y_start = 0 - min([d[2] for d in tmat_int if d[3] == 1]) 
        y_end = image.sizes['Y'] - max([d[2] for d in tmat_int if d[3] == 1])
        x_start = 0 - min([d[1] for d in tmat_int if d[3] == 1]) 
        x_end = image.sizes['X'] - max([d[1] for d in tmat_int if d[3] == 1])
        t_start = min([d[0] for d in tmat_int if d[3] == 1])
        t_end = max([d[0] for d in tmat_int if d[3] == 1])

        print(y_start, y_end, x_start, x_end, t_start, t_end)
        # Crop along the y-axis
        image_cropped = registered_image[:, t_start:t_end, :, :, y_start:y_end, x_start:x_end]

        # Save the registered and cropped image
        if image.sizes['C'] == 1:
            try:
                tifffile.imwrite(registeredFilepath, data=image_cropped[0,:,0,:,:,:], metadata={'axes': 'TZYX'}, compression='zlib')
            except:
                tifffile.imwrite(registeredFilepath, data=image_cropped[0,:,0,:,:,:], metadata={'axes': 'TZYX'}, compression='zlib')
        else:
            tifffile.imwrite(registeredFilepath, data=image_cropped[0,:,:,:,:,:], metadata={'axes': 'TCZYX'}, compression='zlib')


def registration_projection_with_tmat(tmat_int, image, projection_type, projection_zrange, skip_crop, output_path):
    """
    As the previous one but made for the projected image of the z-stack 
    """
    filename_suffix=None
    if projection_zrange is None:
        filename_suffix=projection_type
    elif isinstance(projection_zrange,int) and projection_zrange==0:
        filename_suffix="bestZ"
    elif isinstance(projection_zrange,int):
        filename_suffix=projection_type+str(projection_zrange)
    elif isinstance(projection_zrange,tuple) and len(projection_zrange) == 2 and projection_zrange[0]<=projection_zrange[1]:
        filename_suffix=projection_type+str(projection_zrange[0])+"-"+str(projection_zrange[1])
    registeredFilepath = os.path.join(output_path, image.name + '_' + filename_suffix + '_registered.tif')

    # Assuming empty dimension F
    image6D = image.zProjection(projection_type, projection_zrange)
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


def registration_values(image, projection_type, projection_zrange, channel_position, output_path, registration_method):
    """
    This function calculates the transformation matrices from brightfield images
    Note: aligned images are NOT saved since pixels are recalculated by StackReg method

    Parameters
    ---------------------
    image : Image object
    projection_type : str
        type of projection to perform if it is a z-stack
    projection_zrange: int or (int,int) or None
        the range of z sections to use for projection.
        If zrange is None, use all z sections.
        If zrange is an integer, use all z sections in the interval [z_best-zrange,z_best+zrange]
        where z_best is the Z corresponding to best focus.
        If zrange is tuple (zmin,zmax), use all z sections in the interval [zmin,zmax].
    channel_position : int
        posizion of the channel to register if it is a c-stack
    output_path : str
        parent image path + /registration/
    registration_method : str
        method to use for registration. Can be "stackreg" or "phase correlation"

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
    # if Z not empty then make z-projection (projection_type,projection_zrange)
    if image.sizes['Z'] > 1:
        try:
            projection = image.zProjection(projection_type, projection_zrange)
            logging.getLogger(__name__).info('Made z-projection ('+projection_type+', zrange '+str(projection_zrange)+') for image '+image.basename)
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

    if registration_method == "stackreg":
        logging.getLogger(__name__).info('Registration with stackreg')

        # Translation = only movements on x and y axis
        sr = StackReg(StackReg.TRANSLATION)
        # Align each frame at the previous one
        tmats_float = sr.register_stack(image3D, reference='previous')
        # Convert tmats_float into integers


        # Transformation matrix has 6 columns:
        # timePoint, align_t_x, align_t_y, align_0_1, raw_t_x, raw_t_y (align_ and raw_ values are identical, useful then for the alignment)
        transformation_matrices = np.zeros((tmats_float.shape[0], 8), dtype=np.int)
        transformation_matrices[:, 0] = np.arange(1, tmats_float.shape[0]+1)
        transformation_matrices[:, 1:3] = transformation_matrices[:, 4:6] = tmats_float[:, 0:2, 2].astype(int)
        transformation_matrices[:, 3] = 1
        transformation_matrices[:, 6] = image.sizes['X']
        transformation_matrices[:, 7] = image.sizes['Y']
    
    elif registration_method == "phase correlation":
        logging.getLogger(__name__).info('Registration with phase correlation')
        shifts=register_stack_phase_correlation(image3D,blur=5)
        # Transformation matrix has 6 columns:
        # timePoint, align_t_x, align_t_y, align_0_1, raw_t_x, raw_t_y (align_ and raw_ values are identical, useful then for the alignment)
        transformation_matrices = np.zeros((len(shifts), 8), dtype=int)
        transformation_matrices[:, 0] = np.arange(1, len(shifts)+1)
        transformation_matrices[:, 1:3] = transformation_matrices[:, 4:6] = np.round(np.array(shifts)).astype(int)
        transformation_matrices[:, 3] = 1
        transformation_matrices[:, 6] = image.sizes['X']
        transformation_matrices[:, 7] = image.sizes['Y']
    else:
        logging.getLogger(__name__).error('Error unknown registration method '+registration_method+'\n')

    # Save the txt file with the translation matrix
    txt_name = os.path.join(output_path,'transf_matrices', image.name.split('_')[0] +'_transformationMatrix.txt')
    np.savetxt(txt_name, transformation_matrices, fmt = '%d, %d, %d, %d, %d, %d, %d, %d', header = 'timePoint, align_t_x, align_t_y, align_0_1, raw_t_x, raw_t_y, x, y', delimiter = '\t')

    return transformation_matrices

################################################################


def registration_main(image_path, output_path, channel_position, projection_type, projection_zrange, skip_crop_decision, coalignment_images_list, registration_method):
    # Load image
    # Note: by default the image have to be ALWAYS 3D with TYX
    try:
        image = gf.Image(image_path)
        image.imread()
    except Exception as e:
        logging.getLogger(__name__).error('Error loading image '+image_path+'\n'+str(e))

    # Calculate transformation matrix
    tmat = registration_values(image, projection_type, projection_zrange, channel_position, output_path, registration_method)

    # Align and save
    registration_with_tmat(tmat, image, skip_crop_decision, output_path)

    # If Z not empty it means that in the registration there was a z projection, so save also this
    if image.sizes['Z'] > 1:
        registration_projection_with_tmat(tmat, image, projection_type, projection_zrange, skip_crop_decision, output_path)

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

    return image_path

################################################################


def alignment_main(image_path, skip_crop_decision):
    # Load image and matrix
    output_path = os.path.join(os.path.dirname(image_path),'registration')
    try:
        image = gf.Image(image_path)
        image.imread()
    except Exception as e:
        logging.getLogger(__name__).error('Error loading image '+image_path+'\n'+str(e))
    try:
        tmat_path = os.path.join(output_path, 'transf_matrices', image.name.split('_')[0] + '_transformationMatrix.txt')
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
