import numpy as np
import os
import tifffile
import time
from general import general_functions as gf

def alignment_main(folder_path, fileInventory, skip_crop_decision):
    start = time.time()
    save_folder = folder_path + gf.folder_name(folder_path) + '_registered_with_matrices'
    
    if not os.path.isdir(save_folder):
        os.makedirs(save_folder)
    if fileInventory == '':
        fileInventory = gf.file_handling(folder_path)
    
    txt = 'Working on folder' + folder_path + ' The name of containing folder path is ' + save_folder + ' The save folder path is ' + save_folder
    
    for reference_matrix in fileInventory.keys():
        #Load the transformation matrix
        tmat_path = folder_path+'/'+reference_matrix     
        tmat_int = gf.read_transfMat(tmat_path)
        txt += '\nLoaded transformation matrix ' + reference_matrix + ' to align images:'
        
        for image_file in fileInventory[reference_matrix]:
            txt += '\n\t' + image_file
            image_filepath = folder_path+'/' + image_file
            image, axes_inventory = gf.open_suitable_files(image_filepath)
            axes_number = len(axes_inventory)
    
            if axes_number < 3:
                # In case of images that are not 3D to avoid script breakig
                txt += '!!!Warning!!! Images must have at least 3 dimensions, tyx. Generating an image based on Transformation matrix dimensions to prevent script from braking.'           
                # Generat an 0s that that will be aligned and that will allow process to continue
                image_fake = np.zeros((tmat_int.shape[0], abs(max(tmat_int[:,2])) + abs(min(tmat_int[:,2])), abs(max(tmat_int[:,1])) + abs(min(tmat_int[:,1]))), dtype='uint8')
                registered_cropped_image = gf.register_with_tmat_multiD(tmat_int, image_fake, y_axis=1, x_axis=2, skip_decision=skip_crop_decision)
                
            elif axes_number == 3:            
                txt += 'is a 3 dimensionsional image. Assuming TYX order of axes'
                image_3D = image
                registered_cropped_image = gf.register_with_tmat_multiD(tmat_int, image_3D, y_axis=1, x_axis=2, skip_decision=skip_crop_decision)
            
            elif axes_number > 3:
                txt += 'is a multidimensional image. For files with specified axes (T,Y and X) alignment will be performed along the time(T)-axis'
                t_axis = axes_inventory['T'][0]
                y_axis = axes_inventory['Y'][0]
                x_axis = axes_inventory['X'][0]
                # Check if T-axis is in position 0
                if t_axis == 0:
                    image_4D = image
                else:
                    image_4D = np.swapaxes(image, t_axis, 0)           
                registered_cropped_image = gf.register_with_tmat_multiD(tmat_int, image_4D, y_axis,x_axis, skip_decision=skip_crop_decision)
            
            filenameWithoutExtension, _ = gf.file_name_split(image_file)
            registeredFilename = filenameWithoutExtension + '_registered.tif'
            registeredFilepath = save_folder + '/' + registeredFilename
            tifffile.imwrite(registeredFilepath, registered_cropped_image, imagej=True)                              
            
    with open(save_folder+'/registeredFiles.txt', 'a') as out:
        out.write(txt)
            
    end = time.time()
    print('\nExecution time on the folder is: ', end-start)


if __name__ == "__main__":
    folder_path = '/Users/aravera/Documents/CIG_Alexs/Registration/application/_VLSM_demoset/20230101_P0001_E0008_U003/'
    fileInventory = ''
    skip_crop_decision = ''
    alignment_main(folder_path, fileInventory, skip_crop_decision)