import logging
import numpy as np
import os
from general import general_functions as gf
from modules.image_registration_module import registration_module_functions as rf
import tifffile
from pystackreg import StackReg

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
    pathsInventory = rf.build_paths_inventory(path)
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
                rf.registration_with_tmat(pathsInventory, tmats, imageCoaligned)
