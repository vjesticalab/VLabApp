# Segmentation module

The segmentation module use [Cellpose](https://www.cellpose.org/) v3 [1-3] or [Segment Anything for Microscopy](https://github.com/computational-cell-analytics/micro-sam) [4] (if installed) to perform cell segmentation and generate a segmentation mask.


## Input files

A list of multi-dimensional images with at least `X` and `Y` axes, and optionally `C`, `Z` and `T` axes (see [File formats - images and masks](../general/files.md#images-and-masks) for more information).

To populate the list, use the <kbd>Add file</kbd>, <kbd>Add folder</kbd> and <kbd>Remove selected</kbd> buttons to add images, folder (all images inside the folder) or remove images from the list. Alternatively, images and folder can be dragged and dropped from an external file manager.

When adding files or folders, only files satisfying all filters (click on `▶` above the list to show filters) are added to the list.  By default, only files with a filename containing `_BF` (image with a unique bright-field channel) and ending with one of the accepted file extensions (`.nd2`, `.tif`, `.tiff`, `.ome.tif`, `.ome.tiff`) are accepted.


## Parameters

Output folder
: Either use each input image folder as output folder or specify a
custom output folder. To select a custom folder, either paste the path
into the text box, click on the <kbd>Browse</kbd> button, or drag and drop a
folder from an external file manager. Be careful when using a custom folder: if
two input files share the same filename (from different folders), the
output for both files will be written to the same output file,
resulting in data corruption.

Output suffix
: The output filename will correspond to the input filename with an
additional `_vSM` suffix, optionally followed by a user defined suffix
(containing only `a-z`, `A-Z`, `0-9` and `-` characters). The
resulting output filenames are shown below the suffix.

Segmentation method
: The segmentation method to use, either `Cellpose` (<https://www.cellpose.org/>) or `Segment Anything for Microscopy` (<https://github.com/computational-cell-analytics/micro-sam>, if installed).

Model type
: For Cellpose:
    
    * `User trained model`: a user trained model can be obtained by finetuning a pretrained Cellpose model on a collection of annotated images similar to the input images (see section "Training" in Cellpose documentation <https://cellpose.readthedocs.io/en/v3.1.1.1/>). Note that the [Ground truth generator](../ground_truth_generator_module/reference.md) module can be used to generate a collection of annotated images (training set) for Cellpose.
    * Built-in models: use one of the Cellpose built-in models (`cyto`, `cyto2`, `cyto3`, `nuclei`, `tissuenet_cp3`, `livecell_cp3`, `yeast_PhC_cp3`, `yeast_BF_cp3`, `bact_phase_cp3`, `bact_fluor_cp3`, `deepbacs_cp3` and `cyto2_cp3`).
    
    For Segment Anything for Microscopy:
    
    * Segment Anything models `vit_h`, `vit_l`, `vit_b`, or Segment Anything for Microscopy models `vit_l_lm`, `vit_b_lm`, `vit_l_em_organelles` and `vit_b_em_organelles`. For more information, see section "Finetuned Models" in Segment Anything for Microscopy documentation <https://computational-cell-analytics.github.io/micro-sam/micro_sam.html>.

Model
: path to the Cellpose user trained model. To select a model, either paste the path into the text box, click on the <kbd>Browse</kbd> button, or drag and drop a file from an external file manager. This parameter is available only for Cellpose user trained models.

Diameter
: Expected cell diameter (pixel). If 0, use Cellpose built-in model to estimate diameter (available only for `cyto`, `cyto2`, `cyto3` and `nuclei` models). For more information, see section "Models" in Cellpose documentation <https://cellpose.readthedocs.io/en/v3.1.1.1/>. This parameter is available only for Cellpose built-in models. For user trained models, the median diameter estimated on the training set is used.

Cellprob threshold
: cellprob threshold for Cellpose. For more information, see section "Settings" in Cellpose documentation <https://cellpose.readthedocs.io/en/v3.1.1.1/>. This parameter is available only for Cellpose, click on `▶` to show.

Flow threshold
: cellprob threshold for Cellpose. For more information, see section "Settings" in Cellpose documentation <https://cellpose.readthedocs.io/en/v3.1.1.1/>. This parameter is available only for Cellpose, click on `▶` to show.

Channel position
: If the input image contains more than one channel (`C` axis), the
channel with index specified in `channel position` will be used for
segmentation (0-based indexing).

Projection range and type
: If the input image contains a `Z` axis with
multiple Z sections, the chosen range of Z sections will be projected
using the chosen projection type (see [Z-Projection
module](../zprojection_module/reference.md) for more information).
Note that for best results, the segmentation model used should have
been trained on the selected type of Z-projected images.

Use GPU
: Use a GPU if available. Using this option prevents from using CPU parallelization (use coarse grain parallelization and number of processes are ignored).

Use coarse grain parallelization
: If checked, each input file is assigned to its own process. Otherwise, use fine-grained parallelization on the time frames. Coarse grain parallelization should be used when there are more input files than processes and enough memory (memory usage increases with the number of processes).

Number of processes
: Number of processes to use.

Show results in napari
: If checked, the input image and resulting segmentation mask are shown in [napari](https://napari.org) after segmentation.  This option is disabled if there is more than one input image.

## Output files

* Segmentation mask (see [File formats - images and masks](../general/files.md#images-and-masks) for more information).
* Log file (see [File formats - Log files and metadata](../general/files.md#log-files-and-metadata) for more information).

Output filenames are obtained by adding a `_vSM` suffix to the input filename, optionally followed by a user defined suffix. For example, with input image
```
smp01_BF.nd2
```
the output segmentation mask and log file will have filenames:
```
smp01_BF_vSM.ome.tif
smp01_BF_vSM.log
```


## References

[1] C. Stringer, T. Wang, M. Michaelos and M. Pachitariu (2021). Cellpose: a generalist algorithm for cellular segmentation. Nature Methods 18, 100–106.

[2] M. Pachitariu and C. Stringer (2022). Cellpose 2.0: how to train your own model. Nature Methods 19, 1634–1641.

[3] C. Stringer and M. Pachitariu (2025). Cellpose3: one-click image restoration for improved cellular segmentation. Nature Methods 22, 592-599.

[4] A. Archit, L. Freckmann, S. Nair et al. (2025). Segment Anything for Microscopy. Nature Methods 22, 579-591.


