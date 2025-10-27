package org.hackintosh1980.blebridge;

import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothManager;
import android.bluetooth.le.BluetoothLeScanner;
import android.bluetooth.le.ScanCallback;
import android.bluetooth.le.ScanResult;
import android.content.Context;
import android.util.SparseArray;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;

/**
 * BLE-Bridge v3.2.1 – Mapping-Fix (keine Autodetektion)
 * Reihenfolge (nach Header + Dummy-Short):
 *   t_int, h_int, t_ext, h_ext, (battery)
 */
public class BleBridge {

    public static String scan(Context ctx, int durationMs, String outFileName) {
        try {
            BluetoothManager bm = (BluetoothManager) ctx.getSystemService(Context.BLUETOOTH_SERVICE);
            if (bm == null) return "NO_BLUETOOTH_MANAGER";
            BluetoothAdapter adapter = bm.getAdapter();
            if (adapter == null || !adapter.isEnabled()) return "BT_OFF";

            BluetoothLeScanner scanner = adapter.getBluetoothLeScanner();
            if (scanner == null) return "NO_SCANNER";

            final JSONArray results = new JSONArray();

            ScanCallback cb = new ScanCallback() {
                @Override
                public void onScanResult(int callbackType, ScanResult result) {
                    try {
                        String name = result.getDevice().getName();
                        String addr = result.getDevice().getAddress();
                        if (name == null) name = "";
                        if (addr == null) addr = "";

                        // Gleiches Filtering wie zuvor
                        String low = name.toLowerCase();
                        if (!(low.contains("thermo") || low.contains("vivosun") || low.contains("thermobeacon"))) return;

                        JSONObject o = new JSONObject();
                        o.put("address", addr);
                        o.put("name", name);
                        o.put("rssi", result.getRssi());

                        if (result.getScanRecord() != null) {
                            SparseArray<byte[]> mdata = result.getScanRecord().getManufacturerSpecificData();
                            for (int i = 0; i < mdata.size(); i++) {
                                byte[] payload = mdata.valueAt(i);
                                if (payload == null || payload.length < 14) continue;

                                try {
                                    // Start nach Header
                                    final int startOffset = 6;
                                    ByteBuffer bb = ByteBuffer.wrap(payload).order(ByteOrder.LITTLE_ENDIAN);
                                    if (payload.length > startOffset + 10) {
                                        bb.position(startOffset);
                                    }

                                    // 1) Dummy/Flags überspringen (das war der 221.9-„Wert“)
                                    if (bb.remaining() >= 2) bb.getShort();

                                    // 2) Reales Mapping
                                    float t_int = (bb.remaining() >= 2) ? (bb.getShort() & 0xFFFF) / 16.0f : 0f;
                                    float h_int = (bb.remaining() >= 2) ? (bb.getShort() & 0xFFFF) / 16.0f : 0f;
                                    float t_ext = (bb.remaining() >= 2) ? (bb.getShort() & 0xFFFF) / 16.0f : 0f;
                                    float h_ext = (bb.remaining() >= 2) ? (bb.getShort() & 0xFFFF) / 16.0f : 0f;

                                    // 3) Optional Batterie
                                    int batt = (bb.remaining() > 0) ? (bb.get() & 0xFF) : -1;

                                    o.put("temperature_int", t_int);
                                    o.put("temperature_ext", t_ext);
                                    o.put("humidity_int", h_int);
                                    o.put("humidity_ext", h_ext);
                                    o.put("battery", batt);

                                } catch (Exception decodeErr) {
                                    o.put("decode_error", decodeErr.getMessage());
                                }
                            }
                        }

                        results.put(o);
                    } catch (Exception ignored) { }
                }
            };

            scanner.startScan(cb);
            try { Thread.sleep(durationMs); } catch (InterruptedException ignored) {}
            scanner.stopScan(cb);

            File out = new File(ctx.getFilesDir(), outFileName);
            try (FileOutputStream fos = new FileOutputStream(out, false)) {
                fos.write(results.toString().getBytes()); // keine Pretty-Print, kompakter
                fos.flush();
            }

            return "OK:" + out.getAbsolutePath();
        } catch (Throwable t) {
            return "ERR:" + t.getClass().getSimpleName() + ":" + t.getMessage();
        }
    }
}
