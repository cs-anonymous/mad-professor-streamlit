conda activate professor
conda install -y conda-libmamba-solver
conda config --set solver libmamba

pip install -U magic-pdf[full]==1.3.3 -i https://mirrors.aliyun.com/pypi/simple
pip install -r requirements.txt

pip install --force-reinstall torch torchvision torchaudio "numpy<=2.1.1" --index-url https://download.pytorch.org/whl/cu124
conda install -y -c conda-forge faiss-gpu

pip install --force-reinstall zstandard zstd

python download_models.py
# 将 ~/magic-pdf.json 中 "device-mode": "cuda"
python util/config.py