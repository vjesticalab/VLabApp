import numpy as np
import os
import tifffile
import nd2
from pystackreg import StackReg
from PyQt5.QtWidgets import QMessageBox
import warnings
warnings.filterwarnings(action='ignore', category=DeprecationWarning, message='`np.bool` is a deprecated alias')
#warnings.filterwarnings("error", category=UserWarning)

def base_name(fileName):
    #This function uses the underscore symbol to separate the basename from the channel information
    return fileName.split("_")[0]

def file_name_split(fileName):
    #This function splits the full filename into extension and filename
    return fileName.split(".")[0], fileName.split(".")[1]

def folder_name(path):
    return path.split('/')[-2]

def file_handling(path):
    ############# FILE HANDLING ##############
    content = os.listdir(path)
    #Get a list of image files
    image_files = extract_suitable_files(content)
    transformation_matrices = [i for i in content if i.endswith('_transformationMatrix.txt')]
    transformation_matrices.sort()
    
    #Build dictionary with keys from transformation matrices
    files = {}
    for f in transformation_matrices:
        files[f] = []
    
    #For each transformation matrix find image files with the same basename files
    for reference_matrix in files.keys():
        reference_baseName = reference_matrix.split("_transformationMatrix.txt")[0]
        print(reference_matrix, 'will be used to register files:')
        for image_f in image_files:
            image_baseName= base_name(image_f)
            if reference_baseName == image_baseName:
                files[reference_matrix].append(image_f)
                print('\t',image_f)
    return files

def read_transfMat(tmat_path):
    try:
        tmat_string = np.loadtxt(tmat_path, delimiter=",", dtype=str)

    except Warning as e:
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setText("Error")
        msg.setInformativeText(str(e))
        msg.setWindowTitle("Error")
        msg.exec_()
        return

    else:
        tmat_float = tmat_string.astype(float)
        tmat_int = tmat_float.astype(int)
        return tmat_int

def extract_suitable_files(content):
    #This function filters and sorts the list of files for those that are opened with openSuitableFiles_ver01_ver01 function
    #this version includes TIF and ND2 file formats
    suitable_files = [i for i in content if i.endswith('.nd2') or i.endswith('.tif')]
    suitable_files = sorted(suitable_files)
    return suitable_files
    
def open_suitable_files(filepath):
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
    
    return imageLoad, axes_inventory

def array_slice(a, axis, start, end, step=1):
    return a[(slice(None),) * (axis % a.ndim) + (slice(start, end, step),)]

def register_with_tmat_multiD(tmat_int, image_multiD, y_axis, x_axis, skip_decision):
    #This function uses a transformation matrix to performs registration and cropping of a 3D image
    #   input tmat_int: transormation matrix in intigers, 2D-table where
    #                   [:,0] is timpeoint
    #                   [:,1] is x-displacement    
    #                   [:,2] is y-displacement   
    #   input image_3D: image to register, tyx-dimension order
    #   output img_cropped: registered and cropped image
    #Perform registration
    dimensions = image_multiD.shape
    timepoints_image = dimensions[0]
    h_dim = dimensions[y_axis]
    w_dim = dimensions[x_axis]
    timepoints_tmat, _ = tmat_int.shape
    
    if timepoints_image != timepoints_tmat:
        print('\nNumber of timepoints(',timepoints_image, ') in the image and the transformation matrix(',timepoints_tmat, ') do NOT match. Generating an empty image to prevent script from crashing!')
        fakeImage = np.zeros((tmat_int.shape[0],abs(max(tmat_int[:,2]))+abs(min(tmat_int[:,2])),abs(max(tmat_int[:,1]))+abs(min(tmat_int[:,1]))), dtype='uint8')   
        return fakeImage
    else:
        #Column 4 of the transformation matrix holds information on timepoints that will be
        #registered (value 1) and those that will not be registered (value 0)
        tmat_range = np.array([row for row in tmat_int if row[3]==1])
        timepoints_range, _ = tmat_range.shape
        
        #List of timepoints that are included, which may be non-sequential
        list_included_timepoints = [tp_incl-1 for tp_incl in tmat_range[:,0]]
        #print(list_included_timepoints)
        
        #Extract only the images of timepoints which should be included
        image_range = np.take(image_multiD, list_included_timepoints, axis=0)
        registered_image = np.copy(image_range)
                      
        for timepoint in range(0,timepoints_range):
            yxShift = (tmat_range[timepoint, 2]*-1, tmat_range[timepoint, 1]*-1)
            registered_image[timepoint] = np.roll(image_range[timepoint], yxShift, axis=(y_axis-1,x_axis-1))

        if skip_decision:
            print('\nImage cropping has been skipped')
            return registered_image
        
        else:            
            print('\nshapePostShift ', registered_image.shape)            
            #Crop to desired area
            #Step1: Determine maximum and minimum drifts along x-axis and y-axis, within the range
            max_x = max(tmat_range[:,1])
            max_y = max(tmat_range[:,2])
            min_x = min(tmat_range[:,1])
            min_y = min(tmat_range[:,2])
            #Step2: Determine the croppinng area
            y_start = 0-min_y
            y_end = h_dim-max_y
            x_start = 0-min_x
            x_end = w_dim-max_x
            
            print('\nystart', y_start,'yend', y_end)
            print('\nxstart',x_start, 'xend', x_end)
            #Step3: Crop along the y-axis
            y_croped = array_slice(registered_image, y_axis, y_start, y_end)
            yx_croped = array_slice(y_croped, x_axis, x_start, x_end)
            return yx_croped

def registration_with_tmat_multiD(pathsInventory, tmat_int, image_multiD, img_name, y_axis, x_axis, axes_positions):
    #This function uses a transformation matrix to performs registration and cropping of a 3D image
    #   input tmat_int: transormation matrix in intigers, 2D-table where
    #                   [:,0] is timpeoint
    #                   [:,1] is x-displacement    
    #                   [:,2] is y-displacement   
    #   input image_3D: image to register, tyx-dimension order
    #   output img_cropped: registered and cropped image
    #Perform registration
    dimensions = image_multiD.shape
    timepoints_image = dimensions[0]
    h_dim = dimensions[y_axis]
    w_dim = dimensions[x_axis]
   
    timepoints_tmat, _ = tmat_int.shape
    
    if timepoints_image != timepoints_tmat:
        print('\nNumber of timepoints(',timepoints_image, ') in the image and the transformation matrix(',timepoints_tmat, ') do NOT match. Generating an empty image to prevent script from crashing!')
        yx_cropped=np.zeros((tmat_int.shape[0],abs(max(tmat_int[:,2]))+abs(min(tmat_int[:,2])),abs(max(tmat_int[:,1]))+abs(min(tmat_int[:,1]))), dtype='uint8')   
    else:
        registered_image=np.copy(image_multiD)
        for timepoint in range(0,timepoints_image):
            yxShift=(tmat_int[timepoint, 2]*-1, tmat_int[timepoint, 1]*-1)
            registered_image[timepoint]=np.roll(image_multiD[timepoint], yxShift, axis=(y_axis-1,x_axis-1))
            
        #Crop to desired area
        #Step1: Determine maximum and minimum drifts along x-axis and y-axis
        max_x = max(tmat_int[:,1])
        max_y = max(tmat_int[:,2])
        min_x = min(tmat_int[:,1])
        min_y = min(tmat_int[:,2])
        #Step2: Determine the croppinng range and crop the image
        y_start = 0-min_y
        y_end = h_dim-max_y
        x_start = 0-min_x
        x_end = w_dim-max_x
        #Step3: Crop along the y-axis
        y_croped = array_slice(registered_image, y_axis, y_start, y_end)
        yx_croped = array_slice(y_croped, x_axis, x_start, x_end)       
    
    # Save the registered and cropped image
    fileNameNoExtension, fileExtension = file_name_split(img_name)
    registeredFilename=fileNameNoExtension+'_registered.tif'
    registeredFilepath = pathsInventory['resultsRegisteredImagesFolder']+registeredFilename
    tifffile.imwrite(registeredFilepath, data=yx_croped, metadata={'axes': axes_positions}, imagej=True)

def extract_transfMat(content):
    #This function filters and sorts the list of files for those that are opened with openSuitableFiles_ver01_ver01 function
    #Ver01 includes TIF and ND2 file formats
    suitable_files = [i for i in content if i.endswith('_transformationMatrix.txt')]
    suitable_files = sorted(suitable_files)
    return suitable_files

def build_dictionary(path, _type):
    content = os.listdir(path)
    #Get a list of image files
    image_files = extract_suitable_files(content)
    transformation_matrices = [i for i in content if i.endswith('_transformationMatrix.txt')]
    transformation_matrices.sort()
    
    if _type == 'imageFile':
        #Build dictionary with keys from image files
        files={}
        for f in image_files:
            files[f] = []
        #For each transformation matrix find image files with the same basename files
        for image_file in files.keys():        
            image_baseName = base_name(image_file)
            print(image_file, image_baseName, 'will be registered with matrices:') 
            for transfMat_file in transformation_matrices:
                transfMat_baseName = transfMat_file.split('_transformationMatrix.txt')[0]
                if transfMat_baseName == image_baseName:
                    files[image_file].append(transfMat_file)
                    print('\n\t',transfMat_file)
    
    elif _type == 'transfMat':
        #Build dictionary with keys from transformation matrices
        files = {}
        for f in transformation_matrices:
            files[f] = []
        
        #For each transformation matrix find image files with the same basename files
        for reference_matrix in files.keys():
            nameParts = reference_matrix.split("_transformationMatrix.txt")
            reference_baseName=nameParts[0]
            print(reference_matrix, 'will be used to register files:')
            for image_f in image_files:
                image_baseName = base_name(image_f)
                if reference_baseName == image_baseName:
                    files[reference_matrix].append(image_f)
                    print('\n\t',image_f)
    
    return files

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

def list_transfMat(transfmat_path):
    all_files = os.listdir(transfmat_path)
    print(all_files)
    list_transfmat_files = [i for i in all_files if i.endswith('_transformationMatrix.txt')]
    print('\nTransformation matrices are:', list_transfmat_files)
    list_transfmat_files.sort()
    return list_transfmat_files

def registration_values(pathsInventory, imgForRegCalculations, img_name):
    #This function calculates the transformation matrices from brightfield images
    #input:  imgForRegCalculations = original 3-D image used to calculate registration matrix
    #input:  img_name = name of the image
    #output: tmats = integer pixel values transformation matrix
    #save:   txt_res = file which contains the values t_x and t_y (x and y pixel shifts) as columns for each time point (rows)
    #Note that aligned images are NOT saved since pixels are recalculated by StackReg method
    
    print('\nCalculating transformation matrix for ',img_name)       
    # TRANSLATION: only movements on x and y axis
    sr = StackReg(StackReg.TRANSLATION)
    # previous: align each frame at the previous one
    tmats_float = sr.register_stack(imgForRegCalculations, reference='previous')    
    #The package calculates transormations into tmats_float as floats and not integers. These need to be converted to integers to avoid any image medification
    
    h_dim = imgForRegCalculations.shape[1]
    w_dim = imgForRegCalculations.shape[2]

    #Converting calculated transformation matrix into intigers to avoid any image modification
    tmats_int = tmats_float
    transfation = [] 
    for i in range(0, tmats_int.shape[0]):
        tmats_int[i, 0, 2] = int(tmats_float[i, 0, 2])
        tmats_int[i, 1, 2] = int(tmats_float[i, 1, 2])
        transfation.append([int(i)+1, int(tmats_int[i, 0, 2]), int(tmats_int[i, 1, 2]), 1, int(tmats_int[i, 0, 2]), int(tmats_int[i, 1, 2]), w_dim, h_dim])
    
    #Building the final transformation matrix that has the following 6 columns
    #timePoint, align_t_x, align_t_y, align_0_1, raw_t_x, raw_t_y
    #where align_ and raw_ values are identical. Other scripts will modify align, but not raw_ values which are costly to calculate
    transformation_matrices = np.array(transfation)
    # Save the txt file with the transfation values
    txt_name = pathsInventory['resultsTransformationMatricesFolder'] + base_name(img_name)+'_transformationMatrix.txt'
    np.savetxt(txt_name, transformation_matrices, fmt = '%d, %d, %d, %d, %d, %d, %d, %d', header = 'timePoint, align_t_x, align_t_y, align_0_1, raw_t_x, raw_t_y, x, y', delimiter = '\t')    
    return transformation_matrices

def build_paths_inventory(path):
    pathsInventory={}
    pathsInventory['dataFolder']=path   
    pathsInventory['resultsMasterFolder']=pathsInventory['dataFolder']+folder_name(pathsInventory['dataFolder'])+'_registrationResults/'
    pathsInventory['resultsTransformationMatricesFolder']=pathsInventory['resultsMasterFolder']+folder_name(pathsInventory['dataFolder'])+'_transformationMatrices/'
    pathsInventory['resultsRegisteredImagesFolder']=pathsInventory['resultsMasterFolder']+folder_name(pathsInventory['dataFolder'])+'_registeredImages/'
    pathsInventory['resultsRegistrationAnalysesFolder']=pathsInventory['resultsMasterFolder']+folder_name(pathsInventory['dataFolder'])+'_registrationAnalyses/'
    return pathsInventory
