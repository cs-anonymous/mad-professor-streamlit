import streamlit as st
from util.data_manager import DataManager
from util.AI_manager import AIManager
import markdown
# Add at the very top before other imports
import os
import json  # 添加在文件顶部

# 在文件顶部添加导入
from util.util import katex_scripts, render_markdown

os.environ["TORCH_DISABLE_MLOCK"] = "1"  # Disable PyTorch memory locking

# 在导入之后立即初始化session state
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'is_chinese' not in st.session_state:
    st.session_state.is_chinese = True  # 将此初始化提前到文件顶部

# 初始化核心模块
BASEDIR = os.path.dirname(os.path.abspath(__file__))
data_manager = DataManager(BASEDIR)
ai_manager = AIManager()
data_manager.load_papers_index()

# 应用基础配置
st.set_page_config(
    page_title="暴躁的教授读论文",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 侧边栏 - 论文列表
with st.sidebar:
    st.header("📚 论文列表")
    
    # 论文选择
    selected_paper = st.selectbox(
        "选择论文",
        options=[p['id'] for p in data_manager.papers_index],
        format_func=lambda x: next(p['title'] for p in data_manager.papers_index if p['id'] == x)
    )
    
    # 文件上传
    uploaded_file = st.file_uploader("上传论文", type=["pdf"])
    if uploaded_file:
        # 处理上传逻辑
        save_path = os.path.join("uploads", uploaded_file.name)
        with open(save_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success(f"已上传: {uploaded_file.name}")



# 主界面布局
main_col, right_col = st.columns([7, 3])

# 修改原有的渲染部分
with main_col:
    st.header("📄 论文内容")
    if selected_paper:
        paper = data_manager.load_paper_content(selected_paper)
        paper = {
            'metadata': paper[0],
            'zh_content': paper[1],
            'en_content': paper[2],
        }
        current_lang = 'zh' if st.session_state.is_chinese else 'en'
        content = paper[f"{current_lang}_content"]
        
        st.markdown(content, unsafe_allow_html=True)
        # html_content = render_markdown(content, current_lang)
        # st.components.v1.html(
        #     html_content,
        #     height=800,
        #     scrolling=True
        # )
        # 添加公式重新渲染逻辑
                

with right_col:  # 对应原ChatWidget
    # 顶部设置栏
    with st.container():
        setting_col1, setting_col2 = st.columns([1, 1])
        
        with setting_col1:
            # TTS开关
            tts_enabled = st.checkbox("启用TTS语音", value=True)
            
        with setting_col2:
            # 保持现有代码不变
            # 注意这里逻辑很奇怪，is_chinese切换成True时，会显示英文
            st.session_state['is_chinese'] = st.toggle("显示英文", value=False)
            
    st.header("💬 AI对话")
    # 聊天消息显示
    for msg in st.session_state.get("messages", []):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    
    # 用户输入
    if prompt := st.chat_input("输入您的问题..."):
        # 处理AI响应
        with st.spinner("教授正在思考..."):
            response = ai_manager.get_ai_response(prompt, selected_paper)
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.session_state.messages.append({"role": "assistant", "content": response})
            st.rerun()


# 应用自定义CSS：禁止滚动条
st.markdown(
    """
    <style>
    /* .stApp { overflow: hidden; }   禁止滚动条 */
    .katex { font-size: 1.2em !important; }  /* 添加公式字体大小调整 */
    </style>
    """,
    unsafe_allow_html=True
)