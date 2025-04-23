# File conversion (masks and graphs)

This module exports segmentation masks and/or cell tracking graphs to various file formats, to be reused in other applications. The resulting files are not meant to be read by this application. In addition, VLabApp metadata are lost during conversion (see [File formats - Log files and metadata](../general/files.md#log-files-and-metadata) for more information).

## Input files

A list of multi-dimensional segmentation masks with `X`, `Y` and `T` axes (see [File formats - images and masks](../general/files.md#images-and-masks) for more information) with corresponding cell tracking graphs (see [File formats - Cell tracking graphs](../general/files.md#cell-tracking-graphs) for more information).

Corresponding mask and graph files must be in the same folder. Their filenames must share the same basename and end with the suffixes specified below the table (by default `<basname>.ome.tif` and <basename>.graphmlz).

To populate the table, use the <kbd>Add file</kbd>, <kbd>Add folder</kbd> and <kbd>Remove selected</kbd> buttons to add masks or graphs, folder (all masks and graphs inside the folder) or remove rows from the list. Alternatively, masks, graphs and folders can be dragged and dropped from an external file manager. Masks (resp. graphs) without a corresponding graph (resp. mask) are ignored.

When adding files or folders, only files satisfying all filters (click on `▶` above the list to show filters) are added to the list. By default, only pairs of mask and graph with a filename containing `_vTG` (segmentation masks and cell tracking graphs generated with the cell tracking module) and ending with the suffixes specified below the table (`.ome.tif` and `.graphmlz`) are accepted.


## Parameters

Output folder
: Either use each input mask/graph folder as output folder or specify a
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

Convert segmentation mask
: If checked, export input segmentation masks to ImageJ ROI set (`.zip`) format (see [File formats - images and masks](../general/files.md#images-and-masks) for more information).

Convert cell tracking graph
: If checked, export input cell tracking graphs to the selected file format.

File format
: Export cell tracking graphs to the selected file format. The following formats are available (see [File formats - Cell tracking graphs](../general/files.md#cell-tracking-graphs) for more information):

    * List of edges in tab separated value tabular format (`.tsv`).
    * [Graphviz](https://www.graphviz.org/) dot format (`.dot`).
    * [GraphML](http://graphml.graphdrawing.org/) format (`.graphml`).

Output one file per cell track
: If checked, generate one file per cell track (and append `_<cell track id>` to the output filename). Note that a large number of file can be generated when using this option.


Multi-processing
: Number of processes to use for coarse-grain parallelization (memory
usage increases with the number of processes). This setting is only
useful if there are multiple input mask and graph, as each pair of input mask and graph will be
assigned to its own process.


## Output files

* If option "Convert segmentation mask" is selected, the segmentation mask in ImageJ ROI set format (see [File formats - images and masks](../general/files.md#images-and-masks) for more information).
* If option "Convert cell tracking graph" is selected, the cell tracking graph in the chosen file format (see [File formats - Cell tracking graphs](../general/files.md#cell-tracking-graphs) for more information).


Output filenames are obtained by adding the optional user defined suffix to the input filename, adding a `_<cell track id>` suffix if the option "Output one file per cell track" is selected,  and replacing the file extension. For example, with input segmentation mask and cell tracking graph
```
smp01_BF_vSM_vTG.ome.tif
smp01_BF_vSM_vTG.graphmlz
```
when exporting the segmentation mask to ImageJ ROI set and the cell tracking graph to Graphviz dot format (without the "Output one file per cell track" option), the exported segmentation mask and cell tracking graph will have filenames:
```
smp01_BF_vSM_vTG.zip
smp01_BF_vSM_vTG.dot
```
and with the "Output one file per cell track" option 
```
smp01_BF_vSM_vTG_0000.zip
smp01_BF_vSM_vTG_0000.dot
smp01_BF_vSM_vTG_0001.zip
smp01_BF_vSM_vTG_0001.dot
smp01_BF_vSM_vTG_0002.zip
smp01_BF_vSM_vTG_0002.dot
...
```
