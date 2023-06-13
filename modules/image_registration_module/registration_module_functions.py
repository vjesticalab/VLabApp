from general import general_functions as gf
import numpy as np
import os
import tifffile

def read_transfMat(tmat_path):
    try:
        tmat_string = np.loadtxt(tmat_path, delimiter=",", dtype=str)

    except Warning as e:
        gf.error('Load transformation matrix', str(e))
        return

    else:
        tmat_float = tmat_string.astype(float)
        tmat_int = tmat_float.astype(int)
        return tmat_int

def image_matrix_correspondance(directory, file_type):
    if file_type == 'imageFile':
        image_files = gf.extract_suitable_files(os.listdir(directory))
        # Build dictionary with keys = image_name & values = transformation_matrix_name
        correspondance_dict = {}
        
        for image_file in image_files:        
            baseName = image_file.split("_")[0]
            transfMat_name = baseName+'_transformationMatrix.txt'
            # Transf matrix can be in the same folder of the image
            
            if transfMat_name in os.listdir(directory):
                correspondance_dict[image_file] = directory+'/'+transfMat_name
            # or inside *foldername*_registrationResults/*foldername*_transformationMatrices; *foldername*=os.path.basename(directory)
            else:
                try:
                    if transfMat_name in os.listdir(directory+'/'+os.path.basename(directory)+'_registrationResults/'+os.path.basename(directory)+'_transformationMatrices/'):
                        correspondance_dict[image_file] = directory+'/'+os.path.basename(directory)+'_registrationResults/'+os.path.basename(directory)+'_transformationMatrices/'+transfMat_name
                    else:
                        print('Transformation matrix not found for image '+image_file)
                except:
                    pass

    elif file_type == 'transfMat':
        transformation_matrices = [i for i in os.listdir(directory) if i.endswith('_transformationMatrix.txt')]
        image_files = gf.extract_suitable_files(os.listdir(directory))
        # Build dictionary with keys = transformation_matrix_name & values = LIST of image_names
        correspondance_dict = {}
        for reference_matrix in transformation_matrices:
            correspondance_dict[reference_matrix] = []
            baseName = reference_matrix.split("_transformationMatrix.txt")[0]
            # Images can ONLY be in the same folder of the transf matrix
            for image_f in image_files:
                if baseName == image_f.split("_")[0]:
                    correspondance_dict[reference_matrix].append(directory+'/'+image_f)
    
    return correspondance_dict

def registration_with_tmat(pathsInventory, tmat_int, image: gf.Image, skip_crop = False):
    """
    This function uses a transformation matrix to performs registration and cropping of a 3D image
        input tmat_int: transormation matrix in intigers, 2D-table where
                       [:,0] is timpeoint
                       [:,1] is x-displacement    
                       [:,2] is y-displacement
        input image_3D: image to register, tyx-dimension order
        output img_cropped: registered and cropped image
    """
   
    timepoints_tmat, _ = tmat_int.shape
    
    if image.sizes['T'] != timepoints_tmat:
        gf.error('Image '+image.name,'The number of timepoints(',image.sizes['T'], ') in the image and the transformation matrix(',timepoints_tmat, ') do NOT match. Generating an empty image to prevent script from crashing!')
        return
   
    registered_image = image.image.copy()
    for c in range(0, image.sizes['C']):
        for z in range(0, image.sizes['Z']):
            for timepoint in range(0, image.sizes['T']):
                xyShift = (tmat_int[timepoint, 1]*-1, tmat_int[timepoint, 2]*-1)
                registered_image[0, timepoint, c, z, :, :] = np.roll(image.image[0, timepoint, c, z, :, :], xyShift, axis=(1,0))
    
    if skip_crop:
        # Save the registered and un-cropped image
        registeredFilepath = pathsInventory['resultsRegisteredImagesFolder'] + image.name+'_registered.tif'
        tifffile.imwrite(registeredFilepath, data=registered_image[0,:,:,:,:,:], metadata={'axes': 'TCZYX'})
        return registered_image
    
    # Crop to desired area
    y_start = 0 - min(tmat_int[:,2])
    y_end = image.sizes['Y'] - max(tmat_int[:,2])
    x_start = 0 - min(tmat_int[:,1])
    x_end = image.sizes['X'] - max(tmat_int[:,1])
    # Crop along the y-axis
    image_cropped = registered_image[:, :, :, :, y_start:y_end, x_start:x_end]
    
    # Save the registered and cropped image
    registeredFilepath = pathsInventory['resultsRegisteredImagesFolder'] + image.name+'_registered.tif'
    tifffile.imwrite(registeredFilepath, data=image_cropped[0,:,:,:,:,:], metadata={'axes': 'TCZYX'})
    
    return image_cropped

def build_paths_inventory(directory):
    if not directory.endswith('/'):
        directory = directory + '/'
    folder_name = directory.split('/')[-2]
    pathsInventory={}
    pathsInventory['dataFolder'] = directory   
    pathsInventory['resultsMasterFolder'] = pathsInventory['dataFolder']+folder_name+'_registrationResults/'
    pathsInventory['resultsTransformationMatricesFolder'] = pathsInventory['resultsMasterFolder']+folder_name+'_transformationMatrices/'
    pathsInventory['resultsRegisteredImagesFolder'] = pathsInventory['resultsMasterFolder']+folder_name+'_registeredImages/'
    pathsInventory['resultsRegistrationAnalysesFolder'] = pathsInventory['resultsMasterFolder']+folder_name+'_registrationAnalyses/'
    return pathsInventory

def extract_transfMat(content):
    #This function filters and sorts the list of files for those that are opened with openSuitableFiles_ver01_ver01 function
    #Ver01 includes TIF and ND2 file formats
    suitable_files = [i for i in content if i.endswith('_transformationMatrix.txt')]
    suitable_files = sorted(suitable_files)
    return suitable_files
