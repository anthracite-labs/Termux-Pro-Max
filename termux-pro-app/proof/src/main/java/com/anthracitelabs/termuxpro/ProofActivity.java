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
        try {
            File prefix = new File(getFilesDir(), "usr");
            File bin = new File(prefix, "bin");
            Files.createDirectories(bin.toPath());
            File launcher = new File(getApplicationInfo().nativeLibraryDir, "libtp-launcher.so");
            File driver = new File(getApplicationInfo().nativeLibraryDir, "libtp-driver.so");
            File entry = new File(bin, "gh");
            Files.deleteIfExists(entry.toPath());
            Os.symlink(launcher.getAbsolutePath(), entry.getAbsolutePath());
            File unregistered = new File(bin, "unregistered");
            Files.deleteIfExists(unregistered.toPath());
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
            String result;
            if (!child.waitFor(15, TimeUnit.SECONDS)) {
                child.destroyForcibly();
                result = "E0/E1=FAIL timeout";
            } else {
                result = "E0/E1 candidate probes=" + (child.exitValue() == 0 ? "PASS" : "FAIL")
                    + " exit=" + child.exitValue() + " (matrix review still required)";
            }
            Files.write(log.toPath(), (result + "\n").getBytes(StandardCharsets.UTF_8),
                java.nio.file.StandardOpenOption.APPEND);
            return new String(Files.readAllBytes(log.toPath()), StandardCharsets.UTF_8);
        } catch (Exception error) {
            String failure = "E0/E1=FAIL " + error + "\nE2/E3=NOT RUN";
            try {
                Files.write(log.toPath(), failure.getBytes(StandardCharsets.UTF_8),
                    java.nio.file.StandardOpenOption.CREATE, java.nio.file.StandardOpenOption.APPEND);
            } catch (Exception logError) {
                failure += "\nCannot write proof.log: " + logError;
            }
            return failure;
        } finally {
            if (child != null && child.isAlive()) child.destroyForcibly();
        }
    }
}
