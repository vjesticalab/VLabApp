import os
import logging
import numpy as np
import napari
import tifffile
from cellpose import models
from general import general_functions as gf


def main(image_path, model_path, output_path, display_results=True, use_gpu=False):
    """
    Load image from `image_path`, segment with cellpose and save the resulting masks
    into `output_path` directory using image basename (with .tif extension).

    Parameters
    ----------
    image_path: str
        input image path. Must be a tif or nd2 image with axes T,Y,X.
    model_path: str
        cellpose pretrained model path.
    output_path: str
        output directory.
    display_results: bool, default True
        display input image and segmentation masks in napari.
    use_gpu: bool, default False
        use GPU for cellpose segmentation.

    """

    # setup logging to file in output_path
    logger = logging.getLogger(__name__)
    logger.info("SEGMENTATION MODULE")
    if not os.path.isdir(output_path):
        logger.debug("creating: %s", output_path)
        os.makedirs(output_path)

    # log to file
    logfile = os.path.join(output_path, os.path.splitext(
        os.path.basename(image_path))[0]+".log")
    logger.setLevel(logging.DEBUG)
    logger.debug("writing log output to: %s", logfile)
    logfile_handler = logging.FileHandler(logfile, mode='w')
    logfile_handler.setFormatter(logging.Formatter(
        '%(asctime)s  [%(levelname)s] %(message)s'))
    logfile_handler.setLevel(logging.INFO)
    logger.addHandler(logfile_handler)

    logger.info("image_path: %s", image_path)
    logger.info("model_path: %s", model_path)
    logger.info("output_path: %s", output_path)
    logger.info("use_gpu: %s", use_gpu)
    logger.info("display_results: %s", display_results)

    # load image
    logger.debug("loading %s", image_path)
    input_image, axes = gf.open_suitable_files(image_path)

    # TODO: deal with Z axis (z-stack projection)
    if ''.join(list(axes.keys())).upper() != "CYX":
        raise TypeError(f'Input image is not CYX.\n({image_path})')

    if display_results:
        # show image in napari
        viewer_images = napari.Viewer(title=image_path)
        viewer_images.add_image(input_image, name="Input image")

    # cellpose: create model
    logger.debug("loading cellpose model %s", model_path)
    model = models.CellposeModel(gpu=use_gpu, pretrained_model=model_path)
    logger.info("model diameter:%s", model.diam_labels)

    if display_results:
        # TODO: find a way to use logging package instead?
        # TODO: do not import here.
        # Setup logging into napari window.
        # only import PyQt5 if needed (no need for PyQt5 dependency if display_results is False.
        from PyQt5.QtGui import QCursor
        from PyQt5.QtCore import Qt
        # set cursor to BusyCursor
        napari.qt.get_app().setOverrideCursor(QCursor(Qt.BusyCursor))
        napari.qt.get_app().processEvents()
        # show activity dock & add napari progress bar
        viewer_images.window._status_bar._toggle_activity_dock(True)
        pbr = napari.utils.progress(total=input_image.shape[0])

    # cellpose segmentation
    masks = np.zeros(input_image.shape, dtype='uint16')
    for i in range(input_image.shape[0]):
        if display_results:
            # logging into napari window.
            pbr.set_description(
                f"cellpose segmentation {i+1}/{input_image.shape[0]}")
            pbr.update(1)
        logger.debug("cellpose segmentation %s/%s", i+1, input_image.shape[0])
        masks[i], _, _ = model.eval(input_image[i],
                                    diameter=model.diam_labels,
                                    channels=[0, 0])

    if display_results:
        # stop logging into napari window
        # restore cursor
        napari.qt.get_app().restoreOverrideCursor()
        # hide dock & close progress bar
        viewer_images.window._status_bar._toggle_activity_dock(False)
        pbr.close()

    if display_results:
        # show masks in napari
        layer_masks = viewer_images.add_labels(masks, name="Cell masks")
        # do not allow edition
        layer_masks.editable = False

    # save masks
    output_file = os.path.join(output_path, os.path.splitext(
        os.path.basename(image_path))[0]+".tif")
    logger.info("saving segmentation masks to %s", output_file)
    tifffile.imwrite(output_file, masks, imagej=True, compression='zlib')

    # stop using logfile
    logger.removeHandler(logfile_handler)
