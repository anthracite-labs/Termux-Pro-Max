package com.anthracitelabs.termuxpro;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

/** Owns only the isolated, generated files of one execution experiment. */
final class ProofFiles {
    static Path createRun(Path files) throws IOException {
        Path proof = Files.createDirectories(files.resolve("proof"));
        return Files.createTempDirectory(proof, "run-");
    }

    static void deleteRun(Path run) throws IOException {
        // Delete only our known entries; never walk or follow fixture symlinks.
        for (String entry : new String[] {"usr/bin/gh", "usr/bin/unregistered", "usr/bin", "usr"})
            Files.deleteIfExists(run.resolve(entry));
        Files.delete(run);
    }
}
