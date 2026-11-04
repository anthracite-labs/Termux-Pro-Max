package com.anthracitelabs.termuxpro.bootstrap;

import static com.anthracitelabs.termuxpro.bootstrap.StrictJson.check;
import java.io.IOException;
import java.io.InputStream;
import java.io.RandomAccessFile;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.zip.CRC32;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

/** Validates ZIP metadata omitted by java.util.zip, then bounds every read. */
public final class SafeZip implements AutoCloseable {
    public static final long MAX_BYTES = 512L * 1024 * 1024;
    public static final int MAX_FILES = 20000;
    public final Map<String, Entry> entries = new LinkedHashMap<>();
    private final ZipFile zip;
    public static final class Entry {
        public final String name;
        public final long size, crc;
        public final int mode;
        private Entry(String name, long size, long crc, int mode) {
            this.name = name; this.size = size; this.crc = crc; this.mode = mode;
        }
    }
    private static ByteBuffer header(RandomAccessFile file, long at, int size) throws IOException {
        check(at >= 0 && at <= file.length() - size, "ZIP header out of bounds");
        byte[] bytes = new byte[size]; file.seek(at); file.readFully(bytes);
        return ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN);
    }
    private static int u16(ByteBuffer b, int at) { return Short.toUnsignedInt(b.getShort(at)); }
    private static long u32(ByteBuffer b, int at) { return Integer.toUnsignedLong(b.getInt(at)); }
    public static String path(String name) {
        check(!name.isEmpty() && !name.startsWith("/") && !name.contains("\\"), "unsafe ZIP path");
        for (int i = 0; i < name.length(); i++) check(name.charAt(i) >= 32, "unsafe ZIP path");
        for (String part : name.split("/", -1)) check(!part.isEmpty() && !part.equals(".") && !part.equals(".."), "ZIP path traversal");
        return name;
    }
    public SafeZip(Path path) throws IOException {
        try (RandomAccessFile file = new RandomAccessFile(path.toFile(), "r")) {
            long length = file.length();
            check(length >= 22 && length <= MAX_BYTES, "ZIP size limit");
            ByteBuffer end = header(file, length - 22, 22);
            check(end.getInt(0) == 0x06054b50 && u16(end, 20) == 0, "ZIP comments/trailing data unsupported");
            check(u16(end, 4) == 0 && u16(end, 6) == 0 && u16(end, 8) == u16(end, 10), "split ZIP unsupported");
            int count = u16(end, 10);
            long central = u32(end, 16), cursor = central, total = 0;
            check(count > 0 && count <= MAX_FILES && central + u32(end, 12) == length - 22, "invalid ZIP directory");
            List<long[]> ranges = new ArrayList<>();
            for (int i = 0; i < count; i++) {
                ByteBuffer h = header(file, cursor, 46);
                check(h.getInt(0) == 0x02014b50, "invalid ZIP entry");
                int flags = u16(h, 8), method = u16(h, 10), nameSize = u16(h, 28);
                int mode = (int) (u32(h, 38) >>> 16);
                long size = u32(h, 24), packed = u32(h, 20), localAt = u32(h, 42), crc = u32(h, 16);
                check((flags & ~0x800) == 0 && (method == 0 || method == 8), "unsupported/encrypted ZIP entry");
                check(u16(h, 34) == 0 && size <= MAX_BYTES / 2 && packed <= MAX_BYTES, "ZIP entry size/disk limit");
                check((mode & 0170000) == 0 || (mode & 0170000) == 0100000, "special/symlink ZIP entry");
                byte[] nameBytes = header(file, cursor + 46, nameSize).array();
                String name = path(new String(nameBytes, StandardCharsets.UTF_8));
                check(java.util.Arrays.equals(nameBytes, name.getBytes(StandardCharsets.UTF_8)), "invalid ZIP UTF-8");
                check((flags & 0x800) != 0 || name.chars().allMatch(c -> c < 128), "ZIP filename encoding");
                check(!entries.containsKey(name), "duplicate ZIP entry");
                ByteBuffer local = header(file, localAt, 30);
                check(local.getInt(0) == 0x04034b50 && u16(local, 6) == flags && u16(local, 8) == method,
                      "ZIP local header mismatch");
                check(u32(local, 14) == crc && u32(local, 18) == packed && u32(local, 22) == size
                      && u16(local, 26) == nameSize, "ZIP local sizes mismatch");
                check(java.util.Arrays.equals(nameBytes, header(file, localAt + 30, nameSize).array()), "ZIP local name mismatch");
                long localEnd = localAt + 30 + nameSize + u16(local, 28) + packed;
                check(localEnd <= central, "ZIP entry overlaps directory");
                ranges.add(new long[]{localAt, localEnd});
                entries.put(name, new Entry(name, size, crc, mode & 07777));
                total += size; check(total <= MAX_BYTES, "ZIP decompression limit");
                cursor += 46L + nameSize + u16(h, 30) + u16(h, 32);
            }
            check(cursor == length - 22, "ZIP directory size mismatch");
            ranges.sort(Comparator.comparingLong(a -> a[0]));
            long previous = 0;
            for (long[] range : ranges) {
                check(range[0] == previous, "ZIP overlap/unlisted local data");
                previous = range[1];
            }
            check(previous == central, "ZIP unlisted local data");
        }
        zip = new ZipFile(path.toFile(), StandardCharsets.UTF_8);
    }
    public byte[] read(String name, long limit) throws IOException {
        Entry expected = entries.get(name);
        check(expected != null && expected.size <= limit, "missing/oversized ZIP member: " + name);
        ZipEntry entry = zip.getEntry(name);
        check(entry != null && entry.getSize() == expected.size, "ZIP member mismatch");
        // ZIP central-directory sizes are verified above. Allocate once: growing a
        // ByteArrayOutputStream then copying it doubles peak heap on large GH files.
        check(expected.size <= Integer.MAX_VALUE, "oversized ZIP member");
        byte[] output = new byte[(int) expected.size];
        CRC32 crc = new CRC32();
        try (InputStream input = zip.getInputStream(entry)) {
            int total = 0;
            while (total < output.length) {
                int n = input.read(output, total, output.length - total);
                check(n > 0, "ZIP member truncated");
                crc.update(output, total, n);
                total += n;
            }
            check(input.read() == -1, "ZIP decompression overflow");
            check(crc.getValue() == expected.crc, "ZIP size/CRC mismatch");
        }
        return output;
    }
    @Override public void close() throws IOException { zip.close(); }
}
