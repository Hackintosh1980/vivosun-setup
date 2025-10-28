def fmt_temp(v):
    try: return f"{float(v):.1f} °C"
    except: return "—"

def fmt_hum(v):
    try: return f"{float(v):.1f} %"
    except: return "—"
