# Installation

1. **Install Conda**

    If [Conda](https://conda.io/) is not already installed, download and install Miniconda or Anaconda from <https://www.anaconda.com/download/>.

2. **Download VLabApp**

    Go to the [latest release page](https://github.com/vjesticalab/VLabApp/releases/latest) and download the Source code archive (`.zip` or `.tar.gz`). Extract the archive, then open a terminal or anaconda powershell prompt (Windows) and navigate to the extracted folder. 

3. **Create a new conda environment**

    If an older `venv_VLabApp` environment exists, remove it with `conda env remove --name venv_VLabApp`.
    
    Run the following command to create a new environment
    
        conda create --name venv_VLabApp python=3.11.11

4. **Activate the environment**

    After the environment is created, activate it
    
        conda activate venv_VLabApp

5. **Install dependencies**

    Use `pip` to install dependencies listed in the `requirements.txt` file
    
        pip install -r requirements.txt

    **Windows: CUDA support**
   
    To enable GPU acceleration on Windows with an NVIDIA GPU, a CUDA-enabled build of PyTorch must be installed. Use one of the following commands instead, selecting the CUDA version suited to your system:
    
    * For CUDA 12.9:
        
            pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cu129
    
    * For CUDA 12.8:
        
            pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cu128
    
    * For CUDA 12.6:
        
            pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cu126
    
    More information is available in the official [PyTorch](https://pytorch.org) documentation <https://pytorch.org/get-started/locally/>

6. **Start the application**

    In the `venv_VLabApp` environment, start the application with
    
        python master.py



## On Linux

Be careful on the limit of files that you are allowed to open. The fine-grain parallelization of the segmentation module could open up to 1000 files per process. 
Adjust the maximum number of open file descriptors to 10000 with `ulimit` before starting VLabApp with:
```
ulimit -n 10000
python3 master.py
```
This would be enough for a 10 CPU machine.
