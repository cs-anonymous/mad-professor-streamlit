# 暴躁的教授读论文（streamlit版本）
一个使用Streamlit开发的网页端服务，特色是具有暴躁个性的AI教授，让学术论文阅读更加高效有趣。本项目是在[林亦LYi大佬的项目](https://github.com/LYiHub/mad-professor-public)基础上重构得来的（不再支持PYQT ui），感谢他的开源贡献。

## 项目概述

"暴躁教授读论文"是一个学术论文阅读伴侣应用程序，旨在通过富有个性的AI助手提高论文阅读效率。它集成了PDF处理、AI翻译、RAG检索、AI问答等多种功能（语音交互功能已删除），为学术研究者提供一站式的论文阅读解决方案。

![image-20250503114459104](https://n.ye-sun.com/gallery/2024/202505031145122.png)

![image-20250503114513767](https://n.ye-sun.com/gallery/2024/202505031145101.png)

## 主要特性

- **论文自动处理**：导入PDF后自动提取、翻译和结构化论文内容
- **双语显示**：支持中英文对照阅读论文
- **AI智能问答**：与论文内容结合，提供专业的解释和分析
- **个性化AI教授**：AI以"暴躁教授"的个性回答问题，增加趣味性
- **RAG增强检索**：基于论文内容的精准检索和定位
- **分屏界面**：左侧菜单栏管理+AI问答，高效交互

## 技术架构

- **前端界面**：使用Streamlit构建的网页端服务
- **核心引擎**：
  - AI问答模块：基于LLM的学术问答系统
  - RAG检索系统：向量检索增强的问答精准度
  - 论文处理管线：PDF转MD、自动翻译、结构化解析
- **交互系统**：
  - 情感识别：根据问题内容调整回答情绪

## 安装指南

### 环境要求
- Python 3.10或更高版本
- CUDA支持
- 6GB 以上显存

### 项目依赖
本项目依赖以下开源项目
- MinerU https://github.com/opendatalab/MinerU
- RealtimeSTT https://github.com/KoljaB/RealtimeSTT

本项目依赖以下在线API服务（可以通过修改代码改为本地实现）
- DeepSeek https://api-docs.deepseek.com

### 安装步骤

```
# 使用conda创建环境
# 注意anaconda的版本需要>=23.3.1，低版本的anaconda会导致conda无法解析依赖
conda create -n mad-professor python=3.10.16
conda activate mad-professor

# 按照`install.sh`中的步骤安装依赖
./install.sh

# 模型下载
python download_models.py
# python脚本会自动下载模型文件并配置好配置文件中的模型目录，配置文件可以在用户目录中找到，文件名为magic-pdf.json
# 修改 `~/magic-pdf.json` 中 "device-mode": "cuda"

# 下载语音输入的Whisper模型，避免运行时NetworkError
python util/config.py

# 在项目根目录下新建`.env`文件，添加以下内容
API_BASE_URL=YOUR_API_URL   # 例如：https://api.deepseek.com
API_KEY=YOUR_API_KEY
GLOBAL_MODEL=YOUR_MODEL_NAME    # 例如：deepseek-chat

# 运行项目
./stream.sh
```




## 使用说明

### 教授人设修改
人设prompt修改:

    在`prompt`文件夹中创建一个新的`ai_character_prompt_[你的人设名字].txt`
    
    将`AI_professor_chat.py`程序开头`AI_CHARACTER_PROMPT_PATH`字段修改为相应的人设prompt路径
    ```
    AI_CHARACTER_PROMPT_PATH = "prompt/ai_character_prompt_[你的人设名字].txt"
    ```
    
    当前已有两个人设`ai_character_prompt_keli.txt`和`ai_character_prompt_leidian.txt`，可以作为示例

### 导入论文

![image-20250503120047713](https://n.ye-sun.com/gallery/2024/202505031200869.png)

1. 点击侧边栏的"上传论文"按钮
2. 选择PDF文件导入
3. 点击“继续”，等待处理完成（包括翻译和索引构建）
4. 导入的PDF会存放到data文件夹中，也可以将多篇PDF放入data文件夹，程序会检测未处理的文件批量处理


### 论文阅读

![image-20250503115343250](https://n.ye-sun.com/gallery/2024/202505031153334.png)

1. 在侧边栏选择已经处理好的论文
   
2. 在主窗口查看论文内容，设置可切换中英文
   
3. 左侧可折叠隐藏，提供沉浸式阅读体验

4. 主窗口提供可折叠目录

### AI问答

![image-20250503120146860](https://n.ye-sun.com/gallery/2024/202505031201155.png)

目前仅支持使用文字对话，删除语音问答功能，支持流式响应式问答。

## 项目结构
```
mad-professor/
├── 核心模块 (util/)
│   ├── config.py             # 配置文件，API密钥和模型设置
│   ├── paths.py              # 路径管理，统一管理文件路径
│   ├── AI_manager.py         # AI功能管理器，整合所有AI相关功能
│   ├── AI_professor_chat.py  # AI对话逻辑，实现暴躁教授的交互回答
│   ├── data_manager.py       # 数据管理器，处理论文索引和内容加载
│   ├── pipeline.py           # 处理管线，协调各处理器的工作流程
│   ├── rag_retriever.py      # RAG检索系统，实现向量检索和上下文提取
│   └── threads.py            # 线程管理，处理异步任务和并发
│
├── 处理器模块 (processor/)
│   ├── pdf_processor.py      # PDF处理器，提取PDF内容转为Markdown
│   ├── md_processor.py       # Markdown处理器，结构化解析Markdown
│   ├── json_processor.py     # JSON处理器，处理结构化数据
│   ├── tiling_processor.py   # 分块处理器，将内容分割为块
│   ├── translate_processor.py # 翻译处理器，中英文翻译
│   ├── md_restore_processor.py # Markdown还原处理器
│   ├── extra_info_processor.py # 额外信息处理器，生成摘要和问题
│   └── rag_processor.py      # RAG处理器，生成向量库和检索树
│
├── 提示词模板 (prompt/)
│   ├── ai_character_prompt_keli.txt    # 可莉教授人设提示词
│   ├── ai_character_prompt_leidian.txt # 雷电教授人设提示词
│   ├── ai_explain_prompt.txt           # 解释功能提示词
│   ├── ai_router_prompt.txt            # 路由决策提示词
│   ├── content_translate_prompt.txt    # 内容翻译提示词
│   ├── formula_analysis_prompt.txt     # 公式分析提示词
│   └── summary_generation_prompt.txt   # 摘要生成提示词
│
├── 资源和配置
│   ├── stream.py             # 程序入口文件
│   ├── stream.sh             # 程序启动脚本
│   ├── download_models.py    # 模型下载脚本
│   ├── assets/               # 资源文件目录（图片、样式等）
│   └── static/               # 字体文件，前端目录
│
└── 数据目录
    ├── data/                 # 源数据目录（论文PDF）
    └── output/               # 输出目录（处理结果）
```


## 许可证

本项目采用 Apache 许可证 - 详情见 LICENSE 文件

## 致谢
特别感谢 MinerU、RealtimeSTT 项目和[林亦LYi大佬的项目](https://github.com/LYiHub/mad-professor-public)


## 其他更新

### 2025/05/03
- 完成了项目的重构，去掉了语音交互功能，增加了RAG检索功能
- 修复了图像路径问题，确保图像能够正确显示
- 优化了代码结构，增强了可读性和可维护性

![image-20250503160017217](https://n.ye-sun.com/gallery/2024/202505031600733.png)
