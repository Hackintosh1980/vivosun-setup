// BleBridgeDesktop.java
// Desktop BLE Bridge (Linux): hcitool + hcidump -> decode ThermoBeacon2 (CompanyID 0x0019) -> JSON
// Output: /home/domi/vivosun-setup/blebridge_desktop/ble_scan.json

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.*;
import org.json.simple.JSONArray;
import org.json.simple.JSONObject;

public class BleBridgeDesktop {

    private static final String OUTPUT_JSON = "/home/domi/vivosun-setup/blebridge_desktop/ble_scan.json";
    private static final int CYCLE_SECONDS = 8;           // Dauer je hcidump-Lauf
    private static final int MIN_MSD_BYTES = 2 + 6 + 2 + (2*4) + 1; // CID + skip6 + skip2 + 4 shorts + 1 pkt
    private static final int COMPANY_ID = 0x0019;         // little-endian im MSD
    private static final int KEEP_LAST = 8;               // so viele Einträge im JSON halten

    public static void main(String[] args) {
        log("🌿 Starte BleBridgeDesktop – Decoder ohne Reset …");
        ensureFile();

        // Parallel: lescan im Hintergrund, hcidump in Schleife
        while (true) {
            Process lescan = null;
            Process hcidump = null;
            try {
                // 1) lescan starten (duplicates)
                lescan = new ProcessBuilder("bash", "-lc",
                        "sudo timeout " + CYCLE_SECONDS + "s hcitool lescan --duplicates")
                        .redirectErrorStream(true)
                        .start();

                // 2) hcidump raw starten
                hcidump = new ProcessBuilder("bash", "-lc",
                        "sudo timeout " + CYCLE_SECONDS + "s hcidump --raw")
                        .redirectErrorStream(true)
                        .start();

                // 3) hcidump lesen & dekodieren
                BufferedReader br = new BufferedReader(new InputStreamReader(hcidump.getInputStream(), StandardCharsets.UTF_8));
                ArrayList<Integer> ring = new ArrayList<>(4096);
                ArrayList<JSONObject> hits = new ArrayList<>();

                String line;
                while ((line = br.readLine()) != null) {
                    // Zeile in Bytes zerlegen
                    String[] toks = line.trim().split("\\s+");
                    for (String t : toks) {
                        if (t.length() != 2) continue;
                        int b = parseHexByte(t);
                        if (b < 0) continue;
                        ring.add(b);
                        if (ring.size() > 4096) {
                            ring.subList(0, 1024).clear(); // alten Kram weg
                        }
                    }

                    // Pattern scannen: [len=L][0xFF][0x19][0x00] (MSD)
                    // In Dumps sieht man oft: "... 03 02 F0 FF 17 FF 19 00 <payload...>"
                    // => Wir suchen generisch nach L(7..31), dann 0xFF, 0x19, 0x00
                    int n = ring.size();
                    for (int i = 0; i <= n - 4; i++) {
                        int L = ring.get(i);
                        if (L < 7 || L > 31) continue;              // vernünftige AD-Längen
                        if (ring.get(i + 1) != 0xFF) continue;       // AD-Typ: Manufacturer Specific
                        if (ring.get(i + 2) != 0x19) continue;       // CompanyID low
                        if (ring.get(i + 3) != 0x00) continue;       // CompanyID high

                        int msdStart = i + 2; // ab CompanyID-low
                        int msdTotal = 2 + (L - 3); // CID(2) + payload(L-3); (L schließt Typ+CID+payload ein)
                        int msdEndExclusive = msdStart + msdTotal;
                        if (msdEndExclusive > n) continue; // noch nicht komplett im Ring

                        byte[] msd = new byte[msdTotal];
                        for (int k = 0; k < msdTotal; k++) {
                            msd[k] = (byte)(ring.get(msdStart + k) & 0xFF);
                        }

                        JSONObject j = decodeThermoBeaconPayload(msd, "(unknown)", "ThermoBeacon2");
                        if (j != null) {
                            hits.add(j);
                            log(String.format("📡 %s Tin=%.1f Hin=%.1f | Tex=%.1f Hex=%.1f pkt=%d → JSON",
                                    ts(),
                                    ((Number)j.get("temperature_int")).doubleValue(),
                                    ((Number)j.get("humidity_int")).doubleValue(),
                                    ((Number)j.get("temperature_ext")).doubleValue(),
                                    ((Number)j.get("humidity_ext")).doubleValue(),
                                    ((Number)j.get("packet_counter")).intValue()
                            ));
                        }

                        // i vorsetzen, um Doppeleinträge innerhalb derselben AD-Struktur zu vermeiden
                        i = msdEndExclusive - 1;
                    }
                }

                // 4) JSON schreiben (nur wenn neue Treffer)
                if (!hits.isEmpty()) {
                    // existierende laden
                    JSONArray out = readJsonArray(OUTPUT_JSON);
                    if (out == null) out = new JSONArray();

                    // neue anhängen (ggf. dupl. pkt_counter filtern)
                    HashSet<String> sigSeen = new HashSet<>();
                    // bestehende Signaturen merken
                    for (Object o : out) {
                        if (o instanceof JSONObject) {
                            JSONObject jo = (JSONObject) o;
                            String sig = signatureOf(jo);
                            if (sig != null) sigSeen.add(sig);
                        }
                    }
                    for (JSONObject j : hits) {
                        String sig = signatureOf(j);
                        if (sig == null || !sigSeen.contains(sig)) {
                            out.add(j);
                            sigSeen.add(sig);
                        }
                    }
                    // auf KEEP_LAST begrenzen
                    if (out.size() > KEEP_LAST) {
                        int cut = out.size() - KEEP_LAST;
                        for (int x = 0; x < cut; x++) out.remove(0);
                    }
                    writeJsonArray(OUTPUT_JSON, out);
                    log("✅ JSON aktualisiert → " + OUTPUT_JSON + " (" + out.size() + " Eintrag[e])");
                } else {
                    log("ℹ️ Kein gültiges MSD gefunden – behalte letzte JSON.");
                }

                // sauber beenden
                waitQuiet(lescan);
                waitQuiet(hcidump);

            } catch (Exception e) {
                log("❌ Fehler: " + e.getMessage());
            } finally {
                killQuiet(lescan);
                killQuiet(hcidump);
            }
        }
    }

    // ---------- Dekodierung wie Android: skip6, skip2, 4×short/16, 1×pkt ----------
    private static JSONObject decodeThermoBeaconPayload(byte[] msd, String mac, String name) {
        // Erwartung: msd beginnt mit CompanyID little-endian (0x19 0x00), danach Payload
        if (msd == null || msd.length < MIN_MSD_BYTES) return null;
        int cid = le16(msd[0], msd[1]);
        if (cid != COMPANY_ID) return null;

        int pos = 2;         // nach CID
        pos += 6;            // 6 Bytes Header/SN
        pos += 2;            // Dummy-Short

        if (pos + (2*4) + 1 > msd.length) return null;

        int ti_raw = le16(msd[pos],     msd[pos+1]); pos += 2;
        int hi_raw = le16(msd[pos],     msd[pos+1]); pos += 2;
        int te_raw = le16(msd[pos],     msd[pos+1]); pos += 2;
        int he_raw = le16(msd[pos],     msd[pos+1]); pos += 2;
        int pkt    =  msd[pos] & 0xFF;

        double ti = ti_raw / 16.0;
        double hi = hi_raw / 16.0;
        double te = te_raw / 16.0;
        double he = he_raw / 16.0;

        // grobe Plausis: verwerfen wenn voll off (optional, aber hilft gegen Müll)
        if (ti < -40 || ti > 85) return null;
        if (te < -40 || te > 85) return null;
        if (hi < 0 || hi > 110)  return null;
        if (he < 0 || he > 110)  return null;

        JSONObject j = new JSONObject();
        j.put("name", (name == null) ? "ThermoBeacon2" : name);
        j.put("address", (mac == null) ? "(unknown)" : mac);
        j.put("rssi", 0); // hcidump liefert hier nix stabil
        j.put("temperature_int", ti);
        j.put("humidity_int",   hi);
        j.put("temperature_ext", te);
        j.put("humidity_ext",    he);
        j.put("packet_counter",  pkt);
        return j;
    }

    // ---------- Utils ----------
    private static int parseHexByte(String t) {
        try {
            return Integer.parseInt(t, 16) & 0xFF;
    } catch (Exception e) { return -1; } }

    private static int le16(int lo, int hi) {
        return ((hi & 0xFF) << 8) | (lo & 0xFF);
    }

    private static void ensureFile() {
        try {
            File f = new File(OUTPUT_JSON);
            f.getParentFile().mkdirs();
            if (!f.exists()) {
                try (FileWriter fw = new FileWriter(f)) { fw.write("[]"); }
            }
        } catch (IOException ignored) {}
    }

    private static JSONArray readJsonArray(String path) {
        try (BufferedReader br = new BufferedReader(new FileReader(path))) {
            StringBuilder sb = new StringBuilder();
            String s; while ((s = br.readLine()) != null) sb.append(s);
            String raw = sb.toString().trim();
            if (raw.isEmpty()) return new JSONArray();
            // ganz simpler Parser: json-simple kann JSONArray.parse, aber hier kurz und robust:
            org.json.simple.parser.JSONParser p = new org.json.simple.parser.JSONParser();
            Object o = p.parse(raw);
            if (o instanceof JSONArray) return (JSONArray) o;
        } catch (Exception ignored) {}
        return new JSONArray();
    }

    private static void writeJsonArray(String path, JSONArray arr) {
        File tmp = new File(path + ".tmp");
        try (FileWriter fw = new FileWriter(tmp, false)) {
            fw.write(arr.toJSONString());
            fw.flush();
        } catch (IOException ignored) {}
        // atomarer Replace
        File dst = new File(path);
        tmp.renameTo(dst);
    }

    private static String signatureOf(JSONObject j) {
        try {
            // Signatur: (pkt_counter, ti, hi, te, he) reicht um rasches Duplizieren zu vermeiden
            return "p" + ((Number)j.get("packet_counter")).intValue() +
                    "t" + ((Number)j.get("temperature_int")).doubleValue() +
                    "h" + ((Number)j.get("humidity_int")).doubleValue() +
                    "x" + ((Number)j.get("temperature_ext")).doubleValue() +
                    "y" + ((Number)j.get("humidity_ext")).doubleValue();
        } catch (Exception e) { return null; }
    }

    private static void waitQuiet(Process p) {
        if (p == null) return;
        try { p.waitFor(); } catch (InterruptedException ignored) {}
    }
    private static void killQuiet(Process p) {
        if (p == null) return;
        try { p.destroy(); } catch (Exception ignored) {}
        try { p.destroyForcibly(); } catch (Exception ignored) {}
    }

    private static String ts() {
        return new SimpleDateFormat("HH:mm:ss").format(new Date());
    }
    private static void log(String s) {
        System.out.println(s);
    }
}
