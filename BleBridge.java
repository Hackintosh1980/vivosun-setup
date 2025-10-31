package org.hackintosh1980.blebridge;

import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothManager;
import android.bluetooth.le.BluetoothLeScanner;
import android.bluetooth.le.ScanCallback;
import android.bluetooth.le.ScanResult;
import android.content.Context;
import android.util.SparseArray;
import android.util.Log;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;

/**
 * BLE-Bridge v3.3 – LiveWrite Edition (1 s Write Interval, 60 s Scan)
 * © 2025 Dominik Rosenthal (Hackintosh1980)
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
            final File outFile = new File(ctx.getFilesDir(), outFileName);

            ScanCallback cb = new ScanCallback() {
                @Override
                public void onScanResult(int callbackType, ScanResult result) {
                    try {
                        String name = result.getDevice().getName();
                        String addr = result.getDevice().getAddress();
                        if (name == null) name = "";
                        if (addr == null) addr = "";

                        String low = name.toLowerCase();
                        if (!(low.contains("thermo") || low.contains("vivosun") || low.contains("thermobeacon")))
                            return;

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
                                    final int startOffset = 6;
                                    ByteBuffer bb = ByteBuffer.wrap(payload).order(ByteOrder.LITTLE_ENDIAN);
                                    if (payload.length > startOffset + 10) {
                                        bb.position(startOffset);
                                    }

                                    // Dummy-Short überspringen
                                    if (bb.remaining() >= 2) bb.getShort();

                                    float t_int = (bb.remaining() >= 2) ? (bb.getShort() & 0xFFFF) / 16.0f : 0f;
                                    float h_int = (bb.remaining() >= 2) ? (bb.getShort() & 0xFFFF) / 16.0f : 0f;
                                    float t_ext = (bb.remaining() >= 2) ? (bb.getShort() & 0xFFFF) / 16.0f : 0f;
                                    float h_ext = (bb.remaining() >= 2) ? (bb.getShort() & 0xFFFF) / 16.0f : 0f;
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

                        synchronized (results) {
                            results.put(o);
                        }

                    } catch (Exception ex) {
                        Log.e("BleBridge", "Decode error", ex);
                    }
                }
            };

            // 🔁 Starte Scan
            scanner.startScan(cb);
            Log.i("BleBridge", "LiveScan gestartet (Intervall 1 s / Dauer 60 s)");

            // --- Laufzeitsteuerung ---
            long startTime = System.currentTimeMillis();
            long endTime = startTime + 60000;  // 60 Sekunden Laufzeit
            long lastWrite = startTime;

            while (System.currentTimeMillis() < endTime) {
                long now = System.currentTimeMillis();

                // Alle 1 Sekunde Datei schreiben
                if (now - lastWrite >= 1000) {
                    synchronized (results) {
                        try (FileOutputStream fos = new FileOutputStream(outFile, false)) {
                            fos.write(results.toString().getBytes());
                            fos.flush();
                        }
                    }
                    lastWrite = now;
                }

                Thread.sleep(200); // CPU-Freundlich
            }

            // --- Scan beenden ---
            scanner.stopScan(cb);
            Log.i("BleBridge", "Scan beendet → " + outFile.getAbsolutePath());
            return "OK:" + outFile.getAbsolutePath();

        } catch (Throwable t) {
            return "ERR:" + t.getClass().getSimpleName() + ":" + t.getMessage();
        }
    }
}
