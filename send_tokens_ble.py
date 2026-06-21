#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import glob
import json
import os
import time
from datetime import date, timedelta


DEVICE_NAME = "Codex Buddy"
TOKEN_CHAR_UUID = "7b4f6a11-6d5f-4a6e-9e6f-4f7b6f9a1001"
DEFAULT_CODEX_SESSIONS_GLOB = os.path.expanduser("~/.codex/sessions/**/*.jsonl")
CODEX_SESSIONS_ROOT = os.path.expanduser("~/.codex/sessions")
SESSION_SCAN_INTERVAL = 5.0


async def find_buddy(timeout: float):
    from bleak import BleakScanner

    device = await BleakScanner.find_device_by_filter(
        lambda d, ad: d.name == DEVICE_NAME or ad.local_name == DEVICE_NAME,
        timeout=timeout,
    )
    if device is None:
        raise RuntimeError(f"Could not find BLE device named '{DEVICE_NAME}'")
    return device


async def send_once(client: BleakClient, used: int, total: int, state: str | None = None, reset_seconds: int | None = None):
    text = f"{used},{total}"
    if state:
        text = f"{text},{state}"
    if reset_seconds is not None:
        text = f"{text},{reset_seconds}"
    payload = text.encode("utf-8")
    await client.write_gatt_char(TOKEN_CHAR_UUID, payload, response=True)
    print(f"sent {payload.decode()}")


def latest_codex_session():
    paths = []
    today = date.today()
    for day in (today, today - timedelta(days=1)):
        day_dir = os.path.join(CODEX_SESSIONS_ROOT, day.strftime("%Y/%m/%d"))
        paths.extend(glob.glob(os.path.join(day_dir, "*.jsonl")))
    if not paths:
        # Preserve compatibility with custom/legacy layouts without making the
        # full-history scan part of the normal polling path.
        paths = glob.glob(DEFAULT_CODEX_SESSIONS_GLOB, recursive=True)
    if not paths:
        raise RuntimeError("No Codex session JSONL files found under ~/.codex/sessions")
    return max(paths, key=os.path.getmtime)


class CodexSessionReader:
    """Incrementally read the active Codex JSONL session."""

    def __init__(self, session_path: str | None = None, scan_interval: float = SESSION_SCAN_INTERVAL):
        self.session_path = session_path
        self.scan_interval = scan_interval
        self.path = None
        self.offset = 0
        self.latest_token = None
        self.latest_task_state = "idle"
        self.last_scan_at = 0.0

    def _resolve_path(self):
        if self.session_path:
            return self.session_path

        now = time.monotonic()
        if self.path is None or now - self.last_scan_at >= self.scan_interval:
            self.last_scan_at = now
            return latest_codex_session()
        return self.path

    def _reset(self, path: str):
        self.path = path
        self.offset = 0
        self.latest_token = None
        self.latest_task_state = "idle"

    def snapshot(self):
        path = self._resolve_path()
        if path != self.path:
            self._reset(path)

        if os.path.getsize(path) < self.offset:
            self._reset(path)

        with open(path, "r", encoding="utf-8") as f:
            f.seek(self.offset)
            while True:
                line_start = f.tell()
                line = f.readline()
                if not line:
                    break
                if not line.endswith("\n"):
                    # Leave an incomplete append for the next polling cycle.
                    self.offset = line_start
                    break
                self.offset = f.tell()
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue

                payload = item.get("payload", {})
                if item.get("type") != "event_msg":
                    continue
                if payload.get("type") == "token_count":
                    self.latest_token = payload
                elif payload.get("type") == "task_started":
                    self.latest_task_state = "working"
                elif payload.get("type") == "task_complete":
                    self.latest_task_state = "done"

        if self.latest_token is None:
            raise RuntimeError(f"No token_count event found in {path}")
        return path, self.latest_token, self.latest_task_state


def token_payload_to_progress(token_payload: dict, metric: str, session_budget: int):
    info = token_payload.get("info", {})
    rate_limits = token_payload.get("rate_limits") or {}

    if metric == "rate":
        primary = rate_limits.get("primary") or {}
        resets_at = primary.get("resets_at")
        if resets_at and resets_at <= time.time():
            return 0, 100
        used_percent = primary.get("used_percent") or 0
        return int(round(used_percent)), 100

    if metric == "last":
        used = (info.get("last_token_usage") or {}).get("total_tokens") or 0
        total = info.get("model_context_window") or session_budget
        return int(used), int(total)

    used = (info.get("total_token_usage") or {}).get("total_tokens") or 0
    return int(used), int(session_budget)


def token_payload_to_reset_at(token_payload: dict):
    primary = ((token_payload.get("rate_limits") or {}).get("primary") or {})
    return primary.get("resets_at")


async def run_codex(args, client_type):
    last_used = 0
    last_total = 100
    last_reset_at = None
    last_error = None
    last_ble_error = None
    session_reader = CodexSessionReader(args.session)
    first_codex_snapshot = True
    delivered_done_sessions = set()

    while True:
        disconnected = asyncio.Event()
        try:
            device = await find_buddy(args.scan_timeout)
            async with client_type(device, disconnected_callback=lambda _: disconnected.set()) as client:
                print(f"connected {DEVICE_NAME}")
                last_ble_error = None
                last_payload = None
                done_sent_on_connection = set()
                while client.is_connected and not disconnected.is_set():
                    try:
                        session_path, token_payload, state = session_reader.snapshot()
                        used, total = token_payload_to_progress(token_payload, args.metric, args.session_budget)
                        reset_at = token_payload_to_reset_at(token_payload)
                        if first_codex_snapshot:
                            if state == "done":
                                delivered_done_sessions.add(session_path)
                            first_codex_snapshot = False
                        if state == "working":
                            delivered_done_sessions.discard(session_path)
                            done_sent_on_connection.discard(session_path)
                        elif (
                            state == "done"
                            and session_path in delivered_done_sessions
                            and session_path not in done_sent_on_connection
                        ):
                            state = "idle"
                        last_used, last_total = used, total
                        last_reset_at = reset_at
                        last_error = None
                    except Exception as exc:
                        session_path = args.session or "codex-session-unavailable"
                        used, total, state, reset_at = last_used, last_total, "error", last_reset_at
                        error = str(exc)
                        if error != last_error:
                            print(f"codex read error: {error}")
                            last_error = error

                    payload = (session_path, used, total, state, reset_at)
                    if payload != last_payload:
                        reset_seconds = -1 if reset_at is None else max(0, int(reset_at - time.time()))
                        await send_once(client, used, total, state, reset_seconds)
                        if state == "done":
                            delivered_done_sessions.add(session_path)
                            done_sent_on_connection.add(session_path)
                        last_payload = payload
                    await asyncio.sleep(args.interval)
        except Exception as exc:
            error = str(exc)
            if error != last_ble_error:
                print(f"BLE connection error: {error}")
                last_ble_error = error

        print(f"reconnecting in {args.reconnect_delay:g}s...")
        await asyncio.sleep(args.reconnect_delay)


async def run(args):
    from bleak import BleakClient

    if args.codex:
        await run_codex(args, BleakClient)
        return

    device = await find_buddy(args.scan_timeout)
    async with BleakClient(device) as client:
        if args.demo:
            used = args.used
            while True:
                await send_once(client, used, args.total)
                used += args.step
                if used > args.total:
                    used = 0
                await asyncio.sleep(args.interval)
        else:
            await send_once(client, args.used, args.total)


def main():
    parser = argparse.ArgumentParser(description="Send Codex token usage to Codex Buddy over BLE.")
    parser.add_argument("--used", type=int, default=3200, help="Used tokens.")
    parser.add_argument("--total", type=int, default=10000, help="Token budget.")
    parser.add_argument("--demo", action="store_true", help="Continuously send simulated token usage.")
    parser.add_argument("--codex", action="store_true", help="Continuously send token data from the latest Codex session JSONL.")
    parser.add_argument(
        "--metric",
        choices=("rate", "last", "session"),
        default="rate",
        help="Codex metric to display: rate limit percent, last request tokens, or session total tokens.",
    )
    parser.add_argument("--session", help="Specific Codex session JSONL path. Defaults to latest under ~/.codex/sessions.")
    parser.add_argument("--session-budget", type=int, default=2_000_000, help="Budget used for --metric session.")
    parser.add_argument("--step", type=int, default=311, help="Token increment for demo mode.")
    parser.add_argument("--interval", type=float, default=1.0, help="Seconds between demo updates.")
    parser.add_argument("--scan-timeout", type=float, default=10.0, help="BLE scan timeout in seconds.")
    parser.add_argument("--reconnect-delay", type=float, default=2.0, help="Seconds before reconnecting after BLE disconnects.")
    args = parser.parse_args()

    if args.total <= 0:
        raise SystemExit("--total must be greater than 0")
    if args.used < 0:
        raise SystemExit("--used must be greater than or equal to 0")
    if args.session_budget <= 0:
        raise SystemExit("--session-budget must be greater than 0")
    if args.reconnect_delay < 0:
        raise SystemExit("--reconnect-delay must be greater than or equal to 0")

    asyncio.run(run(args))


if __name__ == "__main__":
    main()
