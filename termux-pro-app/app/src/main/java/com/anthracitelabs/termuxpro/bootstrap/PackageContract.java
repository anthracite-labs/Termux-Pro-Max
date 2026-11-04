package com.anthracitelabs.termuxpro.bootstrap;

import static com.anthracitelabs.termuxpro.bootstrap.StrictJson.check;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** Android consumer of shared/contract.py's native-only package v1 contract. */
public final class PackageContract {
    private PackageContract() {}
    @SuppressWarnings("unchecked") public static Map<String, Object> object(Object value) {
        check(value instanceof Map, "expected JSON object"); return (Map<String, Object>) value;
    }
    @SuppressWarnings("unchecked") public static List<Object> list(Object value) {
        check(value instanceof List, "expected JSON array"); return (List<Object>) value;
    }
    public static String string(Object value) { check(value instanceof String, "expected string"); return (String) value; }
    public static long integer(Object value) { check(value instanceof Long, "expected integer"); return (Long) value; }
    public static String hash(byte[] bytes) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(bytes);
            StringBuilder result = new StringBuilder();
            for (byte b : digest) result.append(String.format(java.util.Locale.ROOT, "%02x", b & 255));
            return result.toString();
        } catch (NoSuchAlgorithmException error) { throw new AssertionError(error); }
    }
    public static Map<String, Object> json(byte[] bytes) {
        String text = new String(bytes, StandardCharsets.UTF_8);
        check(Arrays.equals(bytes, text.getBytes(StandardCharsets.UTF_8)), "invalid JSON UTF-8");
        return object(StrictJson.read(text));
    }
    public static String identifier(Object value) {
        String name = string(value);
        check(name.matches("[A-Za-z0-9][A-Za-z0-9+_.-]{0,63}") && !name.contains(".."), "invalid identifier");
        return name;
    }
    public static String digest(Object value) {
        String text = string(value); check(text.matches("[0-9a-f]{64}"), "invalid SHA-256"); return text;
    }
    private static boolean contains(byte[] data, byte[] pattern) {
        for (int i = 0; i <= data.length - pattern.length; i++) {
            if (data[i] != pattern[0]) continue;
            int j = 1;
            while (j < pattern.length && data[i + j] == pattern[j]) j++;
            if (j == pattern.length) return true;
        }
        return false;
    }
    public static String payloadPath(Object value) {
        String name = SafeZip.path(string(value));
        check(name.startsWith("lib/") || name.startsWith("libexec/") || name.startsWith("share/") || name.startsWith("etc/"), "unmanaged payload root");
        return name;
    }
    public static void identity(Map<String, Object> manifest, Map<String, Object> target) {
        check(integer(manifest.get("schema")) == 1, "unsupported schema");
        for (String field : new String[]{"abi", "prefix", "min_android_api"})
            check(target.get(field).equals(manifest.get(field)), field + " mismatch");
        check(target.get("application_id").equals(manifest.get("app_id")), "app_id mismatch");
    }
    public static final class Validated {
        public final Path archive;
        public final Map<String, Object> manifest;
        public final Map<String, Map<String, Object>> files = new LinkedHashMap<>();
        public final Map<String, String> commands = new LinkedHashMap<>();
        public final Set<String> dependencies = new HashSet<>(), needed = new HashSet<>(), libraries = new HashSet<>();
        private Validated(Path archive, Map<String, Object> manifest) { this.archive = archive; this.manifest = manifest; }
        public String id() { return string(manifest.get("id")); }
    }
    public static Validated validate(Path path, Map<String, Object> target) throws IOException {
        try (SafeZip zip = new SafeZip(path)) {
            Map<String, Object> manifest = json(zip.read("manifest.json", 4 * 1024 * 1024));
            identity(manifest, target); identifier(manifest.get("id")); identifier(manifest.get("version"));
            check(integer(manifest.get("revision")) > 0, "invalid revision");
            Map<String, Object> source = object(manifest.get("source"));
            check(string(source.get("upstream")).startsWith("https://"), "source HTTPS required");
            String revision = string(source.get("revision")); digest(source.get("sha256"));
            check(!revision.isEmpty() && !Arrays.asList("main", "master", "HEAD", "latest").contains(revision), "source must be pinned");
            List<Object> licenses = list(manifest.get("licenses")); check(!licenses.isEmpty(), "missing licenses");
            for (Object license : licenses) check(!string(license).isEmpty(), "missing license");
            Validated result = new Validated(path, manifest);
            for (Object dependency : list(manifest.get("dependencies"))) {
                String id = identifier(dependency);
                check(!id.equals(result.id()) && result.dependencies.add(id), "duplicate/self dependency");
            }
            Set<String> names = new HashSet<>(); names.add("manifest.json");
            for (Object raw : list(manifest.get("files"))) {
                Map<String, Object> item = object(raw);
                check(item.keySet().equals(new HashSet<>(Arrays.asList("path", "sha256", "mode"))), "invalid file entry");
                String name = payloadPath(item.get("path")); digest(item.get("sha256"));
                String mode = string(item.get("mode")); check(mode.equals("0644") || mode.equals("0755"), "invalid file mode");
                check(result.files.put(name, item) == null, "duplicate inventory path");
                names.add("payload/" + name);
            }
            check(names.equals(zip.entries.keySet()), "archive/inventory mismatch");
            for (Object raw : list(manifest.get("commands"))) {
                Map<String, Object> command = object(raw);
                check(command.keySet().equals(new HashSet<>(Arrays.asList("name", "kind", "target"))), "invalid command entry");
                String name = identifier(command.get("name")), real = string(command.get("target"));
                check("elf".equals(command.get("kind")) && real.equals("libexec/tp-real/" + name) && result.files.containsKey(real), "unsupported command target/kind");
                check(result.commands.put(name, real) == null, "duplicate command");
            }
            for (Map.Entry<String, Map<String, Object>> file : result.files.entrySet()) {
                String name = file.getKey(); String entryName = "payload/" + name;
                byte[] data = zip.read(entryName, SafeZip.MAX_BYTES / 2);
                check(hash(data).equals(file.getValue().get("sha256")), "payload checksum mismatch: " + name);
                int mode = zip.entries.get(entryName).mode;
                check(mode == 0 || mode == Integer.parseInt(string(file.getValue().get("mode")), 8), "payload mode mismatch");
                // A full ISO-8859-1 String duplicates multi-megabyte binaries and can
                // exhaust Android's 192 MiB heap. Compare ASCII byte sequences directly.
                for (String bad : new String[]{"/data/data/com.termux/", "/data/user/0/com.termux/", "/workspace/"})
                    check(!contains(data, bad.getBytes(StandardCharsets.US_ASCII)), "foreign/host path in " + name);
                boolean command = result.commands.containsValue(name);
                if (command || (data.length >= 4 && data[0] == 127 && data[1] == 'E' && data[2] == 'L' && data[3] == 'F'))
                    result.needed.addAll(elf(data, command, string(target.get("prefix"))));
                if (name.startsWith("lib/") && name.indexOf('/', 4) < 0 && data.length >= 4
                    && data[0] == 127 && data[1] == 'E' && data[2] == 'L' && data[3] == 'F')
                    result.libraries.add(name.substring(4));
            }
            return result;
        }
    }
    public static void dependencies(List<Validated> packages) {
        Map<String, Validated> byId = new LinkedHashMap<>();
        Set<String> files = new HashSet<>(), commands = new HashSet<>();
        for (Validated pkg : packages) {
            check(byId.put(pkg.id(), pkg) == null, "duplicate package");
            for (String file : pkg.files.keySet()) check(files.add(file), "cross-package file collision");
            for (String cmd : pkg.commands.keySet()) check(commands.add(cmd), "cross-package command collision");
        }
        for (Validated pkg : packages) {
            Set<String> libs = new HashSet<>(Arrays.asList("libc.so", "libm.so", "libdl.so", "liblog.so", "libandroid.so"));
            libs.addAll(pkg.libraries);
            Set<String> visited = new HashSet<>();
            collect(pkg, byId, new HashSet<>(), visited, libs);
            check(libs.containsAll(pkg.needed), "missing DT_NEEDED for " + pkg.id());
        }
    }
    private static void collect(Validated pkg, Map<String, Validated> packages, Set<String> active, Set<String> visited, Set<String> libraries) {
        check(active.add(pkg.id()), "dependency cycle");
        for (String dep : pkg.dependencies) {
            Validated other = packages.get(dep); check(other != null, "missing declared dependency: " + dep);
            libraries.addAll(other.libraries);
            if (!visited.contains(dep)) collect(other, packages, active, visited, libraries);
        }
        active.remove(pkg.id()); visited.add(pkg.id());
    }
    private static long positive(long value) { check(value >= 0, "ELF integer overflow"); return value; }
    private static long u32(ByteBuffer bytes, int at) { return Integer.toUnsignedLong(bytes.getInt(at)); }
    private static String elfString(byte[] table, long offset) {
        check(offset >= 0 && offset < table.length, "invalid ELF string");
        int end = (int) offset;
        while (end < table.length && table[end] != 0) end++;
        check(end < table.length, "unterminated ELF string");
        return new String(table, (int) offset, end - (int) offset, StandardCharsets.UTF_8);
    }
    private static Set<String> elf(byte[] data, boolean executable, String prefix) {
        check(data.length >= 64 && data[0] == 127 && data[1] == 'E' && data[2] == 'L' && data[3] == 'F'
              && data[4] == 2 && data[5] == 1 && data[6] == 1, "expected ELF64 little-endian");
        ByteBuffer bytes = ByteBuffer.wrap(data).order(ByteOrder.LITTLE_ENDIAN);
        check(bytes.getShort(16) == 3 && bytes.getShort(18) == 183, "expected AArch64 ET_DYN");
        long entry = positive(bytes.getLong(24)), ph = positive(bytes.getLong(32));
        int count = Short.toUnsignedInt(bytes.getShort(56));
        check(bytes.getShort(54) == 56 && count > 0 && count <= 128 && ph <= data.length - count * 56L, "invalid ELF program headers");
        List<long[]> loads = new ArrayList<>(); List<long[]> tags = new ArrayList<>();
        byte[] dynamic = null, interpreter = null;
        for (int i = 0; i < count; i++) {
            int at = (int) ph + i * 56, tag = bytes.getInt(at), flags = bytes.getInt(at + 4);
            long offset = positive(bytes.getLong(at + 8)), address = positive(bytes.getLong(at + 16));
            long size = positive(bytes.getLong(at + 32)), memory = positive(bytes.getLong(at + 40)), alignment = positive(bytes.getLong(at + 48));
            check(size <= data.length && offset <= data.length - size && memory >= size, "invalid ELF segment bounds");
            if (tag == 1) {
                check(alignment >= 16384 && (alignment & (alignment - 1)) == 0 && (offset - address) % 16384 == 0 && (flags & 3) != 3, "invalid ELF 16 KB/WX segment");
                loads.add(new long[]{offset, address, size, memory, flags});
            } else if (tag == 2) {
                check(dynamic == null && size % 16 == 0, "invalid dynamic segment");
                dynamic = Arrays.copyOfRange(data, (int) offset, (int) (offset + size));
            } else if (tag == 3) {
                check(interpreter == null, "duplicate ELF interpreter");
                interpreter = Arrays.copyOfRange(data, (int) offset, (int) (offset + size));
            }
        }
        check(!loads.isEmpty() && dynamic != null, "static ELF unsupported");
        if (executable) {
            check(Arrays.equals(interpreter, "/system/bin/linker64\0".getBytes(StandardCharsets.US_ASCII)), "unsupported interpreter");
            boolean validEntry = false;
            for (long[] load : loads) if (entry > 0 && entry >= load[1] && entry - load[1] < load[3] && (load[4] & 1) != 0) validEntry = true;
            check(validEntry, "missing executable entry");
        }
        ByteBuffer dyn = ByteBuffer.wrap(dynamic).order(ByteOrder.LITTLE_ENDIAN);
        long stringsAt = -1, stringsSize = -1;
        for (int at = 0; at < dynamic.length; at += 16) {
            long tag = dyn.getLong(at), value = positive(dyn.getLong(at + 8));
            if (tag == 0) break;
            check(tag != 22 && !(tag == 30 && (value & 4) != 0), "ELF text relocations unsupported");
            tags.add(new long[]{tag, value});
            if (tag == 5) stringsAt = value;
            if (tag == 10) stringsSize = value;
        }
        byte[] table = null;
        for (long[] load : loads) {
            long delta = stringsAt - load[1];
            if (stringsAt >= 0 && stringsSize >= 0 && delta >= 0 && delta <= load[2] && stringsSize <= load[2] - delta) {
                int start = (int) (load[0] + delta);
                table = Arrays.copyOfRange(data, start, start + (int) stringsSize); break;
            }
        }
        check(table != null, "missing ELF string table");
        Set<String> needed = new HashSet<>();
        for (long[] tag : tags) {
            if (tag[0] == 1) { String name = elfString(table, tag[1]); check(!name.contains("/"), "absolute DT_NEEDED"); needed.add(name); }
            if (tag[0] == 15 || tag[0] == 29)
                for (String part : elfString(table, tag[1]).split(":", -1)) check(part.equals(prefix + "/lib"), "unsupported RUNPATH");
        }
        return needed;
    }
}
