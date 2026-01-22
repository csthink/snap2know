#!/usr/bin/env python3
"""
IMX500 Camera Focus Test Tool
用于测试和调整摄像头对焦的独立工具

使用方法:
    python camera_focus_test.py                    # 连续拍照模式
    python camera_focus_test.py --capture          # 单次拍照
    python camera_focus_test.py --libcamera        # 使用 libcamera-still 命令行
"""
import os
import sys
import time
import argparse
import subprocess

def run_libcamera_preview():
    """使用 rpicam-still 的原生预览功能"""
    print("[INFO] Starting rpicam-still preview...")
    print("[TIP] Press Ctrl+C to exit")
    
    # 尝试新命令名 rpicam-still (Bookworm+) 或旧命令 libcamera-still
    for cmd_name in ["rpicam-still", "libcamera-still"]:
        try:
            # 检查命令是否存在
            result = subprocess.run(["which", cmd_name], capture_output=True)
            if result.returncode == 0:
                cmd = [
                    cmd_name,
                    "-t", "0",           # 无限预览
                    "--viewfinder-width", "1280",
                    "--viewfinder-height", "720",
                    "-o", "/tmp/focus_test.jpg"
                ]
                print(f"[INFO] Using: {cmd_name}")
                subprocess.run(cmd)
                return
        except Exception:
            continue
    
    # 都不存在，尝试用 picamera2 的 Qt 预览
    print("[WARN] rpicam-still/libcamera-still not found, trying picamera2 preview...")
    run_picamera2_preview()


def run_picamera2_preview():
    """使用 picamera2 的 Qt 预览功能"""
    try:
        from picamera2 import Picamera2, Preview
    except ImportError as e:
        print(f"[ERROR] picamera2 not found: {e}")
        return
    
    print("[INFO] Starting Picamera2 Qt preview...")
    print("[TIP] Close the preview window or press Ctrl+C to exit")
    
    picam2 = Picamera2()
    config = picam2.create_preview_configuration(
        main={"size": (1280, 720)}
    )
    picam2.configure(config)
    
    # 使用 QTGL 预览 (需要显示环境)
    picam2.start_preview(Preview.QTGL)
    picam2.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[INFO] Stopped by user")
    finally:
        picam2.stop()
        picam2.stop_preview()
        picam2.close()
    
    print("[DONE] Preview ended")


def continuous_capture_mode(duration: int, interval: float = 2.0):
    """连续拍照模式 - 每隔几秒拍一张，保存到固定路径"""
    try:
        from picamera2 import Picamera2
    except ImportError as e:
        print(f"[ERROR] picamera2 not found: {e}")
        sys.exit(1)
    
    output_path = "/tmp/focus_live.jpg"
    
    print(f"[INFO] Continuous capture mode")
    print(f"[INFO] Images saved to: {output_path}")
    print(f"[INFO] Interval: {interval}s, Duration: {duration}s")
    print(f"\n[TIP] 在另一个终端或 VNC 中查看图片:")
    print(f"      watch -n 1 'ls -la {output_path}'")
    print(f"      或用图片查看器打开 {output_path}")
    print(f"\n[INFO] Press Ctrl+C to stop\n")
    
    picam2 = Picamera2()
    
    # 高分辨率配置
    config = picam2.create_still_configuration(
        main={"size": (1920, 1080)},
    )
    picam2.configure(config)
    
    print(f"[INFO] Camera: {picam2.camera_properties.get('Model', 'Unknown')}")
    
    picam2.start()
    time.sleep(1)  # 等待自动曝光稳定
    
    try:
        count = 0
        start_time = time.time()
        
        while (time.time() - start_time) < duration:
            count += 1
            metadata = picam2.capture_metadata()
            
            # 拍照
            picam2.capture_file(output_path)
            
            # 打印信息
            exposure = metadata.get("ExposureTime", 0) / 1000  # 转ms
            gain = metadata.get("AnalogueGain", 0)
            print(f"[{count:03d}] Captured | Exposure: {exposure:.1f}ms | Gain: {gain:.1f}x")
            
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print("\n[INFO] Stopped by user")
    finally:
        picam2.stop()
        picam2.close()
    
    print(f"[DONE] Total captures: {count}")
    print(f"[INFO] Last image: {output_path}")


def single_capture(output: str):
    """单次拍照"""
    try:
        from picamera2 import Picamera2
    except ImportError as e:
        print(f"[ERROR] picamera2 not found: {e}")
        sys.exit(1)
    
    print(f"[INFO] Single capture to: {output}")
    
    picam2 = Picamera2()
    config = picam2.create_still_configuration(
        main={"size": (1920, 1080)},
    )
    picam2.configure(config)
    
    picam2.start()
    time.sleep(2)  # 等待自动曝光
    
    metadata = picam2.capture_metadata()
    picam2.capture_file(output)
    
    picam2.stop()
    picam2.close()
    
    exposure = metadata.get("ExposureTime", 0) / 1000
    gain = metadata.get("AnalogueGain", 0)
    
    print(f"[DONE] Saved: {output}")
    print(f"[INFO] Exposure: {exposure:.1f}ms | Gain: {gain:.1f}x")


def main():
    parser = argparse.ArgumentParser(
        description="IMX500 Camera Focus Test Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python camera_focus_test.py                # 连续拍照 (2秒间隔)
  python camera_focus_test.py --interval 1   # 1秒间隔
  python camera_focus_test.py --capture      # 单次拍照
  python camera_focus_test.py --libcamera    # 使用原生 libcamera 预览
        """
    )
    parser.add_argument("--capture", action="store_true", 
                        help="Single capture mode")
    parser.add_argument("--output", type=str, default="focus_test.jpg",
                        help="Output filename for single capture")
    parser.add_argument("--duration", type=int, default=120,
                        help="Continuous capture duration (seconds, default: 120)")
    parser.add_argument("--interval", type=float, default=2.0,
                        help="Capture interval in seconds (default: 2.0)")
    parser.add_argument("--libcamera", action="store_true",
                        help="Use libcamera-still for native preview")
    args = parser.parse_args()
    
    print("=" * 50)
    print("  IMX500 Camera Focus Test Tool")
    print("=" * 50)
    
    if args.libcamera:
        run_libcamera_preview()
    elif args.capture:
        single_capture(args.output)
    else:
        continuous_capture_mode(args.duration, args.interval)


if __name__ == "__main__":
    main()
