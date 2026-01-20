"""
Snap2Know TTS Player
TTS 分段播报器（缓冲 → 分句 → TTS → 播放队列）
"""
import asyncio
import tempfile
import os
from typing import Optional
from dataclasses import dataclass


@dataclass
class AudioChunk:
    """音频块"""
    text: str
    audio_data: bytes


class TTSPlayer:
    """TTS 分段播放器"""
    
    # 句子分隔符
    SENTENCE_SEPARATORS = "。！？.!?\n"
    
    # 缓冲区最大字符数
    BUFFER_SIZE = 100
    
    def __init__(self, audio_device: str = "plughw:wm8960", mbp_client=None):
        """
        初始化 TTS 播放器
        
        Args:
            audio_device: ALSA 音频设备
            mbp_client: MBP 客户端实例
        """
        self.audio_device = audio_device
        self.mbp_client = mbp_client
        
        self._buffer = ""
        self._queue: asyncio.Queue = asyncio.Queue()
        self._is_playing = False
        self._is_muted = False
        self._should_stop = False
        self._expecting_more = True  # 是否期待更多内容
        self._pending_requests = 0   # 待处理的 TTS 请求数
        self._play_task: Optional[asyncio.Task] = None
        
        # 音频模块（延迟导入）
        self._audio = None
    
    def _get_audio(self):
        """获取音频模块"""
        if self._audio is None:
            try:
                from hardware import Audio
                self._audio = Audio(device=self.audio_device)
            except ImportError:
                from hardware.audio import MockAudio
                self._audio = MockAudio(device=self.audio_device)
        return self._audio
    
    async def add_text(self, text: str):
        """
        添加文本到缓冲区
        
        遇到句子分隔符或缓冲区满时发送 TTS 请求
        """
        if self._should_stop:
            return
        
        self._buffer += text
        
        # 检查是否需要发送
        while self._should_send():
            sentence = self._extract_sentence()
            if sentence:
                await self._send_to_tts(sentence)
    
    def _should_send(self) -> bool:
        """判断是否应该发送缓冲区内容"""
        if not self._buffer:
            return False
        
        # 遇到句子分隔符
        for sep in self.SENTENCE_SEPARATORS:
            if sep in self._buffer:
                return True
        
        # 缓冲区满
        if len(self._buffer) >= self.BUFFER_SIZE:
            return True
        
        return False
    
    def _extract_sentence(self) -> str:
        """从缓冲区提取一个句子"""
        if not self._buffer:
            return ""
        
        # 查找最早的分隔符
        min_pos = len(self._buffer)
        found_sep = None
        
        for sep in self.SENTENCE_SEPARATORS:
            pos = self._buffer.find(sep)
            if pos != -1 and pos < min_pos:
                min_pos = pos
                found_sep = sep
        
        if found_sep is not None:
            sentence = self._buffer[:min_pos + 1]
            self._buffer = self._buffer[min_pos + 1:].lstrip()
            return sentence.strip()
        
        # 缓冲区满时强制分割
        if len(self._buffer) >= self.BUFFER_SIZE:
            sentence = self._buffer[:self.BUFFER_SIZE]
            self._buffer = self._buffer[self.BUFFER_SIZE:]
            return sentence.strip()
        
        return ""
    
    async def _send_to_tts(self, text: str):
        """发送文本到 TTS 服务并加入队列"""
        if not text or self._should_stop:
            return
        
        self._pending_requests += 1
        print(f"[TTS] Requesting: {text[:20]}... (pending: {self._pending_requests})")
        
        try:
            if self.mbp_client:
                audio_data = await self.mbp_client.text_to_speech(text)
                print(f"[TTS] Got audio: {len(audio_data)} bytes for '{text[:15]}...'")
                await self._queue.put(AudioChunk(text=text, audio_data=audio_data))
                print(f"[TTS] Queued, queue size now: {self._queue.qsize()}")
            else:
                print(f"[TTS] No MBP client, skipping: {text}")
        except Exception as e:
            print(f"[TTS] Error getting audio: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._pending_requests -= 1
    
    async def flush(self):
        """刷新缓冲区，发送剩余文本"""
        if self._buffer.strip():
            await self._send_to_tts(self._buffer.strip())
            self._buffer = ""
    
    async def start_playing(self):
        """开始播放队列"""
        if self._play_task and not self._play_task.done():
            return
        
        self._should_stop = False
        self._expecting_more = True  # 开始时期待更多内容
        self._play_task = asyncio.create_task(self._play_loop())
    
    def mark_done(self):
        """标记没有更多内容了"""
        print("[TTS] Marked as done - no more content expected")
        self._expecting_more = False
    
    async def _play_loop(self):
        """播放循环"""
        print("[TTS] Play loop started")
        self._is_playing = True
        
        while not self._should_stop:
            try:
                # 等待音频块（超时 2 秒）
                print(f"[TTS] Waiting for audio chunk, queue size: {self._queue.qsize()}")
                try:
                    chunk = await asyncio.wait_for(self._queue.get(), timeout=2.0)
                except asyncio.TimeoutError:
                    # 检查是否还有内容
                    print(f"[TTS] Timeout, queue: {self._queue.qsize()}, pending: {self._pending_requests}, expecting: {self._expecting_more}")
                    # 只有在不期待更多内容、队列为空、无待处理请求时才退出
                    if self._queue.empty() and self._pending_requests == 0 and not self._expecting_more:
                        break
                    continue
                
                if self._should_stop:
                    break
                
                print(f"[TTS] Got chunk: {chunk.text[:20]}...")
                
                # 播放音频
                if not self._is_muted:
                    await self._play_audio(chunk.audio_data)
                else:
                    print(f"[TTS] Muted, skipping: {chunk.text[:20]}...")
                
            except Exception as e:
                print(f"[TTS] Play error: {e}")
                import traceback
                traceback.print_exc()
        
        print("[TTS] Play loop ended")
        self._is_playing = False
    
    async def _play_audio(self, audio_data: bytes):
        """播放音频数据"""
        print(f"[TTS] Playing audio: {len(audio_data)} bytes")
        audio = self._get_audio()
        
        # 保存到临时文件
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(audio_data)
            temp_path = f.name
        
        try:
            # 使用 mpg123 播放 MP3
            print(f"[TTS] Calling play_bytes with device: {self.audio_device}")
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: audio.play_bytes(audio_data)
            )
            print("[TTS] Audio playback complete")
        except Exception as e:
            print(f"[TTS] Play audio error: {e}")
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def toggle_mute(self) -> bool:
        """
        切换静音
        
        Returns:
            切换后的静音状态
        """
        self._is_muted = not self._is_muted
        print(f"[TTS] Muted: {self._is_muted}")
        return self._is_muted
    
    def stop(self):
        """停止播放并清空队列"""
        print("[TTS] Stopping...")
        self._should_stop = True
        self._buffer = ""
        
        # 清空队列
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except:
                pass
    
    @property
    def is_playing(self) -> bool:
        """是否正在播放"""
        return self._is_playing
    
    @property
    def is_muted(self) -> bool:
        """是否静音"""
        return self._is_muted
    
    async def wait_until_done(self):
        """等待播放完成"""
        if self._play_task:
            await self._play_task


# 测试代码
async def _test():
    """测试 TTS 播放器"""
    player = TTSPlayer()
    
    # 添加文本
    test_text = "你好，这是一个测试。欢迎使用 Snap2Know！请问有什么可以帮助您的？"
    
    for char in test_text:
        await player.add_text(char)
        await asyncio.sleep(0.05)
    
    await player.flush()
    
    print(f"Queue size: {player._queue.qsize()}")


if __name__ == "__main__":
    asyncio.run(_test())
