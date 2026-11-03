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

/** E0/E1 experiment. This is not the terminal application or a package launcher. */
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
        layout.addView(scroll);
        setContentView(layout);
        run.setOnClickListener(view -> {
            run.setEnabled(false);
            new Thread(() -> {
                String report = runProof();
                runOnUiThread(() -> {
                    output.setText(report);
                    run.setEnabled(true);
                });
            }, "execution-proof").start();
        });
        if (getIntent().getBooleanExtra("run_proof", false)) run.performClick();
    }

    private String runProof() {
        File log = new File(getFilesDir(), "proof.log");
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
            File driver = new File(getApplicationInfo().nativeLibraryDir, "libtp-driver.so");
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
                + "\nE2/E3=NOT RUN\n";
            Files.write(log.toPath(), header.getBytes(StandardCharsets.UTF_8));
            ProcessBuilder builder = new ProcessBuilder(driver.getAbsolutePath());
            builder.directory(getFilesDir()).redirectErrorStream(true);
            builder.redirectOutput(ProcessBuilder.Redirect.appendTo(log));
            builder.environment().put("TP_PROOF_PREFIX", prefix.getAbsolutePath());
            builder.environment().put("TP_PROOF_LAUNCHER", launcher.getAbsolutePath());
            builder.environment().put("PATH", bin + ":/system/bin");
            child = builder.start();
            if (!child.waitFor(15, TimeUnit.SECONDS)) {
                stopDriver(child);
                result = "E0/E1=FAIL timeout";
            } else {
                result = child.exitValue() == 124 ? "E0/E1=FAIL per-case timeout"
                    : "E0/E1 candidate probes=" + (child.exitValue() == 0 ? "PASS" : "FAIL")
                        + " exit=" + child.exitValue() + " (matrix review still required)";
            }
        } catch (Exception error) {
            result = "E0/E1=FAIL " + error + "\nE2/E3=NOT RUN";
        } finally {
            try {
                if (child != null && child.isAlive()) stopDriver(child);
                if (runRoot != null) ProofFiles.deleteRun(runRoot);
            } catch (Exception cleanupError) {
                result = "E0/E1=FAIL cleanup " + cleanupError;
            }
        }
        try {
            Files.write(log.toPath(), (result + "\n").getBytes(StandardCharsets.UTF_8),
                java.nio.file.StandardOpenOption.CREATE, java.nio.file.StandardOpenOption.APPEND);
            return new String(Files.readAllBytes(log.toPath()), StandardCharsets.UTF_8);
        } catch (Exception error) {
            return result + "\nE0/E1=FAIL writing/reading proof.log: " + error;
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
