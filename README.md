# Codex Buddy - M5Stick S3 兔兔宠物

6 种状态的像素风兔兔宠物，并通过 BLE 接收 Codex token 用量，显示底部进度条。

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

## BLE token 进度条

M5Stick S3 会广播 BLE 设备名：

```text
Codex Buddy
```

电脑端向 characteristic 写入文本：

```text
used,total
```

也可以附带兔兔状态和重置时间：

```text
used,total,state,reset_seconds
```

支持的状态包括 `sleep`、`idle`、`working`、`attention`、`done`、`error`。

例如：

```text
3200,10000
3200,10000,working,12600
```

屏幕底部会显示 token 百分比进度条，进度条下方显示距离重置还有多久，例如 `Reset in 3h 30m`。BLE 未连接时右上角 `BLE` 为灰色，连接后为绿色。
如果会话中最后一条 usage 的重置时间已经过去，脚本会把过期用量视为 `0%`，不会在首次连接时重复显示刷新前的数值。

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

默认显示 Codex primary rate limit 百分比和 primary rate limit 重置时间。脚本会读取 Codex 的任务生命周期事件：`task_started` 后发送 `working`，`task_complete` 后发送 `done`，M5Stick S3 显示 Done 2 秒后自动回到 Idle。脚本首次启动时如果最新状态已经是 `done`，会发送 `idle`。

异常状态会显示 Error：BLE 曾连接后断开，或脚本读不到 Codex 会话。
S3 重启或 BLE 意外断开后，`--codex` 模式会自动重新扫描连接，并立即重发当前用量和状态。

也可以显示最近一次模型请求的 token / context window：

```bash
python3 send_tokens_ble.py --codex --metric last
```

或显示当前会话累计 token / 自定义预算：

```bash
python3 send_tokens_ble.py --codex --metric session --session-budget 2000000
```

## 状态一览

| # | 状态 | 像素动作 |
|---|---|---|
| 1 | Sleep | 趴下休息 |
| 2 | Idle | 站立待机 |
| 3 | Working | 专注敲电脑 |
| 4 | Attention | 竖耳惊叹 |
| 5 | Done | 举爪庆祝 + 星星 |
| 6 | Error | 垂耳 + X 眼 + 问号 |
