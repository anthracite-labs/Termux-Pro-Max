package com.anthracitelabs.termuxpro;

import static org.junit.Assert.*;
import android.content.Intent;
import android.os.Build;
import android.os.Bundle;
import android.system.Os;
import android.system.OsConstants;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import com.anthracitelabs.termuxpro.bootstrap.PackageContract;
import com.termux.terminal.TerminalSession;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.attribute.PosixFilePermissions;
import java.util.concurrent.atomic.AtomicReference;
import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;

/** Real source-built GH -> Git -> SSH clone; requires the disposable host lab. NOT RUN by CI. */
@RunWith(AndroidJUnit4.class)
public final class GhChainAcceptance {
    private final android.app.Instrumentation instrumentation = InstrumentationRegistry.getInstrumentation();
    private <T> T main(java.util.concurrent.Callable<T> action) {
        AtomicReference<T> result = new AtomicReference<>(); AtomicReference<Exception> error = new AtomicReference<>();
        instrumentation.runOnMainSync(() -> { try { result.set(action.call()); } catch (Exception e) { error.set(e); } });
        if (error.get() != null) throw new AssertionError(error.get()); return result.get();
    }
    private void await(java.util.concurrent.Callable<Boolean> condition, String message) throws Exception {
        long end = android.os.SystemClock.elapsedRealtime() + 90000;
        while (android.os.SystemClock.elapsedRealtime() < end) {
            if (condition.call()) return; Thread.sleep(100);
        }
        fail(message);
    }
    private static String text(Path path) throws Exception { return new String(Files.readAllBytes(path), StandardCharsets.UTF_8); }
    private static String quote(String text) { return "'" + text.replace("'", "'\\''") + "'"; }
    private static JSONObject asset(TerminalApp app, String name) throws Exception {
        try (InputStream input = app.getAssets().open(name); ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192]; int size;
            while ((size = input.read(buffer)) != -1) { assertTrue(output.size() + size < 65536); output.write(buffer, 0, size); }
            return new JSONObject(output.toString("UTF-8"));
        }
    }
    @Test public void sourceBuiltGhGitSshClone() throws Exception {
        Bundle args = InstrumentationRegistry.getArguments();
        String run = args.getString("e3_run", ""); String socket = args.getString("e3_socket", "");
        String ssh = args.getString("e3_ssh_url", ""); String expected = args.getString("e3_expected_commit", "");
        assertTrue("Use ci/run-gh-acceptance.py with a disposable SSH lab", run.matches("[0-9a-f]{32}"));
        assertEquals("tp-gh-e3-" + run, socket);
        assertTrue(ssh.matches("ssh://[A-Za-z0-9_.-]+@127\\.0\\.0\\.1:[0-9]{1,5}/[A-Za-z0-9_./-]+"));
        assertTrue(expected.matches("[0-9a-f]{40}|[0-9a-f]{64}"));
        TerminalApp app = (TerminalApp)instrumentation.getTargetContext().getApplicationContext();
        Path files = app.getFilesDir().toPath(); Path directory = files.resolve("acceptance/gh-e3/" + run);
        assertTrue(Files.isRegularFile(directory.resolve("id_ed25519")));
        assertTrue(Files.isRegularFile(directory.resolve("known_hosts")));
        JSONObject target = asset(app, "target.json"); String prefix = target.getString("prefix");
        instrumentation.startActivitySync(new Intent(app, TerminalActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
        await(() -> main(() -> app.session != null && app.session.getPid() > 0), "Bundled terminal did not start");
        TerminalSession shell = main(() -> app.session);
        try {
            JSONObject commands = new JSONObject(), manifests = new JSONObject();
            String[] names = {"bash", "gh", "git", "ssh"}; String[] packages = {"bash", "gh", "git", "openssh"};
            for (int i = 0; i < names.length; i++) {
                byte[] manifestBytes = Files.readAllBytes(files.resolve("usr/var/lib/termux-pro/packages/" + packages[i] + ".json"));
                manifests.put(packages[i], PackageContract.hash(manifestBytes));
                JSONObject manifest = new JSONObject(new String(manifestBytes, StandardCharsets.UTF_8));
                String path = "libexec/tp-real/" + names[i]; String digest = PackageContract.hash(Files.readAllBytes(files.resolve("usr/" + path)));
                String declared = null; JSONArray inventory = manifest.getJSONArray("files");
                for (int j = 0; j < inventory.length(); j++) {
                    JSONObject file = inventory.getJSONObject(j);
                    if (path.equals(file.getString("path"))) declared = file.getString("sha256");
                }
                assertEquals("Installed source-built command hash", declared, digest); commands.put(names[i], digest);
            }
            Path home = directory.resolve("home"), config = directory.resolve("config");
            Files.createDirectories(home.resolve(".ssh")); Files.createDirectories(config);
            Files.write(config.resolve("config.yml"), ("git_protocol: ssh\nhttp_unix_socket: '@" + socket + "'\n").getBytes(StandardCharsets.UTF_8));
            String sshConfig = "Host 127.0.0.1\n  IdentityFile " + directory.resolve("id_ed25519")
                + "\n  UserKnownHostsFile " + directory.resolve("known_hosts")
                + "\n  IdentitiesOnly yes\n  IdentityAgent none\n  StrictHostKeyChecking yes\n  BatchMode yes\n  ConnectTimeout 10\n";
            Files.write(home.resolve(".ssh/config"), sshConfig.getBytes(StandardCharsets.UTF_8));
            Files.setPosixFilePermissions(home.resolve(".ssh/config"), PosixFilePermissions.fromString("rw-------"));
            Path clone = directory.resolve("clone"), done = directory.resolve("done"), exit = directory.resolve("exit"), commit = directory.resolve("commit");
            assertFalse("Each run needs a fresh clone", Files.exists(clone)); assertFalse(Files.exists(done));
            String command = "HOME=" + quote(home.toString()) + " GH_CONFIG_DIR=" + quote(config.toString())
                + " GH_HOST=e3.invalid GH_ENTERPRISE_TOKEN=fixture-not-a-production-credential GH_PROMPT_DISABLED=1"
                + " GH_NO_UPDATE_NOTIFIER=1 GH_NO_EXTENSION_UPDATE_NOTIFIER=1 DO_NOT_TRACK=1"
                + " GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null GIT_TERMINAL_PROMPT=0"
                + " GIT_SSH=" + quote(prefix + "/bin/ssh") + " GIT_SSH_VARIANT=ssh GIT_TRACE2_EVENT=" + quote(directory.resolve("git-trace.jsonl").toString())
                + " gh repo clone ssh://git@e3.invalid/e3/fixture " + quote(clone.toString())
                + " > " + quote(directory.resolve("gh.log").toString()) + " 2>&1 & tp_gh_pid=$!; wait \"$tp_gh_pid\"; tp_gh_exit=$?;"
                + " printf '%d\\n%d\\n' \"$tp_gh_pid\" \"$tp_gh_exit\" > " + quote(exit.toString())
                + "; if [[ $tp_gh_exit == 0 ]]; then git -C " + quote(clone.toString()) + " rev-parse HEAD > " + quote(commit.toString())
                + "; fi; printf 'done\\n' > " + quote(done.toString()) + "\n";
            main(() -> { shell.write(command); return null; });
            await(() -> Files.exists(done) && text(done).equals("done\n"), "GH clone timed out; collect raw gh.log and Git trace");
            String[] outcome = text(exit).trim().split("\n");
            assertEquals(text(directory.resolve("gh.log")), "0", outcome[1]);
            assertEquals(expected, text(commit).trim()); assertTrue(Files.size(directory.resolve("git-trace.jsonl")) > 0);
            JSONObject record = new JSONObject();
            record.put("status", "PASS_THIS_DEVICE"); record.put("fixture", "source-gh-git-ssh-clone-v1");
            record.put("run", run);
            record.put("build", asset(app, "build.json")); record.put("commands", commands); record.put("manifests", manifests);
            record.put("prefix", prefix); record.put("gh_pid", Integer.parseInt(outcome[0])); record.put("gh_exit", Integer.parseInt(outcome[1]));
            record.put("expected_commit", expected); record.put("actual_commit", text(commit).trim());
            record.put("api", Build.VERSION.SDK_INT); record.put("target_sdk", app.getApplicationInfo().targetSdkVersion);
            record.put("abi", Build.SUPPORTED_ABIS[0]); record.put("page_size", Os.sysconf(OsConstants._SC_PAGESIZE));
            record.put("model", Build.MODEL); record.put("android_fingerprint", Build.FINGERPRINT);
            Files.write(directory.resolve("result.json"), (record.toString(2) + "\n").getBytes(StandardCharsets.UTF_8));
        } finally { main(() -> { app.closeSession(); return null; }); }
    }
}
