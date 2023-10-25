# Methods

## Z-Projection

We consider the problem of reducing a Z-stack of 2D images to a unique 2D image (Z-projection).

The value $v(x,y)$ of the pixel at position $(x,y)$ in the new image is obtained by summarizing the values of the pixels at the same position over all Z sections (or a subset of Z sections) using a given summary statistics (e.g. mean, median, max,...).

The subset of Z sections used for projection can be:

* all Z sections.
* a fixed range of Z sections.
* a range of Z sections around the Z section with best focus.
* only the Z section with best focus.


### All Z sections

All Z sections are used for the projection.


### Fixed range of Z sections

The subset of Z sections used for projection is chosen as all Z sections within the fixed interval $Z\in[Z_\text{min},Z_\text{max}]$, with user-defined $Z_\text{min}$ and $Z_\text{max}$.

Note:

* $Z_\text{min}$ and $Z_\text{max}$ are called "From" and "To" in the GUI and `zrange` or `projection_zrange` in the code (tuple of length 2).


### Range of Z sections around the Z section with best focus.

The subset of Z sections used for projection is chosen as all Z sections within a user specified window around the Z section with best focus. I.e. Z sections with $Z\in \{Z_\text{best}-\Delta_Z,Z_\text{best}-\Delta_Z +1,\cdots,Z_\text{best}+\Delta_Z\}$, where $Z_\text{best}$ corresponds to the Z-section with best focus and $\Delta_Z$ is the size of the Z window.

If $Z_\text{best}$ and $\Delta_Z$ are such that some values in $\{Z_\text{best}-\Delta_Z,Z_\text{best}-\Delta_Z +1,\cdots,Z_\text{best}+\Delta_Z\}$ are outside the range of Z sections existing in the image, then the set is shifted towards valid values of Z.
E.g. a Z-stack with 11 sections (Z=0, 1, ..., 10), $\Delta_Z=3$ and $Z_\text{best}=1$: The set of Z sections to be used for projection is $\{-2,-1,0,1,2,3,4\}$, which contains invalid values (-2 and -1). It is thus shifted in the positive Z direction to avoid negative values $\{0,1,2,3,4,5,6\}$ 

To estimate $Z_\text{best}$ (see Figure 1 and 2), the Laplacian of each Z section is estimated using the function `Laplacian` implemented in OpenCV, with kernel size 11 (Figure 1B and 2B). This function estimate the Laplacian
$$\Delta v(x,y) = \frac{\partial^2 v(x,y)}{\partial x^2} + \frac{\partial^2 v(x,y)}{\partial y^2}$$
using Sobel operators. The Laplacian can be interpreted as a measure of the local curvature. In particular, its absolute value is large for region of the image with sharp discontinuities (such as edges) and zero for regions with constant pixel intensities (or varying linearly with the position).

The "sharpness" is then estimated, for each Z, as the variance of the Laplacian of the corresponding Z section (Figure 1C and 2C).
To find Z with maximum sharpness, a gaussian function
$$f(Z)=A*e^{-\frac{(Z-Z_0)^2}{2\sigma^2}}+B$$
is fitted to the data using unction `curve_fit` implemented in scipy (blue curve in Figure). Finally, $Z_\text{best}$ is obtained by rounding $Z_0$ to the nearest integer value.


<figure>
  <img src="images/sharpness_BF.png" alt="Terminology"/>
  <figcaption>Figure 1: determination of Z section with best focus. Panel A: Z sections of a bright-field image. Panel B: Laplacian of the Z sections. Panel C: Sharpness of each Z section (points) as a function of Z together with a gaussian fit (blue curve). Light blue vertical line indicate the Z position at which the gaussian fit reaches its maximum.</figcaption>
</figure>

<figure>
  <img src="images/sharpness_Fluo.png" alt="Terminology"/>
  <figcaption>Figure 2: same as Figure 1 but with a fluorescence image.</figcaption>
</figure>

Note:

* The window size $\Delta_Z$ is called "Projection range" in the GUI and `zrange` or `projection_zrange` in the code (integer).


### Z section with best focus

The stack of Z sections is simply replaced by the Z section with best focus (obtained as described above).


## Implementation

* Python ([https://www.python.org/](https://www.python.org/)).
* OpenCV ([https://opencv.org/](https://opencv.org/)).
* numpy ([https://numpy.org/](https://numpy.org/)).
* SciPy ([https://scipy.org/](https://scipy.org/)).

