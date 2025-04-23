Install mkdocs-material
```
conda create --name venv_mkdocs python=3.11
conda activate venv_mkdocs
pip install mkdocs-material==9.6.11 mkdocs==1.6.1 mkdocs-glightbox==0.4.0
```

Build documentation
```
mkdocs build
```

Remove conda environment
```
conda deactivate
conda remove --name venv_mkdocs --all
```
