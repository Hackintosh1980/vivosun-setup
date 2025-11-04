package org.hackintosh1980.blebridge;

import android.content.Context;
import android.util.Log;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.*;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.ArrayList;
import java.util.List;

public class BleDecoder implements Runnable {
    private static final String TAG = "BleDecoder";
    private final File rawFile;
    private final File outFile;
    private volatile boolean running = true;

    // Layout: CID(2) + HDR(6) + SKIP(2/4) + 4×short + pkt
    private static final int NEED_MIN = 2 + 6 + 2 + (2 * 4) + 1;
    private static final int KEEP_LAST = 100;

    public BleDecoder(Context ctx, String rawName, String outName) {
        this.rawFile = new File(ctx.getFilesDir(), rawName);
        this.outFile = new File(ctx.getFilesDir(), outName);
    }

    @Override
    public void run() {
        Log.i(TAG, "Decoder running …");
        long lastLen = 0;
        while (running) {
            try {
                Thread.sleep(600);
                if (!rawFile.exists()) continue;
                long len = rawFile.length();
                if (len == lastLen) continue;
                lastLen = len;
                decodeFile();
            } catch (Exception e) {
                Log.e(TAG, "loop", e);
            }
        }
    }

    private void decodeFile() {
        try {
            if (rawFile.length() < 4) return;
            BufferedReader br = new BufferedReader(new FileReader(rawFile));
            JSONArray outArr = new JSONArray();
            String line;
            while ((line = br.readLine()) != null) {
                try {
                    JSONObject src = new JSONObject(line);
                    String name = src.optString("name");
                    String mac = src.optString("address");
                    int rssi = src.optInt("rssi");
                    String hex = src.optString("manufacturer_data_hex");
                    byte[] msd = normalizeCid(hexToBytes(hex));

                    // Offsets: A = ThermoBeacon, B = VSCTLE
                    List<JSONObject> a = decodeAt(name, mac, rssi, msd, 2 + 6 + 2);
                    List<JSONObject> b = decodeAt(name, mac, rssi, msd, 2 + 6 + 4);

                    List<JSONObject> best = (b.size() > a.size()) ? b : a;
                    if (best.isEmpty()) best = a;
                    for (int i = 0; i < best.size(); i++) outArr.put(best.get(i));
                } catch (Exception ignore) {}
            }
            br.close();

            if (outArr.length() > KEEP_LAST) {
                JSONArray trimmed = new JSONArray();
                for (int i = outArr.length() - KEEP_LAST; i < outArr.length(); i++)
                    trimmed.put(outArr.get(i));
                outArr = trimmed;
            }

            // -------- Schreib-Fix mit 12 Einrückungen --------
            try {
                if (outFile.exists()) outFile.delete();   // alte JSON löschen
                String safeJson = outArr.toString();
                if (!safeJson.startsWith("[")) safeJson = "[]";
                FileOutputStream fos = new FileOutputStream(outFile, false);
                fos.write(safeJson.getBytes());
                fos.close();
            } catch (Exception ex) {
                Log.e(TAG, "writeSafe", ex);
            }
            // -------------------------------------------------

            Log.i(TAG, "Decoded " + outArr.length() + " → " + outFile.getName());
        } catch (Exception e) {
            Log.e(TAG, "decodeFile", e);
        }
    }

    private static List<JSONObject> decodeAt(String name, String mac, int rssi, byte[] msd, int start) {
        List<JSONObject> out = new ArrayList<JSONObject>();
        if (msd == null || msd.length < NEED_MIN) return out;
        if (start < 0 || start > msd.length) return out;

        int pos = start;
        while (pos + (2 * 4) + 1 <= msd.length) {
            int ti = le16(msd, pos); pos += 2;
            int hi = le16(msd, pos); pos += 2;
            int te = le16(msd, pos); pos += 2;
            int he = le16(msd, pos); pos += 2;
            int pkt = msd[pos] & 0xFF; pos += 1;

            double Tin = ti / 16.0;
            double Hin = hi / 16.0;
            double Tex = te / 16.0;
            double Hex = he / 16.0;

            if (!plausible(Tin, Hin, Tex, Hex)) continue;

            try {
                JSONObject j = new JSONObject();
                j.put("name", name);
                j.put("address", mac);
                j.put("rssi", rssi);
                j.put("temperature_int", Tin);
                j.put("humidity_int", Hin);
                j.put("temperature_ext", Tex);
                j.put("humidity_ext", Hex);
                j.put("packet_counter", pkt);
                out.add(j);
            } catch (Exception ignore) {}
        }
        return out;
    }

    private static boolean plausible(double ti, double hi, double te, double he) {
        return !(ti < -40 || ti > 85 || te < -40 || te > 85 || hi < 0 || hi > 110 || he < 0 || he > 110);
    }

    private static byte[] normalizeCid(byte[] raw) {
        if (raw == null || raw.length < 2) return raw;
        if ((raw[0] & 0xFF) == 0x19 && (raw[1] & 0xFF) == 0x00) return raw;
        byte[] p = new byte[raw.length + 2];
        p[0] = 0x19; p[1] = 0x00;
        System.arraycopy(raw, 0, p, 2, raw.length);
        return p;
    }

    private static int le16(byte[] a, int off) {
        if (off + 1 >= a.length) return 0;
        return ((a[off + 1] & 0xFF) << 8) | (a[off] & 0xFF);
    }

    private static byte[] hexToBytes(String s) {
        if (s == null) return new byte[0];
        int len = s.length();
        if ((len & 1) == 1) len--;
        byte[] d = new byte[len / 2];
        for (int i = 0; i < len; i += 2)
            d[i / 2] = (byte) Integer.parseInt(s.substring(i, i + 2), 16);
        return d;
    }

    public void stop() { running = false; }
}
