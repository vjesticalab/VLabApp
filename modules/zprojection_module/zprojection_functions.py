import os
import logging
from platform import python_version, platform
from numpy import __version__ as np_version
from cv2 import __version__ as cv_version
from general import general_functions as gf
from aicsimageio.writers import OmeTiffWriter
from aicsimageio.types import PhysicalPixelSizes
from ome_types.model import CommentAnnotation
from version import __version__ as vlabapp_version


def remove_all_log_handlers():
    # remove all handlers for this module
    while len(logging.getLogger(__name__).handlers) > 0:
        logging.getLogger(__name__).removeHandler(logging.getLogger(__name__).handlers[0])
    # remove all handlers for general.general_functions
    while len(logging.getLogger('general.general_functions').handlers) > 0:
        logging.getLogger('general.general_functions').removeHandler(logging.getLogger('general.general_functions').handlers[0])


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

    try:
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
        logfile_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
        logfile_handler.setLevel(logging.INFO)
        logger.addHandler(logfile_handler)
        # Also save general.general_functions logger to the same file (to log information on z-projection)
        logging.getLogger('general.general_functions').setLevel(logging.DEBUG)
        logging.getLogger('general.general_functions').addHandler(logfile_handler)

        # Log to memory
        buffered_handler = gf.BufferedHandler()
        buffered_handler.setFormatter(logging.Formatter('%(asctime)s (VLabApp - z-projection module) [%(levelname)s] %(message)s'))
        buffered_handler.setLevel(logging.INFO)
        logger.addHandler(buffered_handler)
        # Also save general.general_functions logger to the same file (to log information on z-projection)
        logging.getLogger('general.general_functions').addHandler(buffered_handler)

        logger.info("System info:")
        logger.info("- platform: %s", platform())
        logger.info("- python version: %s", python_version())
        logger.info("- VLabApp version: %s", vlabapp_version)
        logger.info("- numpy version: %s", np_version)
        logger.info("- opencv version: %s", cv_version)

        # Load image
        logger.info("Input image path: %s", image_path)
        logger.info("Output path: %s", output_path)
        logger.info("Output basename: %s", output_basename)

        logger.debug("Loading %s", image_path)
        try:
            image = gf.Image(image_path)
            image.imread()
        except Exception:
            logging.getLogger(__name__).exception('Error loading image %s', image_path)
            # Remove all handlers for this module
            remove_all_log_handlers()
            raise

        # load image metadata
        image_metadata = []
        if image.ome_metadata:
            for x in image.ome_metadata.structured_annotations:
                if isinstance(x, CommentAnnotation) and x.namespace == "VLabApp":
                    if len(image_metadata) == 0:
                        image_metadata.append("Metadata for "+image.path+":\n"+x.value)
                    else:
                        image_metadata.append(x.value)

        # Check z existence in the image
        if image.sizes['Z'] == 0:
            logger.error('Image %s has no z dimension', str(image_path))
            # Remove all handlers for this module
            remove_all_log_handlers()
            raise TypeError(f"Image {image_path} has no z dimension")

        # Check 'F' axis has size 1
        if image.sizes['F'] != 1:
            logger.error('Image %s has a F axis with size > 1', str(image_path))
            # Remove all handlers for this module
            remove_all_log_handlers()
            raise TypeError(f"Image {image_path} has a F axis with size > 1")

        # Perform projection
        try:
            projected_image = image.z_projection(projection_type, projection_zrange)
        except Exception:
            logging.getLogger(__name__).exception('Error projecting image %s', image_path)
            # Remove all handlers for this module
            remove_all_log_handlers()
            raise

        # Save the projection
        output_file_name = os.path.join(output_path, output_basename+".ome.tif")
        # TODO: properly deal with 'F' axis.
        logger.info("Saving projected image to %s", output_file_name)
        ome_metadata = OmeTiffWriter.build_ome(data_shapes=[projected_image[0, :, :, 0, :, :].shape],
                                               data_types=[projected_image[0, :, :, 0, :, :].dtype],
                                               dimension_order=["TCYX"],
                                               channel_names=[image.channel_names],
                                               physical_pixel_sizes=[PhysicalPixelSizes(X=image.physical_pixel_sizes[0], Y=image.physical_pixel_sizes[1], Z=image.physical_pixel_sizes[2])])
        ome_metadata.structured_annotations.append(CommentAnnotation(value=buffered_handler.get_messages(), namespace="VLabApp"))
        for x in image_metadata:
            ome_metadata.structured_annotations.append(CommentAnnotation(value=x, namespace="VLabApp"))
        OmeTiffWriter.save(projected_image[0, :, :, 0, :, :], output_file_name, ome_xml=ome_metadata)

        # Remove all handlers for this module
        remove_all_log_handlers()

    except Exception:
        # Remove all handlers for this module
        remove_all_log_handlers()
        raise
