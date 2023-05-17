'''
This script takes a single file from a folder containing .nd2 or .tif images with the following naming structure
    smp00_Bnd2
    smp00_WL520.nd2
    
    smp01_Btif
    smp01_WL614.tif
    
    smp02_Bnd2
    smp02_WL405.tif
    *** Note that the same basename (the string preceeding the underscore character _)
        is shared by all channels from the same biological sample
        
The script takes the user specified channel to:  
    1. Calculate a transformation matrix which is saved in the following format:
        # timePoint, align_t_x, align_t_y, align_0_1, raw_t_x, raw_t_y
        1, 0.000000, 0.000000, 1, 0.000000, 0.000000
        2, 12.000000, 3.000000, 1, 12.000000, 3.000000
        3, 20.000000, 6.000000, 1, 20.000000, 6.000000
        4, 23.000000, 7.000000, 1, 23.000000, 7.000000
        5, 33.000000, 5.000000, 1, 33.000000, 5.000000
        6, 57.000000, 0.000000, 1, 57.000000, 0.000000 
        *** Note that downstream applications should NOT modify columns 1st, 5th and 6th colum

    2. Align the image used for transformation matrix calculation
    3. Optional(user specified): Co-align all the files with the same basename preceeding the underscore character _
    4. Invokes the evaluation script that reports the quality of registration

Function main() description
    main(path, referenceIdentifier, coalignNonReferenceFiles)
    inputs:
        path:   Path to folder that contains images for alignment; 
                Note that the path string should end with '/'
                e.g. '/Users/admin/Desktop/Data/20221226a_P0002_E0008_U002/'

        referenceIdentifier:    A string that is unique to the files used to calculate the registration
                                e.g. '_BF'

        coalignNonReferenceFiles:   True or False value to co-align or not files with the same basename

Registry of observed problems:
    1. The evaluation module fails when registered files have different number of timepoints

'''
import numpy as np
import os
from general import general_functions as gf

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
        
    # Create path to results
    pathsInventory = gf.build_paths_inventory(path)
    
    for pathCreate in pathsInventory:
        if not os.path.isdir(pathsInventory[pathCreate]):
            os.makedirs(pathsInventory[pathCreate])

    # File handling
    content = os.listdir(path)
    suitable_files = gf.extract_suitable_files(content)
      
    # File dictionary: keys - reference files for registration
    #                  values - list of files that are to be aligned with the reference
    files = {}

    # Step1 : Build dictionary keys from files that contain the identifier string
    for f in suitable_files:
        if referenceIdentifier in f:
            files[f] = []
    referenceFiles = list(files.keys())
    
    # Step2 : Introduce dictionary values that match the dictionary keys
    # This is an optional step that determines whether only reference files will be aligned
    if coalignNonReferenceFiles:   
        text= 'The script co-aligned available files to the reference file with the same basename.\n Image files that lack a registration reference are:\n'
        for f in suitable_files:
            if referenceIdentifier not in f:
                matchingBasename = gf.base_name(f)
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
        single_file_process={}
        single_file_process[input_filename]=files[input_filename]
        del files
        files={}
        files[input_filename]=single_file_process[input_filename]
    
    # Step3 : Write file handling into a text file
    with open(pathsInventory['resultsRegistrationAnalysesFolder']+'_file_handling.txt', 'a') as out:
        text+= '\nFile alignments were performed as follows:'
        text+= '\nReference files \tCo-aligned files \n'
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
        fileNameNoExtension, fileExtension = gf.file_name_split(REFfilename)
        registeredFilesList.append(fileNameNoExtension)
        
        # Open file with nd2reader or tiffle depending on format
        imgREF, axesREF = gf.open_suitable_files(pathsInventory['dataFolder']+REFfilename)
        # !!!! CHECK IF IT WORKS WITH MULTIDIMENSIONAL REF FILES       

        # Calculate registration matrices
        tmats = gf.registration_values(pathsInventory, imgREF, REFfilename)
        
        # Register and save - registration works with multidimensional files, as long as the TYX axes are specified
        coAlignment_list = files[REFfilename]
        coAlignment_list.append(REFfilename)

        for coalignedFilename in coAlignment_list:
            imgCoaligned, axes_inventory = gf.open_suitable_files(pathsInventory['dataFolder']+coalignedFilename)
            axes_number=len(axes_inventory)
    
            if axes_number < 3:
                #In case of images that are 2D to avoid script breaking generate an array of 0s that will be aligned
                image_fake = np.zeros((tmats.shape[0],abs(max(tmats[:,2]))+abs(min(tmats[:,2])),abs(max(tmats[:,1]))+abs(min(tmats[:,1]))), dtype='uint8')
                gf.registration_with_tmat_multiD(pathsInventory, tmats, image_fake, coalignedFilename, y_axis=1, x_axis=2, axes_positions='TYX')
                                
            elif axes_number == 3:
                #In case of 3D images, TYX axes order is assumed
                gf.registration_with_tmat_multiD(pathsInventory, tmats, imgCoaligned, coalignedFilename, y_axis=1, x_axis=2, axes_positions='TYX')
                               
            elif axes_number > 3:
                # Example of axes_inventory = {'T': [0, 120],  'Z': [1, 3],  'C': [2, 2],  'Y': [3, 275], 'X': [4, 390]}
                y_axis = axes_inventory['Y'][0]
                x_axis = axes_inventory['X'][0]
                axes_positions = ''
                for el in sorted(((v,k) for k,v in axes_inventory.items())):
                    axes_positions += el[1]          
                gf.registration_with_tmat_multiD(pathsInventory, tmats, imgCoaligned, coalignedFilename, y_axis, x_axis, axes_positions)
