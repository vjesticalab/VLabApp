# VLabApp documentation

## Getting started

* [Installation](general/installation.md)
* [Tutorial](general/tutorial.md)

## Reference

* [File naming conventions and supported formats](general/files.md)
* [Registration module](registration_module/reference.md)
* [Z-Projection module](zprojection_module/reference.md)
* [Segmentation module](segmentation_module/reference.md)
* [Cell tracking module](cell_tracking_module/reference.md)
* [Graph filtering module](graph_filtering_module/reference.md)
* [Events selection module](events_selection_module/reference.md)
* [Pipeline module](pipeline_module/reference.md)
* Tools:
    * [View image, mask and graph](viewer_image_mask_graph_module/reference.md)
    * [View registration matrix](viewer_registration_module/reference.md)
    * [View metadata](viewer_metadata_module/reference.md)
    * [File organization](file_organization_module/reference.md)
    * [File conversion (masks and graphs)](file_conversion_mask_graph_module/reference.md)
    * [File conversion (lossy preview)](file_conversion_lossy_module/reference.md)
    * [Image cropping](image_cropping_module/reference.md)
    * [Ground truth generator](ground_truth_generator_module/reference.md)
* [Plugins](general/plugins.md)


## Citation

If you use VLabApp in your research, please cite the VLabApp paper:
> J. Dorier, A. Ravera and A. Vjestica. In preparation

If you use the registration module with [stackreg](https://bigwww.epfl.ch/thevenaz/stackreg/), please cite the following [publication](https://doi.org/10.1109/83.650848):
> P. Thevenaz, U. E. Ruttimann and M. Unser (1998). A pyramid approach to subpixel registration based on intensity. IEEE Transactions on Image Processing, 7(1), 27–41.

If you use the segmentation module with [Cellpose](https://www.cellpose.org/), please cite the Cellpose 1.0 [publication](https://doi.org/10.1038/s41592-020-01018-x):
> C. Stringer, T. Wang, M. Michaelos and M. Pachitariu (2021). Cellpose: a generalist algorithm for cellular segmentation. Nature Methods 18, 100–106.

If you fine-tune a Cellpose model, please cite the Cellpose 2.0 [publication](https://doi.org/10.1038/s41592-022-01663-4):
> M. Pachitariu and C. Stringer (2022). Cellpose 2.0: how to train your own model. Nature Methods 19, 1634–1641.

If you use the segmentation module with the `cyto3` Cellpose model, please cite the Cellpose 3.0 [publication](https://doi.org/10.1038/s41592-025-02595-5):
> C. Stringer and M. Pachitariu (2025). Cellpose3: one-click image restoration for improved cellular segmentation. Nature Methods 22, 592-599.

If you use the segmentation module with  [Segment Anything for Microscopy](https://github.com/computational-cell-analytics/micro-sam), please cite the Segment Anything for Microscopy [publication](https://doi.org/10.1038/s41592-024-02580-4):
> A. Archit, L. Freckmann, S. Nair et al. (2025). Segment Anything for Microscopy. Nature Methods 22, 579-591.

as well as the original [Segment Anything](https://segment-anything.com/) [publication](https://doi.org/10.48550/arXiv.2304.02643)
> A. Kirillov, E. Mintun, N. Ravi et al. (2023). Segment Anything. http://arxiv.org/abs/2304.02643


### Other tools and libraries used in this project

* [igraph](https://igraph.org/)

    > G. Csardi and T. Nepusz (2006). The igraph software package for complex network research. InterJournal, Complex Systems, 1695.

* [napari](https://napari.org)

    > napari contributors (2019). napari: a multi-dimensional image viewer for python. doi:10.5281/zenodo.3555620

* [NumPy](https://numpy.org/)

    > C.R. Harris, K.J. Millman, S.J. van der Walt et al. (2020). Array programming with NumPy. Nature 585, 357–362.

* [OpenCV](https://opencv.org/)

    > G. Bradski (2000). The OpenCV Library. Dr. Dobb's Journal of Software Tools.

* [Python](https://www.python.org/)

* [Qt](https://www.qt.io/)

* [scikit-image](https://scikit-image.org/)

    > S. van der Walt, J. L. Schönberger, J. Nunez-Iglesias et al. (2014). scikit-image: Image processing in Python. PeerJ 2, e453. 

* [scipy](https://scipy.org/)

    > P. Virtanen, R. Gommers, T.E. Oliphant et al. (2020). SciPy 1.0: Fundamental Algorithms for Scientific Computing in Python. Nature Methods, 17, 261–272.
