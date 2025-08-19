# VLabApplication

Automating cellular image analysis




## About The Project

The VLabApp is created with the aim of automating the cellular image analysis process, from the recording of the movies that come out of the microscope, to the tracking of the events within each time frame.

The application is divided into several modules that can be used consecutively and/or independently:
* **Registration** - to register and align images.
* **Z-Projection** - to make a projection of the z stack. Max, min, std, average and median projections possible.
* **Segmentation** - to segment the images and generate the corresponding masks.
* **Cell tracking** - to track segmented cells over time and create the cell tracking graph.
* **Graph filtering** - to filter and clean the graph and the corresponding mask.
* **Events selection** - to extract fusion or division events from the graph and the corresponding mask.
* **Pipeline** - to create a pipeline by combining individual modules.
* **Viewers** - to easily view the generated images, masks, graphs, registration matrix in Napari.
* **File organization** - to export or clean generated output.
* **File conversion** - to export masks and graphs to various file formats and to convert image and masks to small file-size preview movies or images.
* **Image cropping** - to crop images and masks.
* **Ground truth generator** - to quickly and easily generate the ground truth masks useful for a possible retraining of the network to be used in the Segmentation module.



## Getting Started

### Installation

1. **Install Conda**

    If [Conda](https://conda.io/) is not already installed, download and install Miniconda or Anaconda from <https://www.anaconda.com/download/>.

2. **Download VLabApp**

    Go to the [latest release page](https://github.com/vjesticalab/VLabApp/releases/latest) and download the Source code archive (`.zip` or `.tar.gz`). Extract the archive, then open a terminal or anaconda powershell prompt (Windows) and navigate to the extracted folder. 

3. **Create a new conda environment**

    Run the following command to create a new environment using the provided `environment.yml` file
    
    ```
    conda env create --name venv_VLabApp  --file environment.yml
    ```

4. **Activate the environment**

    After the environment is created, activate it
    
    ```
    conda activate venv_VLabApp
    ```

5. **Start the application**

    In the `venv_VLabApp` environment, start the application with
    
    ```
    python master.py
    ```


Open [doc/site/index.html](doc/site/index.html) from the downloaded VLabApp folder with a web browser to access documentation.

## Citation

If you use VLabApp in your research, please cite the VLabApp paper:
> J. Dorier, A. Raverra and A. Vjestica. In preparation

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


## License

Distributed under the ... License. See `support_files/LICENSE.txt` for more information.


## Credits

Arianna Ravera - Scientific Computing and Research Support Unit, [University of Lausanne](https://www.unil.ch).

Julien Dorier - Bioinformatics Competence Center, [University of Lausanne](https://www.unil.ch).

Aleksandar Vjestica - Center for Integrative Genomics, [University of Lausanne](https://www.unil.ch).

Project Link: [VLabApp](https://github.com/vjesticalab/VLabApp)



