#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import glob
import json
import os
import time


DEVICE_NAME = "Codex Buddy"
TOKEN_CHAR_UUID = "7b4f6a11-6d5f-4a6e-9e6f-4f7b6f9a1001"
DEFAULT_CODEX_SESSIONS_GLOB = os.path.expanduser("~/.codex/sessions/**/*.jsonl")


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
    paths = glob.glob(DEFAULT_CODEX_SESSIONS_GLOB, recursive=True)
    if not paths:
        raise RuntimeError("No Codex session JSONL files found under ~/.codex/sessions")
    return max(paths, key=os.path.getmtime)


def latest_codex_snapshot(session_path: str):
    latest_token = None
    latest_task_state = "idle"
    with open(session_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue

            payload = item.get("payload", {})
            if item.get("type") == "event_msg" and payload.get("type") == "token_count":
                latest_token = payload
            elif item.get("type") == "event_msg" and payload.get("type") == "task_started":
                latest_task_state = "working"
            elif item.get("type") == "event_msg" and payload.get("type") == "task_complete":
                latest_task_state = "done"

    if latest_token is None:
        raise RuntimeError(f"No token_count event found in {session_path}")
    return latest_token, latest_task_state


def token_payload_to_progress(token_payload: dict, metric: str, session_budget: int):
    info = token_payload.get("info", {})
    rate_limits = token_payload.get("rate_limits") or {}

    if metric == "rate":
        used_percent = ((rate_limits.get("primary") or {}).get("used_percent") or 0)
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


async def run(args):
    from bleak import BleakClient

    device = await find_buddy(args.scan_timeout)
    async with BleakClient(device) as client:
        if args.codex:
            last_payload = None
            last_used = 0
            last_total = 100
            last_reset_at = None
            last_error = None
            first_codex_snapshot = True
            suppress_stale_done = False
            while True:
                try:
                    session_path = args.session or latest_codex_session()
                    token_payload, state = latest_codex_snapshot(session_path)
                    used, total = token_payload_to_progress(token_payload, args.metric, args.session_budget)
                    reset_at = token_payload_to_reset_at(token_payload)
                    if first_codex_snapshot:
                        suppress_stale_done = state == "done"
                        first_codex_snapshot = False
                    if suppress_stale_done and state == "done":
                        state = "idle"
                    elif suppress_stale_done and state == "working":
                        suppress_stale_done = False
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
                    last_payload = payload
                await asyncio.sleep(args.interval)
        elif args.demo:
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
    args = parser.parse_args()

    if args.total <= 0:
        raise SystemExit("--total must be greater than 0")
    if args.used < 0:
        raise SystemExit("--used must be greater than or equal to 0")
    if args.session_budget <= 0:
        raise SystemExit("--session-budget must be greater than 0")

    asyncio.run(run(args))


if __name__ == "__main__":
    main()
