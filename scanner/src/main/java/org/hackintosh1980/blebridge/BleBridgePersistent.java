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
 * 🌿 BleBridgePersistent – Ultimate Edition (2025-11)
 *  - Echtzeit-Bridge mit aktivem MAC-Filter (setActiveMac)
 *  - ThermoBeacon / VSCTLE kompatibel
 *  - erkennt fehlende externe Sensoren → ext_present=false, Werte=-99.0
 *  - JSON-Write nur bei Änderungen (50 ms debounce)
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

    private static final int RSSI_MIN = -95;
    private static final int COMPANY_ID = 0x0019;
    private static final int NEED_MIN = 2 + 6 + 2 + (2 * 4) + 1;

    private static final long CHANGE_WRITE_MS = 50L;
    private static long lastWrite = 0L;

    private static volatile String activeMac = null;

    // -----------------------------------------------------------
    // Start
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

            ScanSettings settings = new ScanSettings.Builder()
                    .setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY)
                    .setReportDelay(0)
                    .build();

            callback = new ScanCallback() {
                @Override
                public void onScanResult(int type, ScanResult r) { handle(r); }

                private void handle(ScanResult r) {
                    try {
                        if (!running || r == null || r.getDevice() == null) return;

                        String name = r.getDevice().getName();
                        if (name == null) name = "";
                        String mac = r.getDevice().getAddress();
                        int rssi = r.getRssi();
                        if (rssi < RSSI_MIN) return;

                        // Aktive MAC filtern
                        if (activeMac != null && !mac.equalsIgnoreCase(activeMac)) return;

                        ScanRecord rec = r.getScanRecord();
                        if (rec == null) return;
                        SparseArray<byte[]> md = rec.getManufacturerSpecificData();
                        if (md == null || md.size() == 0) return;

                        byte[] payload = md.get(COMPANY_ID);
                        if (payload == null) {
                            // Fallback: längstes MSD-Feld wählen
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

                        JSONObject j = decodeThermoBeaconLike(name, mac, rssi, payload, type);
                        if (j == null) return;

                        synchronized (lock) {
                            JSONObject prev = lastSeen.get(mac);
                            if (prev == null || !prev.toString().equals(j.toString())) {
                                lastSeen.put(mac, j);
                                long now = System.currentTimeMillis();
                                if (now - lastWrite > CHANGE_WRITE_MS) {
                                    writeSnapshot();
                                    lastWrite = now;
                                }
                            }
                        }

                        if (DEBUG)
                            Log.i(TAG, "UPDATE " + mac
                                    + " Ti=" + j.optDouble("temperature_int")
                                    + " Hi=" + j.optDouble("humidity_int")
                                    + " Te=" + j.optDouble("temperature_ext")
                                    + " He=" + j.optDouble("humidity_ext")
                                    + " ext_present=" + j.optBoolean("ext_present")
                                    + " pkt=" + j.optInt("packet_counter"));

                    } catch (Throwable t) {
                        Log.e(TAG, "handle", t);
                    }
                }
            };

            scanner.startScan(null, settings, callback);
            Log.i(TAG, "RUNNING – ultra-low-latency");
            return "OK:RUNNING";

        } catch (Throwable t) {
            running = false;
            Log.e(TAG, "start", t);
            return "ERR:" + t.getMessage();
        }
    }

    // -----------------------------------------------------------
    // Stop
    // -----------------------------------------------------------
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
    // MAC-Filter
    // -----------------------------------------------------------
    public static void setActiveMac(String mac) {
        try {
            if (mac == null || mac.trim().isEmpty()) {
                activeMac = null;
                Log.i(TAG, "Active MAC cleared");
            } else {
                activeMac = mac.trim().toUpperCase();
                Log.i(TAG, "Active MAC set to " + activeMac);
            }
        } catch (Throwable t) {
            Log.e(TAG, "setActiveMac", t);
        }
    }

    public static String getActiveMac() { return activeMac; }

    // -----------------------------------------------------------
    // JSON-Write
    // -----------------------------------------------------------
    private static void writeSnapshot() {
        try {
            List<JSONObject> snapshot = new ArrayList<>(lastSeen.values());
            JSONArray arr = new JSONArray(snapshot);
            File tmp = new File(outFile.getAbsolutePath() + ".tmp");
            try (FileOutputStream fos = new FileOutputStream(tmp, false)) {
                fos.write(arr.toString().getBytes());
                fos.flush();
            }
            tmp.renameTo(outFile);
        } catch (Throwable e) {
            Log.e(TAG, "writeSnapshot", e);
        }
    }

    // -----------------------------------------------------------
    // Decoder mit ext_present-Logik
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

            boolean extPresent = !(H_e <= 0.1 || H_e > 110.0 || Double.isNaN(H_e));

            // wenn Sensor fehlt → Dummywerte
            if (!extPresent) {
                T_e = -99.0;
                H_e = -99.0;
            }

            if (!(T_i >= -40 && T_i <= 85 && H_i >= 0 && H_i <= 110))
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
            o.put("ext_present", extPresent);
            o.put("packet_counter", pkt);
            return o;

        } catch (Throwable t) {
            Log.e(TAG, "decodeThermoBeaconLike", t);
            return null;
        }
    }

    // -----------------------------------------------------------
    // Helper
    // signed little-endian 16-bit (fix für negative Temperaturen)
    private static int le16(byte[] a, int off) {
        int val = ((a[off + 1] & 0xFF) << 8) | (a[off] & 0xFF);
        if ((val & 0x8000) != 0) val -= 0x10000;   // Zweierkomplement → signed short
        return val;
    }

    private static String ts() {
        return new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSSZ", Locale.US)
                .format(new Date());
    }
}
