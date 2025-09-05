import os
import logging
import concurrent
from platform import python_version, platform
import numpy as np
import napari
from cellpose import models
from cellpose import version as cellpose_version
from torch import __version__ as torch_version
from torch import cuda, set_num_threads
from general import general_functions as gf
from PyQt5.QtGui import QCursor
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QMessageBox
from bioio.writers import OmeTiffWriter
from bioio import PhysicalPixelSizes
from ome_types.model import CommentAnnotation
from version import __version__ as vlabapp_version
from packaging.version import Version
try:
    from micro_sam import __version__ as microsam_version
    from micro_sam.automatic_segmentation import get_predictor_and_segmenter, automatic_instance_segmentation
    microsam_available = True
except ImportError:
    microsam_available = False


def remove_all_log_handlers():
    # remove all handlers for this module
    while len(logging.getLogger(__name__).handlers) > 0:
        logging.getLogger(__name__).removeHandler(logging.getLogger(__name__).handlers[0])
    # remove all handlers for general.general_functions
    while len(logging.getLogger('general.general_functions').handlers) > 0:
        logging.getLogger('general.general_functions').removeHandler(logging.getLogger('general.general_functions').handlers[0])


def run_cellpose(index, image_2D, model, diameter, cellprob_threshold, flow_threshold):
    """
    Wrapper function to track image index passed to Cellpose
    """
    return tuple([index]) + model.eval(image_2D, diameter=diameter, channels=[0, 0], cellprob_threshold=cellprob_threshold, flow_threshold=flow_threshold)


def parallel_run_cellpose(image, mask, model, diameter, cellprob_threshold, flow_threshold, logger, tot_iterations, nprocesses, pbr=None):
    """
    Run model evaluation in parallel
    """
    with concurrent.futures.ProcessPoolExecutor(max_workers=nprocesses) as executor:
        future_reg = {
            executor.submit(
                run_cellpose,
                t,
                image[t, :, :],
                model,
                diameter,
                cellprob_threshold,
                flow_threshold
            ): t for t in range(image.shape[0])
        }
        for future in concurrent.futures.as_completed(future_reg):
            try:
                index, mask[index, :, :], *_ = future.result()
            except Exception:
                logger.exception("An exception occurred")
                raise
            else:
                logger.debug("cellpose segmentation %s/%s", index+1, tot_iterations)
                if pbr is not None:
                    pbr.set_description(f"cellpose segmentation {index+1}/{tot_iterations}")
                    pbr.update(1)

    return mask


def run_microsam(index, image_2D, predictor, segmenter):
    """
    Wrapper function to track image index passed to Segment Anything for Microscopy
    """
    return (index, automatic_instance_segmentation(predictor=predictor, segmenter=segmenter, input_path=image_2D, verbose=False))


def parallel_run_microsam(image, mask, predictor, segmenter, logger, tot_iterations, nprocesses, pbr=None):
    """
    Run model evaluation in parallel
    """
    with concurrent.futures.ProcessPoolExecutor(max_workers=nprocesses) as executor:
        future_reg = {
            executor.submit(
                run_microsam,
                t,
                image[t, :, :],
                predictor,
                segmenter
            ): t for t in range(image.shape[0])
        }
        for future in concurrent.futures.as_completed(future_reg):
            try:
                index, mask[index, :, :] = future.result()
            except Exception:
                logger.exception("An exception occurred")
                raise
            else:
                logger.debug("Segment Anthing for Microscopy segmentation %s/%s", index+1, tot_iterations)
                if pbr is not None:
                    pbr.set_description(f"Segment Anthing for Microscopy segmentation {index+1}/{tot_iterations}")
                    pbr.update(1)

    return mask


def main(image_path, segmentation_method, cellpose_model_type, cellpose_model_path, cellpose_diameter, cellpose_cellprob_threshold, cellpose_flow_threshold, microsam_model_type, output_path, output_basename, channel_position, projection_type, projection_zrange, nprocesses, display_results=True, use_gpu=True, run_parallel=True):
    """
    Load image, segment with cellpose and save the resulting mask
    into `output_path` directory using filename `output_basename`.ome.tif.

    Parameters
    ----------
    image_path: str
        input image path. Must be a tif, ome-tif or nd2 image with axes T,Y,X
    segmentation_method: str
        Segmentation method ("cellpose" or "Segment Anything for Microscopy").
    cellpose_model_type: str
        cellpose model type. Either "User trained model" or one of the cellpose built-in model names (for cellpose 3: cyto, cyto2, cyto3, nuclei, tissuenet_cp3, livecell_cp3, yeast_PhC_cp3, yeast_BF_cp3, bact_phase_cp3, bact_fluor_cp3, deepbacs_cp3 or cyto2_cp3. For cellpose 4: cpsam).
    cellpose_model_path: str
        cellpose pretrained model path (only used if `cellpose_model_type` == "User trained model").
    cellpose_diameter: int
        expected cell diameter for cellpose  (only used if `cellpose_model_type` != "User trained model"). If 0, use cellpose built-in model to estimate diameter (available only for cellpose_model_type cyto, cyto2, cyto3, nuclei and cpsam). See cellpose documentation for more information https://cellpose.readthedocs.io/en/latest/index.html.
    cellpose_cellprob_threshold: float
        cellpose cellprob threshold. See cellpose documentation for more information https://cellpose.readthedocs.io/en/latest/index.html.
    cellpose_flow_threshold: float
        cellpose flow threshold. See cellpose documentation for more information https://cellpose.readthedocs.io/en/latest/index.html.
    microsam_model_type: str
        Segment Anything for Microscopy model type ("vit_h", "vit_l", "vit_b", "vit_l_lm", "vit_b_lm", "vit_l_em_organelles" or "vit_b_em_organelles").
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
    nprocesses: int
        number of processes for fine grain paralleleism.
    display_results: bool, default True
        display input image and segmentation mask in napari
    use_gpu: bool, default False
        use GPU for cellpose segmentation
    run_parallel: bool
        activate fine grain parallelism
    """

    try:
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
        logfile_handler.setFormatter(logging.Formatter('%(asctime)s (VLabApp - segmentation module) [%(levelname)s] %(message)s'))
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
        logger.info("- VLabApp version: %s", vlabapp_version)
        logger.info("- numpy version: %s", np.__version__)
        if segmentation_method == "cellpose":
            logger.info("- cellpose version: %s", cellpose_version)
        elif segmentation_method == "Segment Anything for Microscopy" and microsam_available:
            logger.info("- micro_sam version: %s", microsam_version)
        logger.info("- torch version: %s", torch_version)
        if display_results:
            logger.info("- napari version: %s", napari.__version__)

        logger.info("Input image path: %s", image_path)
        logger.info("Segmentation method: %s", segmentation_method)
        if segmentation_method == "cellpose":
            logger.info("Model type: %s", cellpose_model_type)
            if cellpose_model_type == "User trained model":
                logger.info("User trained model path: %s", cellpose_model_path)
            else:
                logger.info("Diameter: %s", cellpose_diameter)
            logger.info("cellprob threshold: %s", cellpose_cellprob_threshold)
            logger.info("flow threshold: %s", cellpose_flow_threshold)
        elif segmentation_method == "Segment Anything for Microscopy":
            logger.info("Model type: %s", microsam_model_type)
        logger.debug("use_gpu: %s", use_gpu)
        logger.debug("display_results: %s", display_results)

        # check
        if segmentation_method == "Segment Anything for Microscopy" and not microsam_available:
            logger.error('Segmentation method "Segment Anything for Microscopy" is not available')
            # Remove all handlers for this module
            remove_all_log_handlers()
            raise RuntimeError('Segmentation method "Segment Anything for Microscopy" is not available')

        # Load image
        logger.debug("loading %s", image_path)
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

        # Check 'F' axis has size 1
        if image.sizes['F'] != 1:
            logger.error('Image %s has a F axis with size > 1', str(image_path))
            # Remove all handlers for this module
            remove_all_log_handlers()
            raise TypeError(f"Image {image_path} has a F axis with size > 1")

        # Project Z axis if needed and select channel
        if image.sizes['Z'] > 1:
            logger.info('Preparing image to segment: performing Z-projection')
            image3D = image.z_projection(projection_type, projection_zrange)
        else:
            image3D = image.image
        # keep only selected channel ('C' axis)
        if image.sizes['C'] > channel_position:
            logging.getLogger(__name__).info('Preparing image to segment: selecting channel %s', channel_position)
            image3D = image3D[0, :, channel_position, 0, :, :]
        else:
            logging.getLogger(__name__).error('Position of the channel given (%s) is out of range for image %s', channel_position, image.basename)
            # Remove all handlers for this module
            remove_all_log_handlers()
            raise TypeError(f"Position of the channel given ({channel_position}) is out of range for image {image.basename}")

        tot_iterations = image.sizes['T']

        if display_results:
            # TODO: find a better solution to open a modal napari window.
            global viewer_images
            viewer_images = napari.Viewer(show=False, title=image_path)
            viewer_images.window._qt_window.setWindowModality(Qt.ApplicationModal)
            viewer_images.show()
            image_napari = image3D
            layer = viewer_images.add_image(image_napari, name="Input image")
            layer.editable = False
            # Set cursor to BusyCursor
            napari.qt.get_qapp().setOverrideCursor(QCursor(Qt.BusyCursor))
            napari.qt.get_qapp().processEvents()
            # Show activity dock & add napari progress bar
            viewer_images.window._status_bar._toggle_activity_dock(True)
            pbr = napari.utils.progress(total=tot_iterations)
        else:
            pbr = None

        # limit number of theads used by torch on CPU
        set_num_threads(1)

        if segmentation_method == "cellpose":
            # Create cellpose model
            if Version(cellpose_version).major == 4:
                if cellpose_model_type == "User trained model":
                    logger.debug("loading cellpose model %s", cellpose_model_path)
                    cellpose_model = models.CellposeModel(gpu=use_gpu, pretrained_model=cellpose_model_path)
                    cellpose_diameter = None
                else:
                    logger.debug("loading cellpose model %s", cellpose_model_type)
                    cellpose_model = models.CellposeModel(gpu=use_gpu, pretrained_model=cellpose_model_type)
                    if cellpose_diameter == 0:
                        cellpose_diameter = None
            elif Version(cellpose_version).major == 3:
                if cellpose_model_type == "User trained model":
                    logger.debug("loading cellpose model %s", cellpose_model_path)
                    cellpose_model = models.CellposeModel(gpu=use_gpu, pretrained_model=cellpose_model_path)
                    cellpose_diameter = cellpose_model.diam_labels
                elif cellpose_model_type in ['cyto', 'cyto2', 'cyto3', 'nuclei']:
                    logger.debug("loading cellpose model %s", cellpose_model_type)
                    cellpose_model = models.Cellpose(gpu=use_gpu, model_type=cellpose_model_type)
                    if cellpose_diameter == 0:
                        cellpose_diameter = None
                else:
                    logger.debug("loading cellpose model %s", cellpose_model_type)
                    cellpose_model = models.CellposeModel(gpu=use_gpu, model_type=cellpose_model_type)

            # Cellpose segmentation
            logger.info("Cellpose segmentation (diameter=%s)", cellpose_diameter)

            iteration = 0
            mask = np.zeros(image3D.shape, dtype='uint16')
            if run_parallel and nprocesses > 1:
                mask = parallel_run_cellpose(image3D, mask, cellpose_model, cellpose_diameter, cellpose_cellprob_threshold, cellpose_flow_threshold, logger, tot_iterations, nprocesses, pbr)
            else:
                for t in range(image3D.shape[0]):
                    iteration += 1
                    image_2D = image3D[t, :, :]
                    if display_results:
                        # Logging into napari window
                        pbr.set_description(f"cellpose segmentation {iteration}/{tot_iterations}")
                        pbr.update(1)
                    logger.debug("cellpose segmentation %s/%s", iteration, tot_iterations)
                    _, mask[t, :, :], *_ = run_cellpose(t, image_2D, cellpose_model, cellpose_diameter, cellpose_cellprob_threshold, cellpose_flow_threshold)
        elif segmentation_method == "Segment Anything for Microscopy":
            # create predictor and segmenter
            logger.debug("loading Segment Anything for Microscopy model %s", microsam_model_type)
            microsam_predictor, microsam_segmenter = get_predictor_and_segmenter(model_type=microsam_model_type, device=None if use_gpu else 'cpu')

            # Cellpose segmentation
            logger.info("Segment Anything for Microscopy segmentation")

            iteration = 0
            mask = np.zeros(image3D.shape, dtype='uint16')
            if run_parallel and nprocesses > 1:
                mask = parallel_run_microsam(image3D, mask, microsam_predictor, microsam_segmenter, logger, tot_iterations, nprocesses, pbr)
            else:
                for t in range(image3D.shape[0]):
                    iteration += 1
                    image_2D = image3D[t, :, :]
                    if display_results:
                        # Logging into napari window
                        pbr.set_description(f"Segment Anything for Microscopy segmentation {iteration}/{tot_iterations}")
                        pbr.update(1)
                    logger.debug("Segment Anything for Microscopy segmentation %s/%s", iteration, tot_iterations)
                    _, mask[t, :, :] = run_microsam(t, image_2D, microsam_predictor, microsam_segmenter)

        if use_gpu:
            cuda.empty_cache()

        # Save the mask
        output_name = os.path.join(output_path, output_basename+".ome.tif")
        logger.info("Saving segmentation mask to %s", output_name)
        ome_metadata = OmeTiffWriter.build_ome(data_shapes=[mask.shape],
                                               data_types=[mask.dtype],
                                               dimension_order=["TYX"],
                                               channel_names=[['Segmentation mask']],
                                               physical_pixel_sizes=[PhysicalPixelSizes(X=image.physical_pixel_sizes[0], Y=image.physical_pixel_sizes[1], Z=image.physical_pixel_sizes[2])])
        ome_metadata.structured_annotations.append(CommentAnnotation(value=buffered_handler.get_messages(), namespace="VLabApp"))
        for x in image_metadata:
            ome_metadata.structured_annotations.append(CommentAnnotation(value=x, namespace="VLabApp"))
        OmeTiffWriter.save(mask, output_name, ome_xml=ome_metadata)

        if display_results:
            # Show mask in napari
            layer_mask = viewer_images.add_labels(mask, name="Cell mask")
            layer_mask.editable = False
            # Restore cursor
            napari.qt.get_qapp().restoreOverrideCursor()
            QMessageBox.information(viewer_images.window._qt_window, 'File saved', 'Mask saved to\n' + output_name)
            # Stop logging into napari window
            napari.qt.get_qapp().restoreOverrideCursor()
            viewer_images.window._status_bar._toggle_activity_dock(False)
            pbr.close()

        # Remove all handlers for this module
        remove_all_log_handlers()

    except Exception:
        # Remove all handlers for this module
        remove_all_log_handlers()
        if display_results:
            # Restore cursor
            napari.qt.get_qapp().restoreOverrideCursor()
            try:
                # close napari window
                viewer_images.close()
            except:
                pass
        raise
