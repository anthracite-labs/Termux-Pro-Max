package com.anthracitelabs.termuxpro.bootstrap;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;

/** Runs the production Java consumer and transaction code without Android stubs. */
public final class BootstrapHost {
    public static void main(String[] args) throws Exception {
        Path input = Path.of(args[1]);
        Map<String, Object> target = PackageContract.json(Files.readAllBytes(Path.of(args[2])));
        switch (args[0]) {
            case "validate":
                PackageContract.Validated pkg = PackageContract.validate(input, target);
                PackageContract.dependencies(java.util.Collections.singletonList(pkg));
                break;
            case "closure":
                java.util.List<PackageContract.Validated> packages = new java.util.ArrayList<>();
                try (java.nio.file.DirectoryStream<Path> files = Files.newDirectoryStream(input, "*.tpkg")) {
                    for (Path file : files) packages.add(PackageContract.validate(file, target));
                }
                if (packages.isEmpty()) throw new IllegalArgumentException("No packages to verify");
                PackageContract.dependencies(packages);
                System.out.println("Android Java package consumer: PASS_STATIC closure=" + packages.size() + "; Android runtime NOT RUN");
                break;
            case "install":
                Path files = Path.of(args[3]);
                target.put("prefix", files.toRealPath().resolve("usr").toString());
                String stop = args.length > 5 ? args[5] : "";
                BootstrapInstaller installer = new BootstrapInstaller(files, point -> {
                    if (point.equals(stop)) Runtime.getRuntime().halt(77);
                });
                installer.install(input, PackageContract.hash(Files.readAllBytes(input)), Path.of(args[4]), target);
                break;
            case "recover":
                new BootstrapInstaller(input).recoverInterruptedInstall();
                break;
            case "json": StrictJson.read(Files.readString(input)); break;
            default: throw new IllegalArgumentException("unknown test command");
        }
    }
}
