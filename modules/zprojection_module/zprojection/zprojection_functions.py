import os
import logging
import tifffile
from general import general_functions as gf


def main(image_path, output_path, projection_type):
    """
    ...

    Parameters
    ----------
    image_path: str
        input image path
    output_path: str
        output directory
    projection_type: str
        type of the projection to perfrom

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
        logger.error(e)
    
    image.imread()
    projected_image = image.zProjection(projection_type)
    output_file_name = output_path+image.name+".tif"
    tifffile.imwrite(output_file_name, projected_image, metadata={'axes': 'FTCZYX'}, compression='zlib')

    logger.info("Projection performed and saved (%s)", output_file_name)

    # stop using logfile
    logger.removeHandler(logfile_handler)
