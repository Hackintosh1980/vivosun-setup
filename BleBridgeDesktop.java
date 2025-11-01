import java.io.*;
import java.nio.file.*;
import java.util.*;
import org.freedesktop.dbus.connections.impl.DBusConnection;
import org.freedesktop.dbus.interfaces.DBusInterface;
import org.freedesktop.dbus.types.Variant;

public class BleBridgeDesktop {

    public static void main(String[] args) {
        try {
            List<Map<String, Object>> devices = new ArrayList<>();

            // Minimaler BlueZ-Scan über hcitool (schnell & robust)
            Process p = new ProcessBuilder("bash", "-c",
                    "timeout 4s hcitool lescan --duplicates | grep ':'").start();

            BufferedReader br = new BufferedReader(new InputStreamReader(p.getInputStream()));
            String line;
            Set<String> seen = new HashSet<>();
            while ((line = br.readLine()) != null) {
                if (!line.contains(":")) continue;
                String[] parts = line.trim().split(" ", 2);
                String addr = parts[0].trim();
                String name = parts.length > 1 ? parts[1].trim() : "Unknown";
                if (!seen.add(addr)) continue;

                Map<String, Object> d = new LinkedHashMap<>();
                d.put("address", addr);
                d.put("name", name);
                devices.add(d);
            }
            br.close();

            // JSON speichern
            Path out = Paths.get("ble_scan.json");
            try (BufferedWriter w = Files.newBufferedWriter(out)) {
                w.write("[\n");
                for (int i = 0; i < devices.size(); i++) {
                    Map<String, Object> d = devices.get(i);
                    w.write(String.format("  {\"address\": \"%s\", \"name\": \"%s\"}%s\n",
                            d.get("address"), d.get("name"),
                            i < devices.size() - 1 ? "," : ""));
                }
                w.write("]\n");
            }
            System.out.println("✅ Scan abgeschlossen → ble_scan.json (" + devices.size() + " Geräte)");
        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}
