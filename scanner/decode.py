#!/usr/bin/env python3
# decode_from_json.py
# Liest blebridge_desktop/ble_scan.json (ndjson oder JSON-Array) und decodiert manufacturer_data_hex
import json, os, sys, re

# Pfad anpassen falls nötig
PATH = os.path.join(os.path.dirname(__file__), "blebridge_desktop", "ble_scan.json")

def hex_to_bytes(h):
    s = re.sub(r'[^0-9a-fA-F]', '', h)
    if len(s) % 2 == 1: s = s[:-1]
    return bytes.fromhex(s)

def le16(lo, hi):
    return ((hi & 0xFF) << 8) | (lo & 0xFF)

def decode_msd_bytes(b):
    # normalize: ensure starts with 0x19 0x00
    if len(b) >= 2 and b[0] == 0x19 and b[1] == 0x00:
        msd = b
    else:
        msd = bytes([0x19,0x00]) + b
    need = 2 + 6 + 2 + (2*4) + 1
    if len(msd) < need:
        return {"error":"too short","len":len(msd)}
    res = {"len": len(msd), "cid": (msd[1]<<8)|msd[0], "blocks": []}
    pos = 2 + 6 + 2
    while pos + (2*4) + 1 <= len(msd):
        ti_raw = le16(msd[pos], msd[pos+1]); pos+=2
        hi_raw = le16(msd[pos], msd[pos+1]); pos+=2
        te_raw = le16(msd[pos], msd[pos+1]); pos+=2
        he_raw = le16(msd[pos], msd[pos+1]); pos+=2
        pkt = msd[pos]; pos+=1
        ti = ti_raw / 16.0
        hi = hi_raw / 16.0
        te = te_raw / 16.0
        he = he_raw / 16.0
        res["blocks"].append({
            "pkt": pkt,
            "ti_raw": ti_raw, "hi_raw": hi_raw, "te_raw": te_raw, "he_raw": he_raw,
            "ti": ti, "hi": hi, "te": te, "he": he
        })
    return res

def load_json_lines(path):
    if not os.path.exists(path):
        print("ERROR: file not found:", path); sys.exit(1)
    raw = open(path, "r", encoding="utf8").read().strip()
    items = []
    # try JSON array
    try:
        j = json.loads(raw)
        if isinstance(j, list):
            items = j
        else:
            items = [j]
    except Exception:
        # try NDJSON (one JSON object per line)
        for L in raw.splitlines():
            L = L.strip()
            if not L: continue
            try:
                items.append(json.loads(L))
            except Exception:
                # ignore parse errors
                pass
    return items

def main():
    items = load_json_lines(PATH)
    print("Loaded", len(items), "entries from", PATH)
    found = 0
    for it in items:
        hexv = it.get("manufacturer_data_hex") or it.get("manufacturer_data") or ""
        if not hexv: continue
        found += 1
        name = it.get("name") or it.get("identifier") or "(unknown)"
        addr = it.get("address") or it.get("identifier") or ""
        rssi = it.get("rssi", "")
        print("\n--- Entry:", found, "| name:", name, "| addr:", addr, "| rssi:", rssi)
        print("raw hex:", hexv)
        b = hex_to_bytes(hexv)
        dec = decode_msd_bytes(b)
        if "error" in dec:
            print(" decode error:", dec["error"], "len:", dec.get("len"))
            continue
        print(" CID: 0x%04x  msd_len:%d  blocks:%d" % (dec["cid"], dec["len"], len(dec["blocks"])))
        for i,blk in enumerate(dec["blocks"]):
            print("  block#%d pkt=%d  Ti=%.4f°C  Hi=%.4f%%  Te=%.4f°C  He=%.4f%%  (raw:%d,%d,%d,%d)" %
                  (i, blk["pkt"], blk["ti"], blk["hi"], blk["te"], blk["he"],
                   blk["ti_raw"], blk["hi_raw"], blk["te_raw"], blk["he_raw"]))
    if found == 0:
        print("No manufacturer_data_hex fields found in file.")

if __name__ == '__main__':
    main()
