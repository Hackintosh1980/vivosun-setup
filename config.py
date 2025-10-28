import json, os

CONFIG_FILE = "config.json"

DEFAULTS = {
    "device_id": "",
    "refresh_interval": 4  # Sekunden
}

def load():
    if not os.path.exists(CONFIG_FILE):
        return DEFAULTS.copy()
    try:
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
        merged = DEFAULTS.copy()
        merged.update(data or {})
        return merged
    except Exception:
        return DEFAULTS.copy()

def save(data: dict):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print("⚠️ Config speichern fehlgeschlagen:", e)

def get(key, default=None):
    data = load()
    return data.get(key, DEFAULTS.get(key, default))

def save_device_id(dev_id: str):
    data = load()
    data["device_id"] = dev_id
    save(data)
    return data

def get_refresh_interval() -> int:
    return int(get("refresh_interval", DEFAULTS["refresh_interval"]))

def set_refresh_interval(seconds: int):
    data = load()
    data["refresh_interval"] = int(max(1, seconds))
    save(data)
    return data
