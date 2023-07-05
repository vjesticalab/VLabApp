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
        logging.getLogger(__name__).error('Image '+image.name+'\nThe number of timepoints(' + str(image.sizes['T'])+') in the image and the transformation matrix('+ str(timepoints_tmat)+ ') do NOT match. Generating an empty image to prevent script from crashing!')
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


def registration_values(pathsInventory, image):
    """
    This function calculates the transformation matrices from brightfield images
        input:  image : Image object
        output: tmats = integer pixel values transformation matrix
        save:   txt_res = file which contains the values t_x and t_y (x and y pixel shifts) as columns for each time point (rows)
    Note that aligned images are NOT saved since pixels are recalculated by StackReg method
    and that by default the registration will ALWAYS be compute over the first axes of F and C and on the best Z, since the image needs to be 3D 
    """
    
    print('\nCalculating transformation matrix for ',image.name)       
    # TRANSLATION: only movements on x and y axis
    sr = StackReg(StackReg.TRANSLATION)
    # Align each frame at the previous one
    z = 0
    if image.sizes['Z'] > 1:
        z = int(image.sizes['Z']/2)
    tmats_float = sr.register_stack(image.image[0,:,0,z,:,:], reference='previous')    
    # The package calculates transformations into tmats_float as floats and not integers.
    # These need to be converted to integers to avoid any image medification
    tmats_int = tmats_float
    translation = [] 
    for i in range(0, tmats_int.shape[0]):
        tmats_int[i, 0, 2] = int(tmats_float[i, 0, 2])
        tmats_int[i, 1, 2] = int(tmats_float[i, 1, 2])
        translation.append([int(i)+1, int(tmats_int[i, 0, 2]), int(tmats_int[i, 1, 2]), 1, int(tmats_int[i, 0, 2]), int(tmats_int[i, 1, 2]), image.sizes['X'], image.sizes['Y']])
    
    # Building the final transformation matrix that has the following 6 columns:
    # timePoint, align_t_x, align_t_y, align_0_1, raw_t_x, raw_t_y (align_ and raw_ values are identical, useful then for the alignment)
    transformation_matrices = np.array(translation)
    # Save the txt file with the translation values
    txt_name = pathsInventory['resultsTransformationMatricesFolder'] + image.name.split('_')[0] +'_transformationMatrix.txt'
    np.savetxt(txt_name, transformation_matrices, fmt = '%d, %d, %d, %d, %d, %d, %d, %d', header = 'timePoint, align_t_x, align_t_y, align_0_1, raw_t_x, raw_t_y, x, y', delimiter = '\t')    
    return transformation_matrices

def registration_main(path, referenceIdentifier, coalignNonReferenceFiles):
    # referenceIdentifier is the unique string used to distinguish the channel that will be used for alignments

    # Check whether path is a folder path or a file path    
    if os.path.isfile(path):
        singleFile = True
        input_folderpath, input_filename = os.path.split(path)       
        path = input_folderpath+'/'
        referenceIdentifier = '_'+input_filename.split('_')[-1]
    else:
        singleFile = False

    # File handling
    content = os.listdir(path)
    suitable_files = gf.extract_suitable_files(content)

    if len(suitable_files) == 0:
        logging.getLogger(__name__).error('Image format.\nImage(s) format not supported, nothing to process.')
        return
    
    # Create path to results
    pathsInventory = build_paths_inventory(path)
    for pathCreate in pathsInventory:
        if not os.path.isdir(pathsInventory[pathCreate]):
            os.makedirs(pathsInventory[pathCreate])
      
    # File dictionary: keys - reference files for registration ; values - list of files that are to be aligned with the reference
    files = {}
    
    # Step1 : Build dictionary keys from files that contain the identifier string
    for f in suitable_files:
        if referenceIdentifier in f:
            files[f] = []
    referenceFiles = list(files.keys())
    
    # Step2 : Introduce dictionary values that match the dictionary keys
    # This is an optional step that determines whether only reference files will be aligned
    if coalignNonReferenceFiles:   
        text = 'The script co-aligned available files to the reference file with the same basename.\n Image files that lack a registration reference are:\n'
        for f in suitable_files:
            if referenceIdentifier not in f:
                matchingBasename = f.split("_")[0]
                referenceKey=''
                for searchRef in referenceFiles:
                    if matchingBasename in searchRef:
                        referenceKey = searchRef
                if referenceKey == '':
                    text+=f+'\n'
                else:
                    files[referenceKey].append(f)
    else:
        text= 'The script was instructed NOT to attempt to co-align available files to the reference file with the same basename.'    

    # Patch for single file processing
    if singleFile:
        single_file_process = {}
        single_file_process[input_filename] = files[input_filename]
        del files
        files = {}
        files[input_filename] = single_file_process[input_filename]
    
    # Step3 : Write file handling into a text file
    with open(pathsInventory['resultsRegistrationAnalysesFolder']+'_file_handling.txt', 'a') as out:
        text += '\nFile alignments were performed as follows:'
        text += '\nReference files \tCo-aligned files \n'
        out.write(text)
        for f in files.keys():
            out.write(f)
            for c in files[f]:
                out.write('\t')
                out.write(c)
            out.write('\n')
       
    ############## REGISTRATION ##############      
    registeredFilesList=[]
    for REFfilename in files:
        fileNameNoExtension, _ = REFfilename.split(".")
        registeredFilesList.append(fileNameNoExtension)
        
        # Open the image file and read the image
        try:
            imageREF = gf.Image(pathsInventory['dataFolder']+REFfilename)
        except Exception as e:
            logging.getLogger(__name__).error(e)

        imageREF.imread()     

        # Calculate registration matrices
        tmats = registration_values(pathsInventory, imageREF)
        
        # Register and save - registration works with multidimensional files, as long as the TYX axes are specified
        coAlignment_list = files[REFfilename]
        coAlignment_list.append(REFfilename)

        for coalignedFilename in coAlignment_list:
            try:
                imageCoaligned = gf.Image(pathsInventory['dataFolder']+coalignedFilename)
            except Exception as e:
                logging.getLogger(__name__).error(e)
            
            imageCoaligned.imread()
    
            if imageCoaligned.sizes['T'] == 1:
                # In case there is no multiple timepoits -> there is nothing to register
                logging.getLogger(__name__).error('Image format.\nImage format not supported for the registration. Missing the time dimension.')
                return
            if imageCoaligned.sizes['F'] > 1:
                # In case there is no multiple timepoits -> there is nothing to register
                logging.getLogger(__name__).error('Image format.\nImage format not supported for the registration. Registration does not work with multiple fields of view.')
                return                    
            else:
                registration_with_tmat(pathsInventory, tmats, imageCoaligned)


def file_handling(path):
    ############# FILE HANDLING ##############
    content = os.listdir(path)
    #Get a list of image files
    image_files = gf.extract_suitable_files(content)
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
            image_baseName = image_f.split("_")[0]
            if reference_baseName == image_baseName:
                files[reference_matrix].append(image_f)
                print('\t',image_f)
    return files

def alignment_main(file_type, path, inventory, selected_file, skip_crop_decision):
    ###########################
    # Load image, mask and graph
    ###########################

    pathsInventory = build_paths_inventory(path)

    if file_type == 'transfMat':   
        tmat_path = path+selected_file
        tmat_int = read_transfMat(tmat_path)
        try:
            for image_path in inventory[selected_file]:
                try:
                    image = gf.Image(image_path)
                except Exception as e:
                    logging.getLogger(__name__).error(e)
                
                image.imread()
                registration_with_tmat(pathsInventory, tmat_int, image, skip_crop_decision)
                print(image.name,' DONE!')
        except Exception as e:
            logging.getLogger(__name__).error('Alignment failed.\nFile '+selected_file+' - '+str(e))
    else:
        try:
            image = gf.Image(os.path.join(path, selected_file))  
        except Exception as e:
            logging.getLogger(__name__).error(e)
                         
        try:
            tmat_path = inventory[selected_file]
            tmat_int = read_transfMat(tmat_path)
            image.imread()
            registration_with_tmat(pathsInventory, tmat_int, image, skip_crop_decision)
            print(image.name,' DONE!')
        except Exception as e:
            logging.getLogger(__name__).error('Alignment failed\nFile '+selected_file+' - '+str(e))

def view_main(path, image_name, inventory, skip_crop_decision):
    ###########################
    # Load image, mask and graph
    ###########################

    try:
        image = gf.Image(os.path.join(path, image_name)) 
    except Exception as e:
        logging.getLogger(__name__).error(e)
                               
    try: 
        transfMat_path = inventory[image_name]
        # Open transformation matrix and image
        transfMat = read_transfMat(transfMat_path)
        image.imread()
        pathsInventory = build_paths_inventory(path)
        image_registered = registration_with_tmat(pathsInventory, transfMat, image)

        
        viewer = napari.Viewer()
        for c in range(image.sizes['C']):
            if c == 0:
                viewer = napari.view_image(image_registered[0,:,c,:,:,:]) 
            else:
                viewer.add_image(image_registered, name="Channel "+str(c), blending="additive")
    except:
        logging.getLogger(__name__).error('Missing matrix.\nTransformation matrix not found for image '+image_name)


def list_transfMat(transfmat_path):
    all_files = os.listdir(transfmat_path)
    print(all_files)
    list_transfmat_files = [i for i in all_files if i.endswith('_transformationMatrix.txt')]
    print('\nTransformation matrices are:', list_transfmat_files)
    list_transfmat_files.sort()
    return list_transfmat_files

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
    np.savetxt(reference_matrix_path, tmat_updated, fmt = '%d, %d, %d, %d, %d, %d, %d, %d', header=headerText, delimiter='\t')
