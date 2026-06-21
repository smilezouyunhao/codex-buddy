# Codex Buddy - M5Stick S3

[中文 README](README.md)

A pixel-art bunny pet with six states. It receives Codex token usage over BLE and displays the usage as a progress bar at the bottom of the screen.

The interface uses a 135x240 cyber-terminal pixel background. The source PNG is stored in `assets/backgrounds/`. Regenerate the firmware bitmap with:

```bash
python3 scripts/generate-background-bitmap.py
```

## Hardware

- M5Stick S3
- USB-C data cable

## Arduino Libraries

| Library | Installation command |
|---|---|
| M5Unified | `arduino-cli lib install M5Unified` |
| M5GFX | `arduino-cli lib install M5GFX` |

The ESP32 BLE library is provided by the M5Stack ESP32 core, so no additional Arduino library is required.

## Build and Upload

```bash
# Build
arduino-cli compile \
  --fqbn m5stack:esp32:m5stack_sticks3 \
  .

# Upload (replace the serial port if necessary)
arduino-cli upload \
  --fqbn m5stack:esp32:m5stack_sticks3 \
  -p /dev/cu.usbmodem* \
  .
```

## BLE Token Progress Bar

The M5Stick S3 advertises the following BLE device name:

```text
Codex Buddy
```

The computer writes a text payload to the token characteristic:

```text
used,total
```

The bunny state and reset countdown can also be included:

```text
used,total,state,reset_seconds
```

Supported states are `sleep`, `idle`, `working`, `attention`, `done`, and `error`.

Examples:

```text
3200,10000
3200,10000,working,12600
```

The token usage percentage is shown at the bottom of the screen. When a reset time is available, the remaining time is shown below it, for example `RESET 3H30M`. The `BLE` indicator in the top-right corner is gray while disconnected and green while connected.

If the reset time in the latest usage event has already passed, the script treats the usage as `0%` instead of replaying stale data when it first connects.

### Computer-Side Script

Install the Python BLE and image-generation dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Send simulated usage once:

```bash
python3 send_tokens_ble.py --used 3200 --total 10000
```

Continuously send simulated usage:

```bash
python3 send_tokens_ble.py --demo --total 10000
```

Demo mode can also set the bunny state, allowing the token progress bar and a state screen to be tested together:

```bash
python3 send_tokens_ble.py --demo --total 10000 --state working
```

`--state` accepts `sleep`, `idle`, `working`, `attention`, `done`, and `error`. The default is `idle`. This option only affects `--demo` mode; `--codex` selects the state automatically from the Codex task lifecycle.

Continuously read real statistics from the latest local Codex session:

```bash
python3 send_tokens_ble.py --codex
```

By default, the display shows the Codex primary rate-limit usage percentage and reset time. The script also follows Codex task lifecycle events: it sends `working` after `task_started` and `done` after `task_complete`. Done remains visible for five seconds before the M5Stick S3 returns to Idle. If the latest state is already `done` when the script starts, it sends `idle` instead. A delivered Done state is not replayed after a BLE reconnection.

Error is displayed after an established BLE connection is lost or when the script cannot read a Codex session. In `--codex` mode, the script automatically scans and reconnects after the S3 restarts or BLE disconnects, then immediately resends the current usage and state.

To display the most recent model request's tokens relative to the context window:

```bash
python3 send_tokens_ble.py --codex --metric last
```

This mode shows how much of the context window was used by one model request. For example, if the latest request used 20,000 tokens and the model context window is 200,000 tokens, the display shows approximately `10%`. This is useful for seeing how close the current conversation is to its context limit. This metric has no reset countdown, so the screen shows `RESET --`.

To display cumulative tokens for the current session relative to a custom budget:

```bash
python3 send_tokens_ble.py --codex --metric session --session-budget 2000000
```

This mode tracks the entire Codex session's cumulative token usage against a custom reference budget. For example, 500,000 cumulative tokens against a budget of 2,000,000 displays `25%`. `--session-budget` is only a local display reference; it is not an OpenAI quota or enforced limit. The screen therefore shows `RESET --`.

When `--metric` is omitted, the default `rate` mode shows the percentage used in the current primary rate-limit window. The default is recommended for everyday account usage monitoring. Use `last` to focus on a single request's context size, or `session` to track cumulative usage for one work session.

## State Overview

| # | State | Pixel action |
|---|---|---|
| 1 | Sleep | Resting on the ground |
| 2 | Idle | Standing by |
| 3 | Working | Focused at the computer |
| 4 | Attention | Ears raised with an exclamation mark |
| 5 | Done | Paw raised in celebration with sparkles |
| 6 | Error | Drooping ears, X-shaped eyes, and a question mark |
