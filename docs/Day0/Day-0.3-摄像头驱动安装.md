# Day 0.3：摄像头驱动安装

在开始之前，先将 Pi 正常停机，然后将 Pi AI Camera 连接到 CSI 接口，再开机执行后续的安装过程

```shell
ssh mars@raspberry

# 等待30s左右再断开 Pi 的电源
sudo shutdown -h now
```

## 安装摄像头驱动

- 安装完摄像头后重启 Pi,ssh 登录到Pi

```shell
sudo apt-get update && sudo apt-get upgrade -y
```

```shell
sudo apt install imx500-all
```

```shell
sudo reboot
```

```shell
sudo apt install python3-opencv python3-munkres
```

```shell
mkdir /opt/src/RPI_AI_Cam
```

- 下载 imx500 相关文件

**方式一**：本地下载后上传
- 从 [GitHub](https://github.com/raspberrypi/picamera2) 下载
- 上传至 Pi 的 `/opt/src/RPI_AI_Cam` 目录

**方式二**：Pi 上直接 clone（可能需要代理）
```shell
cd /opt/src/RPI_AI_Cam
git clone https://github.com/raspberrypi/picamera2.git
```


```shell
cd /opt/src/RPI_AI_Cam/picamera2/examples/imx500
```

```shell
ls /usr/share/imx500-models
```

```shell
mkdir /opt/src/RPI_AI_Cam/Test_1
cp /usr/share/imx500-models/* /opt/src/RPI_AI_Cam/Test_1/
```

- 测试

```shell
cd /opt/src/RPI_AI_Cam/Test_1
python python_file_name.py --model models/model_name.rpk
```

- Raspberry Pi AI Camera (IMX500) Neural Network Model

[Raspberry Pi AI Camera (IMX500) Model Zoo](https://github.com/raspberrypi/imx500-models)


https://cocodataset.org/


```shell
python imx500_object_detection_demo.py --model models/imx500_network_yolov8n_pp.rpk
```







