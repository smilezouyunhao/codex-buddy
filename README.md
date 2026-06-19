# Codex Buddy - M5Stick S3 兔兔宠物

6 种状态的 ASCII 兔兔宠物，并通过 BLE 接收 Codex token 用量，显示底部进度条。

## 硬件

- M5Stick S3
- USB-C 数据线

## 依赖库

| 库 | 安装命令 |
|---|---|
| M5Unified | `arduino-cli lib install M5Unified` |
| M5GFX | `arduino-cli lib install M5GFX` |

ESP32 BLE 库由 M5Stack ESP32 core 提供，不需要额外安装 Arduino 库。

## 编译 & 烧录

```bash
# 编译
arduino-cli compile \
  --fqbn m5stack:esp32:m5stack_sticks3 \
  codex-buddy

# 烧录（替换串口）
arduino-cli upload \
  --fqbn m5stack:esp32:m5stack_sticks3 \
  -p /dev/cu.usbmodem* \
  codex-buddy
```

## 按键

| 按键 | 功能 |
|---|---|
| BtnA (正面) | 下一个状态 |
| BtnB (右侧) | 上一个状态 |

## BLE token 进度条

M5Stick S3 会广播 BLE 设备名：

```text
Codex Buddy
```

电脑端向 characteristic 写入文本：

```text
used,total
```

例如：

```text
3200,10000
```

屏幕底部会显示 token 百分比进度条。BLE 未连接时右上角 `BLE` 为灰色，连接后为绿色。

### 电脑端脚本

先安装 Python BLE 依赖：

```bash
python3 -m pip install bleak
```

发送一次模拟用量：

```bash
python3 send_tokens_ble.py --used 3200 --total 10000
```

持续发送模拟用量：

```bash
python3 send_tokens_ble.py --demo --total 10000
```

读取本机最新 Codex 会话的真实统计并持续发送：

```bash
python3 send_tokens_ble.py --codex
```

默认显示 Codex primary rate limit 百分比，适合进度条。也可以显示最近一次模型请求的 token / context window：

```bash
python3 send_tokens_ble.py --codex --metric last
```

或显示当前会话累计 token / 自定义预算：

```bash
python3 send_tokens_ble.py --codex --metric session --session-budget 2000000
```

## 状态一览

| # | 状态 | 表情特征 |
|---|---|---|
| 1 | Sleep | 闭眼 + zZ |
| 2 | Idle | 圆眼 |
| 3 | Working | 专注 |
| 4 | Attention | 大眼 + 感叹号 |
| 5 | Done | 微笑 + 小星星 |
| 6 | Error | X 眼 + 问号 |
