import json
import queue
import pyaudio
import requests
from PyQt6.QtCore import QThread, QObject, pyqtSignal, QMutex, QTimer
from util.config import TTS_GROUP_ID, TTS_API_KEY

url = "https://api.minimax.chat/v1/t2a_v2?GroupId=" + TTS_GROUP_ID
VOICE_ID = 'female-yujie'
headers = {"Content-Type": "application/json", "Authorization": "Bearer " + TTS_API_KEY}

class TTSThread(QThread):
    """TTS播放线程，负责播放音频数据"""
    
    # 添加实际播放开始的信号
    audio_playback_started = pyqtSignal(bytes, object)  # 音频数据和附加信息
    
    def __init__(self, audio_config):
        super().__init__()
        self.audio_config = audio_config
        self.audio_queue = queue.Queue()
        self.is_running = True
        self.mutex = QMutex()
        self.full_audio = b""
        
    def run(self):
        """线程主函数，负责播放队列中的音频数据"""
        p = pyaudio.PyAudio()
        stream = p.open(
            format=self.audio_config['format'],
            channels=self.audio_config['channels'],
            rate=self.audio_config['rate'],
            output=True
        )

        try:
            while self.is_running:
                try:
                    # 从队列获取音频数据和元数据
                    data = self.audio_queue.get(timeout=0.1)
                    if not data:
                        continue
                        
                    # 解包数据和元数据
                    if isinstance(data, tuple) and len(data) == 2:
                        audio_data, metadata = data
                    else:
                        audio_data, metadata = data, None
                    
                    # 发出实际播放开始信号
                    if audio_data:
                        self.audio_playback_started.emit(audio_data, metadata)
                    
                    # 播放音频数据
                    stream.write(audio_data)
                    
                except queue.Empty:
                    continue
                except Exception as e:
                    print(f"[播放错误] {str(e)}")

        finally:
            stream.stop_stream()
            stream.close()
            p.terminate()
    
    def stop(self):
        """停止线程"""
        self.is_running = False
        self.wait()
    
    # 修改add_audio方法，支持元数据
    def add_audio(self, audio_data, metadata=None):
        """添加音频数据到队列"""
        self.audio_queue.put((audio_data, metadata))
        self.full_audio += audio_data
    
    def clear_queue(self):
        """清空音频队列"""
        try:
            while not self.audio_queue.empty():
                self.audio_queue.get_nowait()
        except queue.Empty:
            pass
            
    def is_queue_empty(self):
        """检查队列是否为空"""
        return self.audio_queue.empty()
    
    def cancel_request_id(self, request_id):
        """取消特定请求ID的所有待播放音频"""
        if not request_id:
            return
            
        # 创建新队列并过滤数据
        new_queue = queue.Queue()
        cancelled_count = 0
        
        # 加锁防止并发问题
        self.mutex.lock()
        try:
            # 逐个检查队列中的项目
            while not self.audio_queue.empty():
                try:
                    item = self.audio_queue.get_nowait()
                    if not item:
                        continue
                        
                    # 检查元数据中的请求ID
                    if isinstance(item, tuple) and len(item) == 2:
                        audio_data, metadata = item
                        # 如果元数据是元组且包含请求ID
                        if isinstance(metadata, tuple) and len(metadata) >= 2 and metadata[1] == request_id:
                            cancelled_count += 1
                            continue
                    
                    # 保留不匹配的项目
                    new_queue.put(item)
                    
                except queue.Empty:
                    break
            
            # 替换原队列
            self.audio_queue = new_queue
            
        finally:
            self.mutex.unlock()
        
        if cancelled_count > 0:
            print(f"已从播放队列中移除 {cancelled_count} 条过时音频")

class TTSManager(QObject):
    # 修改信号：添加request_id参数
    tts_playback_started = pyqtSignal(str, str)  # (text, request_id)
    # 添加新信号：实际播放开始信号
    tts_audio_playback_started = pyqtSignal(str, str)  # (text, request_id)
    
    def __init__(self):
        super().__init__()
        # 音频配置 - 与API请求中的配置保持一致
        self.audio_config = {
            'channels': 1,
            'rate': 32000,  # 与API的sample_rate一致
            'format': pyaudio.paInt16  # 16位PCM
        }
        
        # 创建播放线程
        self.player_thread = TTSThread(self.audio_config)
        self.player_thread.start()
        
        # 连接实际播放开始信号
        self.player_thread.audio_playback_started.connect(self._on_audio_playback_started)
        
        # 当前请求是否正在进行
        self.is_requesting = False
        
        # 修改请求队列结构，包含文本和请求ID
        self.request_queue = []  # [(text, request_id, emotion), ...]
        self.is_processing = False
        
        # 当前正在处理的请求ID
        self.current_processing_id = None

    def is_queue_empty(self) -> bool:
        """
        检查是否还有音频在队列中等待播放
        
        Returns:
            bool: True 表示队列为空（没有音频在播放或等待），False 表示队列非空
        """
        return self.player_thread.is_queue_empty() and len(self.request_queue) == 0

    def build_tts_stream_headers(self) -> dict:
        """构建请求头"""
        headers = {
            'accept': 'application/json, text/plain, */*',
            'content-type': 'application/json',
            'authorization': "Bearer " + TTS_API_KEY,
        }
        return headers

    def build_tts_stream_body(self, text: str, emotion: str = "neutral") -> dict:
        """构建请求体"""
        # 映射简化的情绪到minimax支持的情绪
        emotion_mapping = {
            "happy": "happy",
            "sad": "sad",
            "angry": "angry",
            "fearful": "fearful",
            "disgusted": "disgusted",
            "surprised": "surprised",
            "neutral": "neutral"
        }
        
        # 获取映射后的情绪，如果没有则使用neutral作为默认值
        mapped_emotion = emotion_mapping.get(emotion, "neutral")
        
        body = json.dumps({
            "model": "speech-02-turbo",
            "text": text,
            "stream": True,
            "voice_setting": {
                "voice_id": VOICE_ID,
                "speed": 1,
                "vol": 1,
                "pitch": 0,
                "emotion": mapped_emotion
            },
            "audio_setting": {
                "sample_rate": 32000,
                "bitrate": 128000,
                "format": "pcm",
                "channel": 1
            }
        })
        return body

    def request_tts(self, text: str, request_id: str = None, emotion: str = "neutral"):
        """
        发起TTS请求
        
        Args:
            text: 要转换的文本
            request_id: 请求标识符，用于跟踪特定请求的TTS
            emotion: 情绪类型，用于调整语音风格
        """
        if not text or not text.strip():
            return
        
        # 如果没有提供请求ID，生成一个特殊标记
        if request_id is None:
            request_id = "default_request"
        
        # 将请求添加到队列，包含文本、请求ID和情绪
        self.request_queue.append((text, request_id, emotion))
        print(f"已添加TTS请求到队列: '{text[:20]}...' (请求ID: {request_id}, 情绪: {emotion})")
        
        # 如果当前没有处理中的请求，开始处理
        if not self.is_processing:
            self._process_next_request()
    
    def _on_audio_playback_started(self, audio_data, metadata):
        """处理音频实际开始播放事件"""
        if metadata and isinstance(metadata, tuple) and len(metadata) == 2:
            text, request_id = metadata
            # 发送实际播放开始信号
            self.tts_audio_playback_started.emit(text, request_id)
    
    def _process_next_request(self):
        """处理队列中的下一个TTS请求"""
        if not self.request_queue:
            self.is_processing = False
            self.current_processing_id = None
            return
            
        # 设置处理标志
        self.is_processing = True
        
        # 解包请求数据
        if len(self.request_queue[0]) == 3:
            text, request_id, emotion = self.request_queue.pop(0)
        else:
            # 兼容旧格式
            text, request_id = self.request_queue.pop(0)
            emotion = "neutral"
        
        self.current_processing_id = request_id
        
        print(f"开始处理TTS请求: '{text[:20]}...' (请求ID: {request_id}, 情绪: {emotion})")
        
        # 处理TTS请求
        tts_headers = self.build_tts_stream_headers()
        tts_body = self.build_tts_stream_body(text, emotion)  # 传递情绪参数
        
        try:
            response = requests.request("POST", url, stream=True, headers=tts_headers, data=tts_body)
            
            print(f"请求状态码: {response.status_code}", response)
            # 即时处理所有音频块
            audio_chunks = []
            for chunk in response.raw:
                if chunk and chunk[:5] == b'data:':
                    data = json.loads(chunk[5:])
                    if "data" in data and "extra_info" not in data:
                        if "audio" in data["data"]:
                            audio_hex = data["data"]['audio']
                            if audio_hex and audio_hex != '\n':
                                audio_data = bytes.fromhex(audio_hex)
                                audio_chunks.append(audio_data)
            
            # 合并所有音频数据
            full_chunk = b"".join(audio_chunks)
            print(f"接收到音频数据: {len(full_chunk)} bytes")
            
            # 添加带元数据的音频到播放队列
            self.player_thread.add_audio(full_chunk, (text, request_id))
            
            # 发送队列添加信号（保持原有行为，可以在UI中用于显示进度或状态）
            self.tts_playback_started.emit(text, request_id)
            
            # 处理下一个请求
            QTimer.singleShot(100, self._process_next_request)
                                    
        except Exception as e:
            print(f"[TTS请求错误] {str(e)}")
            self.is_processing = False
            self.current_processing_id = None
            
            # 出错时也继续处理队列
            QTimer.singleShot(500, self._process_next_request)

    def stop_playing(self):
        """停止当前播放并清空队列"""
        self.request_queue = []
        self.is_processing = False
        self.current_processing_id = None
        self.player_thread.clear_queue()
        print("已停止所有TTS播放和请求")

    def cancel_request_id(self, request_id: str):
        """
        取消特定请求ID的所有TTS请求
        """
        print(f"取消请求ID为 {request_id} 的所有TTS请求")
        
        # 过滤掉队列中指定请求ID的项目
        self.request_queue = [(text, rid, emotion) for text, rid, emotion in self.request_queue if rid != request_id]
        
        # 如果当前正在处理的请求是要取消的请求，则停止处理
        if self.current_processing_id == request_id:
            self.is_processing = False
            self.current_processing_id = None
        
        # 清理播放队列中的过时音频 - 增加这一行
        self.player_thread.cancel_request_id(request_id)
        
        # 如果还有其他请求，则开始处理
        if not self.is_processing and self.request_queue:
            QTimer.singleShot(100, self._process_next_request)

    def stop(self):
        """停止播放并清理资源"""
        self.player_thread.stop()
        
    def get_audio(self) -> bytes:
        """获取收集的完整音频数据"""
        return self.player_thread.full_audio