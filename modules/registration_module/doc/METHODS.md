# Methods

## Registration

The following registration methods are implemented:

* **StackReg**: Registration using pyStackReg with translation transformation. pyStackReg is a Python/C++ port of the ImageJ extension TurboReg/StackReg written by Philippe Thevenaz/EPFL [1] ([http://bigwww.epfl.ch/thevenaz/turboreg/](http://bigwww.epfl.ch/thevenaz/turboreg/)).

* **Phase correlation**: Registration using the phase correlation method implemented in OpenCV (function `phaseCorrelate()`), which uses the Fourrier shift theorem to detect translational shift in the frequency domain (see [https://en.wikipedia.org/wiki/Phase_correlation](https://en.wikipedia.org/wiki/Phase_correlation)). This method fast, but tend to fail when there too many non-moving artefacts are present in the image (e.g. dust).

* **Feature matching**: Four variants of the "feature matching" registration methods are available (ORB, BRISK, AKAZE and SIFT). In this method, registration is performed in three steps:

  1. Feature (keypoints) detection and evaluation of the descriptors using methods implemented in OpenCV. Four keypoints detector an descriptor extractor algorithms are available:

    * ORB (Oriented FAST and Rotated BRIEF) [2].

    * BRISK (Binary Robust invariant scalable keypoints) [3].

    * AKAZE (Accelerated-KAZE) [4].

    * SIFT (scale-invariant feature transform) [5].
  
  2. Feature matching. Features found in consecutive image frames are matched using the FLANN-based descriptor matcher implemented in OpenCV  (FLANN stands for Fast Library for Approximate Nearest Neighbors). Matches are further filtered using the distance ratio test proposed by Lowe [5] (with threshold 0.75).

  3. Parameter estimation using RANSAC. The shift between consecutive image frames is then estimated with the Random sample consensus (RANSAC) method implemented in scikit-image using a custom transformation model with translation only.

  Preliminary tests on few sample images suggest that registration using  ORB, BRISK, AKAZE or SIFT algorithms give results of similar quality.
  Note that the scale and rotational invariance is not so important when considering consecutive image frames, as the size and orientation of the features is not expected to change on short time scale.
   However, computation time varies significantly. From fastest to slowest: ORB, BRISK, AKAZE, SIFT.


## Implementation

* Python ([https://www.python.org/](https://www.python.org/)).
* OpenCV ([https://opencv.org/](https://opencv.org/)).
* pyStackReg ([https://github.com/glichtner/pystackreg](https://github.com/glichtner/pystackreg)).
* scikit-image ([https://scikit-image.org/](https://scikit-image.org/))


## References

[1] P. Thevenaz, U. E. Ruttimann and M. Unser (1998). A pyramid approach to subpixel registration based on intensity. IEEE Transactions on Image Processing, 7(1), 27–41.

[2] E. Rublee, V. Rabaud, K. Konolige and G. Bradski (2011). ORB: An efficient alternative to SIFT or SURF. Procedings of the IEEE International Conference on Computer Vision, 2564–2571.

[3] S. Leutenegger, M. Chli and R. Y. Siegwart (2011). Brisk: Binary robust invariant scalable keypoints.  Procedings of the IEEE International Conference on Computer Vision, 2548–2555.

[4] P. F. Alcantarilla, J. Nuevo and A. Bartoli (2013). Fast explicit diffusion for accelerated features in nonlinear scale spaces.  Procedings of the British Machine Vision Conference 2013, 13.1-13.11.

[5] D. G. Lowe (2004). Distinctive Image Features from Scale-Invariant Keypoints. International Journal of Computer Vision, 60(2), 91–110.

