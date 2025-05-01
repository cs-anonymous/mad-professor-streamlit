import pyaudio
from PyQt6.QtCore import QObject, pyqtSignal, QThread, QMutex, QMutexLocker
from RealtimeSTT import AudioToTextRecorder
from zhconv import convert

class VoiceInputThread(QThread):
    """语音输入线程 - 使用QThread实现的长寿命线程"""
    
    # 定义信号
    text_received = pyqtSignal(str)         # 接收到文本信号
    vad_started = pyqtSignal()              # 语音活动开始信号
    vad_stopped = pyqtSignal()              # 语音活动结束信号
    error_occurred = pyqtSignal(str)        # 错误信号
    initialization_complete = pyqtSignal(bool)  # 初始化完成信号(成功/失败)
    
    def __init__(self, parent=None):
        """初始化语音输入线程"""
        super().__init__(parent)
        
        # 状态变量
        self.input_device_index = 0         # 当前使用的输入设备索引
        self.recorder = None                # 录音器实例
        self.is_active = False              # 是否激活语音识别
        self.need_init = True               # 是否需要初始化录音器
        self.last_working_device = 0        # 上一个工作正常的设备索引
        self.init_in_progress = False       # 是否正在初始化
        self.abort_current_init = False     # 是否中止当前初始化（用于设备切换）
        self.pending_device_change = None   # 待处理的设备变更
        
        # 互斥锁，保护多线程访问
        self.mutex = QMutex()
        
    def run(self):
        """QThread的主要执行方法，包含线程的主循环"""
        print("语音输入线程已启动")
        
        while not self.isInterruptionRequested():
            try:
                # 检查是否有待处理的设备变更
                with QMutexLocker(self.mutex):
                    if self.pending_device_change is not None:
                        self.input_device_index = self.pending_device_change
                        self.pending_device_change = None
                        self.need_init = True
                        self.abort_current_init = True
                        if self.init_in_progress:
                            print("检测到设备切换请求，中止当前初始化")
                
                # 检查是否需要初始化录音器
                if self.need_init and not self.init_in_progress:
                    with QMutexLocker(self.mutex):
                        self.init_in_progress = True
                        self.abort_current_init = False
                    
                    self._initialize_recorder()
                    
                    with QMutexLocker(self.mutex):
                        self.need_init = False
                        self.init_in_progress = False
                
                # 首先检查是否需要停止 - 解决问题2
                with QMutexLocker(self.mutex):
                    is_active = self.is_active
                    recorder = self.recorder
                
                # 如果不活跃，立即跳过此次循环
                if not is_active:
                    self.msleep(10)
                    continue
                
                # 只有在活跃状态且有录音器时才获取文本
                if recorder:
                    try:
                        # 获取语音识别结果
                        input_text = convert(recorder.text(), 'zh-cn')
                        
                        # 再次检查状态 - 可能在获取文本期间已经更改了状态
                        with QMutexLocker(self.mutex):
                            if not self.is_active:
                                # 如果不再活跃，立即跳过处理
                                continue
                        
                        # 如果有文本，发送信号
                        if input_text and input_text.strip():
                            print(f"\n[用户] {input_text}")
                            self.text_received.emit(input_text.strip())
                    except Exception as e:
                        with QMutexLocker(self.mutex):
                            still_active = self.is_active
                        
                        if still_active:  # 只在真正的错误时通知
                            print(f"语音识别错误: {str(e)}")
                            self.error_occurred.emit(f"语音识别错误: {str(e)}")
                
                # QThread的方式暂停线程，更加优雅且响应中断
                self.msleep(10)  # 10毫秒，相当于time.sleep(0.01)
                
            except Exception as e:
                print(f"语音线程循环出错: {str(e)}")
                self.error_occurred.emit(f"语音线程错误: {str(e)}")
                self.msleep(500)  # 错误后稍微长一点的延迟
    
    def _initialize_recorder(self):
        """初始化录音器"""
        success = False
        current_device = 0
        
        with QMutexLocker(self.mutex):
            current_device = self.input_device_index
        
        try:
            print(f"初始化录音器 (设备: {current_device})...")
            
            with QMutexLocker(self.mutex):
                # 关闭现有录音器
                if self.recorder:
                    try:
                        self.recorder.shutdown()
                    except Exception as e:
                        print(f"关闭旧录音器失败: {str(e)}")
                    self.recorder = None
            
            # 检查是否需要中止初始化
            should_abort = False
            with QMutexLocker(self.mutex):
                should_abort = self.abort_current_init
            
            if should_abort:
                print("初始化过程被中止")
                self.initialization_complete.emit(False)
                return
                
            with QMutexLocker(self.mutex):
                # 创建新录音器
                self.recorder = AudioToTextRecorder(
                    spinner=False,
                    model='large-v2',
                    language='zh',
                    input_device_index=current_device,
                    silero_sensitivity=0.5,
                    silero_use_onnx=True,
                    silero_deactivity_detection=True,
                    webrtc_sensitivity=2,
                    post_speech_silence_duration=0.3,
                    no_log_file=True,
                    on_vad_start=self._on_vad_start,
                    on_vad_stop=self._on_vad_stop
                )
                
                self.last_working_device = current_device
            
            print("录音器初始化成功")
            success = True
            
        except Exception as e:
            print(f"初始化录音器失败: {str(e)}")
            self.error_occurred.emit(f"初始化语音录音失败: {str(e)}")
            
            # 检查是否需要中止错误处理
            should_abort = False
            with QMutexLocker(self.mutex):
                should_abort = self.abort_current_init
            
            if should_abort:
                print("初始化错误处理被中止")
                return
                
            # 尝试恢复到上一个工作设备
            with QMutexLocker(self.mutex):
                if current_device != self.last_working_device:
                    print(f"尝试回退到设备 {self.last_working_device}")
                    self.input_device_index = self.last_working_device
                    self.need_init = True  # 触发重新初始化
        
        # 直接发出信号，QThread允许从工作线程直接发送信号
        self.initialization_complete.emit(success)
    
    def _on_vad_start(self):
        """检测到语音活动开始"""
        print("检测到语音活动开始")
        self.vad_started.emit()

    def _on_vad_stop(self):
        """检测到语音活动结束"""
        print("检测到语音活动结束")
        self.vad_stopped.emit()
    
    def cleanup(self):
        """清理录音器资源"""
        with QMutexLocker(self.mutex):
            if self.recorder:
                try:
                    self.recorder.shutdown()
                except Exception as e:
                    print(f"关闭录音器失败: {str(e)}")
                finally:
                    self.recorder = None


class VoiceInput(QObject):
    """语音输入管理器 - 使用QThread实现的长寿命线程封装类"""
    
    # 定义转发信号
    text_received = pyqtSignal(str)         # 接收到文本信号
    vad_started = pyqtSignal()              # 语音活动开始信号
    vad_stopped = pyqtSignal()              # 语音活动结束信号
    error_occurred = pyqtSignal(str)        # 错误信号
    initialization_complete = pyqtSignal(bool)  # 初始化完成信号(成功/失败)
    
    def __init__(self, input_device_index=0, parent=None):
        """初始化语音输入管理器"""
        super().__init__(parent)
        
        # 创建并配置工作线程
        self.thread = VoiceInputThread(self)
        self.thread.input_device_index = input_device_index
        
        # 连接信号到转发信号
        self.thread.text_received.connect(self.text_received)
        self.thread.vad_started.connect(self.vad_started)
        self.thread.vad_stopped.connect(self.vad_stopped)
        self.thread.error_occurred.connect(self.error_occurred)
        self.thread.initialization_complete.connect(self.initialization_complete)
        
        # 启动线程
        self.thread.start()
    
    def start_listening(self):
        """激活语音识别"""
        with QMutexLocker(self.thread.mutex):
            if self.thread.is_active:
                return True
            
            if not self.thread.recorder and not self.thread.need_init:
                self.thread.need_init = True
                return False
            
            self.thread.is_active = True
        return True
    
    def stop_listening(self):
        """停止语音识别"""
        with QMutexLocker(self.thread.mutex):
            self.thread.is_active = False
        return True
    
    def switch_device(self, device_index):
        """切换输入设备"""
        with QMutexLocker(self.thread.mutex):
            if device_index == self.thread.input_device_index and self.thread.recorder:
                return True
            
            # 使用待处理队列，解决问题1
            self.thread.pending_device_change = device_index
            
            # 如果正在初始化，设置终止标志
            if self.thread.init_in_progress:
                self.thread.abort_current_init = True
                print(f"请求中止当前初始化并切换到设备 {device_index}")
            else:
                self.thread.need_init = True
                print(f"请求切换到设备 {device_index}")
        
        return True
    
    def initialize(self):
        """保留兼容性的方法，现在只是设置需要初始化的标志"""
        with QMutexLocker(self.thread.mutex):
            self.thread.need_init = True
        return True
    
    @staticmethod
    def get_input_devices():
        """获取所有可用的音频输入设备"""
        devices = []
        p = pyaudio.PyAudio()
        
        try:
            info = p.get_host_api_info_by_index(0)
            num_devices = info.get('deviceCount')
            
            for i in range(num_devices):
                device_info = p.get_device_info_by_index(i)
                if device_info.get('maxInputChannels') > 0:  # 只显示输入设备
                    devices.append((i, device_info.get('name')))
        finally:
            p.terminate()
            
        return devices
    
    def cleanup(self):
        """清理资源"""
        print("正在清理语音输入资源...")
        
        # 首先停止语音识别
        with QMutexLocker(self.thread.mutex):
            self.thread.is_active = False
        
        # 请求线程中断并清理录音器
        self.thread.cleanup()
        self.thread.requestInterruption()
        
        # 等待线程结束
        if not self.thread.wait(2000):  # 等待最多2秒
            print("语音线程未能在超时时间内结束，强制终止")
            self.thread.terminate()  # 强制终止（应尽量避免使用）
            self.thread.wait()       # 确保线程完全终止
        
        print("语音线程已结束")