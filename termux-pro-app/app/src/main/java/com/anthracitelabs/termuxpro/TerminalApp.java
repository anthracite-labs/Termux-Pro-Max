package com.anthracitelabs.termuxpro;

import android.app.Application;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.os.Handler;
import android.os.Looper;
import android.system.Os;
import android.system.OsConstants;
import android.util.Log;
import android.view.KeyEvent;
import android.view.MotionEvent;
import com.anthracitelabs.termuxpro.bootstrap.BootstrapInstaller;
import com.anthracitelabs.termuxpro.bootstrap.PackageContract;
import com.termux.terminal.TerminalSession;
import com.termux.terminal.TerminalSessionClient;
import com.termux.view.TerminalViewClient;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.lang.ref.WeakReference;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.Map;

/** Session owner survives rotation without retaining an Activity. */
public final class TerminalApp extends Application implements TerminalSessionClient, TerminalViewClient {
    TerminalSession session;
    volatile boolean preparing;
    WeakReference<TerminalActivity> activity = new WeakReference<>(null);
    private final Handler main = new Handler(Looper.getMainLooper());
    private float fontSp = 14;
    int fontPixels() { return Math.round(fontSp * getResources().getDisplayMetrics().scaledDensity); }
    private byte[] asset(String name) throws Exception {
        try (InputStream input = getAssets().open(name); ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[16384]; int n;
            while ((n = input.read(buffer)) != -1) {
                if (output.size() + n > 4 * 1024 * 1024) throw new IllegalArgumentException("Oversized configuration asset");
                output.write(buffer, 0, n);
            }
            return output.toByteArray();
        }
    }
    void prepare(boolean repair) {
        if (preparing || (session != null && session.isRunning())) return;
        preparing = true;
        TerminalActivity current = activity.get(); if (current != null) current.showStatus(getString(R.string.preparing), false);
        new Thread(() -> {
            try {
                Path files = getFilesDir().toPath().toRealPath();
                Map<String, Object> target = PackageContract.json(asset("target.json"));
                String prefix = PackageContract.string(target.get("prefix"));
                if (!files.resolve("usr").toString().equals(prefix)) throw new IllegalArgumentException("This Android user/profile has a different private prefix");
                Path bundle = getCacheDir().toPath().resolve("bundled-bootstrap.zip");
                Files.deleteIfExists(bundle);
                try (InputStream input = getAssets().open("bootstrap.zip")) { Files.copy(input, bundle, StandardCopyOption.REPLACE_EXISTING); }
                String expected = new String(asset("bootstrap.sha256"), StandardCharsets.US_ASCII).trim();
                Path launcher = java.nio.file.Paths.get(getApplicationInfo().nativeLibraryDir, "libtp-launcher.so");
                new BootstrapInstaller(files).install(bundle, expected, launcher, target, repair);
                Files.deleteIfExists(bundle);
                Path home = files.resolve("home");
                if (Files.isSymbolicLink(home)) throw new IllegalArgumentException("HOME must be a private directory");
                Files.createDirectories(home);
                if (!Files.isDirectory(home, LinkOption.NOFOLLOW_LINKS)) throw new IllegalArgumentException("HOME is not a directory");
                String[] environment = {"HOME=" + home, "PREFIX=" + prefix, "PATH=" + prefix + "/bin:/system/bin",
                    "TMPDIR=" + prefix + "/tmp", "TERM=xterm-256color", "LANG=C.UTF-8", "COLORTERM=truecolor", "SHELL=" + prefix + "/bin/bash"};
                main.post(() -> {
                    preparing = false;
                    if (activity.get() == null) return;
                    session = new TerminalSession(launcher.toString(), home.toString(),
                        new String[]{launcher.toString(), "--tp-command", "bash", "--login", "-i"}, environment, 5000, this);
                    TerminalActivity ui = activity.get(); if (ui != null) ui.attach();
                });
            } catch (Exception error) {
                main.post(() -> {
                    preparing = false;
                    TerminalActivity ui = activity.get(); if (ui != null) ui.showStatus("Shell setup failed: " + error.getMessage(), true);
                });
            }
        }, "BootstrapSetup").start();
    }
    void send(String text) { if (session != null) session.write(text); }
    void closeSession() {
        TerminalSession closing = session;
        if (closing == null || closing.getPid() <= 0) return;
        try { Os.kill(closing.getPid(), OsConstants.SIGHUP); } catch (Exception ignored) {}
        main.postDelayed(() -> { if (closing.getPid() > 0) closing.finishIfRunning(); }, 1000);
    }
    @Override public void onTextChanged(TerminalSession changed) { TerminalActivity ui = activity.get(); if (ui != null) ui.terminal.onScreenUpdated(); }
    @Override public void onTitleChanged(TerminalSession changed) { TerminalActivity ui = activity.get(); if (ui != null) ui.setTitle(changed.getTitle()); }
    @Override public void onSessionFinished(TerminalSession changed) { TerminalActivity ui = activity.get(); if (ui != null) { ui.terminal.onScreenUpdated(); ui.finished(); } }
    @Override public void onCopyTextToClipboard(TerminalSession changed, String text) {
        if (activity.get() != null) ((ClipboardManager)getSystemService(CLIPBOARD_SERVICE)).setPrimaryClip(ClipData.newPlainText(getString(R.string.clipboard_label), text));
    }
    @Override public void onPasteTextFromClipboard(TerminalSession changed) {
        if (activity.get() == null || changed.getEmulator() == null) return;
        ClipData clip = ((ClipboardManager)getSystemService(CLIPBOARD_SERVICE)).getPrimaryClip();
        if (clip != null && clip.getItemCount() > 0) changed.getEmulator().paste(clip.getItemAt(0).coerceToText(this).toString());
    }
    @Override public void onBell(TerminalSession changed) {}
    @Override public void onColorsChanged(TerminalSession changed) { onTextChanged(changed); }
    @Override public void onTerminalCursorStateChange(boolean state) { TerminalActivity ui = activity.get(); if (ui != null) ui.terminal.invalidate(); }
    @Override public Integer getTerminalCursorStyle() { return 0; }
    @Override public float onScale(float scale) {
        fontSp = Math.max(8, Math.min(32, fontSp * scale));
        TerminalActivity ui = activity.get(); if (ui != null) ui.terminal.setTextSize(fontPixels()); return 1;
    }
    @Override public void onSingleTapUp(MotionEvent event) { TerminalActivity ui = activity.get(); if (ui != null) ui.keyboard(); }
    @Override public boolean shouldBackButtonBeMappedToEscape() { return false; }
    @Override public boolean shouldEnforceCharBasedInput() { return false; }
    @Override public boolean shouldUseCtrlSpaceWorkaround() { return false; }
    @Override public boolean isTerminalViewSelected() { return true; }
    @Override public void copyModeChanged(boolean selected) {}
    @Override public boolean onKeyDown(int code, KeyEvent event, TerminalSession changed) { return false; }
    @Override public boolean onKeyUp(int code, KeyEvent event) { return false; }
    @Override public boolean onLongPress(MotionEvent event) { return false; }
    @Override public boolean readControlKey() { return false; }
    @Override public boolean readAltKey() { return false; }
    @Override public boolean readShiftKey() { return false; }
    @Override public boolean readFnKey() { return false; }
    @Override public boolean onCodePoint(int code, boolean ctrl, TerminalSession changed) { return false; }
    @Override public void onEmulatorSet() {}
    @Override public void logError(String tag, String message) { Log.e(tag, message); }
    @Override public void logWarn(String tag, String message) { Log.w(tag, message); }
    @Override public void logInfo(String tag, String message) { Log.i(tag, message); }
    @Override public void logDebug(String tag, String message) {}
    @Override public void logVerbose(String tag, String message) {}
    @Override public void logStackTraceWithMessage(String tag, String message, Exception error) { Log.e(tag, message + ": " + error.getClass().getSimpleName()); }
    @Override public void logStackTrace(String tag, Exception error) { Log.e(tag, error.getClass().getSimpleName()); }
}
