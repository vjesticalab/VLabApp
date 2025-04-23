# Installation

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



## On Linux

Be careful on the limit of files that you are allowed to open. The fine-grain parallelization of the segmentation module could open up to 1000 files per process. 
Adjust the maximum number of open file descriptors to 10000 with `ulimit` before starting VLabApp with:
```
ulimit -n 10000
python3 master.py
```
This would be enough for a 10 CPU machine.
