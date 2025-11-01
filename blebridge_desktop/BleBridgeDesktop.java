import java.io.*;
import java.util.*;
import org.json.simple.JSONArray;
import org.json.simple.JSONObject;

public class BleBridgeDesktop {

    public static void main(String[] args) {
        String jsonPath = "ble_scan.json";
        System.out.println("🚀 Starte BleBridgeDesktopLight (hcitool lescan) …");
        System.out.println("💾 Schreibe nach: " + jsonPath);

        JSONArray devices = new JSONArray();

        try {
            ProcessBuilder pb = new ProcessBuilder("hcitool", "lescan", "--duplicates");
            pb.redirectErrorStream(true);
            Process process = pb.start();

            BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream()));
            String line;
            long start = System.currentTimeMillis();

            while ((line = reader.readLine()) != null) {
                line = line.trim();
                if (line.isEmpty()) continue;
                if (line.startsWith("LE Scan")) continue;

                // Beispiel: "F0:F1:00:00:06:19 ThermoBeacon2"
                String[] parts = line.split(" ", 2);
                if (parts.length < 1) continue;

                String addr = parts[0].trim();
                String name = parts.length > 1 ? parts[1].trim() : "(unknown)";

                boolean exists = false;
                for (Object obj : devices) {
                    JSONObject dev = (JSONObject) obj;
                    if (addr.equals(dev.get("address"))) {
                        exists = true;
                        break;
                    }
                }

                if (!exists) {
                    JSONObject dev = new JSONObject();
                    dev.put("address", addr);
                    dev.put("name", name);
                    devices.add(dev);
                    System.out.println("📡 Gefunden: " + addr + " " + name);
                }

                // Nach 6 Sekunden abbrechen
                if (System.currentTimeMillis() - start > 6000)
                    break;
            }

            reader.close();
            process.destroy();

            try (FileWriter fw = new FileWriter(jsonPath)) {
                fw.write(devices.toJSONString());
                fw.flush();
            }

            System.out.println("✅ Scan fertig → " + jsonPath + " (" + devices.size() + " Geräte)");

        } catch (Exception e) {
            System.err.println("❌ Fehler beim Scan: " + e);
        }
    }
}
