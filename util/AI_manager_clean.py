from PyQt6.QtCore import QObject, pyqtSignal, QUuid
from util.AI_professor_chat import AIProfessorChat
from util.threads import AIResponseThread
from util.TTS_manager import TTSManager
from util.voice_input import VoiceInput
from util.rag_retriever import RagRetriever
import os

class AIManager(QObject):
    """
    AI管理类 - 处理所有AI相关的功能
    
    包括:
    - AI对话逻辑
    - RAG检索增强生成
    """
    # 信号定义
    ai_response_ready = pyqtSignal(str)       # AI回复准备好信号
    ai_sentence_ready = pyqtSignal(str, str)  # 单句AI回复准备好信号（内容, 请求ID）
    ai_generation_cancelled = pyqtSignal()    # AI生成被取消信号
    
    def __init__(self):
        """初始化AI管理器"""
        super().__init__()
        
        # 初始化AI聊天助手
        self._init_ai_assistant()
        
        # 缓存待显示的句子
        self.pending_sentences = {}
        self.data_manager = None  # 将在later设置
        
        # 添加状态标志来跟踪是否有正在进行的AI生成
        self.is_generating_response = False
        
        # 当前活动的请求ID
        self.current_request_id = None

        # 添加累积响应变量
        self.accumulated_response = ""
        
    
    def set_data_manager(self, data_manager):
        """设置数据管理器引用"""
        self.data_manager = data_manager
    
    def _init_ai_assistant(self):
        """初始化AI聊天助手和响应线程"""
        self.ai_chat = AIProfessorChat()
        self.ai_response_thread = AIResponseThread(self.ai_chat)
        self.ai_response_thread.response_ready.connect(self._on_ai_response_ready)
        # 连接新的单句信号
        self.ai_response_thread.sentence_ready.connect(self._on_ai_sentence_ready)
    
    def cancel_current_response(self):
        """取消当前正在生成的AI响应"""
        print("取消当前的AI响应...")
        
        # 处理已收集的部分响应
        # 只有当有实际内容时才添加到历史记录
        if self.accumulated_response and self.accumulated_response.strip():
            print(f"保存已生成的部分响应到对话历史: {self.accumulated_response[:30]}...")
            # 将已生成的部分添加到对话历史
            if hasattr(self.ai_chat, 'conversation_history'):
                # 添加到对话历史
                self.ai_chat.conversation_history.append({
                    "role": "assistant", 
                    "content": self.accumulated_response
                })
        # 无论是否添加到历史，都重置累积响应
        self.accumulated_response = ""
        
        # 清空待处理的句子
        self.pending_sentences.clear()
        
        # 中断AI响应线程
        if self.ai_response_thread.isRunning():
            print("正在停止AI生成...")
            self.ai_response_thread.requestInterruption()
            self.ai_response_thread.wait(1000)  # 等待最多1秒
            
            # 发出取消信号，以便UI清理loading bubble
            self.is_generating_response = False
            self.ai_generation_cancelled.emit()
            
            # 清除当前请求ID
            self.current_request_id = None
    
    def is_busy(self):
        """检查是否有AI响应正在生成或TTS正在播放"""
        return self.is_generating_response
    
    def get_ai_response(self, query, paper_id=None, visible_content=None):
        """获取AI对用户查询的响应"""
        try:
            # 如果已经有正在生成的响应，先取消它
            if self.is_generating_response:
                print("[AIManager] Cancelling existing response before starting new one")
                self.cancel_current_response()
            
            # 确保线程不在运行状态
            if self.ai_response_thread.isRunning():
                print("等待上一个AI响应线程结束...")
                self.ai_response_thread.requestInterruption()
                self.ai_response_thread.wait(1000)  # 等待最多1秒
                
                # 如果线程仍在运行，创建新的线程
                if self.ai_response_thread.isRunning():
                    print("创建新的AI响应线程...")
                    self._init_ai_assistant()
            
            # 生成新的请求ID
            request_id = str(QUuid.createUuid().toString(QUuid.StringFormat.Id128))
            self.current_request_id = request_id
            print(f"创建新的AI请求，ID: {request_id}")
            
            # 确保有论文上下文(如果必要)
            if not paper_id and self.data_manager and self.data_manager.current_paper:
                paper_id = self.data_manager.current_paper.get('id')
                
            # 获取论文数据并设置上下文
            if paper_id and self.data_manager:
                paper_data = self.data_manager.load_rag_tree(paper_id)
                if paper_data:
                    self.ai_chat.set_paper_context(paper_id, paper_data)
            
            # 设置请求参数并启动线程
            self.ai_response_thread.set_request(query, paper_id, visible_content)
            
            # 更新状态标志
            self.is_generating_response = True
            
            # 启动线程
            self.ai_response_thread.start()
            
            # 返回请求ID，以便调用者可以使用
            return request_id
        except Exception as e:
            print(f"AI响应生成失败: {str(e)}")
            self.is_generating_response = False
            self.current_request_id = None
            self.ai_response_ready.emit(f"抱歉，处理您的问题时出现错误: {str(e)}")
            return None

    def _on_ai_response_ready(self, response):
        """处理AI响应就绪事件"""
        # 更新状态标志
        self.is_generating_response = False
        
        # 发出信号通知UI
        self.ai_response_ready.emit(response)
        
    
    def _on_ai_sentence_ready(self, sentence, emotion, scroll_info=None):
        """处理单句AI响应就绪事件"""
        # 如果没有当前请求ID，可能是已经被取消，忽略这个句子
        if not self.current_request_id:
            return
        
        # 缓存句子，并关联请求ID和情绪
        sentence_id = id(sentence)  # 使用对象id作为唯一标识
        self.pending_sentences[sentence_id] = (sentence, self.current_request_id, emotion)
        
        # 累积响应
        self.accumulated_response += sentence
        
        # 删除此行，不在AI生成时触发显示
        self.ai_sentence_ready.emit(sentence, self.current_request_id)
        
        # 处理滚动信息 - 如果有滚动信息且markdown_view被设置，则执行滚动
        if scroll_info and hasattr(self, 'markdown_view') and self.markdown_view:
            self._scroll_to_content(scroll_info)
    
    def cleanup(self):
        """清理所有资源"""
        # 删除语音识别清理代码
        if self.ai_response_thread and self.ai_response_thread.isRunning():
            self.ai_response_thread.requestInterruption()
            self.ai_response_thread.wait()

    def init_rag_retriever(self, base_path):
        """在后台初始化RAG检索器"""
        try:
            print(f"[INFO] 开始初始化RAG检索器: {base_path}")
            
            # 创建RAG检索器并开始后台加载
            self.retriever = RagRetriever(base_path)
            
            # 确保AI聊天模块使用相同的检索器
            if hasattr(self, 'ai_chat') and self.ai_chat:
                if self.ai_chat.retriever is not None:
                    print("[INFO] 替换AI聊天模块中的旧检索器")
                self.ai_chat.retriever = self.retriever
                
            # 连接加载完成信号以进行日志记录
            self.retriever.loading_complete.connect(self._on_retriever_loaded)
            
            return True
        except Exception as e:
            print(f"[ERROR] 初始化RAG检索器失败: {str(e)}")
            return False

    def _on_retriever_loaded(self, success):
        """处理检索器加载完成事件"""
        if success:
            print(f"[INFO] RAG检索器加载完成，共加载了 {len(self.retriever.paper_vector_paths)} 篇论文的向量库索引")
            
            # 可以添加额外验证代码
            for paper_id, path in self.retriever.paper_vector_paths.items():
                if not os.path.exists(path):
                    print(f"[WARNING] 论文 {paper_id} 的向量库路径不存在: {path}")
        else:
            print("[ERROR] RAG检索器加载失败或没有找到论文")

    def add_paper_vector_store(self, paper_id, vector_store_path):
        """添加新论文的向量库
        
        在处理完新论文后调用此方法
        
        Args:
            paper_id: 论文ID
            vector_store_path: 向量库路径
            
        Returns:
            bool: 成功返回True
        """
        if hasattr(self, 'retriever'):
            return self.retriever.add_paper(paper_id, vector_store_path)
        return False

    def _scroll_to_content(self, scroll_info):
        """根据滚动信息滚动到对应内容"""
        if not scroll_info:
            return
            
        # 获取当前语言
        current_lang = self.markdown_view.get_current_language()
        
        # 根据当前语言选择内容
        content = scroll_info['zh_content'] if current_lang == 'zh' else scroll_info['en_content']
        node_type = scroll_info.get('node_type', 'text')
        is_title = scroll_info.get('is_title', False)
        
        # 如果内容为空，尝试使用另一种语言的内容
        if not content:
            content = scroll_info['en_content'] if current_lang == 'zh' else scroll_info['zh_content']
        
        # 执行滚动
        if content:
            # 根据节点类型确定滚动类型
            if is_title:
                self.markdown_view._scroll_to_matching_content(content, 'title')
            else:
                self.markdown_view._scroll_to_matching_content(content, 'text')
