package io.github.iamwilmar.xenoblade3port;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileReader;
import java.io.FileWriter;
import java.io.IOException;
import java.io.InputStream;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

// Busca en una carpeta los archivos del juego que el usuario extrajo de su propia consola: el ExeFS y la RomFS del juego
// con la actualización aplicada y, si el juego los tiene, la RomFS de cada DLC; y comprueba que son de este juego y de la
// versión del port. No descifra nada ni abre NSP/XCI/NCA: solo lee carpetas con archivos ya extraídos. Lo que encuentra
// va a <carpeta>/rutas.txt, que lee el runtime (rutas.h). Sin nada de Android, para probarlo en un PC:
// java ... DumpScanner <carpeta>.
final class DumpScanner {
    private static final boolean ES = Locale.getDefault().getLanguage().equals("es");

    static String tr(String es, String en) {
        return ES ? es : en;
    }

    static final class Result {
        String exefs, romfs;
        final TreeMap<Integer, String> dlc = new TreeMap<>();  // índice del DLC -> su RomFS
        String exefsProblem, romfsProblem;  // por qué no vale lo que se encontró (null: no había nada)
        String version;  // la versión del juego si su build está en Game.KNOWN_BUILDS (null: no probada)
        String versionNote;  // aviso para la pantalla (versión no probada) o null
        String metadataSize;  // tamaño esperado de Game.VERSION_FILE para esa versión (null: no se comprueba)
        int unknownDlc;  // RomFS de DLC sin su id de título en el nombre de ninguna carpeta

        boolean ready() {
            return exefs != null && romfs != null;
        }
    }

    // Id de título en un nombre de carpeta (las herramientas de extracción lo ponen: "... (0100…3001) (RomFS)").
    private static final Pattern TITLE_ID = Pattern.compile("(?i)(?<![0-9a-f])(01[0-9a-f]{14})(?![0-9a-f])");
    private static final int MAX_DEPTH = 8, MAX_DIRS = 50000;

    private final Result result = new Result();
    private int visited;

    static Result scan(File root) {
        DumpScanner scanner = new DumpScanner();
        scanner.visit(root, 0, -1);
        scanner.checkPair();
        return scanner.result;
    }

    // Versión conocida: la RomFS tiene que ser de la misma (en Unity el global-metadata.dat va con su ejecutable; mezclar
    // versiones cierra el juego al arrancar). Se mira el tamaño de Game.VERSION_FILE, que cambia con cada versión.
    private void checkPair() {
        Result r = result;
        if (r.exefs == null || r.romfs == null || r.metadataSize == null || Game.VERSION_FILE == null) return;
        long size = new File(r.romfs, Game.VERSION_FILE).length();
        if (size != Long.parseLong(r.metadataSize)) {
            r.romfsProblem = tr("La RomFS es de otra versión que el ExeFS (" + r.version + "): extrae las dos de la misma "
                    + "copia, con la misma actualización instalada.",
                    "The RomFS is from a different version than the ExeFS (" + r.version + "): extract both from the same "
                    + "copy, with the same update installed.");
            r.romfs = null;
        }
    }

    // ¿Está esta marca (un archivo, o una ruta relativa "carpeta/archivo") en la carpeta? names: lo que hay dentro.
    // Una marca sin "/" puede llevar comodines, ? (un carácter) y * (cualquier tramo): "bf3_dlc0?.arh" vale para la
    // RomFS de cada DLC aunque cada una traiga su número. Sin comodines es el nombre exacto, como siempre.
    private static boolean has(File dir, Set<String> names, String marker) {
        if (marker == null) return false;
        int slash = marker.indexOf('/');
        if (slash >= 0) return names.contains(marker.substring(0, slash)) && new File(dir, marker).isFile();
        if (marker.indexOf('?') < 0 && marker.indexOf('*') < 0) return names.contains(marker);
        Pattern glob = globPattern(marker);
        for (String name : names)
            if (glob.matcher(name).matches()) return true;
        return false;
    }

    // "bf3_dlc0?.arh" -> la expresión regular equivalente (el resto de caracteres, literales).
    static Pattern globPattern(String marker) {
        StringBuilder re = new StringBuilder();
        for (char c : marker.toCharArray())
            re.append(c == '?' ? "." : c == '*' ? ".*" : Pattern.quote(String.valueOf(c)));
        return Pattern.compile(re.toString());
    }

    // tid: el id de título del nombre de esta carpeta o de la más cercana de encima que tenga uno (-1: ninguna).
    private void visit(File dir, int depth, long tid) {
        if (depth > MAX_DEPTH || ++visited > MAX_DIRS) return;
        String[] names = dir.list();
        if (names == null) return;
        Matcher m = TITLE_ID.matcher(dir.getName());
        if (m.find()) tid = Long.parseLong(m.group(1), 16);
        Set<String> set = new HashSet<>(Arrays.asList(names));
        if (set.contains("main") && set.contains("main.npdm")) checkExefs(dir);
        if (has(dir, set, Game.ROMFS_MARKER)) {  // las RomFS no se recorren: miles de carpetas
            checkRomfs(dir, set);
            return;
        }
        if (has(dir, set, Game.DLC_MARKER)) {
            addDlc(dir, tid);
            return;
        }
        Arrays.sort(names);
        for (String name : names) {
            File sub = new File(dir, name);
            if (!name.startsWith(".") && sub.isDirectory()) visit(sub, depth + 1, tid);
        }
    }

    // El primer archivo de Game.EXEFS_EXTRA que no está en esa carpeta de ExeFS, o null si están todos.
    static String missingExefsFile(File dir) {
        if (Game.EXEFS_EXTRA == null) return null;
        for (String name : Game.EXEFS_EXTRA)
            if (!new File(dir, name).isFile()) return name;
        return null;
    }

    private void checkExefs(File dir) {
        if (result.exefs != null) return;
        byte[] npdm = read(new File(dir, "main.npdm"), 1 << 16), nso = read(new File(dir, "main"), 0x60);
        if (npdm == null || nso == null || npdm.length < 0x80 || nso.length < 0x60) return;
        if (!magic(npdm, 0, "META") || !magic(nso, 0, "NSO0")) {
            if (result.exefsProblem == null)
                result.exefsProblem = tr("El ExeFS de \"" + dir.getName() + "\" está cifrado o no es un ExeFS extraído.",
                        "The ExeFS in \"" + dir.getName() + "\" is encrypted or not an extracted ExeFS.");
            return;
        }
        // Otros archivos del ExeFS que este juego necesita además de main (Game.EXEFS_EXTRA: bibliotecas propias del
        // juego que la app carga tal cual; null en la mayoría).
        String missing = missingExefsFile(dir);
        if (missing != null) {
            if (result.exefsProblem == null)
                result.exefsProblem = tr("Al ExeFS de \"" + dir.getName() + "\" le falta el archivo " + missing
                                + ": copia la carpeta del ExeFS entera.",
                        "The ExeFS in \"" + dir.getName() + "\" is missing the file " + missing
                                + ": copy the whole ExeFS folder.");
            return;
        }
        int aci = (int) le(npdm, 0x70, 4);
        if (aci < 0 || aci + 0x18 > npdm.length || !magic(npdm, aci, "ACI0")) return;
        StringBuilder build = new StringBuilder();
        for (int k = 0x40; k < 0x54; k++) build.append(String.format("%02x", nso[k] & 0xff));
        if (le(npdm, aci + 0x10, 8) != Game.APP_ID) {
            if (result.exefsProblem == null)
                result.exefsProblem = tr("El ExeFS de \"" + dir.getName() + "\" es de otro juego.",
                        "The ExeFS in \"" + dir.getName() + "\" belongs to a different game.");
        } else {
            String[] known = null;
            for (String[] b : Game.KNOWN_BUILDS)
                if (build.toString().equals(b[0])) known = b;
            if (known == null && Game.STRICT_VERSION) {
                result.exefsProblem = tr("El ExeFS es de otra versión del juego: este port necesita la " + Game.VERSION
                        + ". Vuelve a extraerlo con la actualización " + Game.VERSION + " instalada.",
                        "The ExeFS is from a different game version: this port needs " + Game.VERSION
                        + ". Extract it again with update " + Game.VERSION + " installed.");
                return;
            }
            result.exefs = dir.getPath();
            result.exefsProblem = null;
            if (known != null) {
                result.version = known[1];
                result.metadataSize = known.length > 2 ? known[2] : null;
            } else {
                // Puertos sin parches por dirección: otra versión debería funcionar. Se avisa, no se bloquea.
                result.versionNote = tr("Versión no probada (build " + build.substring(0, 16) + "): debería funcionar; "
                        + "probado con la " + Game.VERSION + ". Si algo falla, dilo indicando tu versión.",
                        "Untested version (build " + build.substring(0, 16) + "): it should work; tested with "
                        + Game.VERSION + ". If something breaks, report it with your version.");
            }
        }
    }

    private void checkRomfs(File dir, Set<String> names) {
        if (result.romfs != null) return;
        if (Game.UPDATE_MARKER == null || has(dir, names, Game.UPDATE_MARKER)) {
            result.romfs = dir.getPath();
            result.romfsProblem = null;
        } else {
            result.romfsProblem = tr("La RomFS no trae la actualización: vuelve a extraerla con la actualización aplicada.",
                    "The RomFS does not include the update: extract it again with the update applied.");
        }
    }

    // El índice del DLC es su id menos el del juego con 0x1000 sumado (aoc.cpp). Sin id en el nombre vale también una
    // carpeta aoc/<índice>.
    private void addDlc(File dir, long tid) {
        long index = tid >= 0 ? tid - Game.APP_ID - 0x1000 : -1;
        File parent = dir.getParentFile();
        if ((index <= 0 || index >= 4096) && parent != null && parent.getName().equals("aoc")) {
            try {
                index = Integer.parseInt(dir.getName());
            } catch (NumberFormatException e) {
                index = -1;
            }
        }
        if (index > 0 && index < 4096) {
            result.dlc.putIfAbsent((int) index, dir.getPath());
        } else {
            result.unknownDlc++;
        }
    }

    static void writePaths(File data, Result r) throws IOException {
        File tmp = new File(data, "rutas.txt.tmp");
        try (FileWriter w = new FileWriter(tmp)) {
            w.write("# Written by the app's start screen: where each part of the game files is.\n");
            w.write("exefs=" + r.exefs + "\n");
            w.write("romfs=" + r.romfs + "\n");
            for (Map.Entry<Integer, String> e : r.dlc.entrySet()) w.write("aoc " + e.getKey() + "=" + e.getValue() + "\n");
        }
        if (!tmp.renameTo(new File(data, "rutas.txt"))) throw new IOException("cannot write rutas.txt in " + data);
    }

    // Lo que apuntó la última vez, si sigue en su sitio (null: hay que volver a buscar).
    static Result load(File data) {
        Result r = new Result();
        try (BufferedReader in = new BufferedReader(new FileReader(new File(data, "rutas.txt")))) {
            for (String line; (line = in.readLine()) != null; ) {
                int eq = line.indexOf('=');
                if (line.startsWith("#") || eq < 0) continue;
                String key = line.substring(0, eq), value = line.substring(eq + 1);
                if (key.equals("exefs")) r.exefs = value;
                else if (key.equals("romfs")) r.romfs = value;
                else if (key.startsWith("aoc ")) r.dlc.put(Integer.parseInt(key.substring(4)), value);
            }
        } catch (IOException | NumberFormatException e) {
            return null;
        }
        String romfsCheck = Game.UPDATE_MARKER != null ? Game.UPDATE_MARKER : Game.ROMFS_MARKER;
        boolean present = r.ready() && new File(r.exefs, "main").isFile() && new File(r.romfs, romfsCheck).isFile()
                && missingExefsFile(new File(r.exefs)) == null;
        if (!present) return null;
        // La versión, como al buscar: por el build ID del main (rutas.txt no la guarda). Sin esto la pantalla decía
        // "versión no probada" desde el segundo arranque también con una versión probada.
        byte[] nso = read(new File(r.exefs, "main"), 0x60);
        if (nso != null && nso.length >= 0x60) {
            StringBuilder build = new StringBuilder();
            for (int k = 0x40; k < 0x54; k++) build.append(String.format("%02x", nso[k] & 0xff));
            for (String[] b : Game.KNOWN_BUILDS)
                if (build.toString().equals(b[0])) r.version = b[1];
            if (r.version == null)
                r.versionNote = tr("Versión no probada (build " + build.substring(0, 16) + "): debería funcionar; "
                        + "probado con la " + Game.VERSION + ". Si algo falla, dilo indicando tu versión.",
                        "Untested version (build " + build.substring(0, 16) + "): it should work; tested with "
                        + Game.VERSION + ". If something breaks, report it with your version.");
        }
        return r;
    }

    private static byte[] read(File file, int max) {
        try (InputStream in = new FileInputStream(file)) {
            byte[] buf = new byte[max];
            int n = 0;
            for (int k; n < max && (k = in.read(buf, n, max - n)) > 0; ) n += k;
            return Arrays.copyOf(buf, n);
        } catch (IOException e) {
            return null;
        }
    }

    private static boolean magic(byte[] b, int at, String m) {
        for (int k = 0; k < 4; k++)
            if (b[at + k] != m.charAt(k)) return false;
        return true;
    }

    private static long le(byte[] b, int at, int size) {
        long v = 0;
        for (int k = size - 1; k >= 0; k--) v = (v << 8) | (b[at + k] & 0xff);
        return v;
    }

    public static void main(String[] args) {
        Result r = scan(new File(args[0]));
        System.out.println("exefs: " + r.exefs + (r.exefsProblem != null ? " — " + r.exefsProblem : "")
                + " versión: " + (r.version != null ? r.version : "no probada") + (r.versionNote != null ? " — " + r.versionNote : ""));
        System.out.println("romfs: " + r.romfs + (r.romfsProblem != null ? " — " + r.romfsProblem : ""));
        System.out.println("dlc: " + r.dlc.size() + (r.dlc.isEmpty() ? "" : " (" + r.dlc.firstKey() + ".." + r.dlc.lastKey() + ")")
                + ", unknown: " + r.unknownDlc + ", ready: " + r.ready());
    }
}
