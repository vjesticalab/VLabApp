## [Unreleased]

### Added

* Graph filtering module: add "filename must include" and "filename must NOT include" filters to table of input files (FileTableWidget2).
* Graph filtering module: Add a "Delete" shortcut to table of input files (FileTableWidget2).
* Segmentation module: add option to perform z-projection and select a specific channel (C axis) before segmentation.
* Add a new "file organization" module.
* Add metadata to .ome.tif, .graphmlz and .csv output files (with same content as in log file).
* Add channel_names and physiscal_pixel_sizes attributes to class Image.
* For .ome.tif output, add channel_names and physiscal_pixel_sizes to metadata.
* Add version.py.
* Viewer module: new registration matrix viewer.
* Viewer module: new metadata viewer.
* Add a minimal documentation for all modules.
* Add a new "pipeline" module.

### Changed

* Image class: shape and sizes attributes are populated in the constructor.
* Z-projection module: change output file naming (do not create a zprojection/ sub-folder, add _vPR<projection> suffix, use same basename as projected file for log file).
* GroundTruth module: change output file naming (do not create a ground_truth/ sub-folder, add _vGT suffix).
* Segmentation module: change output file naming (do not create a segmentation_masks/ sub-folder, add _vSM suffix instead of _mask suffix).
* Segmentation module: if input image contains multiple fields of view (F axis), raise an error instead of saving one image per field of view.
* Cell tracking module: change output file naming (do not create a cell_tracking/ sub-folder, add _vTG suffix instead of _mask and _graph suffixes).
* Graph filtering module: change output file naming (do not create a graph_filtering/ sub-folder, add _vGF suffix instead of _mask and _graph suffixes).
* Registration module: the z-projected image (evaluated when the input image contains a Z-stack) is not saved anymore.
* Registration module: save transformation matrices with .csv extension instead of .txt. Remove space character at the beginning of each field.
* Registration module: change output file naming (do not create a registration/ nor registration/transf_matrices/ sub-folders, add _vRG suffix instead of _registered and _transformationMatrix suffixes). Add a new "Output" box in the GUI.
* Registration module (Alignment tab): search for matching transformation matrices based on unique identifier (part of the basename before the first "_") and warn if multiple matches are found.
* Event filter module: change output file naming (do not create a event_filter/ sub-folder, add _vEF suffix instead of _mask, _graph and _dictionary suffixes).
* Registration module: log to file.
* Use .ome.tif file extension for output files instead of using .tif extension (but saving in ome-tif format).
* Place the "filename must include" and "filename must NOT include" filters in a collapsible widget (FileListWidget and FileTableWidget2).
* Registration module: use "feature matching (SIFT)"  registration methods by default instead of "stackreg".
* New viewer for images, masks and/or cell tracking graphs (allow image with more than T,Y,X axes, such as T,C,Z,Y,X).
* Cell tracking module: when showing results in napari, images with more than T,Y,X axes are allowed (e.g. T,C,Z,Y,X).
* Reorder tabs.
* Collapsible documentation sections.

### Removed

### Fixed

* Z-projection module: check that input image does not contain multiple fields of view (axis F).
* Segmentation module: remove default path for Cellpose model (it was pointing to a model trained on images with only Z section with best focus, which should not be used for images obtained with another Z-projection method).
* Segmentation module: warn that only the first channel is used for segmentation if input image contains more than one channel (axis C).
* Image class: raise an error if get_TYXarray() is used with a non-TYX image.
* Registration module: when coaligning files with same unique identifier, only select image files (instead of all file types) and do not select images already aligned.
* Registration module: check that input image does not contain multiple fields of view (axis F).
* Fix handling of .ome.tif files.
* Force non-editable napari layers to stay non-editable (In napari v0.4.17, changing an axis value using the corresponding slider makes the layer editable).
* Set random seed in "feature matching" registration methods for reproducibility.
* Segmentation module: fix napari progress bar when using CPU.
* Close log file when leaving events_filter module.
* Graph filtering module: fix evaluation of number of stable frames before/after cell divisions/fusions.


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
