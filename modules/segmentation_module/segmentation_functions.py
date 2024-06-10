import os
import logging
from platform import python_version, platform
import numpy as np
import napari
import tifffile
from cellpose import models
from cellpose import version as cellpose_version
from torch import __version__ as torch_version
from general import general_functions as gf
from PyQt5.QtGui import QCursor
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QMessageBox
from aicsimageio.writers import OmeTiffWriter
from aicsimageio.types import PhysicalPixelSizes
from ome_types.model import CommentAnnotation
from concurrent.futures import ProcessPoolExecutor
import concurrent


def call_evaluate(index, model, image_2D, diameter, channels):
    """
    Wrapper function to track image index passed to Cellpose
    """
    return tuple([index]) + model.eval(image_2D, diameter=diameter, channels=channels)


def par_run_eval(image, mask, model, logger, tot_iterations, n_count, pbr=None):
    """
    Run model evaluation in parallel
    """
    with ProcessPoolExecutor(max_workers=n_count) as executor:
        future_reg = {
            executor.submit(
                call_evaluate,
                t,
                model,
                image[t, :, :],
                model.diam_labels, [0, 0]
            ): t for t in range(image.shape[0])
        }
        for future in concurrent.futures.as_completed(future_reg):
            try:
                index, mask[index, :, :], _, _ = future.result()
            except Exception:
                logger.exception("An exception occurred")
            else:
                logger.debug("cellpose segmentation %s/%s", index+1, tot_iterations)
                if pbr is not None:
                    pbr.set_description(f"cellpose segmentation {index+1}/{tot_iterations}")
                    pbr.update(1)

    return mask


def main(image_path, model_path, output_path, output_basename, channel_position, projection_type, projection_zrange, n_count, display_results=True, use_gpu=True, run_parallel=True):
    """
    Load image, segment with cellpose and save the resulting mask
    into `output_path` directory using filename <image basename>.ome.tif
    Note : we assume that the image first channel is ALWAYS BF and we will only apply the segmentation on that channel

    Parameters
    ----------
    image_path: str
        input image path. Must be a tif, ome-tif or nd2 image with axes T,Y,X
    model_path: str
        cellpose pretrained model path
    output_path: str
        output directory
    output_basename: str
        output basename. Output file will be saved as `output_path`/`output_basename`.ome.tif and `output_path`/`output_basename`.log.
    channel_position : int
        position of the channel to segment if the image is a c-stack
    projection_type : str
        type of projection to perform if the image is a z-stack
    projection_zrange: int or (int,int) or None
        the range of z sections to use for projection.
        If zrange is None, use all z sections.
        If zrange is an integer, use all z sections in the interval [z_best-zrange,z_best+zrange]
        where z_best is the Z corresponding to best focus.
        If zrange is tuple (zmin,zmax), use all z sections in the interval [zmin,zmax].
    display_results: bool, default True
        display input image and segmentation mask in napari
    use_gpu: bool, default False
        use GPU for cellpose segmentation
    run_parallel: bool
        activate fine grain parallelism
    """

    # Setup logging to file in output_path
    logger = logging.getLogger(__name__)
    logger.info("SEGMENTATION MODULE")
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
    buffered_handler.setFormatter(logging.Formatter('%(asctime)s (VLabApp - segmentation module) [%(levelname)s] %(message)s'))
    buffered_handler.setLevel(logging.INFO)
    logger.addHandler(buffered_handler)
    # Also save general.general_functions logger to the same file (to log information on z-projection)
    logging.getLogger('general.general_functions').addHandler(buffered_handler)

    # Cellpose_version already contains platform, python version and torch version
    logger.info("System info:")
    logger.info("- platform: %s", platform())
    logger.info("- python version: %s", python_version())
    logger.info("- numpy version: %s", np.__version__)
    logger.info("- cellpose version: %s", cellpose_version)
    logger.info("- torch version: %s", torch_version)
    if display_results:
        logger.info("- napari version: %s", napari.__version__)

    logger.info("Image path: %s", image_path)
    logger.info("Cellpose model path: %s", model_path)
    logger.info("Output path: %s", output_path)
    logger.info("Output basename: %s", output_basename)
    logger.debug("use_gpu: %s", use_gpu)
    logger.debug("display_results: %s", display_results)

    # Load image
    logger.debug("loading %s", image_path)
    try:
        image = gf.Image(image_path)
        image.imread()
    except:
        logging.getLogger(__name__).exception('Error loading image %s', image_path)
        # stop using logfile
        logger.removeHandler(logfile_handler)
        logging.getLogger('general.general_functions').removeHandler(logfile_handler)
        logger.removeHandler(buffered_handler)
        logging.getLogger('general.general_functions').removeHandler(buffered_handler)
        raise

    # Check 'F' axis has size 1
    if image.sizes['F'] != 1:
        logger.error('Image %s has a F axis with size > 1', str(image_path))
        # Close logfile
        logger.removeHandler(logfile_handler)
        logging.getLogger('general.general_functions').removeHandler(logfile_handler)
        logger.removeHandler(buffered_handler)
        logging.getLogger('general.general_functions').removeHandler(buffered_handler)
        raise TypeError(f"Image {image_path} has a F axis with size > 1")

    # Project Z axis if needed and select channel
    if image.sizes['Z'] > 1:
        logger.info('Preparing image to segment: performing Z-projection')
        image3D = image.zProjection(projection_type, projection_zrange)
    else:
        image3D = image.image
    # keep only selected channel ('C' axis)
    if image.sizes['C'] > channel_position:
        logging.getLogger(__name__).info('Preparing image to segment: selecting channel %s',channel_position)
        image3D = image3D[0,:,channel_position,0,:,:]
    else:
        logging.getLogger(__name__).error('Position of the channel given (%s) is out of range for image %s', channel_position, image.basename)
        # Close logfile
        logger.removeHandler(logfile_handler)
        logging.getLogger('general.general_functions').removeHandler(logfile_handler)
        logger.removeHandler(buffered_handler)
        logging.getLogger('general.general_functions').removeHandler(buffered_handler)
        raise TypeError(f"Position of the channel given ({channel_position}) is out of range for image {image.basename}")

    # Create cellpose model
    logger.debug("loading cellpose model %s", model_path)
    model = models.CellposeModel(gpu=use_gpu, pretrained_model=model_path)

    tot_iterations = image.sizes['T']

    if display_results:
        # Open image in napari
        viewer_images = napari.Viewer(title=image_path)
        image_napari = image3D
        # TCYX
        image_napari = image_napari[:, np.newaxis, :, :]
        viewer_images.add_image(image_napari, name="Input image")

        # TODO: find a way to use logging package instead?
        # Setup logging into napari window.

        # Set cursor to BusyCursor
        napari.qt.get_app().setOverrideCursor(QCursor(Qt.BusyCursor))
        napari.qt.get_app().processEvents()
        # Show activity dock & add napari progress bar
        viewer_images.window._status_bar._toggle_activity_dock(True)
        pbr = napari.utils.progress(total=tot_iterations)
    else:
        pbr = None

    # Cellpose segmentation
    logger.info("Cellpose segmentation (model diameter=%s)", model.diam_labels)

    iteration = 0
    mask = np.zeros(image3D.shape, dtype='uint16')
    if run_parallel and n_count > 1:
        mask = par_run_eval(image3D, mask, model, logger, tot_iterations, n_count, pbr)
    else:
        for t in range(image3D.shape[0]):
            iteration += 1
            image_2D = image3D[t, :, :]
            if display_results:
                # Logging into napari window
                pbr.set_description(f"cellpose segmentation {iteration}/{tot_iterations}")
                pbr.update(1)
            logger.debug("cellpose segmentation %s/%s", iteration, tot_iterations)
            mask[t, :, :], _, _ = model.eval(image_2D, diameter=model.diam_labels, channels=[0, 0])



    # Save the mask
    output_name = os.path.join(output_path, output_basename+".ome.tif")
    mask = mask[:, np.newaxis, :, :]
    logger.info("Saving segmentation mask to %s", output_name)
    ome_metadata=OmeTiffWriter.build_ome(data_shapes=[mask.shape],
                                         data_types=[mask.dtype],
                                         dimension_order=["TCYX"],
                                         channel_names=[['Segmentation mask']],
                                         physical_pixel_sizes=[PhysicalPixelSizes(X=image.physical_pixel_sizes[0], Y=image.physical_pixel_sizes[1], Z=image.physical_pixel_sizes[2])])
    ome_metadata.structured_annotations.append(CommentAnnotation(value=buffered_handler.get_messages(),namespace="VLabApp"))
    OmeTiffWriter.save(mask, output_name, ome_xml=ome_metadata)
    #buffered_handler.reset()


    if display_results:
        # Restore cursor
        napari.qt.get_app().restoreOverrideCursor()
        QMessageBox.information(viewer_images.window._qt_window, 'File saved', 'Mask saved to\n' + output_name)
        # Stop logging into napari window
        napari.qt.get_app().restoreOverrideCursor()
        viewer_images.window._status_bar._toggle_activity_dock(False)
        pbr.close()
        # Show mask in napari
        layer_mask = viewer_images.add_labels(mask, name="Cell mask")
        layer_mask.editable = False
        # In the current version of napari (v0.4.17), editable is set to True whenever we change the axis value by clicking on the corresponding slider.
        # This is a quick and dirty hack to force the layer to stay non-editable.
        layer_mask.events.editable.connect(lambda e: setattr(e.source,'editable',False))

    # stop using logfile
    logger.removeHandler(logfile_handler)
    logging.getLogger('general.general_functions').removeHandler(logfile_handler)
    logger.removeHandler(buffered_handler)
    logging.getLogger('general.general_functions').removeHandler(buffered_handler)
