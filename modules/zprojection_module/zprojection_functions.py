import os
import logging
from platform import python_version, platform
import tifffile
from numpy import __version__ as np_version
from cv2 import __version__ as cv_version
from general import general_functions as gf
from aicsimageio.writers import OmeTiffWriter


def main(image_path, output_path, output_basename, projection_type, projection_zrange):
    """
    Perform z projection of the image given

    Parameters
    ---------------------
    image_path: str
        input image path
    output_path: str
        output directory
    output_basename: str
        output basename. Output file will be saved as `output_path`/`output_basename`.ome.tif and `output_path`/`output_basename`.log.
    projection_type: str
        type of the projection to perfrom
    projection_zrange:  int or (int,int) or None
        the range of z sections to use for projection.
        If zrange is None, use all z sections.
        If zrange is an integer, use all z sections in the interval [z_best-zrange,z_best+zrange]
        where z_best is the Z corresponding to best focus.
        If zrange is tuple (zmin,zmax), use all z sections in the interval [zmin,zmax].

    Saves
    ---------------------
    image: ndarray
        z-projection image, in output directory

    """

    # Setup logging to file in output_path
    logger = logging.getLogger(__name__)
    logger.info("Z-PROJECTION MODULE")
    if not os.path.isdir(output_path):
        logger.debug("creating: %s", output_path)
        os.makedirs(output_path)

    # Log to file
    logfile = os.path.join(output_path, output_basename+".log")
    logger.setLevel(logging.DEBUG)
    logger.debug("writing log output to: %s", logfile)
    logfile_handler = logging.FileHandler(logfile, mode='w')
    logfile_handler.setFormatter(logging.Formatter('%(asctime)s  [%(levelname)s] %(message)s'))
    logfile_handler.setLevel(logging.INFO)
    logger.addHandler(logfile_handler)

    # Also save general.general_functions logger to the same file (to log information on z-projection)
    logging.getLogger('general.general_functions').setLevel(logging.DEBUG)
    logging.getLogger('general.general_functions').addHandler(logfile_handler)

    logger.info("System info:")
    logger.info("- platform: %s", platform())
    logger.info("- python version: %s", python_version())
    logger.info("- numpy version: %s", np_version)
    logger.info("- opencv version: %s", cv_version)

    # Load image
    logger.info("Image path: %s", image_path)
    logger.info("Output path: %s", output_path)
    logger.info("Output basename: %s", output_basename)

    logger.debug("Loading %s", image_path)
    try:
        image = gf.Image(image_path)
        image.imread()
    except:
        logging.getLogger(__name__).exception('Error loading image %s', image_path)
        # Close logfile
        logger.removeHandler(logfile_handler)
        logging.getLogger('general.general_functions').removeHandler(logfile_handler)
        raise

    # Check z existence in the image
    if image.sizes['Z'] == 0:
        logger.error('Image %s has no z dimension', str(image_path))
        # Close logfile
        logger.removeHandler(logfile_handler)
        logging.getLogger('general.general_functions').removeHandler(logfile_handler)
        raise TypeError(f"Image {image_path} has no z dimension")

    # Check 'F' axis has size 1
    if image.sizes['F'] != 1:
        logger.error('Image %s has a F axis with size > 1', str(image_path))
        # Close logfile
        logger.removeHandler(logfile_handler)
        logging.getLogger('general.general_functions').removeHandler(logfile_handler)
        raise TypeError(f"Image {image_path} has a F axis with size > 1")

    # Perform projection
    try:
        projected_image = image.zProjection(projection_type, projection_zrange)
    except:
        logging.getLogger(__name__).exception('Error projecting image %s', image_path)
        # Close logfile
        logger.removeHandler(logfile_handler)
        logging.getLogger('general.general_functions').removeHandler(logfile_handler)
        raise

    # Save the projection
    output_file_name = os.path.join(output_path, output_basename+".ome.tif")
    # TODO: properly deal with 'F' axis.
    OmeTiffWriter.save(projected_image[0, :, :, 0, :, :], output_file_name, dim_order="TCYX")
    logger.info("Saving projected image to %s", output_file_name)

    print('Saving projected image to '+output_file_name)

    # Close logfile
    logger.removeHandler(logfile_handler)
    logging.getLogger('general.general_functions').removeHandler(logfile_handler)


if __name__ == "__main__":
    image_path = '/Volumes/RECHERCHE/FAC/FBM/CIG/avjestic/zygoticfate/D2c/Lab_Data/20221111_P0001_E0008_U002/Sporulated-BF10/001_SP10.nd2'
    output_path = '/Users/aravera/Desktop/'
    projection_type = 'max'
    projection_zrange = 3
    main(image_path, output_path, projection_type, projection_zrange)
