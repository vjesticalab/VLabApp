import os
import logging
import tifffile
from general import general_functions as gf


def main(image_path, output_path, projection_type, projection_zrange):
    """
    Perform z projection of the image given
    
    Parameters
    ---------------------
    image_path: str
        input image path
    output_path: str
        output directory
    projection_type: str
        type of the projection to perfrom
    projection_zrange: int
        the number of z sections on each side of the Z with best focus
        to use for for the projection.

    Saves
    ---------------------
    image: ndarry
        z-projection image, in output directory

    """

    # Setup logging to file in output_path
    logger = logging.getLogger(__name__)
    logger.info("Z-PROJECTION MODULE")
    if not os.path.isdir(output_path):
        logger.debug("creating: %s", output_path)
        os.makedirs(output_path)

    # Log to file
    logfile = os.path.join(output_path, os.path.splitext(os.path.basename(image_path))[0]+".log")
    logger.setLevel(logging.DEBUG)
    logger.debug("writing log output to: %s", logfile)
    logfile_handler = logging.FileHandler(logfile, mode='w')
    logfile_handler.setFormatter(logging.Formatter('%(asctime)s  [%(levelname)s] %(message)s'))
    logfile_handler.setLevel(logging.INFO)
    logger.addHandler(logfile_handler)

    # Also save general.general_functions logger to the same file (to log information on z-projection)
    logging.getLogger('general.general_functions').setLevel(logging.DEBUG)
    logging.getLogger('general.general_functions').addHandler(logfile_handler)

    # Load image
    logger.debug("loading %s", image_path)
    try:
        image = gf.Image(image_path)
        image.imread()
    except Exception as e:
        logging.getLogger(__name__).error('Error loading image '+image_path+'\n'+str(e))
        return

    # Check z existance in the image
    if image.sizes['Z'] == 0:
        logger.error('Image '+str(image_path)+' has no z dimension')
        return

    # Perform projection
    try:
        projected_image = image.zProjection(projection_type,projection_zrange)
    except Exception as e:
        logging.getLogger(__name__).error('Error loading image '+image_path+'\n'+str(e))
        return

    # Save the projection
    output_file_name = os.path.join(output_path, image.name+"_"+projection_type+("" if projection_type == "bestZ" else str(projection_zrange))+".tif")
    # TODO: properly deal with 'F' axis, i.e. the first 0 in projected_image[0,:,:,0,:,:] is problematic if there are more than one FOV.
    tifffile.imwrite(output_file_name, projected_image[0,:,:,0,:,:].astype('uint16'), metadata={'axes': 'TCYX'}, imagej=True, compression='zlib')
    logger.info("Projection performed and saved (%s)", output_file_name)

    print('Projection performed and saved '+output_file_name)

    # Close logfile
    logger.removeHandler(logfile_handler)
    logging.getLogger('general.general_functions').removeHandler(logfile_handler)


if __name__ == "__main__":
    image_path = '/Volumes/RECHERCHE/FAC/FBM/CIG/avjestic/zygoticfate/D2c/Lab_Data/20221111_P0001_E0008_U002/Sporulated-BF10/001_SP10.nd2'
    output_path = '/Users/aravera/Desktop/'
    projection_type = 'max'
    projection_zrange = 3
    main(image_path, output_path, projection_type, projection_zrange)
