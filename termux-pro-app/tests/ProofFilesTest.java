package com.anthracitelabs.termuxpro;

import java.nio.file.Files;
import java.nio.file.Path;

public final class ProofFilesTest {
    public static void main(String[] args) throws Exception {
        Path files = Path.of(args[0]);
        Path packageEntry = files.resolve("usr/bin/gh");
        Files.createDirectories(packageEntry.getParent());
        Files.writeString(packageEntry, "existing package command");
        Path first = ProofFiles.createRun(files);
        Path second = ProofFiles.createRun(files);
        if (first.equals(second) || !first.getParent().equals(files.resolve("proof")))
            throw new AssertionError("Each run must own a distinct proof directory");
        for (Path run : new Path[] {first, second}) {
            Files.createDirectories(run.resolve("usr/bin"));
            Files.createSymbolicLink(run.resolve("usr/bin/gh"), packageEntry);
            Files.createSymbolicLink(run.resolve("usr/bin/unregistered"), packageEntry);
        }
        ProofFiles.deleteRun(first);
        if (Files.exists(first) || !Files.exists(second.resolve("usr/bin/gh")))
            throw new AssertionError("Cleanup must affect only its own run");
        ProofFiles.deleteRun(second);
        if (!Files.readString(packageEntry).equals("existing package command"))
            throw new AssertionError("Proof must preserve the real package tree");
        Path unexpected = ProofFiles.createRun(files);
        Files.writeString(unexpected.resolve("keep"), "diagnostic");
        try {
            ProofFiles.deleteRun(unexpected);
            throw new AssertionError("Cleanup must refuse unexpected contents");
        } catch (java.nio.file.DirectoryNotEmptyException expected) {
            if (!Files.readString(unexpected.resolve("keep")).equals("diagnostic"))
                throw new AssertionError("Unexpected files must remain intact");
        }
    }
}
