package org.hackintosh1980.blebridge;

import android.bluetooth.*;
import android.bluetooth.le.*;
import android.content.Context;
import android.util.Log;
import android.util.SparseArray;
import org.json.*;
import java.io.File;
import java.io.FileOutputStream;
import java.nio.*;
import java.util.*;

public class BleBridgePersistent {

    private static final String TAG = "BleBridgePersistent";
    private static volatile boolean running = false;
    private static BluetoothLeScanner scanner;
    private static ScanCallback callback;
    private static File outFile;

    private static final List<JSONObject> buf = new ArrayList<>();
    private static final Object lock = new Object();

    // fine-tuning
    private static final int RSSI_MIN = -90;
    private static final int MIN_PAYLOAD_LEN = 14;
    private static final long WRITE_MS = 250L;
    private static final long THROTTLE_MS = 120L;

    private static long lastAppend = 0;

    private static JSONObject parse(String name, String mac, int rssi, byte[] p) {
        try {
            if (p == null || p.length < MIN_PAYLOAD_LEN) return null;
            if (rssi < RSSI_MIN) return null;
            ByteBuffer bb = ByteBuffer.wrap(p).order(ByteOrder.LITTLE_ENDIAN);
            if (bb.remaining() >= 6) bb.position(6);
            if (bb.remaining() >= 2) bb.getShort();

            float ti = (bb.remaining() >= 2) ? ((bb.getShort() & 0xFFFF) / 16f) : 0f;
            float hi = (bb.remaining() >= 2) ? ((bb.getShort() & 0xFFFF) / 16f) : 0f;
            float te = (bb.remaining() >= 2) ? ((bb.getShort() & 0xFFFF) / 16f) : 0f;
            float he = (bb.remaining() >= 2) ? ((bb.getShort() & 0xFFFF) / 16f) : 0f;
            int pkt = (bb.remaining() > 0) ? (bb.get() & 0xFF) : -1;

            JSONObject o = new JSONObject();
            o.put("name", name == null ? "" : name);
            o.put("address", mac == null ? "" : mac);
            o.put("rssi", rssi);
            o.put("temperature_int", ti);
            o.put("humidity_int", hi);
            o.put("temperature_ext", te);
            o.put("humidity_ext", he);
            o.put("packet_counter", pkt);
            return o;
        } catch (Exception e) {
            Log.w(TAG, "parse", e);
            return null;
        }
    }

    public static String start(Context ctx, String outFileName) {
        try {
            if (running) return "ALREADY_RUNNING";
            running = true;

            BluetoothManager bm = (BluetoothManager) ctx.getSystemService(Context.BLUETOOTH_SERVICE);
            BluetoothAdapter a = bm.getAdapter();
            if (a == null || !a.isEnabled()) { running = false; return "BT_OFF"; }
            scanner = a.getBluetoothLeScanner();
            if (scanner == null) { running = false; return "NO_SCANNER"; }

            outFile = new File(ctx.getFilesDir(), outFileName);

            // ⚙️ balanced low-latency
            ScanSettings s = new ScanSettings.Builder()
                    .setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY)
                    .setReportDelay(300) // milder batching
                    .build();

            callback = new ScanCallback() {
                @Override
                public void onBatchScanResults(List<ScanResult> results) {
                    for (ScanResult r : results) handle(r);
                }
                @Override
                public void onScanResult(int t, ScanResult r) { handle(r); }
                private void handle(ScanResult r) {
                    try {
                        if (r == null || r.getDevice() == null) return;
                        String n = r.getDevice().getName();
                        if (n == null || !n.equals("ThermoBeacon2")) return;
                        String mac = r.getDevice().getAddress();
                        int rs = r.getRssi();

                        SparseArray<byte[]> md = r.getScanRecord().getManufacturerSpecificData();
                        if (md == null || md.size() == 0) return;
                        int best = 0; byte[] pay = null;
                        for (int i = 0; i < md.size(); i++) {
                            byte[] p = md.valueAt(i);
                            if (p != null && p.length > best) { best = p.length; pay = p; }
                        }
                        if (pay == null) return;

                        long now = System.currentTimeMillis();
                        if (now - lastAppend < THROTTLE_MS) return; // sanfter Flow
                        lastAppend = now;

                        JSONObject j = parse(n, mac, rs, pay);
                        if (j != null) {
                            synchronized (lock) { buf.add(j); }
                            Log.i(TAG, String.format(
                                    "OK %s rssi=%d Tin=%.1f Hin=%.1f Tex=%.1f Hex=%.1f pkt=%d",
                                    n, rs,
                                    j.optDouble("temperature_int"),
                                    j.optDouble("humidity_int"),
                                    j.optDouble("temperature_ext"),
                                    j.optDouble("humidity_ext"),
                                    j.optInt("packet_counter", -1)
                            ));
                        }
                    } catch (Exception e) { Log.e(TAG, "handle", e); }
                }
            };

            // Writer smoother
            Thread t = new Thread(() -> {
                android.os.Process.setThreadPriority(android.os.Process.THREAD_PRIORITY_BACKGROUND);
                try {
                    while (running) {
                        Thread.sleep(WRITE_MS);
                        List<JSONObject> snap;
                        synchronized (lock) {
                            if (buf.isEmpty()) continue;
                            snap = new ArrayList<>(buf);
                            buf.clear();
                        }
                        JSONArray arr = new JSONArray(snap);
                        File tmp = new File(outFile.getAbsolutePath() + ".tmp");
                        try (FileOutputStream fos = new FileOutputStream(tmp, false)) {
                            fos.write(arr.toString().getBytes());
                            fos.flush();
                        }
                        tmp.renameTo(outFile);
                        Log.d(TAG, "JSON flush (" + arr.length() + ")");
                    }
                } catch (Throwable th) { Log.e(TAG, "writer", th); }
            });
            t.start();

            scanner.startScan(null, s, callback);
            Log.i(TAG, "Candidate+ Flow-Balancer started");
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
            if (scanner != null && callback != null) scanner.stopScan(callback);
            Log.i(TAG, "Bridge stopped");
            return "OK:STOPPED";
        } catch (Throwable t) {
            Log.e(TAG, "stop", t);
            return "ERR:" + t.getMessage();
        }
    }
}
