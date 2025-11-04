#!/usr/bin/env python3
import json, asyncio
from bleak import BleakScanner, BleakClient

# UUIDs bitte an dein Gerät anpassen
UUID_TEMP = "0000fff1-0000-1000-8000-00805f9b34fb"
UUID_HUMI = "0000fff2-0000-1000-8000-00805f9b34fb"

async def read_device(device):
    async with BleakClient(device.address) as client:
        t = await client.read_gatt_char(UUID_TEMP)
        h = await client.read_gatt_char(UUID_HUMI)
        return {
            "name": device.name or "Unknown",
            "address": device.address,
            "temperature_int": int.from_bytes(t, "little") / 100,
            "humidity_int": int.from_bytes(h, "little") / 100
        }

async def main():
    devices = await BleakScanner.discover(timeout=5)
    data = []
    for d in devices:
        if d.name and ("Thermo" in d.name or "Vivosun" in d.name):
            try:
                vals = await read_device(d)
                data.append(vals)
            except Exception as e:
                print("⚠️", d.name, e)
    with open("ble_scan.json", "w") as f:
        json.dump(data, f, indent=2)
    print(f"✅ {len(data)} Gerät(e) mit Messwerten gespeichert")

asyncio.run(main())
