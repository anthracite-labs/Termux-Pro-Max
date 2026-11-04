package com.anthracitelabs.termuxpro;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;
import android.content.Intent;
import android.os.SystemClock;
import android.util.Log;
import android.view.WindowInsets;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputConnection;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.Test;
import org.junit.runner.RunWith;

/** Real Android Activity, IME and bundled Bash acceptance. */
@RunWith(AndroidJUnit4.class)
public final class TerminalStartupSmoke {
    @Test public void activityDisplaysTerminalView() {
        var instrumentation = InstrumentationRegistry.getInstrumentation();
        var app = (TerminalApp) instrumentation.getTargetContext().getApplicationContext();
        var activity = (TerminalActivity) instrumentation.startActivitySync(
            new Intent(app, TerminalActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
        assertNotNull(activity.terminal);
        instrumentation.runOnMainSync(() -> assertTrue("Terminal view is not attached",
            activity.terminal.isAttachedToWindow()));
    }

    @Test public void keyboardAppearsAndImeTextExecutesInBash() throws Exception {
        var instrumentation = InstrumentationRegistry.getInstrumentation();
        var app = (TerminalApp) instrumentation.getTargetContext().getApplicationContext();
        var activity = (TerminalActivity) instrumentation.startActivitySync(
            new Intent(app, TerminalActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
        // startActivitySync does not guarantee foreground window focus. An emulator
        // with a system ANR dialog cannot display our keyboard, regardless of app code.
        AtomicBoolean windowFocused = new AtomicBoolean();
        long deadline = SystemClock.elapsedRealtime() + 20000;
        while (SystemClock.elapsedRealtime() < deadline) {
            instrumentation.runOnMainSync(() -> windowFocused.set(
                activity.terminal.isAttachedToWindow() && activity.getWindow().getDecorView().hasWindowFocus()));
            if (windowFocused.get()) break;
            Thread.sleep(100);
        }
        assertTrue("Android did not focus Termux Pro window (system ANR/overlay); IME test inconclusive",
            windowFocused.get());
        AtomicBoolean focused = new AtomicBoolean();
        instrumentation.runOnMainSync(() -> {
            assertTrue("Terminal must be focusable in touch mode", activity.terminal.isFocusableInTouchMode());
            activity.keyboard(); // Same path used by the KEYBOARD button and terminal tap.
            focused.set(activity.terminal.hasFocus());
        });
        assertTrue("Keyboard request did not focus terminal", focused.get());
        AtomicBoolean visible = new AtomicBoolean();
        deadline = SystemClock.elapsedRealtime() + 10000;
        while (SystemClock.elapsedRealtime() < deadline) {
            instrumentation.runOnMainSync(() -> {
                WindowInsets insets = activity.terminal.getRootWindowInsets();
                visible.set(insets != null && insets.isVisible(WindowInsets.Type.ime()));
            });
            if (visible.get()) break;
            Thread.sleep(100);
        }
        assertTrue("Keyboard request did not show the Android IME", visible.get());

        Log.i("TermuxProSmoke", "IME_VISIBLE; waiting for verified bundled Bash startup");
        AtomicBoolean bashReady = new AtomicBoolean();
        // ARM64 translated through a heavily loaded x86_64 emulator can take much
        // longer than a physical phone to validate/extract the ten-package ZIP.
        // Run 41831407333 timed out at 60s while BootstrapSetup was still in
        // BootstrapInstaller/SafeZip; keep this bound and all end-to-end asserts.
        deadline = SystemClock.elapsedRealtime() + 240000;
        while (SystemClock.elapsedRealtime() < deadline) {
            instrumentation.runOnMainSync(() -> bashReady.set(app.session != null &&
                app.session.getPid() > 0 && app.session.getEmulator() != null));
            if (bashReady.get()) break;
            Thread.sleep(100);
        }
        assertTrue("Bundled Bash did not start after a bounded 240s (preparing=" + app.preparing + ")", bashReady.get());
        Log.i("TermuxProSmoke", "BASH_READY; checking actual IME-to-command roundtrip");
        Path directory = app.getFilesDir().toPath().resolve("acceptance");
        Files.createDirectories(directory);
        Path marker = directory.resolve("ime-roundtrip.txt");
        Files.deleteIfExists(marker);
        String command = "printf 'IME_OK\\n' > '" + marker + "'\n";
        instrumentation.runOnMainSync(() -> {
            InputConnection input = activity.terminal.onCreateInputConnection(new EditorInfo());
            assertNotNull("Terminal has no IME input connection", input);
            assertTrue("IME rejected command", input.commitText(command, 1));
        });
        deadline = SystemClock.elapsedRealtime() + 10000;
        while (SystemClock.elapsedRealtime() < deadline && !Files.isRegularFile(marker)) Thread.sleep(100);
        assertTrue("IME text never reached bundled Bash", Files.isRegularFile(marker));
        assertEquals("IME_OK\n", new String(Files.readAllBytes(marker), StandardCharsets.UTF_8));
    }
}
