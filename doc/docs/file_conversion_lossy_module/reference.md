# File conversion (lossy preview)

This module exports images and segmentation masks to small file-size preview movies (mp4) or images (jpg).
 The resulting mp4 movies or jpg images are encoded using lossy compression, which results in data loss and distortion. These files should not be used for scientific applications. In addition, when converting to mp4 movie, X and Y axes are resized to the nearest multiple of 16.


## Input files

A list of multi-dimensional images or masks with at least `X` and `Y` axes, and optionally `C`, `Z` and `T` axes (see [File formats - images and masks](../general/files.md#images-and-masks) for more information).

To populate the list, use the <kbd>Add file</kbd>, <kbd>Add folder</kbd> and <kbd>Remove selected</kbd> buttons to add images or masks, folder (all images and masks inside the folder) or remove files from the list. Alternatively, files and folder can be dragged and dropped from an external file manager.

When adding files or folders, only files satisfying all filters (click on `▶` above the list to show filters) are added to the list.  By default, only files with a filename ending with one of the accepted file extensions (`.nd2`, `.tif`, `.tiff`, `.ome.tif`, `.ome.tiff`) are accepted.


## Parameters

Output folder
: Either use each input image or mask folder as output folder or specify a
custom output folder. To select a custom folder, either paste the path
into the text box, click on the <kbd>Browse</kbd> button, or drag and drop a
folder from an external file manager. Be careful when using a custom folder: if
two input files share the same filename (from different folders), the
output for both files will be written to the same output file,
resulting in data corruption.

Output suffix
: The output filename will correspond to the input filename with an
additional optional user defined suffix (containing only `a-z`, `A-Z`,
`0-9` and `-` characters). The resulting output filenames are shown
below the suffix.

Input types
: Images and segmentation masks are not processed in the same way during export. This parameters allows users to specify the type of input files:

    * Auto-detect:  try to detect input file types using a heuristic.
    * Images: Consider all input files as images.
    * Segmentation masks: Consider all input files as images.

Auto-contrast
: If checked, adjust contrast when exporting images.

Channel colors
: When exporting an image with multiple channels, channels are colored then merged. Click on a color to change it.

Projection range and type
: If the input image or mask contains a `Z` axis with
multiple Z sections, the chosen range of Z sections will be projected
using the chosen projection type (see [Z-Projection
module](../zprojection_module/reference.md) for more information).

Output format
: Choose one of the available options:

    * Auto: Convert to mp4 movie if input file has more than one time frame, to jpg otherwise.
    * jpg images: convert all files to jpg images (export only the first time frame).
    * mp4 movies: Convert all files to mp4 movies. This option can generate unreadable mp4 movies if the number of time frames is too low.

Quality
: mp4 movies quality. From 0 (low quality, small file-size) to 10 (high quality, large file-size).

Frame per seconds
: number of frames per second for mp4 movies.


Multi-processing
: Number of processes to use for coarse-grain parallelization (memory
usage increases with the number of processes). This setting is only
useful if there are multiple input files, as each input file will be
assigned to its own process.


## Output files

* images or segmentation masks in jpg or mp4 format (see [File formats - images and masks](../general/files.md#images-and-masks) for more information).


Output filenames are obtained by adding the optional user defined suffix to the input filename and replacing the file extension. For example, with input segmentation mask
```
smp01_BF_vSM_vTG.ome.tif
```
when exporting to mp4 format, the exported segmentation mask will have filename:
```
smp01_BF_vSM_vTG.mp4
```
