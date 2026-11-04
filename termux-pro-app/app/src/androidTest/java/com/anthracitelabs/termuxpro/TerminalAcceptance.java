package com.anthracitelabs.termuxpro;

import static org.junit.Assert.*;
import android.content.Intent;
import android.os.Build;
import android.system.Os;
import android.system.OsConstants;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import com.termux.terminal.TerminalSession;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicReference;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;

/** Real installed APK + bundled source-built Bash. No emulator or synthetic PASS. */
@RunWith(AndroidJUnit4.class)
public final class TerminalAcceptance {
    private static final long TIMEOUT_MS = 90000;
    private final android.app.Instrumentation instrumentation = InstrumentationRegistry.getInstrumentation();
    private <T> T main(java.util.concurrent.Callable<T> action) {
        AtomicReference<T> result = new AtomicReference<>();
        AtomicReference<Exception> error = new AtomicReference<>();
        instrumentation.runOnMainSync(() -> { try { result.set(action.call()); } catch (Exception failure) { error.set(failure); } });
        if (error.get() != null) throw new AssertionError(error.get());
        return result.get();
    }
    private static String text(Path path) throws Exception { return new String(Files.readAllBytes(path), StandardCharsets.UTF_8); }
    private void await(java.util.concurrent.Callable<Boolean> condition, String message) throws Exception {
        long until = android.os.SystemClock.elapsedRealtime() + TIMEOUT_MS;
        while (android.os.SystemClock.elapsedRealtime() < until) {
            if (condition.call()) return;
            Thread.sleep(100);
        }
        fail(message);
    }
    private static int foreground(int shell) throws Exception {
        String stat = text(java.nio.file.Paths.get("/proc/" + shell + "/stat"));
        return Integer.parseInt(stat.substring(stat.lastIndexOf(')') + 2).split("\\s+")[5]);
    }
    @Test public void bundledBashManagedChildPtySignalsAndResize() throws Exception {
        TerminalApp app = (TerminalApp)instrumentation.getTargetContext().getApplicationContext();
        Path directory = app.getFilesDir().toPath().resolve("acceptance"); Files.createDirectories(directory);
        Path result = directory.resolve("terminal-result.json"); Files.deleteIfExists(result);
        Intent launch = new Intent(app, TerminalActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        instrumentation.startActivitySync(launch);
        await(() -> main(() -> app.session != null && app.session.getPid() > 0), "Bundled Bash did not start");
        TerminalSession shell = main(() -> app.session); int pid = main(shell::getPid);
        String token = UUID.randomUUID().toString();
        Path log = directory.resolve(token + ".log");
        String command = "[[ -t 0 && -t 1 && -t 2 ]]; tp_tty=$?; "
            + "{ printf 'bash=%s\\n' \"$BASH_VERSION\"; "
            + "printf 'tty=%d\\n' \"$tp_tty\"; "
            + "bash --noprofile --norc -c '[[ $# == 3 && $1 == \"\" && $2 == \"a b\" && $3 == \"日本語\" ]]' fixture '' 'a b' '日本語'; "
            + "printf 'managed-child=%d\\n' \"$?\"; "
            + "value=$(printf 'a b' | /system/bin/cat); [[ $value == 'a b' ]]; printf 'pipe=%d\\n' \"$?\"; "
            + "/system/bin/sleep 0.1 & wait $!; printf 'background-wait=%d\\n' \"$?\"; "
            + "printf 'done\\n'; } > '" + log + "'\n";
        main(() -> { shell.write(command); return null; });
        await(() -> Files.exists(log) && text(log).endsWith("done\n"), "Bash fixture did not finish");
        String output = text(log);
        assertTrue(output, output.startsWith("bash=5.2.37"));
        for (String expected : new String[]{"tty=0\n", "managed-child=0\n", "pipe=0\n", "background-wait=0\n"}) assertTrue(output, output.contains(expected));
        Path size = directory.resolve(token + ".size");
        main(() -> { shell.updateSize(103, 37, 8, 16); shell.write("/system/bin/stty size > '" + size + "'\n"); return null; });
        await(() -> Files.exists(size) && text(size).trim().equals("37 103"), "PTY resize was not reflected by stty");
        main(() -> { shell.write("/system/bin/sleep 30\n"); return null; });
        await(() -> { int group = foreground(pid); Path comm = java.nio.file.Paths.get("/proc/" + group + "/comm");
            return group != pid && Files.exists(comm) && text(comm).trim().equals("sleep"); }, "Foreground sleep did not start");
        main(() -> { shell.write("\003"); return null; });
        await(() -> foreground(pid) == pid, "Ctrl+C did not return the foreground terminal to Bash");
        Path control = directory.resolve(token + ".control");
        main(() -> { shell.write("printf 'interrupt=%d\\n' \"$?\" > '" + control + "'\n"); return null; });
        await(() -> Files.exists(control) && text(control).equals("interrupt=130\n"), "Ctrl+C status was not 130");
        main(() -> { shell.write("printf '\\033[31mTP-ANSI-日本語\\033[0m\\n'\n"); return null; });
        await(() -> main(() -> java.util.Arrays.stream(shell.getEmulator().getScreen().getTranscriptText().split("\n")).anyMatch(line -> line.trim().equals("TP-ANSI-日本語"))), "Unicode/ANSI output was not rendered");
        JSONObject record = new JSONObject();
        record.put("status", "PASS_THIS_DEVICE"); record.put("fixture", "bundled-bash-pty-v1");
        record.put("model", Build.MODEL); record.put("api", Build.VERSION.SDK_INT);
        record.put("target_sdk", app.getApplicationInfo().targetSdkVersion);
        record.put("abis", android.text.TextUtils.join(",", Build.SUPPORTED_ABIS));
        record.put("page_size", Os.sysconf(OsConstants._SC_PAGESIZE));
        record.put("checks", "bundled Bash, tty, managed child/args, pipe, background wait, resize, Ctrl+C, Unicode/ANSI");
        record.put("E2", "SEPARATE_PROOF_REQUIRED"); record.put("E3", "NOT RUN");
        main(() -> { app.closeSession(); return null; });
        await(() -> main(() -> shell.getPid() == -1), "Session did not close/reap");
        main(() -> { shell.updateSize(80, 24, 8, 16); return null; });
        record.put("closed_session_resize", "PASS");
        record.put("close_reap", "PASS");
        Files.write(result, (record.toString(2) + "\n").getBytes(StandardCharsets.UTF_8));
    }
}
