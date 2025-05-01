from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                           QTextEdit, QScrollArea, QLabel, QFrame, QComboBox)
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QIcon, QFont

# 导入自定义组件和工具类
from util.paths import get_asset_path
from ui.message_bubble import MessageBubble, LoadingBubble
from util.AI_manager import AIManager

class ChatWidget(QWidget):
    """
    AI对话框组件
    
    提供用户与AI助手进行对话的界面，包括消息显示、输入框和控制按钮
    """
    # 颜色常量定义
    COLOR_UNINIT = "#9E9E9E"  # 灰色：未初始化
    COLOR_INIT = "#2196F3"    # 蓝色：初始化完成未激活
    COLOR_ACTIVE = "#4CAF50"  # 绿色：激活待命
    COLOR_VAD = "#FFC107"     # 黄色：检测到语音活动
    COLOR_ERROR = "red"       # 红色：错误状态

    def __init__(self, parent=None):
        """初始化聊天组件"""
        super().__init__(parent)
        self.ai_controller = None  # AI控制器引用
        self.paper_controller = None  # 论文控制器引用
        self.loading_bubble = None  # 加载动画引用
        self.is_voice_active = False  # 语音功能是否激活
        
        # 初始化UI
        self.init_ui()
        
        # 界面显示后立即初始化语音功能
        QTimer.singleShot(500, self.init_voice_recognition)
        
    def set_ai_controller(self, ai_controller:AIManager):
        """设置AI控制器引用"""
        self.ai_controller = ai_controller
        # 连接AI控制器信号
        self.ai_controller.ai_response_ready.connect(self.on_ai_response_ready)
        self.ai_controller.ai_sentence_ready.connect(self.on_ai_sentence_ready)  
        self.ai_controller.voice_text_received.connect(self.on_voice_text_received)
        self.ai_controller.vad_started.connect(self.on_vad_started)
        self.ai_controller.vad_stopped.connect(self.on_vad_stopped)
        self.ai_controller.voice_error.connect(self.on_voice_error)
        self.ai_controller.voice_ready.connect(self.on_voice_ready)
        self.ai_controller.voice_device_switched.connect(self.on_device_switched)
        # 新增信号连接
        self.ai_controller.ai_generation_cancelled.connect(self.on_ai_generation_cancelled)
        
        # 保存当前活动请求ID
        self.active_request_id = None
    
    def set_paper_controller(self, paper_controller):
        """设置论文控制器引用"""
        self.paper_controller = paper_controller

    # 修改set_markdown_view方法
    def set_markdown_view(self, markdown_view):
        """设置Markdown视图引用"""
        self.markdown_view = markdown_view
        # 将markdown_view传递给AI管理器
        if self.ai_controller:
            self.ai_controller.markdown_view = markdown_view
            
    def init_ui(self):
        """初始化用户界面"""
        # 创建主布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建组件
        title_bar = self.create_title_bar()
        chat_container = self.create_chat_container()
        
        # 添加到主布局
        layout.addWidget(title_bar)
        layout.addWidget(chat_container)
    
    def create_title_bar(self):
        """
        创建聊天区域标题栏
        
        Returns:
            QFrame: 配置好的标题栏
        """
        # 标题栏
        title_bar = QFrame()
        title_bar.setObjectName("chatTitleBar")
        title_bar.setFixedHeight(40)
        title_bar.setStyleSheet("""
            #chatTitleBar {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                             stop:0 #1565C0, stop:1 #0D47A1);
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                color: white;
            }
        """)
        
        # 标题栏布局
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(15, 0, 15, 0)
        
        # 设置标题文本和字体
        title_font = QFont("Source Han Sans SC", 11, QFont.Weight.Bold)
        title_label = QLabel("你的导师")
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: white; font-weight: bold;")
        
        title_layout.addWidget(title_label)
        
        return title_bar
    
    def create_chat_container(self):
        """
        创建聊天内容容器
        
        Returns:
            QFrame: 配置好的聊天容器
        """
        # 聊天容器
        chat_container = QFrame()
        chat_container.setObjectName("chatContainer")
        chat_container.setStyleSheet("""
            #chatContainer {
                background-color: #E8EAF6;
                border-left: 1px solid #CFD8DC;
                border-right: 1px solid #CFD8DC;
                border-bottom: 1px solid #CFD8DC;
                border-bottom-left-radius: 12px;
                border-bottom-right-radius: 12px;
            }
        """)
        
        container_layout = QVBoxLayout(chat_container)
        container_layout.setContentsMargins(10, 10, 10, 10)
        
        # 创建消息显示区域
        self.scroll_area = self.create_message_display_area()
        
        # 创建输入区域
        input_frame = self.create_input_area()
        
        # 添加到容器布局
        container_layout.addWidget(self.scroll_area, 1)
        container_layout.addWidget(input_frame)
        
        return chat_container
    
    def create_message_display_area(self):
        """
        创建消息显示区域
        
        Returns:
            QScrollArea: 配置好的消息滚动区域
        """
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #FFFFFF;
                border: 1px solid #E0E0E0;
                border-radius: 10px;
            }
        """)
        
        # 创建消息容器
        self.messages_container = QWidget()
        self.messages_layout = QVBoxLayout(self.messages_container)
        self.messages_layout.setContentsMargins(0, 10, 0, 10)
        self.messages_layout.setSpacing(10)
        self.messages_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.messages_container.setStyleSheet("background-color: transparent;")
        
        # 设置滚动区域的内容
        scroll_area.setWidget(self.messages_container)
        
        return scroll_area
    
    def create_input_area(self):
        """
        创建消息输入区域
        
        Returns:
            QFrame: 配置好的输入区域框架
        """
        # 输入区域框架
        input_frame = QFrame()
        input_frame.setObjectName("inputFrame")
        input_frame.setStyleSheet("""
            #inputFrame {
                background-color: #FFFFFF;
                border: 1px solid #CFD8DC;
                border-radius: 12px;
                padding: 5px;
            }
        """)
        
        input_layout = QVBoxLayout(input_frame)
        input_layout.setContentsMargins(12, 12, 12, 12)
        input_layout.setSpacing(10)  # 增加间距
        
        # 创建文本输入框
        self.message_input = QTextEdit()
        self.message_input.setPlaceholderText("输入您对导师的问题...")
        self.message_input.setMaximumHeight(100)
        self.message_input.setObjectName("messageInput")
        self.message_input.setStyleSheet("""
            #messageInput {
                border: none;
                background-color: #F5F7FA;
                border-radius: 8px;
                padding: 10px;  /* 增加内边距 */
                font-family: 'Source Han Sans SC', 'Segoe UI', sans-serif;
                font-size: 13px;
            }
        """)
        # 连接回车键发送功能
        self.message_input.installEventFilter(self)
        
        # 创建控制区容器
        control_container = QWidget()
        control_layout = QHBoxLayout(control_container)
        control_layout.setContentsMargins(0, 8, 0, 0)
        control_layout.setSpacing(12)  # 增加控件间距
        
        # 创建语音控制区
        voice_container = self.create_voice_container()
        
        # 创建发送按钮
        send_button = self.create_send_button()
        
        # 添加到控制布局
        control_layout.addWidget(voice_container)
        control_layout.addStretch(1)
        control_layout.addWidget(send_button)
        
        # 添加到主布局
        input_layout.addWidget(self.message_input)
        input_layout.addWidget(control_container)
        
        return input_frame
    
    def create_voice_container(self):
        """
        创建语音控制容器，包含状态指示灯、麦克风按钮和设备选择
        """
        # 创建容器
        voice_container = QWidget()
        voice_layout = QHBoxLayout(voice_container)
        voice_layout.setContentsMargins(0, 0, 0, 0)
        voice_layout.setSpacing(10)
        
        # 状态指示灯 - 保持不变
        self.voice_status_indicator = QLabel()
        self.voice_status_indicator.setFixedSize(10, 10)
        self.voice_status_indicator.setStyleSheet("""
            background-color: #9E9E9E;
            border-radius: 5px;
            border: 1px solid rgba(0, 0, 0, 0.1);
        """)
        voice_layout.addWidget(self.voice_status_indicator)
        
        # 麦克风按钮 - 保持不变
        self.voice_button = self.create_voice_button()
        voice_layout.addWidget(self.voice_button)
        
        # 创建可交互的设备选择组件
        self.device_combo = QComboBox()
        self.device_combo.setFixedWidth(185)
        self.device_combo.setObjectName("deviceCombo")
        
        # 优化样式：修复三角形和添加下拉列表圆角
        self.device_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #C5CAE9;
                border-radius: 5px;
                padding: 4px 10px 4px 8px;
                background-color: white;
                color: #303F9F;
                font-size: 12px;
                selection-background-color: #E8EAF6;
            }
            QComboBox:hover {
                border: 1px solid #7986CB;
                background-color: #F5F7FA;
            }
            QComboBox:focus {
                border: 1px solid #3F51B5;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 16px;
                border-left: 1px solid #C5CAE9;
                border-top-right-radius: 4px;
                border-bottom-right-radius: 4px;
                background-color: #E8EAF6;
            }
            QComboBox::down-arrow {
                image: url(""" + get_asset_path("down_arrow.svg").replace("\\", "/") + """);
                width: 10px;
                height: 10px;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #C5CAE9;
                selection-background-color: #E8EAF6;
                selection-color: #303F9F;
                background-color: white;
                border-radius: 5px;
                padding: 5px;
                outline: none;
            }
        """)
        
        # 连接信号
        self.device_combo.currentIndexChanged.connect(self.on_device_changed)
        voice_layout.addWidget(self.device_combo)
        
        return voice_container
    
    def create_voice_button(self):
        """
        创建语音按钮
        
        Returns:
            QPushButton: 配置好的语音按钮
        """
        voice_button = QPushButton()
        voice_button.setIcon(QIcon(get_asset_path("microphone.svg")))
        voice_button.setObjectName("voiceButton")
        voice_button.setFixedSize(32, 32)
        voice_button.setCursor(Qt.CursorShape.PointingHandCursor)
        voice_button.setToolTip("点击开启/关闭语音识别")
        voice_button.setIconSize(QSize(16, 16))
        voice_button.setStyleSheet("""
            #voiceButton {
                background-color: #E3F2FD;
                border: 1px solid #BBDEFB;
                border-radius: 16px;
                padding: 5px;
            }
            #voiceButton:hover {
                background-color: #BBDEFB;
            }
        """)
        voice_button.clicked.connect(self.toggle_voice_chat)
        
        return voice_button
    
    def create_send_button(self):
        """
        创建发送按钮
        
        Returns:
            QPushButton: 配置好的发送按钮
        """
        send_button = QPushButton("发送")
        send_button.setCursor(Qt.CursorShape.PointingHandCursor)
        send_button.setObjectName("sendButton")
        send_button.setFixedHeight(36)  # 增加高度
        send_button.setMinimumWidth(100)  # 增加宽度
        
        # 美化发送按钮
        send_button.setStyleSheet("""
            #sendButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                             stop:0 #303F9F, stop:1 #1A237E);
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 20px;
                font-weight: bold;
                font-size: 14px;
            }
            #sendButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                             stop:0 #3949AB, stop:1 #303F9F);
            }
            #sendButton:pressed {
                background: #1A237E;
                padding-left: 22px;
                padding-top: 10px;
            }
        """)
        send_button.clicked.connect(self.send_message)
        
        return send_button
    
    def send_message(self):
        """
        发送用户消息
        
        获取输入框中的消息，创建用户消息气泡并清空输入框
        """
        message = self.message_input.toPlainText().strip()
        if message:
            # 添加用户消息气泡
            user_bubble = MessageBubble(message, is_user=True)
            self.messages_layout.addWidget(user_bubble)
            
            # 清空输入框
            self.message_input.clear()
            
            # 滚动到底部
            QTimer.singleShot(100, self.scroll_to_bottom)
            
            # 处理消息并获取AI响应
            self.process_message(message)
    
    def process_message(self, message):
        """处理用户消息并获取AI响应"""
        if self.loading_bubble:
            self.loading_bubble.stop_animation()
            self.messages_layout.removeWidget(self.loading_bubble)
            self.loading_bubble.deleteLater()
            self.loading_bubble = None

        # 如果有AI控制器，则使用AI控制器处理消息
        if self.ai_controller:
            # 如果已经有正在生成的响应或TTS正在播放，先取消它
            if self.ai_controller.is_busy():
                # 中止当前的AI生成和TTS播放
                self.ai_controller.cancel_current_response()
                
                # 如果尚未生成任何内容，检查是否需要合并问题
                if not self.ai_controller.accumulated_response and self.ai_controller.ai_chat:
                    history = self.ai_controller.ai_chat.conversation_history
                    if len(history) >= 1 and history[-1]["role"] == "user":
                        # 找到上一个用户问题
                        prev_question = history[-1]["content"]
                        # 合并问题
                        combined_question = f"{prev_question} {message}"
                        print(f"合并连续问题: '{combined_question}'")
                        
                        # 更新历史记录中的问题
                        history[-1]["content"] = combined_question
                        
                        # 更新message为合并后的问题
                        message = combined_question
            
            # 获取当前论文ID，如果有的话
            paper_id = None
            if self.paper_controller and self.paper_controller.current_paper:
                paper_id = self.paper_controller.current_paper.get('id')

            # 获取当前可见文本，如果有的话
            visible_content = None
            if hasattr(self, 'markdown_view') and self.markdown_view:
                visible_content = self.markdown_view.get_current_visible_text()
            
            # 显示加载动画
            self.loading_bubble = LoadingBubble()
            self.messages_layout.addWidget(self.loading_bubble)
            self.scroll_to_bottom()
            
            # 通过AI控制器获取AI响应，同时保存请求ID
            request_id = self.ai_controller.get_ai_response(message, paper_id, visible_content)
            self.active_request_id = request_id
        else:
            # 使用默认响应
            QTimer.singleShot(500, lambda: self.receive_ai_message(
                f"我已收到您的问题：{message}\n\nAI控制器未连接，无法获取具体响应。"))
    
    def receive_ai_message(self, message):
        """
        接收并显示AI消息
        
        Args:
            message: AI返回的消息内容
        """
        # 添加AI消息气泡
        ai_bubble = MessageBubble(message, is_user=False)
        self.messages_layout.addWidget(ai_bubble)
        
        # 滚动到底部
        QTimer.singleShot(100, self.scroll_to_bottom)

    def on_ai_sentence_ready(self, sentence, request_id):
        """处理单句AI响应"""
        # 如果请求ID不匹配当前活动请求，忽略这句话
        if request_id != self.active_request_id:
            print(f"忽略过时请求的句子: '{sentence[:20]}...' (请求ID: {request_id})")
            return
            
        # 如果有加载动画且这是第一个句子，移除加载动画
        if self.loading_bubble is not None:
            self.loading_bubble.stop_animation()
            self.messages_layout.removeWidget(self.loading_bubble)
            self.loading_bubble.deleteLater()
            self.loading_bubble = None
        
        # 显示单句回复
        ai_bubble = MessageBubble(sentence, is_user=False)
        self.messages_layout.addWidget(ai_bubble)
        
        # 滚动到底部
        QTimer.singleShot(100, self.scroll_to_bottom)
    
    def on_ai_response_ready(self, response):
        """
        当完整AI响应准备好时调用（仅用于非流式响应或流式响应结束）
        
        对于流式响应，主要通过on_ai_sentence_ready处理
        """
        # 如果仍有加载动画，说明是非流式响应或没有分句成功，移除加载动画
        if self.loading_bubble is not None:
            self.loading_bubble.stop_animation()
            self.messages_layout.removeWidget(self.loading_bubble)
            self.loading_bubble.deleteLater()
            self.loading_bubble = None
            
            # 对于非流式响应，才直接显示完整回复
            if not self.ai_controller.ai_response_thread.use_streaming:
                self.receive_ai_message(response)
            # 否则不显示，等TTS播放时显示
    
    def on_ai_generation_cancelled(self):
        """处理AI生成被取消的情况"""
        # 清理loading bubble
        if self.loading_bubble:
            self.loading_bubble.stop_animation()
            self.messages_layout.removeWidget(self.loading_bubble)
            self.loading_bubble.deleteLater()
            self.loading_bubble = None
        
        # 清除当前请求ID，因为请求已被取消
        self.active_request_id = None
    
    def scroll_to_bottom(self):
        """滚动到对话底部"""
        self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        )
    
    def toggle_voice_chat(self):
        """切换语音聊天功能开关"""
        if not self.ai_controller:
            return
            
        self.is_voice_active = not self.is_voice_active
        success = self.ai_controller.toggle_voice_detection(self.is_voice_active)
        
        # 更新UI状态
        if success and self.is_voice_active:
            # 绿色表示激活待命状态
            self.set_indicator_color(self.COLOR_ACTIVE)
            self.voice_button.setToolTip("点击关闭语音识别")
            self.voice_button.setStyleSheet("""
                #voiceButton {
                    background-color: #303F9F;
                    border: 1px solid #1A237E;
                    border-radius: 16px;
                    padding: 5px;
                }
                #voiceButton:hover {
                    background-color: #3949AB;
                }
            """)
        else:
            self.is_voice_active = False  # 如果失败，重置状态
            # 蓝色表示初始化完成但未激活
            self.set_indicator_color(self.COLOR_INIT)
            self.voice_button.setToolTip("点击开启语音识别")
            self.voice_button.setStyleSheet("""
                #voiceButton {
                    background-color: #E3F2FD;
                    border: 1px solid #BBDEFB;
                    border-radius: 16px;
                    padding: 5px;
                }
                #voiceButton:hover {
                    background-color: #BBDEFB;
                }
            """)
    
    def set_indicator_color(self, color):
        """设置语音状态指示灯颜色"""
        self.voice_status_indicator.setStyleSheet(f"""
            background-color: {color}; 
            border-radius: 5px;
            border: 1px solid rgba(0, 0, 0, 0.1);
        """)
    
    def init_voice_recognition(self):
        """初始化语音识别"""
        if self.ai_controller:
            # 初始化前先设置为灰色，表示系统正在初始化
            self.set_indicator_color(self.COLOR_UNINIT)
            
            # 初始化设备列表
            self.refresh_devices()
            
            # 获取选中的设备ID
            device_id = self.get_selected_device_index()
            
            # 初始化AI管理器中的语音识别
            self.ai_controller.init_voice_recognition(device_id)
    
    def refresh_devices(self):
        """刷新设备列表"""
        if not self.ai_controller:
            return
            
        try:
            # 保存当前选择
            current_index = self.device_combo.currentIndex()
            current_device_id = self.device_combo.currentData() if current_index >= 0 else None
            
            # 清空并重新填充设备列表
            self.device_combo.clear()
            
            # 获取设备列表
            devices = self.ai_controller.get_voice_devices()
            for device_id, device_name in devices:
                self.device_combo.addItem(device_name, device_id)
            
            # 尝试恢复之前选择
            if current_device_id is not None:
                index = self.device_combo.findData(current_device_id)
                if index >= 0:
                    self.device_combo.setCurrentIndex(index)
                        
        except Exception as e:
            print(f"刷新设备列表失败: {str(e)}")
    
    def get_selected_device_index(self):
        """获取当前选择的设备索引"""
        index = self.device_combo.currentIndex()
        if index >= 0:
            return self.device_combo.itemData(index)
        return 1  # 默认设备索引
    
    def on_device_changed(self, index):
        """设备选择变更事件"""
        if index < 0 or not self.ai_controller:
            return
                
        device_id = self.device_combo.itemData(index)
        
        # 设置为灰色表示开始初始化
        self.set_indicator_color(self.COLOR_UNINIT)
        self.device_combo.setEnabled(False)
        
        # 切换设备
        success = self.ai_controller.switch_voice_device(device_id)
        if not success:  # 如果切换立即失败
            self.device_combo.setEnabled(True)
            self.set_indicator_color(self.COLOR_ERROR)
            QTimer.singleShot(2000, lambda: 
                self.set_indicator_color(self.COLOR_ACTIVE) if self.is_voice_active 
                else self.set_indicator_color(self.COLOR_INIT))
    
    def on_device_switched(self, success):
        """设备切换结果处理"""
        self.device_combo.setEnabled(True)
        
        if success:
            if self.is_voice_active:
                # 如果语音激活，恢复绿色
                self.set_indicator_color(self.COLOR_ACTIVE)
            else:
                # 如果语音未激活，恢复蓝色
                self.set_indicator_color(self.COLOR_INIT)
        else:
            # 错误时显示红色
            self.set_indicator_color(self.COLOR_ERROR)
            QTimer.singleShot(2000, lambda: 
                self.set_indicator_color(self.COLOR_ACTIVE) if self.is_voice_active 
                else self.set_indicator_color(self.COLOR_INIT))
    
    def on_voice_text_received(self, text):
        """接收到语音文本"""
        self.message_input.setText(text)
        # 自动发送
        self.send_message()
    
    def on_vad_started(self):
        """检测到语音活动开始"""
        if self.is_voice_active:
            # 变为黄色表示检测到语音活动
            self.set_indicator_color(self.COLOR_VAD)
    
    def on_vad_stopped(self):
        """检测到语音活动结束"""
        if self.is_voice_active:
            # 回到绿色表示激活待命状态
            self.set_indicator_color(self.COLOR_ACTIVE)
    
    def on_voice_error(self, error_message):
        """语音识别错误"""
        print(f"语音识别错误: {error_message}")
        self.set_indicator_color(self.COLOR_ERROR)
        QTimer.singleShot(2000, lambda: 
            self.set_indicator_color(self.COLOR_ACTIVE) if self.is_voice_active 
            else self.set_indicator_color(self.COLOR_INIT))
    
    def on_voice_ready(self):
        """语音识别准备就绪"""
        # 启用对话按钮
        self.voice_button.setEnabled(True)
        # 初始化完成后设置为蓝色待命状态
        self.set_indicator_color(self.COLOR_INIT)
    
    def eventFilter(self, obj, event):
        """
        事件过滤器，处理输入框按键事件
        
        当按下回车键且没有按下Shift键时发送消息，
        当按下Shift+回车时插入换行符
        
        Args:
            obj: 事件源对象
            event: 事件对象
            
        Returns:
            bool: 事件是否已处理
        """
        # 检查事件是否来自messageInput，且是键盘按下事件，且按键是回车
        if obj == self.message_input and event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key.Key_Return and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                # 回车键按下且没有按下Shift键，触发发送消息
                self.send_message()
                return True  # 事件已处理
            elif event.key() == Qt.Key.Key_Return and event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                # Shift+回车，插入换行符
                return False  # 让QTextEdit处理这个事件
        
        # 其他事件交给父类处理
        return super().eventFilter(obj, event)
    
    def closeEvent(self, event):
        """窗口关闭事件处理"""
        # 不再需要手动处理voice_thread，由ai_manager负责清理
        # 如果有父类方法，调用它
        if hasattr(super(), 'closeEvent'):
            super().closeEvent(event)