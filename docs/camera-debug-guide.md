# 摄像头调试指南

本指南说明如何调试 IMX500 摄像头，包括对焦检查和实时预览。

## 快速开始：浏览器实时预览

这是最简单的调试方法，可以在任何设备的浏览器中查看摄像头实时画面。

### 1. 启动流服务器

在 Raspberry Pi 上运行：

```bash
cd /opt/snap2know
source .venv/bin/activate
python device_agent/tools/camera_stream.py
```

### 2. 浏览器查看

在 Mac/PC/手机浏览器中打开：

```
http://192.168.1.55:8080
```

> 注：将 IP 替换为你的 Pi 实际地址

### 3. 调整焦距

IMX500 是**定焦镜头**，无法电动调焦。调整方法：

1. **物理距离**：移动设备与文档的距离，通常 **30-50cm** 最清晰
2. **手动旋转镜头**：部分模块支持微调镜头环（顺/逆时针 1/8 圈）
3. **增加光线**：光线不足会导致快门变慢造成模糊

---

## 其他调试工具

### 连续拍照模式

每隔固定时间拍一张照片，保存到 `/tmp/focus_live.jpg`：

```bash
python device_agent/tools/camera_focus_test.py --interval 1
```

### 单次拍照

```bash
python device_agent/tools/camera_focus_test.py --capture --output /tmp/test.jpg
```

---

## 常见问题

| 问题 | 原因 | 解决方法 |
|------|------|----------|
| 画面模糊 | 距离不对 | 调整到 30-50cm |
| 画面暗淡 | 光线不足 | 增加光源 |
| 画面抖动 | 手抖/快门慢 | 固定设备或增加光线 |
| 颜色偏差 | 白平衡问题 | 通常自动调整，等待几秒 |
