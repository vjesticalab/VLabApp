import os
import logging
import tifffile
from general import general_functions as gf


def main(image_path, output_path, projection_type):
    """
    Perform z projection of the image given
    ---------------------
    Parameters:
        image_path: str - input image path
        output_path: str - output directory
        projection_type: str - type of the projection to perfrom
    Save:
        z-projection image in the output directory

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

    # Load image
    logger.debug("loading %s", image_path)
    try:
        image = gf.Image(image_path)
    except Exception as e:
        logger.error('Error loading image '+image_path+' - '+str(e))
    image.imread()

    # Check z existance in the image
    if image.sizes['Z'] == 0:
        logger.error('Image '+str(image_path)+' has no z dimension')
        return

    # Perform projection
    projected_image = image.zProjection(projection_type)
    
    # Save the projection
    output_file_name = output_path+image.name+".tif"
    tifffile.imwrite(output_file_name, projected_image, metadata={'axes': 'FTCZYX'}, compression='zlib')
    logger.info("Projection performed and saved (%s)", output_file_name)

    # Close logfile
    logger.removeHandler(logfile_handler)
