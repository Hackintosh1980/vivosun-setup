package org.hackintosh1980.blebridge;

import android.bluetooth.*;
import android.bluetooth.le.*;
import android.content.Context;
import android.util.Log;
import android.util.SparseArray;
import org.json.*;
import java.io.*;
import java.text.SimpleDateFormat;
import java.util.*;

/**
 * ⚡ BleBridgePersistent ULTRAFAST (Dominik Edition)
 *  - extrem schnelle JSON-Updates (≈100 ms Flush)
 *  - keine Scan-Batching-Verzögerung (reportDelay=0)
 *  - optimiertes Throttling & stabiler Multidevice-Flow
 *  - kompatibel mit VSCTLE42A Controller + ThermoBeacon2 Sensor
 */
public class BleBridgePersistent {

    private static final String TAG = "BleBridgePersistent";
    private static final boolean DEBUG = true;

    private static volatile boolean running = false;
    private static BluetoothLeScanner scanner;
    private static ScanCallback callback;
    private static File outFile;

    private static final Object lock = new Object();
    private static final Map<String, JSONObject> lastSeen = new HashMap<>();

    // --- Fine tuning ---
    private static final int RSSI_MIN = -95;
    private static final int COMPANY_ID = 0x0019;
    private static final int NEED_MIN = 2 + 6 + 2 + (2 * 4) + 1;

    // 🔥 Aggressive flush tuning
    private static final long WRITE_MS = 150L;   // flush alle 0.15 s
    private static final long THROTTLE_MS = 50L; // 50 ms minimaler Abstand
    private static long lastAppend = 0;

    // -----------------------------------------------------------
    // Start / Stop
    // -----------------------------------------------------------
    public static String start(Context ctx, String outFileName) {
        try {
            if (running) return "ALREADY_RUNNING";
            running = true;

            BluetoothManager bm = (BluetoothManager) ctx.getSystemService(Context.BLUETOOTH_SERVICE);
            BluetoothAdapter adapter = bm != null ? bm.getAdapter() : null;
            if (adapter == null || !adapter.isEnabled()) {
                running = false;
                return "BT_OFF";
            }

            scanner = adapter.getBluetoothLeScanner();
            if (scanner == null) {
                running = false;
                return "NO_SCANNER";
            }

            outFile = new File(ctx.getFilesDir(), outFileName);
            Log.i(TAG, "Start → file=" + outFile.getAbsolutePath());

            // 🏎 Sofortige Ergebnislieferung, kein Delay
            ScanSettings settings = new ScanSettings.Builder()
                    .setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY)
                    .setReportDelay(0) // Echtzeit, keine Batch-Verzögerung
                    .build();

            callback = new ScanCallback() {
                @Override
                public void onScanResult(int type, ScanResult r) { handle(r); }
                @Override
                public void onBatchScanResults(List<ScanResult> results) {
                    for (ScanResult res : results) handle(res);
                }

                private void handle(ScanResult r) {
                    try {
                        if (r == null || r.getDevice() == null) return;
                        String name = r.getDevice().getName();
                        if (name == null) name = "";
                        String mac = r.getDevice().getAddress();
                        int rssi = r.getRssi();
                        if (rssi < RSSI_MIN) return;

                        ScanRecord rec = r.getScanRecord();
                        if (rec == null) return;
                        SparseArray<byte[]> md = rec.getManufacturerSpecificData();
                        if (md == null || md.size() == 0) return;

                        byte[] payload = md.get(COMPANY_ID);
                        if (payload == null) {
                            int bestLen = 0;
                            for (int i = 0; i < md.size(); i++) {
                                byte[] p = md.valueAt(i);
                                if (p != null && p.length > bestLen) {
                                    bestLen = p.length;
                                    payload = p;
                                }
                            }
                        }
                        if (payload == null) return;

                        String type = (name.toLowerCase().contains("vsctle")) ? "controller"
                                : (name.toLowerCase().contains("thermobeacon")) ? "sensor"
                                : "unknown";

                        long now = System.currentTimeMillis();
                        if (now - lastAppend < THROTTLE_MS) return;
                        lastAppend = now;

                        JSONObject j = decodeThermoBeaconLike(name, mac, rssi, payload, type);
                        if (j != null) {
                            synchronized (lock) {
                                lastSeen.put(mac, j);
                            }
                        }

                    } catch (Throwable t) {
                        Log.e(TAG, "handle", t);
                    }
                }
            };

            // 🔄 Writer Thread (Echtzeit-JSON)
            Thread writer = new Thread(() -> {
                android.os.Process.setThreadPriority(android.os.Process.THREAD_PRIORITY_BACKGROUND);
                try {
                    while (running) {
                        Thread.sleep(WRITE_MS);
                        List<JSONObject> snapshot;
                        synchronized (lock) {
                            if (lastSeen.isEmpty()) continue;
                            snapshot = new ArrayList<>(lastSeen.values());
                        }
                        JSONArray arr = new JSONArray(snapshot);
                        File tmp = new File(outFile.getAbsolutePath() + ".tmp");
                        try (FileOutputStream fos = new FileOutputStream(tmp, false)) {
                            fos.write(arr.toString().getBytes());
                            fos.flush();
                        }
                        tmp.renameTo(outFile);
                        if (DEBUG) Log.d(TAG, "⚡ JSON flush (" + arr.length() + ")");
                    }
                } catch (Throwable th) {
                    Log.e(TAG, "writer", th);
                }
            });
            writer.start();

            scanner.startScan(null, settings, callback);
            Log.i(TAG, "RUNNING – UltraFast BLE bridge active");
            return "OK:RUNNING";

        } catch (Throwable t) {
            running = false;
            Log.e(TAG, "start", t);
            return "ERR:" + t.getMessage();
        }
    }

    public static String stop() {
        try {
            if (!running) return "NOT_RUNNING";
            running = false;
            if (scanner != null && callback != null) {
                try { scanner.stopScan(callback); } catch (Throwable ignored) {}
            }
            Log.i(TAG, "STOPPED");
            return "OK:STOPPED";
        } catch (Throwable t) {
            Log.e(TAG, "stop", t);
            return "ERR:" + t.getMessage();
        }
    }

    // -----------------------------------------------------------
    // Decoder (wie zuvor)
    // -----------------------------------------------------------
    private static JSONObject decodeThermoBeaconLike(String name, String mac, int rssi, byte[] payload, String type) {
        try {
            byte[] b = payload;
            if (b == null || b.length < NEED_MIN) return null;

            int cid = le16(b, 0);
            if (cid != COMPANY_ID) {
                byte[] msd = new byte[b.length + 2];
                msd[0] = 0x19; msd[1] = 0x00;
                System.arraycopy(b, 0, msd, 2, b.length);
                b = msd;
            }

            int pos = 2 + 6 + 2;
            if (b.length < pos + (2 * 4) + 1) return null;

            int ti = le16(b, pos); pos += 2;
            int hi = le16(b, pos); pos += 2;
            int te = le16(b, pos); pos += 2;
            int he = le16(b, pos); pos += 2;
            int pkt = b[pos++] & 0xFF;

            double T_i = ti / 16.0;
            double H_i = hi / 16.0;
            double T_e = te / 16.0;
            double H_e = he / 16.0;

            if (!(T_i >= -40 && T_i <= 85 && T_e >= -40 && T_e <= 85 && H_i >= 0 && H_i <= 110 && H_e >= 0 && H_e <= 110))
                return null;

            JSONObject o = new JSONObject();
            o.put("timestamp", ts());
            o.put("name", name);
            o.put("address", mac);
            o.put("rssi", rssi);
            o.put("type", type);
            o.put("temperature_int", T_i);
            o.put("humidity_int", H_i);
            o.put("temperature_ext", T_e);
            o.put("humidity_ext", H_e);
            o.put("packet_counter", pkt);

            if (DEBUG)
                Log.i(TAG, String.format("UPDATE %s Ti=%.2f Hi=%.2f Te=%.2f He=%.2f pkt=%d", mac, T_i, H_i, T_e, H_e, pkt));

            return o;

        } catch (Throwable t) {
            Log.e(TAG, "decodeThermoBeaconLike", t);
            return null;
        }
    }

    // -----------------------------------------------------------
    // Helpers
    // -----------------------------------------------------------
    private static int le16(byte[] a, int off) {
        return ((a[off + 1] & 0xFF) << 8) | (a[off] & 0xFF);
    }

    private static String ts() {
        return new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSSZ", Locale.US).format(new Date());
    }
}
