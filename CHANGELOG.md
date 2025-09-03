## [Unreleased]

### Added

### Changed

* Replace aicsimageio by bioio.

### Removed

### Fixed

* Cell tracking module: fix option to select missing vertices in the graph (when showing results in napari).








## [v2.4.2] 2025-09-01

### Changed

* Cell tracking module: add option to select missing vertices in the graph (when showing results in napari).

### Fixed

* Cell tracking module: fix a crash when input mask is empty.




## [v2.4.1] 2025-08-25

### Fixed

* Fix dependency error when using ome-zarr version 0.12.2 (force version 0.11.1).




## [v2.4.0] 2025-08-25

### Added

* Segmentation module: add option to use cellpose built-in models (cyto, cyto2, cyto3, nuclei, tissuenet_cp3, livecell_cp3, yeast_PhC_cp3, yeast_BF_cp3, bact_phase_cp3, bact_fluor_cp3, deepbacs_cp3, cyto2_cp3).
* Segmentation module: add option to use Segment Anything for Microscopy.
* File organization module: add option to select image cropping module files.
* Add coarse-grained parallelization (registration, z-projection, cell tracking, graph filtering, file conversion and image cropping modules).
* Add documentation (using MkDocs).
* Add small sample images and cellpose model fine-tuned for bright-field images of yeast cells.
* Add simple plugins system.
* Add a new Events selection module.
* Add About VLabApp.

### Changed

* Segmentation module: use cellpose v3 (instead of v2).
* Use napari v0.5.6 (instead of v0.4.19).
* Graph filtering module: when showing results in napari, images with more than T,Y,X axes are allowed (e.g. T,C,Z,Y,X).
* Image cropping module: raise an error if the cropping range does not include valid axis values (e.g. cropping range from 2 to 4 for a T axis of lenght 1).
* Registration: transformation matrix file format changed to 5 columns (x, y, keep, x_raw, y_raw) instead of 8 columns (timePoint, align_t_x, align_t_y, align_0_1, raw_t_x, raw_t_y, x, y). File with 8 columns are still accepted as input.

### Removed

* Remove Registration - Editing (batch) sub-module.
* Remove Events filter module.

### Fixed

* Cell tracking module: add missing axes to layer showing mask modifications (when showing results in napari).
* File organization module: also consider mp4 files.
* Registration module: check no duplicated output when coaligning files.
* Registration module: fix selection of files to coalign (e.g. when registering image1_BF.ome.tif, do not coalign image10_BF.ome.tif).
* Check images/masks are valid before starting processing (to avoid problems with parallel processing).
* Registration module (alignment): check distinct input files generate distinct output files.
* Cell tracking module: fix a crash when redrawing the mask and graph with option "show selected" labels.
* Ground truth generator module: fix a crash with image paths automatic filling.
* Fix documentation widget links with fragments not opening on Windows.
* Registration (Alignment): fix matching image to transformation matrix when image filename does not contain a '_'.
* Cell tracking module and Viewer module: fix a crash when clicking the Quit button in the mask/image viewer after the graph viewer has been closed.
* Graph filtering module and Events selection module: fix a crash when input mask and graph are empty.




## [v2.3.0] 2025-03-14

### Added

* Add a new Image cropping module.

### Changed

* Registration module: standardize interpretation of the timepoint range "From" and "To" parameters. Now "From" and "To" correspond to zero-based time frame indices and the timepoint range include both "From" and "To" values.
* Registration module: when using StackReg, round registration shifts to nearest integer.
* Rename sub-module "File conversion (to mp4 movies)" to "File conversion (lossy preview)" and add option to save to jpg.

### Removed

* Registration module, Editing (batch): remove option to plot registration matrix.

### Fixed

* Registration module with "timepoint range" option: mark timepoints outside of the selected range as ignored in the transformation matrix (set column align_0_1 to 0). For the registered image, save only only time frames within the selected range.
* Registration module with "timepoint range" option: fix a bug with the output transformation matrix (alignment values assigned to the wrong timepoint).
* Registration module: fix missing frame when saving registered without cropping.
* Cell tracking module: fix a crash when saving multiple times from napari.




## [v2.2.0] 2024-12-23

### Added

* Add a new File conversion module (to convert masks and graphs to various file formats and images and masks to mp4 movies).

### Changed

* Registration module, Editing (manual): control point color corresponds to modification status (red: modified, green: not modified) and transparency corresponds to frame range selection status (opaque: selected, semi-transparent: not selected).
* Metadata viewer: add image data type (dtype).
* Ground truth module: input images can have T or Z axis (but no C axis), add option to export cellpose training set (with optional out-of-focus images), add option to start with an existing mask, generate logfile, save metadata.
* File organization module: reorganize the GUI (only one "Files selection" box with 3 buttons "Copy files", "Move files" and "Remove files").
* List of modules on the left (instead of tabs on top).

### Removed

* Remove fusion_correction_module.

### Fixed

* Registration module, Editing (manual): guess image (resp. matrix) path based on the matrix (resp. image) path.
* Registration matrix viewer: Do not change image or matrix path when cancelling in file selection dialog.
* Pipeline module: fix checking of duplicated output when coaligning files during registration (on Windows).
* All modules: do not erase previous file path when cancelling in file selection dialog.
* Cell tracking and graph filtering modules: avoid duplicate "Manually editing mask" entries in metadata.
* Ground truth module: fix thresholding algorithm.
* Registration, Segmentation and Ground truth modules: open napari as a modal window to avoid potential problems with logfile when opening multiple napari windows.
* Cell tracking and graph filtering modules: quit if a napari window is already open to avoid potential problems with logfiles.
* Cell tracking and graph filtering modules: restore default status bar info after displaying logging information to napari status bar.
* Registration module: set maximum for time point range to 1000 (instead of 100).
* Events filter module: fix "Attribute does not exist" error.
* Fix file paths on Windows (use '\' instead of '/' everywhere).
* Always close log files on error.
* Restore cursor when closing napari window.
* File organization module: fix crash and show dialog with error messages.
* Show absolute path for the output filename when using custom output folder.
* To avoid problems with GraphML support in igraph on Windows: add a comment in README.md to install igraph using conda instead of pip.
* Ground truth module: input segmentation mask in a collapsible widget.




## [v2.1.0] 2024-10-11

### Added

* Add option to coalign files when using registration in a pipeline.

### Changed

* Registration matrix viewer and manual editor: "move view with alignment point" checked by default

### Fixed

* Cell tracking module: fix a problem with equations in METHODS.md.
* Event filter and GroundTruth modules: add brief documentation.
* Registration matrix viewer and manual editor: adjust text for control modifier to the OS (CTRL for Linux/Windows and CMD for Mac OS X) in the documentation.
* Registration module: More explicit error message when registration shift is too large resulting in an empty registered image after cropping.
* Metadata viewer: fix file type filter in file selection dialog.




## [v2.0.0] 2024-07-12

### Added

* Add a new File organization module (to export or clean files in output folders).
* Add a new Pipeline module.
* Add a new Viewer module: images, masks and/or cell tracking graphs viewer (linked graph and mask views, accept images with more than T,Y,X axes, e.g. T,C,Z,Y,X), new registration matrix and new metatadata viewer.
* Add a minimal documentation for all modules.
* Add version.py.
* Add metadata to .ome.tif, .graphmlz and .csv output files (with same content as in log file).
* Add channel_names and physiscal_pixel_sizes attributes to class Image and add it to saved images metadata.
* Graph filtering module: add "filename must include" and "filename must NOT include" filters as well as a "Delete" shortcut to table of input files (FileTableWidget2).
* Segmentation module: add option to perform z-projection and select a specific channel (C axis) before segmentation.

### Changed

* Change output file naming: directly save to output folder (without creating a sub-folder per module) and  add a per-module suffix to the input basename ("_vRG" for registration module, "_vPR<projection>" for Z-projection module, "_vSM" for segmentation module, "_vTG" for cell tracking module, "_vGF" for graph filtering module, "_vEF" for event filter module and "_GT" for groundtruth module).
* Use .ome.tif file extension for output files instead of using .tif extension (but saving in ome-tif format).
* Image class: shape and sizes attributes are populated in the constructor.
* Place the "filename must include" and "filename must NOT include" filters in a collapsible widget (FileListWidget and FileTableWidget2).
* Registration module: use "feature matching (SIFT)"  registration methods by default instead of "stackreg".
* Registration module: Add a new "Output" box in the GUI.
* Segmentation module: if input image contains multiple fields of view (F axis), raise an error instead of saving one image per field of view.
* Registration module: the z-projected image (evaluated when the input image contains a Z-stack) is not saved anymore.
* Registration module: save transformation matrices with .csv extension instead of .txt. Remove space character at the beginning of each field.
* Registration module: log to file.
* Registration module (Alignment tab): search for matching transformation matrices based on unique identifier (part of the basename before the first "_") and warn if multiple matches are found.
* Registration module (Alignment tab): replace list of images by a table showing images and matching matrices.
* Z-projection module: use same basename as projected file for log file.
* Cell tracking module: when showing results in napari, images with more than T,Y,X axes are allowed (e.g. T,C,Z,Y,X).
* Reorder tabs (and group Viewer, GroundTruth and File organization modules in a new "Tools" tab).
* Collapsible documentation sections.

### Fixed

* Fix handling of .ome.tif files (add to list of accepted image types, properly split basename/extension).
* Force non-editable napari layers to stay non-editable (In napari v0.4.17, changing an axis value using the corresponding slider makes the layer editable).
* Z-projection and registration modules: check that input image does not contain multiple fields of view (axis F).
* Registration module: when coaligning files with same unique identifier, only select image files (instead of all file types) and do not select images already aligned.
* Registration module: set random seed in "feature matching" registration methods for reproducibility.
* Segmentation module: remove default path for Cellpose model (it was pointing to a model trained on images with only Z section with best focus, which should not be used for images obtained with another Z-projection method).
* Segmentation module: warn that only the first channel is used for segmentation if input image contains more than one channel (axis C).
* Segmentation module: fix napari progress bar when using CPU.
* Segmentation module: fix CUDA out of memory when using multiple processes.
* Cell tracking and Viewer modules: fix loading empty cell tracking graph and mask in napari.
* Graph filtering module: fix evaluation of number of stable frames before/after cell divisions/fusions.
* Event filter module: close log file when leaving.
* Image class: raise an error if get_TYXarray() is used with a non-TYX image (instead of silently returning the array at position 0 for F, C and Z axes).




## [v1.5.0] 2024-03-21

### Added

* Manual correction of registration matrix with napari (registration module).

### Changed

* Update installation instructions

### Fixed

* Fix the "AttributeError: module 'numpy' has no attribute 'int'" due to removal of numpy.int in numpy 1.24.




## [v1.4.1] 2024-03-12

### Added

* Add a "Delete" shortcut to list of input files (DropFilesListWidget).
* Add "filename must NOT include" filter to list of input files (FileListWidget).

### Fixed

* bugfix: In list of input files (FileListWidget) do not reject all files when "file types" filter is empty.




## [v1.4.0] 2024-03-11

### Added

* Add optional registration methods "feature matching" (with ORB, BRISK, AKAZE or SIFT algorithm) to Registration module.




## [v1.3.1] 2024-03-07

### Added
* Fusion timepoint correction events_filter module
* Savecrop options for saving single fusion cropped events in events_filter module
* Registration for a fixed timepoint range

### Changed
* Name of graph_event_filter in events_filter
* Minor changes in the labels as the group suggested

### Removed

### Fixed

* Fix a bug with image cropping in image registration




## [v1.3.0] 2023-12-15

### Added

* Registration module: Add option to specify number of processes.
* Add parallelization to Segmentation module.

### Changed

* Registration module: add error collection and reporting to Registration tab.




## [v1.2.2] 2023-12-11

### Changed

* Registration module: to avoid interruptions during batch processing, errors are collected during the run and reported only at the end using a new dialog with a status summary table.

### Fixed

* Fix logging level.




## [v1.2.1] 2023-11-23

### Changed

* Use a more robust Z-projection method (tenengrad variance).
* The tiff saving format has been changed to the ome tiff format, mainly because it is more easily readable by imagej.

### Fixed

* Fix a typo in registration module (error "Edit object has no attribute matrices_listB")



## [v1.2.0] 2023-11-10

### Added

* Z-projection, Segmentation, Cell tracking and Graph filtering module: check that output filenames are unique (i.e. to avoid two input files with same output filename).

### Changed

* Z-projection, Segmentation, Cell tracking and Graph filtering module: to avoid interruptions during batch processing, errors are collected during the run and reported only at the end using a new dialog with a status summary table.

### Removed

* Segmentation module: remove option to use GPU (always try to use GPU).

### Fixed

* Fix a crash in segmentation module when dropping a file to the cellpose model text box.




## [v1.1.0] 2023-11-06

### Added

* Add batch processing to Graph filtering module.
* Add 'OPTIONS' menu into Graph filtering module.
* Add batch processing to Cell tracking module.
* Add optional registration method "phase correlation" to Registration module.
* Add parallelization into Registration module (lib: multiprocessing).
  (Note that the parellilization works on multiple images and not on the analysis of a single image)
* Add 'OPTIONS' menu into Registration module
* Add a description of the methods in cell_tracking_module.
* Add a description of the methods in zprojection_module.


### Changed

* Graph filtering module: save to input mask folder instead of input image folder by default.
* Cell tracking module: save to input mask folder instead of input image folder by default.
* Z-projection method improved with option to project a user-specified range of Z sections (all, fixed range, only best focus or window around best focus).


### Fixed

* Fix a crash in graph filtering module when not removing logging handlers.
* Bux fix in graph filtering module: filtering cell area for at least one cell was filtering on all cells instead of at least one cell.
* Small bugs in Registration module
* Bug into Aligment: with edited transformation matrices we weren't cropping the selected timepoints




## [v1.0.0] 2023-07-13

First release
