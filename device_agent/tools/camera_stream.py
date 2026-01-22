#!/usr/bin/env python3
"""
Camera HTTP Stream Server
在浏览器中实时查看摄像头画面

使用方法:
    python camera_stream.py
    
然后在浏览器中打开: http://raspberrypi:8080
"""
import io
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# 全局变量存储最新帧
latest_frame = None
frame_lock = threading.Lock()


class StreamHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            # 返回简单的 HTML 页面
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            html = '''
            <!DOCTYPE html>
            <html>
            <head>
                <title>Camera Focus Test</title>
                <style>
                    body { background: #222; color: white; text-align: center; font-family: sans-serif; }
                    img { max-width: 100%; border: 2px solid #666; }
                    h1 { color: #4CAF50; }
                </style>
            </head>
            <body>
                <h1>📷 IMX500 Camera Live View</h1>
                <p>调整设备到文档的距离，找到最清晰的位置 (通常 30-50cm)</p>
                <img src="/stream" />
                <p><small>Refresh: ~2 FPS</small></p>
            </body>
            </html>
            '''
            self.wfile.write(html.encode())
            
        elif self.path == '/stream':
            # MJPEG 流
            self.send_response(200)
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=--frame')
            self.end_headers()
            
            try:
                while True:
                    with frame_lock:
                        if latest_frame:
                            self.wfile.write(b'--frame\r\n')
                            self.wfile.write(b'Content-Type: image/jpeg\r\n\r\n')
                            self.wfile.write(latest_frame)
                            self.wfile.write(b'\r\n')
                    time.sleep(0.5)  # ~2 FPS
            except (BrokenPipeError, ConnectionResetError):
                pass
        else:
            self.send_error(404)
    
    def log_message(self, format, *args):
        # 静默日志
        pass


def capture_loop():
    """持续拍照线程"""
    global latest_frame
    
    try:
        from picamera2 import Picamera2
    except ImportError:
        print("[ERROR] picamera2 not found")
        return
    
    print("[INFO] Starting camera...")
    picam2 = Picamera2()
    config = picam2.create_still_configuration(main={"size": (1280, 720)})
    picam2.configure(config)
    picam2.start()
    time.sleep(1)
    
    print("[INFO] Capture loop running...")
    
    try:
        while True:
            stream = io.BytesIO()
            picam2.capture_file(stream, format='jpeg')
            
            with frame_lock:
                latest_frame = stream.getvalue()
            
            time.sleep(0.3)  # ~3 FPS capture rate
            
    except Exception as e:
        print(f"[ERROR] Capture error: {e}")
    finally:
        picam2.stop()
        picam2.close()


def main():
    print("=" * 50)
    print("  Camera HTTP Stream Server")
    print("=" * 50)
    
    # 启动拍照线程
    capture_thread = threading.Thread(target=capture_loop, daemon=True)
    capture_thread.start()
    
    # 等待摄像头初始化
    time.sleep(2)
    
    # 启动 HTTP 服务器
    port = 8080
    server = HTTPServer(('0.0.0.0', port), StreamHandler)
    
    print(f"\n[OK] Stream server running!")
    print(f"[OK] Open in browser: http://raspberrypi:{port}")
    print(f"[OK] Or: http://<Pi-IP>:{port}")
    print(f"\n[TIP] Press Ctrl+C to stop\n")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[INFO] Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
