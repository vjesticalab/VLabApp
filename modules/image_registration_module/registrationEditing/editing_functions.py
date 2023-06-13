import numpy as np
import os
import time
from  general import general_functions as gf
from modules.image_registration_module import registration_module_functions as rf

def list_transfMat(transfmat_path):
    all_files = os.listdir(transfmat_path)
    print(all_files)
    list_transfmat_files = [i for i in all_files if i.endswith('_transformationMatrix.txt')]
    print('\nTransformation matrices are:', list_transfmat_files)
    list_transfmat_files.sort()
    return list_transfmat_files


def edit_main(reference_matrix_path, reference_timepoint, range_start, range_end):
    # Load the transformation matrix 
    tmat_int = rf.read_transfMat(reference_matrix_path)
    
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
