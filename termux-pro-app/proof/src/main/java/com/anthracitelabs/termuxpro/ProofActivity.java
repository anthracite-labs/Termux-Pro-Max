package com.anthracitelabs.termuxpro;

import android.app.Activity;
import android.os.Build;
import android.os.Bundle;
import android.system.Os;
import android.system.OsConstants;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.concurrent.TimeUnit;
import java.security.MessageDigest;

/** Separate execution experiments; not a terminal or production command registry. */
public final class ProofActivity extends Activity {
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        Button run = new Button(this);
        run.setText("Run execution proof");
        TextView output = new TextView(this);
        output.setTextIsSelectable(true);
        output.setText("E0/E1 NOT RUN. Runs with this app's UID, not adb shell's UID.");
        ScrollView scroll = new ScrollView(this);
        scroll.addView(output);
        layout.addView(run);
        Button e2 = new Button(this);
        e2.setText("Run E2 linker / PTY proof");
        layout.addView(e2);
        layout.addView(scroll);
        setContentView(layout);
        android.view.View.OnClickListener listener = view -> {
            run.setEnabled(false);
            e2.setEnabled(false);
            new Thread(() -> {
                String report = runProof(view == e2);
                runOnUiThread(() -> {
                    output.setText(report);
                    run.setEnabled(true);
                    e2.setEnabled(true);
                });
            }, "execution-proof").start();
        };
        run.setOnClickListener(listener);
        e2.setOnClickListener(listener);
        if (getIntent().getBooleanExtra("run_e2", false)) e2.performClick();
        else if (getIntent().getBooleanExtra("run_proof", false)) run.performClick();
    }

    private String runProof(boolean e2) {
        String gate = e2 ? "E2" : "E0/E1";
        File log = new File(getFilesDir(), e2 ? "e2-proof.log" : "proof.log");
        Process child = null;
        Path runRoot = null;
        String result = "E0/E1=FAIL incomplete";
        try {
            Files.write(log.toPath(), new byte[0]);
            runRoot = ProofFiles.createRun(getFilesDir().toPath());
            File prefix = runRoot.resolve("usr").toFile();
            File bin = new File(prefix, "bin");
            Files.createDirectories(bin.toPath());
            File launcher = new File(getApplicationInfo().nativeLibraryDir, "libtp-launcher.so");
            File driver = new File(getApplicationInfo().nativeLibraryDir, e2 ? "libtp-e2-driver.so" : "libtp-driver.so");
            File entry = new File(bin, "gh");
            Os.symlink(launcher.getAbsolutePath(), entry.getAbsolutePath());
            File unregistered = new File(bin, "unregistered");
            Os.symlink(launcher.getAbsolutePath(), unregistered.getAbsolutePath());
            String header = "APP_ID=" + getPackageName()
                + "\nAPI=" + Build.VERSION.SDK_INT + " targetSdk=" + getApplicationInfo().targetSdkVersion
                + "\nABIS=" + String.join(",", Build.SUPPORTED_ABIS)
                + "\npage_size=" + Os.sysconf(OsConstants._SC_PAGESIZE)
                + "\nfingerprint=" + Build.FINGERPRINT
                + "\nPREFIX=" + prefix + "\nnativeLibraryDir=" + launcher.getParent()
                + (e2 ? "\nE0/E1=NOT RUN in this E2 invocation\nE3=NOT RUN\n" : "\nE2/E3=NOT RUN\n");
            Files.write(log.toPath(), header.getBytes(StandardCharsets.UTF_8));
            ProcessBuilder builder = new ProcessBuilder(driver.getAbsolutePath());
            builder.directory(getFilesDir()).redirectErrorStream(true);
            builder.redirectOutput(ProcessBuilder.Redirect.appendTo(log));
            builder.environment().put("TP_PROOF_PREFIX", prefix.getAbsolutePath());
            builder.environment().put("TP_PROOF_LAUNCHER", launcher.getAbsolutePath());
            builder.environment().put("PATH", bin + ":/system/bin");
            if (e2) {
                Path target = prefix.toPath().resolve("libexec/tp-real/e2-target");
                Files.createDirectories(target.getParent());
                try (java.io.InputStream asset = getAssets().open("e2-target")) {
                    Files.copy(asset, target);
                }
                String wanted;
                try (java.io.InputStream digest = getAssets().open("e2-target.sha256")) {
                    wanted = new java.io.BufferedReader(new java.io.InputStreamReader(digest, StandardCharsets.UTF_8)).readLine();
                }
                byte[] bytes = MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(target));
                StringBuilder actual = new StringBuilder();
                for (byte value : bytes) actual.append(String.format(java.util.Locale.ROOT, "%02x", value & 255));
                if (!actual.toString().equals(wanted)) throw new IllegalStateException("E2 asset checksum mismatch");
                builder.environment().put("TP_E2_TARGET", target.toString());
                builder.environment().put("TP_E2_LAUNCHER", new File(getApplicationInfo().nativeLibraryDir, "libtp-e2-launcher.so").getAbsolutePath());
                builder.directory(runRoot.toFile());
            }
            child = builder.start();
            if (!child.waitFor(e2 ? 45 : 15, TimeUnit.SECONDS)) {
                stopDriver(child);
                result = gate + "=FAIL timeout";
            } else {
                result = child.exitValue() == 124 ? gate + "=FAIL per-case timeout"
                    : gate + " candidate probes=" + (child.exitValue() == 0 ? "PASS" : "FAIL")
                        + " exit=" + child.exitValue() + " (matrix review still required)";
            }
        } catch (Exception error) {
            result = gate + "=FAIL " + error + "\nE3=NOT RUN";
        } finally {
            try {
                if (child != null && child.isAlive()) stopDriver(child);
                if (runRoot != null) ProofFiles.deleteRun(runRoot);
            } catch (Exception cleanupError) {
                result = gate + "=FAIL cleanup " + cleanupError;
            }
        }
        try {
            Files.write(log.toPath(), (result + "\n").getBytes(StandardCharsets.UTF_8),
                java.nio.file.StandardOpenOption.CREATE, java.nio.file.StandardOpenOption.APPEND);
            return new String(Files.readAllBytes(log.toPath()), StandardCharsets.UTF_8);
        } catch (Exception error) {
            return result + "\n" + gate + "=FAIL writing/reading proof log: " + error;
        }
    }

    private static void stopDriver(Process child) throws InterruptedException {
        child.destroy(); // SIGTERM lets the driver kill its case group and reap the child.
        if (!child.waitFor(3, TimeUnit.SECONDS)) {
            child.destroyForcibly();
            if (!child.waitFor(3, TimeUnit.SECONDS))
                throw new IllegalStateException("Driver did not terminate");
        }
    }
}
