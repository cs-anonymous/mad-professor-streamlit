from PyQt6.QtCore import QThread, pyqtSignal
from pathlib import Path

class ProcessingThread(QThread):
    """处理PDF文件的线程"""
    processing_finished = pyqtSignal(str)  # 处理完成信号
    processing_error = pyqtSignal(str, str)  # 处理错误信号
    
    def __init__(self, pipeline, pdf_path, output_dir):
        super().__init__()
        self.pipeline = pipeline
        self.pdf_path = pdf_path
        self.output_dir = output_dir
        self.is_running = True
    
    def run(self):
        try:
            output_paths = self.pipeline.process(
                self.pdf_path, 
                self.output_dir
            )
            
            if self.is_running:  # 检查是否被取消
                self.processing_finished.emit(Path(self.pdf_path).stem)
        except Exception as e:
            if self.is_running:  # 只有在线程没有被手动停止时才报告错误
                self.processing_error.emit(Path(self.pdf_path).stem, str(e))
    
    def stop(self):
        """立即停止线程处理"""
        self.is_running = False
        self.terminate()  # 强制终止线程

# 修改 AIResponseThread 类以传递滚动信息
class AIResponseThread(QThread):
    """AI响应线程 - 处理AI响应生成，避免阻塞UI"""
    
    # 修改信号定义，添加滚动信息
    response_ready = pyqtSignal(str)
    sentence_ready = pyqtSignal(str, str, object)  # (句子, 情绪, 滚动信息)
    
    def __init__(self, ai_chat):
        """初始化AI响应线程"""
        super().__init__()
        self.ai_chat = ai_chat
        self.query = ""
        self.paper_id = None
        self.visible_content = None
        self.use_streaming = True  # 默认使用流式响应
    
    def set_request(self, query, paper_id=None, visible_content=None):
        """设置请求参数"""
        self.query = query
        self.paper_id = paper_id
        self.visible_content = visible_content
    
    def run(self):
        """执行线程"""
        if self.use_streaming:
            # 流式处理
            response = ""
            try:
                # 修改这里，接收情绪参数
                for sentence, emotion, scroll_info in self.ai_chat.process_query_stream(self.query, self.visible_content):
                    # 检查线程是否被请求中断
                    if self.isInterruptionRequested():
                        print("AI响应生成被中断")
                        break
                        
                    # 发射句子信号，传递实际情绪
                    self.sentence_ready.emit(sentence, emotion, scroll_info)
                    response += sentence
            except Exception as e:
                print(f"AI响应生成失败: {str(e)}")
                # 发射错误信号
                self.response_ready.emit(f"抱歉，处理您的问题时出现错误: {str(e)}")
                return
                
            # 发射完整响应信号
            if not self.isInterruptionRequested():
                self.response_ready.emit(response)
        else:
            # 非流式处理 - 单次响应
            try:
                # 直接处理查询并获取完整响应
                response = list(self.ai_chat.process_query_stream(self.query, self.visible_content))
                
                if self.isInterruptionRequested():
                    print("AI响应生成被中断")
                    return
                    
                # 发射完整响应信号
                if response:
                    self.response_ready.emit(response[-1][0])  # 只发送最后一个结果的句子部分
            except Exception as e:
                print(f"AI响应生成失败: {str(e)}")
                self.response_ready.emit(f"抱歉，处理您的问题时出现错误: {str(e)}")