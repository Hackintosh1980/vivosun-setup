package org.hackintosh1980.blebridge;

import android.bluetooth.*;
import android.bluetooth.le.*;
import android.content.Context;
import android.util.Log;
import android.util.SparseArray;
import org.json.*;
import java.io.*;
import java.nio.*;
import java.util.concurrent.*;

public class BleBridgePersistent {

    private static boolean running = false;
    private static BluetoothLeScanner scanner;
    private static ScanCallback callback;
    private static File outFile;

    /** Startet einen permanenten Scan und schreibt regelmäßig JSON */
    public static String start(Context ctx, String outFileName) {
        try {
            if (running) return "ALREADY_RUNNING";
            running = true;

            BluetoothManager bm = (BluetoothManager) ctx.getSystemService(Context.BLUETOOTH_SERVICE);
            BluetoothAdapter adapter = bm.getAdapter();
            if (adapter == null || !adapter.isEnabled()) return "BT_OFF";

            scanner = adapter.getBluetoothLeScanner();
            if (scanner == null) return "NO_SCANNER";

            outFile = new File(ctx.getFilesDir(), outFileName);

            callback = new ScanCallback() {
                @Override
                public void onScanResult(int type, ScanResult r) {
                    try {
                        String n = r.getDevice().getName();
                        if (n == null || !(n.toLowerCase().contains("thermo") || n.toLowerCase().contains("vivosun")))
                            return;

                        JSONObject o = new JSONObject();
                        o.put("name", n);
                        o.put("address", r.getDevice().getAddress());
                        o.put("rssi", r.getRssi());

                        SparseArray<byte[]> mdata = r.getScanRecord().getManufacturerSpecificData();
                        for (int i = 0; i < mdata.size(); i++) {
                            byte[] p = mdata.valueAt(i);
                            if (p == null || p.length < 14) continue;

                            ByteBuffer bb = ByteBuffer.wrap(p).order(ByteOrder.LITTLE_ENDIAN);
                            bb.position(6);
                            if (bb.remaining() >= 2) bb.getShort(); // Dummy

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
                        }

                        JSONArray arr = new JSONArray();
                        arr.put(o);
                        synchronized (BleBridgePersistent.class) {
                            try (FileOutputStream fos = new FileOutputStream(outFile, false)) {
                                fos.write(arr.toString().getBytes());
                            }
                        }

                    } catch (Exception e) {
                        Log.e("BleBridgePersistent", "Decode error", e);
                    }
                }
            };

            // 🔁 Einmal starten – nie wieder stoppen
            scanner.startScan(callback);
            Log.i("BleBridgePersistent", "Permanent scan gestartet");

            return "OK:RUNNING";
        } catch (Throwable t) {
            running = false;
            return "ERR:" + t.getMessage();
        }
    }

    /** Stoppt den Scan sauber */
    public static String stop() {
        try {
            if (!running) return "NOT_RUNNING";
            running = false;
            if (scanner != null && callback != null) scanner.stopScan(callback);
            Log.i("BleBridgePersistent", "Permanent scan gestoppt");
            return "OK:STOPPED";
        } catch (Throwable t) {
            return "ERR:" + t.getMessage();
        }
    }
}
