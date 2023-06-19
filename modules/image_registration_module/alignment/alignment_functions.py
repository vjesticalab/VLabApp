import logging
import numpy as np
import os
import tifffile
from general import general_functions as gf
from modules.image_registration_module import registration_module_functions as rf
import napari


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
            image_baseName = gf.base_name(image_f)
            if reference_baseName == image_baseName:
                files[reference_matrix].append(image_f)
                print('\t',image_f)
    return files


def alignment_main(file_type, path, inventory, selected_file, skip_crop_decision):
    pathsInventory = rf.build_paths_inventory(path)

    if file_type == 'transfMat':   
        tmat_path = path+selected_file
        tmat_int = rf.read_transfMat(tmat_path)
        try:
            for image_path in inventory[selected_file]:
                image = gf.Image(image_path)
                image.imread()
                rf.registration_with_tmat(pathsInventory, tmat_int, image, skip_crop_decision)
                print(image.name,' DONE!')
        except Exception as e:
            logging.getLogger(__name__).error('Alignment failed.\nFile '+selected_file+' - '+str(e))
    else:
        image = gf.Image(os.path.join(path, selected_file))                   
        try:
            tmat_path = inventory[selected_file]
            tmat_int = rf.read_transfMat(tmat_path)
            image.imread()
            rf.registration_with_tmat(pathsInventory, tmat_int, image, skip_crop_decision)
            print(image.name,' DONE!')
        except Exception as e:
            logging.getLogger(__name__).error('Alignment failed\nFile '+selected_file+' - '+str(e))


def view_main(path, image_name, inventory, skip_crop_decision):
    image = gf.Image(os.path.join(path, image_name))                   
    try: 
        transfMat_path = inventory[image_name]
        # Open transformation matrix and image
        transfMat = rf.read_transfMat(transfMat_path)
        image.imread()
        pathsInventory = rf.build_paths_inventory(path)
        image_registered = rf.registration_with_tmat(pathsInventory, transfMat, image)

        
        viewer = napari.Viewer()
        for c in range(image.sizes['C']):
            if c == 0:
                viewer = napari.view_image(image_registered[0,:,c,:,:,:]) 
            else:
                viewer.add_image(image_registered, name="Channel "+str(c), blending="additive")
    except:
        logging.getLogger(__name__).error('Missing matrix.\nTransformation matrix not found for image '+image_name)

if __name__ == "__main__":
    folder_path = '/Users/aravera/Documents/CIG_Alexs/Registration/application/_VLSM_demoset/20230101_P0001_E0008_U003/'
    fileInventory = ''
    skip_crop_decision = ''
    alignment_main(folder_path, fileInventory, skip_crop_decision)