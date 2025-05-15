import streamlit as st
from util.data_manager import DataManager
# Add at the very top before other imports
import os
import json  # 添加在文件顶部
from util.AI_professor_chat import AIProfessorChat
import uuid
import shutil
import re
import urllib.parse  # 添加导入
from pypinyin import lazy_pinyin


os.environ["TORCH_DISABLE_MLOCK"] = "1"  # Disable PyTorch memory locking

# 应用基础配置
st.set_page_config(
    page_title="暴躁的教授读论文",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 在导入之后立即初始化session state
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'show_log' not in st.session_state:
    st.session_state.show_log = False 
if 'edit_mode' not in st.session_state:
    st.session_state.edit_mode = False
# 在现有session_state初始化后添加
if 'ai_is_generating' not in st.session_state:
    st.session_state.ai_is_generating = False
if 'ai_current_request_id' not in st.session_state:
    st.session_state.ai_current_request_id = None
if 'ai_accumulated_response' not in st.session_state:
    st.session_state.ai_accumulated_response = ""
if 'selected_paper' not in st.session_state:
    st.session_state.selected_paper = None    
if 'selected_file' not in st.session_state:
    st.session_state.selected_file = 'article_zh'    # 设置默认值为中文文档
if 'ai_chat' not in st.session_state:
    st.session_state.ai_chat = AIProfessorChat()

# 初始化核心模块
BASEDIR = os.path.dirname(os.path.abspath(__file__))

# 整个应用生命周期内保持单例
@st.cache_resource
def init_data_manager():
    data_manager = DataManager(BASEDIR)
    data_manager.load_papers_index()
    data_manager.scan_for_unprocessed_files()
    return data_manager

# 替换原有的初始化
data_manager = init_data_manager()


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


# st.session_state.selected_paper = data_manager.papers_index[0]['id'] if data_manager.papers_index else None
# change_seleted_paper()



# 在现有函数后添加文件上传回调函数
def handle_file_upload():
    if "uploaded_file" in st.session_state:
        uploaded_file = st.session_state.uploaded_file
        file_id = uploaded_file.name.strip('.pdf').replace(" ", "_")[:50]

        if file_id in [p['id'] for p in data_manager.papers_index]:
            st.error("该论文已存在，请选择其他文件")
            del st.session_state.uploaded_file
            return

        # 确保路径处理正确
        save_path = os.path.abspath(os.path.join("static", "data", file_id+".pdf"))
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
            format_func=lambda x: next(p['translated_title'] for p in data_manager.papers_index if p['id'] == x),
            key='selected_paper',
            on_change=change_seleted_paper,
            placeholder="请选择论文",
        )

        if selected_paper:
            selected_file = st.selectbox(
                "选择文件",
                options=['metadata', 'article_en', 'article_zh', 'rag_md', 'rag_tree'],
                format_func=lambda x: {
                    'metadata': '元数据',
                    'article_en': '英文文档',
                    'article_zh': '中文文档',
                    'rag_md': 'RAG文档',
                    'rag_tree': 'RAG树'
                }[x],
                key='selected_file',
                placeholder="中文文档",
                index=2  # 设置默认选中'article_zh'（第3个选项）
            )

            # 新增：显示/隐藏Markdown原文按钮（放在侧边栏）
            show_source_file_types = ['article_en', 'article_zh', 'rag_md']
            if selected_file in show_source_file_types:
                if 'show_markdown_source' not in st.session_state:
                    st.session_state['show_markdown_source'] = False
                btn_label = "显示Markdown源码" if not st.session_state['show_markdown_source'] else "渲染Markdown视图"
                if st.button(btn_label, key="toggle_md_source_btn_sidebar"):
                    st.session_state['show_markdown_source'] = not st.session_state['show_markdown_source']
                    st.rerun()  # 添加rerun()来解决按钮点击两次的问题

        col1, col2, col3 = st.columns([1,1,1])
        with col1:
            if st.button("📝 编辑文件", key="edit_paper_btn"):
                st.session_state.edit_mode = True
        with col2:
            # 删除论文对应文件夹
            if st.button("🗑️ 删除论文", key="delete_paper_btn"):
                paper_path = os.path.join(BASEDIR, 'output', st.session_state['selected_paper'])
                if os.path.exists(paper_path):
                    shutil.rmtree(paper_path)
                    st.rerun()
                else:
                    st.error("论文文件夹不存在")
        with col3:
            if st.button("🔄 刷新列表", key="refresh_db"):
                data_manager.deduplicate_paper_index()
    
    
    # 修改文件上传组件
    with st.expander("🚀 处理队列", expanded=True):
        uploaded_file = st.file_uploader(
            "上传论文", 
            type=["pdf"],
            key="uploaded_file",
            on_change=handle_file_upload
        )
            
        # 修改后的控制按钮行
        col1, col2, col3 = st.columns([1,1,1])
        with col1:
            # 切换式按钮
            if data_manager.is_paused:
                if st.button("▶️ 继续处理", key="resume_btn"):
                    data_manager.resume_processing()
                    data_manager.is_paused = False
            else:
                if st.button("⏸️ 暂停处理", key="pause_btn"):
                    data_manager.pause_processing()
                    data_manager.is_paused = True
        with col2:
            if st.button("🔄 更新进度", key="scan"):
                data_manager.scan_for_unprocessed_files()
        with col2:
            st.session_state['show_log'] = st.toggle("显示日志", value=False)
        
        st.write(f"当前处理队列（共{len(data_manager.processing_queue)}项），是否暂停：{data_manager.is_paused}，正在处理：{data_manager.is_processing}")
        if data_manager.processing_queue:
            for item in data_manager.processing_queue:
                status_icon = {"pending": "⏳", "processing": "🔄", "completed": "✅", "failed": "❌", "incomplete": "🔧"}[item['status']]
                st.write(f"{status_icon} ({item['status']}) {item['id']}")
            
            current_item = data_manager.processing_queue[0] if data_manager.processing_queue else None
            if current_item:
                progress_data = data_manager.processing_progress
                st.caption("处理进度")
                st.write(f"{progress_data['stage_name']}\tprogress: {progress_data['progress']}% ({progress_data['index']}/{progress_data['total']})") 
                st.progress(progress_data['progress']/100)

            
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
    if st.session_state.show_log:
        log_container = st.empty()
        last_position = 0  # 追踪文件读取位置
        try:
            # 初始化时获取最后20行
            with open('stream.log', 'r') as f:
                lines = f.readlines()[-20:]
                log_content = "".join(lines)
                last_position = f.tell()
                log_container.markdown(log_content)  # 改用text组件
            
            # 持续监控更新
            import time
            while st.session_state.show_log:
                with open('stream.log', 'r') as f:
                    f.seek(last_position)
                    new_lines = f.readlines()
                    if new_lines:
                        log_content += "".join(new_lines)
                        # 保持最多保留100行
                        MAX_LINES = 100
                        if len(log_content.split('\n')) > MAX_LINES:
                            log_content = '\n'.join(log_content.split('\n')[-MAX_LINES:])
                        log_container.markdown(log_content)
                        last_position = f.tell()
                time.sleep(1)  # 降低检查频率
        except FileNotFoundError:
            st.error("日志文件stream.log不存在")
    elif selected_paper:
        paper = data_manager.load_paper_content(selected_paper)
        content = paper[selected_file] if selected_file in paper else paper['article_zh']

        # 添加编辑模式判断
        if st.session_state.edit_mode:
            # 编辑模式显示文本编辑框
            if selected_file in ['metadata', 'rag_tree']:
                content = json.dumps(content, indent=4, ensure_ascii=False)
            edited_content = st.text_area(
                "编辑内容",
                value=content,
                height=600,
                key="edit_content"
            )
            if st.button("保存修改"):
                # 这里可以添加保存逻辑
                data_manager.save_file(selected_paper, selected_file, edited_content)
                st.session_state.edit_mode = False
                st.success("修改已保存")

        else:
            # 原有内容渲染逻辑
            show_source_file_types = ['article_en', 'article_zh', 'rag_md']
            if selected_file in show_source_file_types and st.session_state.get('show_markdown_source', False):
                # 修改显示方式，添加height参数使其占满可用空间
                st.code(content, language="markdown", line_numbers=True, wrap_lines=True)
            elif selected_file in ['metadata', 'rag_tree']:
                st.json(content, expanded=True)
            else:
                # Generate TOC and add anchors to content
                toc = []
                content_with_anchors = content  # Initialize content with anchors

                # Extract headings and generate TOC
                def replace_heading(match):
                    level = len(match.group(1))  # Number of '#' determines the level
                    title = match.group(2).strip()  # Remove leading/trailing spaces
                    # Convert Chinese characters to pinyin
                    title_ascii = ''.join(lazy_pinyin(title))
                    anchor = urllib.parse.quote(title_ascii.replace(' ', '-').lower(), safe='')
                    toc.append((level, title, anchor))  # Add to TOC
                    return f'<h{level} id="{anchor}" data-custom-id="{anchor}">{title}</h{level}>'  # Add anchor to heading

                # Add anchors to content
                content_with_anchors = re.sub(r'(?m)^(#+)\s+(.*)', replace_heading, content)
                toc_markdown = []
                for level, title, anchor in toc:
                    indent = " " * (level - 1) * 4  # Indent based on heading level
                    toc_markdown.append(f"{indent}- [{title}](#{anchor})")
                toc_markdown = "\n".join(toc_markdown)
                print("📑 生成目录完成", toc)

                with st.expander("📑 目录", expanded=True):
                    st.markdown(toc_markdown, unsafe_allow_html=True)

                image_prefix = os.path.join('app', 'static', 'output', selected_paper)
                # 如果路径中出现了空格，替换为%20
                image_prefix = image_prefix.replace(" ", "%20")
                # Replace image paths in content
                content_with_anchors = re.sub(r'!\[(.*?)\]\((.*?)\)', lambda m: f'![{m.group(1)}]({image_prefix}/{m.group(2)})', content_with_anchors)

                print("📷 替换图片路径完成", content_with_anchors)
                # Render the combined markdown
                st.markdown(content_with_anchors, unsafe_allow_html=True)

                # 没有输出是因为 Streamlit 的 st.components.v1.html 注入的 JavaScript 代码运行在一个 iframe 中
                # JavaScript 代码无法直接访问主页面的 DOM，因此无法修改主页面的标题 id。
                st.components.v1.html("""
                <script>
                    function checkHeaders() {
                        console.log('Checking and updating headers...');
                        parent.document.querySelectorAll("h1, h2, h3, h4, h5, h6").forEach((el) => {
                            const customId = el.getAttribute('data-custom-id');
                            if (customId && el.id !== customId) {
                                el.id = customId;  // 替换 Streamlit 自动生成的 ID
                                console.log(`Updated ID: ${customId}`);
                            }
                        });
                    }

                    // 每隔2秒检查一次
                    // setInterval(() => checkHeaders(), 2000);
                    setTimeout(() => checkHeaders(), 1000);  // 初始调用
                    setTimeout(() => checkHeaders(), 2000);  // 初始调用
                </script>
                """, height=0)
    
    else:
        st.markdown("""
# 哼！又来一个不读论文的学生是吧？

很好，至少你知道打开这个软件。我是你的论文指导教授，**不要期望我对你手下留情**。

## 听好了，这是你能做的事：

- **选论文**：左边那一堆，挑一篇你能看懂的（如果有的话）
- **换语言**：中英文看不懂？按上面那个按钮切换，别指望换了语言就能理解内容
- **问问题**：有不懂的就右边提问，我会回答，虽然你的问题可能很蠢
- **看摘要**：懒得读全文？我给你总结重点，省得你到处抓瞎

## 开始用吧，别磨蹭！

从左边随便选一篇，然后开始读。有不明白的就问我，**别憋着装懂**！

记住：_真正的学术是刀尖起舞，而不是像你平时那样浅尝辄止！_

...不过别担心，我会一直在这陪你读完的。
""")


with open("static/css/style.css", "r", encoding="utf-8") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

