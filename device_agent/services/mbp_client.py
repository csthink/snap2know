"""
Snap2Know MBP Client
与 MBP 后端通信的客户端（HTTP + WebSocket）
"""
import asyncio
import json
from typing import Callable, Optional
import httpx


class MBPClient:
    """MBP 后端通信客户端"""
    
    def __init__(
        self,
        base_url: str = "http://192.168.1.38:8000",
        timeout: float = 30.0
    ):
        """
        初始化 MBP 客户端
        
        Args:
            base_url: MBP 后端基础 URL
            timeout: 请求超时时间（秒）
        """
        self.base_url = base_url.rstrip("/")
        self.ws_url = self.base_url.replace("http", "ws")
        self.timeout = timeout
        self.session_id: Optional[str] = None
        self._http_client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端"""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=self.timeout)
        return self._http_client
    
    async def close(self):
        """关闭客户端"""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
    
    async def health_check(self) -> bool:
        """
        健康检查
        
        Returns:
            是否连接成功
        """
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/health")
            return response.status_code == 200
        except Exception as e:
            print(f"[MBPClient] Health check failed: {e}")
            return False
    
    async def create_session(self) -> str:
        """
        创建会话
        
        Returns:
            session_id
        """
        try:
            client = await self._get_client()
            response = await client.post(f"{self.base_url}/session")
            response.raise_for_status()
            data = response.json()
            self.session_id = data.get("session_id")
            return self.session_id
        except Exception as e:
            print(f"[MBPClient] Create session failed: {e}")
            raise
    
    async def upload_image(self, image_data: bytes) -> dict:
        """
        上传图片进行 OCR 入库
        
        Args:
            image_data: 图片字节数据（JPEG）
        
        Returns:
            包含 image_id, num_chunks 等信息的字典
        """
        if not self.session_id:
            await self.create_session()
        
        try:
            client = await self._get_client()
            
            files = {
                "image": ("capture.jpg", image_data, "image/jpeg")
            }
            
            response = await client.post(
                f"{self.base_url}/upload/image",
                files=files,
                params={"session_id": self.session_id}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"[MBPClient] Upload image failed: {e}")
            raise
    
    async def speech_to_text(self, audio_data: bytes) -> str:
        """
        语音转文字
        
        Args:
            audio_data: WAV 格式音频数据
        
        Returns:
            识别的文字
        """
        if not self.session_id:
            await self.create_session()
        
        try:
            client = await self._get_client()
            
            files = {
                "audio": ("recording.wav", audio_data, "audio/wav")
            }
            
            response = await client.post(
                f"{self.base_url}/upload/audio",
                files=files,
                params={"session_id": self.session_id}
            )
            response.raise_for_status()
            data = response.json()
            return data.get("question_text", "")
        except Exception as e:
            print(f"[MBPClient] STT failed: {e}")
            raise
    
    async def text_to_speech(self, text: str) -> bytes:
        """
        文字转语音
        
        Args:
            text: 要转换的文字
        
        Returns:
            音频数据（MP3）
        """
        try:
            client = await self._get_client()
            
            response = await client.post(
                f"{self.base_url}/tts",
                json={"text": text}
            )
            response.raise_for_status()
            return response.content
        except Exception as e:
            print(f"[MBPClient] TTS failed: {e}")
            raise
    
    async def ask_question(
        self,
        question: str,
        on_meta: Callable[[dict], None] = None,
        on_token: Callable[[str], None] = None,
        on_done: Callable[[dict], None] = None,
        on_error: Callable[[str], None] = None,
        top_k: int = 6
    ):
        """
        WebSocket 流式问答
        
        Args:
            question: 问题文本
            on_meta: 收到 meta 消息时的回调
            on_token: 收到 token 时的回调
            on_done: 完成时的回调
            on_error: 错误时的回调
            top_k: 检索的文档数量
        """
        if not self.session_id:
            await self.create_session()
        
        try:
            import websockets
            
            ws_url = f"{self.ws_url}/ws/chat?session_id={self.session_id}"
            
            async with websockets.connect(ws_url) as ws:
                # 发送问题
                await ws.send(json.dumps({
                    "question_text": question,
                    "top_k": top_k
                }))
                
                # 接收消息
                async for message in ws:
                    data = json.loads(message)
                    msg_type = data.get("type")
                    
                    if msg_type == "meta":
                        if on_meta:
                            on_meta(data)
                    elif msg_type == "token":
                        if on_token:
                            on_token(data.get("text", ""))
                    elif msg_type == "done":
                        if on_done:
                            on_done(data)
                        break
                    elif msg_type == "error":
                        if on_error:
                            on_error(data.get("message", "Unknown error"))
                        break
                        
        except Exception as e:
            print(f"[MBPClient] WebSocket error: {e}")
            if on_error:
                on_error(str(e))
            raise


# 测试代码
async def _test():
    """测试 MBP 客户端"""
    client = MBPClient()
    
    print("Testing health check...")
    ok = await client.health_check()
    print(f"  Health: {ok}")
    
    if ok:
        print("Testing create session...")
        session_id = await client.create_session()
        print(f"  Session: {session_id}")
        
        print("Testing WebSocket Q&A...")
        answer = []
        
        def on_token(text):
            answer.append(text)
            print(text, end="", flush=True)
        
        await client.ask_question(
            "如何登录管理后台",
            on_token=on_token,
            on_done=lambda d: print(f"\n  Done: {d}")
        )
        
        print(f"\n  Total answer: {len(''.join(answer))} chars")
    
    await client.close()


if __name__ == "__main__":
    asyncio.run(_test())
