import numpy as np
import time
from  general import general_functions as gf

def edit_main(reference_matrix_path, reference_timepoint, range_start, range_end):
    # Load the transformation matrix 
    tmat_int = gf.read_transfMat(reference_matrix_path)
    
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
