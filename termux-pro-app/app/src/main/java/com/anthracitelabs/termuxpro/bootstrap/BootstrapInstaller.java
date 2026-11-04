package com.anthracitelabs.termuxpro.bootstrap;

import static com.anthracitelabs.termuxpro.bootstrap.StrictJson.check;
import static com.anthracitelabs.termuxpro.bootstrap.PackageContract.*;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.channels.FileChannel;
import java.nio.channels.FileLock;
import java.nio.charset.StandardCharsets;
import java.nio.file.FileVisitResult;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.SimpleFileVisitor;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.nio.file.attribute.BasicFileAttributes;
import java.nio.file.attribute.PosixFilePermissions;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.function.Consumer;

/** APK-bundled packages only. A prefix transaction never walks or deletes HOME. */
public final class BootstrapInstaller {
    private static final LinkOption[] NOFOLLOW = {LinkOption.NOFOLLOW_LINKS};
    private final Path root, prefix, stage, backup, cache, journal;
    private final Consumer<String> fault;
    public BootstrapInstaller(Path files) throws IOException { this(files, point -> {}); }
    BootstrapInstaller(Path files, Consumer<String> fault) throws IOException {
        root = files.toRealPath(); this.fault = fault;
        prefix = root.resolve("usr"); stage = root.resolve(".tp-stage");
        backup = root.resolve(".tp-backup"); cache = root.resolve(".tp-packages");
        journal = root.resolve("tp-install.journal");
    }
    private static boolean exists(Path path) { return Files.exists(path, NOFOLLOW); }
    private static void directory(Path path) {
        check(!Files.isSymbolicLink(path) && Files.isDirectory(path, NOFOLLOW), "unsafe runtime directory: " + path.getFileName());
    }
    private static void remove(Path path) throws IOException {
        if (!exists(path)) return;
        Files.walkFileTree(path, new SimpleFileVisitor<Path>() {
            @Override public FileVisitResult visitFile(Path file, BasicFileAttributes attributes) throws IOException {
                Files.delete(file); return FileVisitResult.CONTINUE;
            }
            @Override public FileVisitResult postVisitDirectory(Path folder, IOException error) throws IOException {
                if (error != null) throw error;
                Files.delete(folder); return FileVisitResult.CONTINUE;
            }
        });
    }
    private static void sync(Path directory) throws IOException {
        try (FileChannel channel = FileChannel.open(directory, StandardOpenOption.READ)) { channel.force(true); }
    }
    private static void write(Path path, byte[] bytes, String mode) throws IOException {
        Files.createDirectories(path.getParent());
        check(!exists(path), "staged path collision");
        try (FileOutputStream stream = new FileOutputStream(path.toFile())) {
            stream.write(bytes);
            Files.setPosixFilePermissions(path, PosixFilePermissions.fromString(mode));
            stream.getFD().sync();
        }
    }
    private void recover() throws IOException {
        if (exists(journal)) {
            check(!Files.isSymbolicLink(journal) && Files.isRegularFile(journal, NOFOLLOW) && Files.size(journal) < 64, "invalid install journal");
            String state = new String(Files.readAllBytes(journal), StandardCharsets.US_ASCII);
            check(state.equals("prepared old=true\n") || state.equals("prepared old=false\n"), "invalid install journal");
            if (exists(backup)) {
                directory(backup); remove(prefix);
                Files.move(backup, prefix, StandardCopyOption.ATOMIC_MOVE); sync(root);
            } else if (state.equals("prepared old=false\n")) {
                remove(prefix);
            } else if (exists(prefix)) directory(prefix);
            else throw new IOException("Interrupted install has no recoverable previous prefix");
            remove(stage); Files.delete(journal); sync(root);
        } else {
            if (exists(backup)) { directory(prefix); remove(backup); }
            remove(stage);
        }
        remove(cache);
    }
    private static Path managed(Path base, String relative) throws IOException {
        Path path = base;
        for (String part : relative.split("/")) {
            path = path.resolve(part);
            check(!Files.isSymbolicLink(path), "symlink in installed payload");
        }
        check(Files.isRegularFile(path, NOFOLLOW), "missing installed payload: " + relative);
        return path;
    }
    private boolean reuse(List<Validated> packages, String expectedHash, Path launcher) throws IOException {
        if (!exists(prefix)) return false;
        directory(prefix);
        Path marker = prefix.resolve("var/lib/termux-pro/bootstrap.sha256");
        if (!exists(marker)) return false;
        check(Files.size(managed(prefix, "var/lib/termux-pro/bootstrap.sha256")) < 128, "invalid bootstrap marker");
        if (!new String(Files.readAllBytes(marker), StandardCharsets.US_ASCII).equals(expectedHash + "\n")) return false;
        for (Validated pkg : packages) {
            for (Map.Entry<String, Map<String, Object>> file : pkg.files.entrySet()) {
                Path installed = managed(prefix, file.getKey());
                check(Files.size(installed) <= SafeZip.MAX_BYTES / 2 && hash(Files.readAllBytes(installed)).equals(file.getValue().get("sha256")),
                      "Installed payload is corrupt or modified; use Repair bootstrap (HOME is preserved)");
            }
            for (Map.Entry<String, String> command : pkg.commands.entrySet()) {
                Path registered = managed(prefix, "var/lib/termux-pro/commands/" + command.getKey());
                check(Files.size(registered) < 256 && new String(Files.readAllBytes(registered), StandardCharsets.US_ASCII).equals(command.getValue() + "\n"), "corrupt command registry; repair bootstrap");
                Path bin = prefix.resolve("bin"); directory(bin);
                Path link = bin.resolve(command.getKey());
                if (Files.isSymbolicLink(link) && Files.readSymbolicLink(link).equals(launcher)) continue;
                Path temporary = bin.resolve(".tp-link-" + command.getKey());
                Files.deleteIfExists(temporary); Files.createSymbolicLink(temporary, launcher);
                Files.move(temporary, link, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING); sync(bin);
            }
        }
        return true;
    }
    public void install(Path bootstrap, String expectedHash, Path launcher, Map<String, Object> target) throws IOException {
        install(bootstrap, expectedHash, launcher, target, false);
    }
    public void install(Path bootstrap, String expectedHash, Path launcher, Map<String, Object> target, boolean repair) throws IOException {
        check(root.resolve("usr").toString().equals(target.get("prefix")), "fixed prefix/user profile mismatch");
        check(!Files.isSymbolicLink(root.resolve("tp-install.lock")), "unsafe install lock");
        try (FileChannel channel = FileChannel.open(root.resolve("tp-install.lock"), StandardOpenOption.CREATE, StandardOpenOption.WRITE);
             FileLock lock = channel.tryLock()) {
            check(lock != null, "another bootstrap operation is active");
            recover();
            check(Files.size(bootstrap) <= SafeZip.MAX_BYTES, "bootstrap size limit");
            check(hash(Files.readAllBytes(bootstrap)).equals(digest(expectedHash)), "bootstrap checksum mismatch");
            Path protectedLauncher = launcher.toRealPath();
            check(Files.isRegularFile(protectedLauncher) && Files.isExecutable(protectedLauncher), "protected launcher unavailable");
            List<Validated> packages = new ArrayList<>();
            Files.createDirectory(cache);
            try (SafeZip zip = new SafeZip(bootstrap)) {
                Map<String, Object> index = json(zip.read("index.json", 4 * 1024 * 1024)); identity(index, target);
                Set<String> names = new HashSet<>(); names.add("index.json");
                Set<String> ids = new HashSet<>();
                for (Object raw : list(index.get("packages"))) {
                    Map<String, Object> item = object(raw);
                    String id = identifier(item.get("id")), path = SafeZip.path(string(item.get("path")));
                    check(path.matches("packages/[A-Za-z0-9+_.-]+\\.tpkg") && !path.contains("..") && names.add(path) && ids.add(id), "invalid/duplicate bootstrap package");
                    byte[] bytes = zip.read(path, SafeZip.MAX_BYTES / 2);
                    check(hash(bytes).equals(digest(item.get("sha256"))), "package archive checksum mismatch");
                    Path cached = cache.resolve(id + ".tpkg"); write(cached, bytes, "rw-------");
                    Validated pkg = validate(cached, target); check(pkg.id().equals(id), "bootstrap/package identity mismatch");
                    packages.add(pkg);
                }
                check(names.equals(zip.entries.keySet()) && !packages.isEmpty(), "bootstrap inventory mismatch");
            }
            dependencies(packages);
            if (!repair && reuse(packages, expectedHash, protectedLauncher)) { remove(cache); return; }
            // Existing payload must match the signed bundle before sessions may start.
            // A corrupt/update state is replaced as one transaction; HOME is a sibling.
            if (exists(prefix)) directory(prefix);
            Files.createDirectory(stage);
            StringBuilder ownership = new StringBuilder();
            for (Validated pkg : packages) {
                try (SafeZip zip = new SafeZip(pkg.archive)) {
                    for (Map.Entry<String, Map<String, Object>> file : pkg.files.entrySet()) {
                        byte[] bytes = zip.read("payload/" + file.getKey(), SafeZip.MAX_BYTES / 2);
                        check(hash(bytes).equals(file.getValue().get("sha256")), "staging checksum mismatch");
                        String mode = "0755".equals(file.getValue().get("mode")) ? "rwxr-xr-x" : "rw-r--r--";
                        write(stage.resolve(file.getKey()), bytes, mode);
                        ownership.append(file.getKey()).append('\t').append(pkg.id()).append('\n');
                    }
                    write(stage.resolve("var/lib/termux-pro/packages/" + pkg.id() + ".json"), zip.read("manifest.json", 4 * 1024 * 1024), "rw-------");
                }
                for (Map.Entry<String, String> command : pkg.commands.entrySet()) {
                    Path link = stage.resolve("bin/" + command.getKey()); Files.createDirectories(link.getParent());
                    Files.createSymbolicLink(link, protectedLauncher);
                    write(stage.resolve("var/lib/termux-pro/commands/" + command.getKey()),
                          (command.getValue() + "\n").getBytes(StandardCharsets.US_ASCII), "rw-------");
                }
            }
            Files.createDirectories(stage.resolve("tmp"));
            write(stage.resolve("var/lib/termux-pro/owners.tsv"), ownership.toString().getBytes(StandardCharsets.UTF_8), "rw-------");
            write(stage.resolve("var/lib/termux-pro/bootstrap.sha256"), (expectedHash + "\n").getBytes(StandardCharsets.US_ASCII), "rw-------");
            Files.walkFileTree(stage, new SimpleFileVisitor<Path>() {
                @Override public FileVisitResult postVisitDirectory(Path folder, IOException error) throws IOException {
                    if (error != null) throw error;
                    sync(folder); return FileVisitResult.CONTINUE;
                }
            });
            fault.accept("staged");
            boolean old = exists(prefix);
            write(journal, ("prepared old=" + old + "\n").getBytes(StandardCharsets.US_ASCII), "rw-------"); sync(root);
            fault.accept("prepared");
            if (old) { Files.move(prefix, backup, StandardCopyOption.ATOMIC_MOVE); sync(root); }
            fault.accept("old-moved");
            Files.move(stage, prefix, StandardCopyOption.ATOMIC_MOVE); sync(root);
            fault.accept("new-moved");
            Files.delete(journal); sync(root); // Durable commit point.
            fault.accept("committed");
            remove(backup); remove(cache); sync(root);
        }
    }
    /** Recover before any shell start; used by startup and crash-injection tests. */
    public void recoverInterruptedInstall() throws IOException {
        check(!Files.isSymbolicLink(root.resolve("tp-install.lock")), "unsafe install lock");
        try (FileChannel channel = FileChannel.open(root.resolve("tp-install.lock"), StandardOpenOption.CREATE, StandardOpenOption.WRITE);
             FileLock lock = channel.tryLock()) {
            check(lock != null, "another bootstrap operation is active"); recover();
        }
    }
}
