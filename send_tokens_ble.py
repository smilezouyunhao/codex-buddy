#!/usr/bin/env python3
import argparse
import asyncio

from bleak import BleakClient, BleakScanner


DEVICE_NAME = "Codex Buddy"
TOKEN_CHAR_UUID = "7b4f6a11-6d5f-4a6e-9e6f-4f7b6f9a1001"


async def find_buddy(timeout: float):
    device = await BleakScanner.find_device_by_filter(
        lambda d, ad: d.name == DEVICE_NAME or ad.local_name == DEVICE_NAME,
        timeout=timeout,
    )
    if device is None:
        raise RuntimeError(f"Could not find BLE device named '{DEVICE_NAME}'")
    return device


async def send_once(client: BleakClient, used: int, total: int):
    payload = f"{used},{total}".encode("utf-8")
    await client.write_gatt_char(TOKEN_CHAR_UUID, payload, response=True)
    print(f"sent {payload.decode()}")


async def run(args):
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
    parser.add_argument("--step", type=int, default=311, help="Token increment for demo mode.")
    parser.add_argument("--interval", type=float, default=1.0, help="Seconds between demo updates.")
    parser.add_argument("--scan-timeout", type=float, default=10.0, help="BLE scan timeout in seconds.")
    args = parser.parse_args()

    if args.total <= 0:
        raise SystemExit("--total must be greater than 0")
    if args.used < 0:
        raise SystemExit("--used must be greater than or equal to 0")

    asyncio.run(run(args))


if __name__ == "__main__":
    main()
