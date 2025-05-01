import streamlit as st
from util.data_manager_clean import DataManager
# Add at the very top before other imports
import os
import json  # 添加在文件顶部
from util.AI_professor_chat import AIProfessorChat
import uuid
import shutil

os.environ["TORCH_DISABLE_MLOCK"] = "1"  # Disable PyTorch memory locking

# 在导入之后立即初始化session state
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'is_chinese' not in st.session_state:
    st.session_state.is_chinese = True  # 将此初始化提前到文件顶部
# 在现有session_state初始化后添加
if 'ai_is_generating' not in st.session_state:
    st.session_state.ai_is_generating = False
if 'ai_current_request_id' not in st.session_state:
    st.session_state.ai_current_request_id = None
if 'ai_accumulated_response' not in st.session_state:
    st.session_state.ai_accumulated_response = ""
if 'selected_paper' not in st.session_state:
    st.session_state.selected_paper = None    
if 'ai_chat' not in st.session_state:
    st.session_state.ai_chat = AIProfessorChat()

# 初始化核心模块
BASEDIR = os.path.dirname(os.path.abspath(__file__))
data_manager = DataManager(BASEDIR)
# 替换原有的ai_manager初始化

# 修改get_ai_response中的调用
def get_ai_response(query, paper_id=None):
    try:
        print("✅ [DEBUG] 进入AI响应流程")  # 控制台输出
        st.write("✅ 进入AI响应流程")
        print(f"📡 [DEBUG] 请求参数: query='{query}', paper_id={paper_id}")  # 参数带引号避免空格问题
        st.write(f"请求参数: query={query}, paper_id={paper_id}")
        
        if st.session_state.ai_is_generating:
            print("⚠️ [DEBUG] 检测到已有进行中的请求，触发取消")
            st.warning("⚠️ 检测到已有生成中的请求，正在取消...")
            cancel_ai_response()
            
        # 生成请求ID
        st.session_state.ai_current_request_id = str(uuid.uuid4())
        st.session_state.ai_is_generating = True
        print(f"🚀 [DEBUG] 创建新请求ID: {st.session_state.ai_current_request_id}")
        st.write(f"🚀 创建新请求ID: {st.session_state.ai_current_request_id}")
        
        # 获取AI响应
        print("🔄 [DEBUG] 正在调用process_query_stream...")
        st.write("🔄 正在获取AI响应流...")
        response = st.session_state.ai_chat.process_query_stream(query, paper_id)
        
        # 收集完整响应
        full_response = ""
        for response_tuple in response:  # 修改变量名为response_tuple
            sentence, emotion, scroll_info = response_tuple  # 解包元组
            print(f"📥 [DEBUG] 收到流片段: {sentence}")  # 只记录文本内容
            st.write(f"📥 收到响应片段: {sentence}")
            full_response += sentence
            yield sentence  # 保持只返回文本内容
            
        if not full_response:
            print("❌ [ERROR] AI响应为空！")
            st.error("❌ AI响应为空，请检查AI模型配置")
            
        # 保存到对话历史
        st.session_state.ai_accumulated_response = full_response
        print("💾 [DEBUG] 响应保存完成")
        st.write("💾 响应保存完成")
        
    except Exception as e:
        print(f"❌ [CRITICAL] 异常发生: {str(e)}")
        st.error(f"❌ AI响应生成失败: {str(e)}")
        import traceback
        traceback.print_exc()  # 控制台输出完整堆栈
        st.write(f"🔍 完整错误追踪:\n{traceback.format_exc()}")
    finally:
        st.session_state.ai_is_generating = False
        print("🛑 [DEBUG] 清理生成状态")
        st.write("🛑 清理生成状态")

def cancel_ai_response():
    if st.session_state.ai_is_generating:
        # 重置状态
        st.session_state.ai_is_generating = False
        st.session_state.ai_current_request_id = None

def change_seleted_paper():
    paper_id = st.session_state.selected_paper
    if paper_id:
        print(f"📚 切换到论文: {paper_id}")
        paper_data = data_manager.load_rag_tree(paper_id)
        if paper_data:
            print("📚 加载RAG树成功")
            st.session_state.ai_chat.set_paper_context(paper_id, paper_data)

data_manager.load_papers_index()
# st.session_state.selected_paper = data_manager.papers_index[0]['id'] if data_manager.papers_index else None
# change_seleted_paper()

# 应用基础配置
st.set_page_config(
    page_title="暴躁的教授读论文",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 在现有函数后添加文件上传回调函数
def handle_file_upload():
    if "uploaded_file" in st.session_state:
        uploaded_file = st.session_state.uploaded_file
        # 确保路径处理正确
        save_path = os.path.abspath(os.path.join("data", uploaded_file.name))
        with open(save_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        data_manager.upload_file(save_path)
        data_manager.is_paused = False
        data_manager.process_next_in_queue()
        # 清除上传状态防止重复触发
        del st.session_state.uploaded_file

# 侧边栏 - 论文列表
with st.sidebar:
    with st.expander("📚 论文列表", expanded=True):
        # 论文选择
        selected_paper = st.selectbox(
            "选择论文",
            options=[p['id'] for p in data_manager.papers_index],
            format_func=lambda x: next(p['title'] for p in data_manager.papers_index if p['id'] == x),
            key='selected_paper',
            on_change=change_seleted_paper
        )
        col1, col2 = st.columns([1,1])
        with col1:
            if st.button("📝 编辑论文", key="edit_paper_btn"):
                st.session_state['selected_paper'] = selected_paper
        with col2:
            # 删除论文对应文件夹
            if st.button("🗑️ 删除论文", key="delete_paper_btn"):
                paper_path = os.path.join(BASEDIR, 'output', st.session_state['selected_paper'])
                if os.path.exists(paper_path):
                    shutil.rmtree(paper_path)
                    st.rerun()
                else:
                    st.error("论文文件夹不存在")

        
        # 文件上传
    
    
    # 修改文件上传组件
    with st.expander("🚀 处理队列", expanded=True):
        uploaded_file = st.file_uploader(
            "上传论文", 
            type=["pdf"],
            key="uploaded_file",
            on_change=handle_file_upload
        )
            
        
        # 修改后的控制按钮行
        col1, col2 = st.columns([1,1])
        with col1:
            # 切换式按钮
            if data_manager.is_paused:
                if st.button("▶️ 继续处理", key="resume_btn"):
                    data_manager.is_paused = False
                    data_manager.process_next_in_queue()
                    st.rerun()
            else:
                if st.button("⏸️ 暂停处理", key="pause_btn"):
                    data_manager.pause_processing()
                    st.rerun()
        with col2:
            if st.button("🔄 刷新列表", key="refresh_db"):
                data_manager.load_papers_index()
                st.rerun()
        
        if data_manager.processing_queue:
            st.caption("当前处理队列:")
            for item in data_manager.processing_queue:
                status_icon = "🟡" if item['status'] == 'incomplete' else "🟢"
                st.write(f"{status_icon} {item['id']} - {item['status']}")


    with st.expander("⚙️ 设置", expanded=True):
        setting_col1, setting_col2 = st.columns([1, 1])
        
        with setting_col1:
            # TTS开关
            tts_enabled = st.checkbox("启用TTS语音", value=True)
            
        with setting_col2:
            # 保持现有代码不变
            # 注意一定要在main_col之前定义st.session_state['is_chinese']
            st.session_state['is_chinese'] = st.toggle("显示中文", value=True)
            
    with st.expander("💬 AI对话", expanded=True):
        # 聊天消息显示
        for msg in st.session_state.get("messages", []):
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
        
        # 用户输入
        # 修改原有的聊天输入处理部分
        if prompt := st.chat_input("输入您的问题..."):
            with st.spinner("教授正在思考..."):
                # 添加用户消息
                st.session_state.messages.append({"role": "user", "content": prompt})
                
                # 流式获取AI响应
                response_container = st.empty()
                full_response = ""
                for chunk in get_ai_response(prompt, selected_paper):
                    full_response += chunk
                    response_container.markdown(full_response + "▌")
                
                # 添加最终响应
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                st.rerun()

# 主界面布局
main_col = st.columns([10])[0]

# 修改原有的渲染部分
with main_col:
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
                


with open("static/css/style.css", "r", encoding="utf-8") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# st.markdown(
#     """
#     <style>
#     /* .stApp { overflow: hidden; }   禁止滚动条 */
#     .katex { font-size: 1.2em !important; }  /* 添加公式字体大小调整 */
#     </style>
#     """,
#     unsafe_allow_html=True
