# Codex Buddy — M5Stick S3 兔兔宠物

6 种状态（Sleep / Idle / Busy / Attention / Done / Error），M5GFX 矢量绘制。

## 硬件

- M5Stick S3
- USB-C 数据线

## 依赖库

| 库 | 安装命令 |
|---|---|
| M5Unified | `arduino-cli lib install M5Unified` |
| M5GFX | `arduino-cli lib install M5GFX` |

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

自动 3 秒轮播切换。

## 状态一览

| # | 状态 | 表情特征 |
|---|---|---|
| 1 | Sleep | 闭眼横线 + zzz 呼吸闪烁 |
| 2 | Idle | 圆眼 + 眨眼动画（每 3s 眨一次） |
| 3 | Busy | 专注斗鸡眼 + 汗滴 + 橙色粒子 |
| 4 | Attention | 大眼 + 张嘴 + ⚠ 感叹号 |
| 5 | Done | 眯眼笑 + ⭐ 星星闪烁 |
| 6 | Error | X 眼 + 撇嘴 + 红色感叹号 |
