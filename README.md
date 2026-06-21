# Codex Buddy - M5Stick S3 兔兔宠物

[English README](README_EN.md)

6 种状态的像素风兔兔宠物，并通过 BLE 接收 Codex token 用量，显示底部进度条。

界面使用 135x240 赛博终端像素背景。背景 PNG 位于 `assets/backgrounds/`，可通过以下命令重新生成固件位图：

```bash
python3 scripts/generate-background-bitmap.py
```

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
  .

# 烧录（替换串口）
arduino-cli upload \
  --fqbn m5stack:esp32:m5stack_sticks3 \
  -p /dev/cu.usbmodem* \
  .
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

屏幕底部会显示 token 百分比进度条，进度条下方显示距离重置还有多久，例如 `RESET 3H30M`。BLE 未连接时右上角 `BLE` 为灰色，连接后为绿色。
如果会话中最后一条 usage 的重置时间已经过去，脚本会把过期用量视为 `0%`，不会在首次连接时重复显示刷新前的数值。

### 电脑端脚本

先安装 Python BLE 和图片生成依赖：

```bash
python3 -m pip install -r requirements.txt
```

发送一次模拟用量：

```bash
python3 send_tokens_ble.py --used 3200 --total 10000
```

持续发送模拟用量：

```bash
python3 send_tokens_ble.py --demo --total 10000
```

Demo 模式也可以指定兔兔状态，用于同时测试 token 进度条和不同状态画面：

```bash
python3 send_tokens_ble.py --demo --total 10000 --state working
```

`--state` 支持 `sleep`、`idle`、`working`、`attention`、`done` 和 `error`，默认值为 `idle`。该参数仅用于 `--demo` 模式；`--codex` 模式会根据 Codex 任务生命周期自动选择状态。

读取本机最新 Codex 会话的真实统计并持续发送：

```bash
python3 send_tokens_ble.py --codex
```

默认显示 Codex primary rate limit 百分比和 primary rate limit 重置时间。脚本会读取 Codex 的任务生命周期事件：`task_started` 后发送 `working`，`task_complete` 后发送 `done`，M5Stick S3 显示 Done 5 秒后自动回到 Idle。脚本首次启动时如果最新状态已经是 `done`，会发送 `idle`；BLE 重连也不会重复播放已经投递过的 Done。

异常状态会显示 Error：BLE 曾连接后断开，或脚本读不到 Codex 会话。
S3 重启或 BLE 意外断开后，`--codex` 模式会自动重新扫描连接，并立即重发当前用量和状态。

也可以显示最近一次模型请求的 token / context window：

```bash
python3 send_tokens_ble.py --codex --metric last
```

此模式用于观察单次模型请求占用了多少上下文窗口。例如最近一次请求使用了 20,000 token，而模型上下文窗口为 200,000，屏幕会显示约 `10%`。它适合判断当前对话距离上下文上限还有多远。此指标没有重置倒计时，屏幕显示 `RESET --`。

或显示当前会话累计 token / 自定义预算：

```bash
python3 send_tokens_ble.py --codex --metric session --session-budget 2000000
```

此模式用于统计整个 Codex 会话的累计 token 消耗，并与自定义参考预算比较。例如累计使用了 500,000 token、预算为 2,000,000，屏幕会显示 `25%`。`--session-budget` 只是本地显示使用的参考线，不代表 OpenAI 的实际额度或限制，因此屏幕显示 `RESET --`。

如果不指定 `--metric`，默认使用 `rate` 模式，显示当前 primary rate limit 周期已经使用的百分比。日常查看账号周期用量时推荐使用默认模式；`last` 更适合关注单次请求的上下文大小，`session` 更适合观察一次工作会话的累计消耗。

## 状态一览

| # | 状态 | 像素动作 |
|---|---|---|
| 1 | Sleep | 趴下休息 |
| 2 | Idle | 站立待机 |
| 3 | Working | 专注敲电脑 |
| 4 | Attention | 竖耳惊叹 |
| 5 | Done | 举爪庆祝 + 星星 |
| 6 | Error | 垂耳 + X 眼 + 问号 |
