## [Unreleased]

### Added

* Z-projection module: check that output filenames are unique (i.e. to avoid two input files with same output filename).
* Segmentation module: check that output filenames are unique (i.e. to avoid two input files with same output filename).
* Cell tracking module: check that output filenames are unique (i.e. to avoid two input files with same output filename).

### Changed

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
