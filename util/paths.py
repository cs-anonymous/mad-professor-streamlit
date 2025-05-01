import os

# 获取项目根目录
BASEDIR = os.path.dirname(os.path.dirname(__file__))
PROJECT_ROOT = os.path.abspath(BASEDIR)

# 常用目录
FONT_DIR = os.path.join(PROJECT_ROOT, "font")
ASSETS_DIR = os.path.join(PROJECT_ROOT, "assets")

# 辅助函数
def get_font_path(font_name):
    return os.path.join(FONT_DIR, font_name)

def get_asset_path(asset_name):
    return os.path.join(ASSETS_DIR, asset_name)