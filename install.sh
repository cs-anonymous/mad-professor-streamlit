# 设置conda解析器为libmamba
conda install -y conda-libmamba-solver
conda config --set solver libmamba

# 安装MinerU依赖
pip install -U magic-pdf[full]==1.3.3 -i https://mirrors.aliyun.com/pypi/simple

# 安装剩余依赖
pip install -r requirements.txt

# 安装电脑显卡版本匹配的CUDA和torch, 要求numpy<=2.1.1，例（具体版本请按电脑配置修改，目前支持CUDA 11.8/12.4/12.6）
pip install --force-reinstall torch torchvision torchaudio "numpy<=2.1.1" --index-url https://download.pytorch.org/whl/cu124

# 安装FAISS的gpu版本 (注：faiss-gpu版本只能通过conda安装，无法通过pip安装)
conda install -y -c conda-forge faiss-gpu

# 部分冲突的依赖需要强制重装
pip install --force-reinstall zstandard zstd

