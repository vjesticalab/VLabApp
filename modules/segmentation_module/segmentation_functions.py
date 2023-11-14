import os
import logging
import numpy as np
import napari
import tifffile
from cellpose import models
from cellpose import version_str as cellpose_version
from general import general_functions as gf
from PyQt5.QtGui import QCursor
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QMessageBox
from aicsimageio.writers import OmeTiffWriter
from concurrent.futures import ProcessPoolExecutor
import concurrent


def call_evaluate(index, model, image_2D, diameter, channels):
    """
    Wrapper function to track image index passed to Cellpose
    """
    return tuple([index]) + model.eval(image_2D, diameter=diameter, channels=channels)


def par_run_eval(image, mask, model, f, logger, tot_iterations):
    """
    Run model evaluation in parallel
    """

    with ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
        future_reg = {
            executor.submit(
                call_evaluate,
                t,
                model,
                image.image[f, t, 0, 0, :, :],
                model.diam_labels, [0, 0]
            ): t for t in range(image.sizes['T'])
        }
        for future in concurrent.futures.as_completed(future_reg):
            try:
                index, mask[index, :, :], _, _ = future.result()
            except Exception:
                logger.exception("An exception occurred")
            else:
                logger.info("cellpose segmentation %s/%s", index, tot_iterations)

    return mask


def main(image_path, model_path, output_path, output_basename, display_results=True, use_gpu=True, run_parallel=True):
    """
    Load image, segment with cellpose and save the resulting mask
    into `output_path` directory using filename <image basename>_mask.tif
    Note : we assume that the image first channel is ALWAYS BF and we will only apply the segmentation on that channel

    Parameters
    ----------
    image_path: str
        input image path. Must be a tif or nd2 image with axes T,Y,X
    model_path: str
        cellpose pretrained model path
    output_path: str
        output directory
    output_basename: str
        output basename. Output file will be saved as `output_path`/`output_basename`_mask.tif and `output_path`/`output_basename`.log.
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
    logfile_handler.setFormatter(logging.Formatter('%(asctime)s  [%(levelname)s] %(message)s'))
    logfile_handler.setLevel(logging.INFO)
    logger.addHandler(logfile_handler)

    # Cellpose_version already contains platform, python version and torch version
    logger.info("System info: %s\nnumpy version: %s\nnapari version: %s", cellpose_version, np.__version__, napari.__version__)
    logger.info("image: %s", image_path)
    logger.info("cellpose model: %s", model_path)
    logger.info("output: %s", output_path)
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
        raise

    # Create cellpose model
    logger.debug("loading cellpose model %s", model_path)
    model = models.CellposeModel(gpu=use_gpu, pretrained_model=model_path)

    tot_iterations = image.sizes['Z']*image.sizes['T']*image.sizes['F']

    if display_results:
        # Open image in napari
        viewer_images = napari.Viewer(title=image_path)
        image_napari = image.get_TYXarray()
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

    # Cellpose segmentation
    logger.info("Cellpose segmentation (model diameter=%s)", model.diam_labels)

    iteration = 0
    multiple_fov = True if image.sizes['F'] > 1 else False
    for f in range(image.sizes['F']):
        mask = np.zeros((image.sizes['T'], image.sizes['Y'], image.sizes['X']), dtype='uint16')
        if run_parallel:
            mask = par_run_eval(image, mask, model, f, logger, tot_iterations)
        else:
            for t in range(image.sizes['T']):
                # Always assuming BF in channel=0 and only one Z channel
                iteration += 1
                image_2D = image.image[f, t, 0, 0, :, :]
                if display_results:
                    # Logging into napari window
                    pbr.set_description(f"cellpose segmentation {iteration}/{tot_iterations}")
                    pbr.update(1)
                logger.info("cellpose segmentation %s/%s", iteration, tot_iterations)
                mask[t, :, :], _, _ = model.eval(image_2D, diameter=model.diam_labels, channels=[0, 0])



        # Save image for each FoV
        if multiple_fov:
            output_name_originalimage = os.path.join(output_path, output_basename+"_FoV"+str(f+1)+".tif")
            fov_image = image.get_TYXarray()
            fov_image = fov_image[:, np.newaxis, :, :]
            OmeTiffWriter.save(fov_image, output_name_originalimage, dim_order="TCYX")
    
            output_name = os.path.join(output_path, output_basename+"_FoV"+str(f+1)+"_mask.tif")
        else:
            output_name = os.path.join(output_path, output_basename+"_mask.tif")
        # Save the mask
        mask = mask[:, np.newaxis, :, :]
        OmeTiffWriter.save(mask, output_name, dim_order="TCYX")

        logger.info("Saving segmentation masks to %s", output_name)

        if display_results:
            QMessageBox.information(viewer_images.window._qt_window, 'File saved', 'Masks saved to\n' + output_name)

    if display_results:
        # Stop logging into napari window & restore cursor
        napari.qt.get_app().restoreOverrideCursor()
        viewer_images.window._status_bar._toggle_activity_dock(False)
        pbr.close()
        # Show mask in napari
        layer_mask = viewer_images.add_labels(mask, name="Cell mask")
        layer_mask.editable = False

    # stop using logfile
    logger.removeHandler(logfile_handler)
