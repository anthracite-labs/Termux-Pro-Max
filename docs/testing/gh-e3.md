# Real GH → Git → SSH Android acceptance

**Status: NOT RUN.** The source build/static checks and a compiled test APK do not
establish Android E2, terminal acceptance or E3. Run the separate E2 proof and
terminal acceptance first. ADR-004 and release approval remain open.

`GhChainAcceptance` uses the installed source-built Bash, GH, Git and OpenSSH
programs. GH executes its normal `repo clone` command and resolves Git through
managed PATH; Git uses the registered SSH entry. A real disposable SSH server
serves a nonempty bare Git repository. Successful clone, the expected commit,
APK/bootstrap/package hashes and successful Git-to-managed-SSH trace are required.
No fake `gh`, `git`, `ssh` or echo-wrapper executable is used.

Only GitHub API **data** is stubbed. Upstream GH's `http_unix_socket` configuration
connects to an ADB-reversed abstract Unix socket; the host loopback HTTP fixture
answers one `RepositoryInfo` query with the lab SSH URL. The fake API token never
leaves that socket. No external account, production credentials, TLS bypass or
SSH host-key bypass is needed. The GH implementation is unchanged for this API
route. References at pinned GH `63837fb778d6a39f02be0ce76ff89f2bc8d74bdc`:
`pkg/cmd/repo/clone/clone.go`, `api/queries_repo.go`, and pinned go-gh v2.17.0
`pkg/api/http_client.go` / `client_options.go`.

## Disposable Linux SSH lab

Use an isolated Linux test host/container with host `git`, `ssh-keygen` and
`sshd`. These are test-host tools, not downloaded Android target packages. The
new SSH daemon must bind loopback only, use new keys, and force only this fixture's
`git-upload-pack`. Do not alter the host's system SSH service or reuse personal
keys. Depending on the lab image, starting this separate daemon may require its
normal privilege-separation setup; resolve that in the disposable lab.

From the repository root, create a fresh lab (never commit its keys):

```sh
mkdir -p -m 700 build/e3-labs
lab_dir=$(mktemp -d "$PWD/build/e3-labs/termux-e3-lab.XXXXXX")
ssh-keygen -q -t ed25519 -N '' -C termux-pro-e3-fixture -f "$lab_dir/id_ed25519"
ssh-keygen -q -t ed25519 -N '' -C termux-pro-e3-fixture-host -f "$lab_dir/host_key"
git init -b main "$lab_dir/work"
git -C "$lab_dir/work" -c user.name=E3 -c user.email=e3@example.invalid commit --allow-empty -m fixture
git clone --bare "$lab_dir/work" "$lab_dir/repo.git"
printf '[127.0.0.1]:38222 %s\n' "$(cut -d' ' -f1,2 "$lab_dir/host_key.pub")" > "$lab_dir/known_hosts"
cat > "$lab_dir/sshd_config" <<EOF
Port 38223
ListenAddress 127.0.0.1
HostKey $lab_dir/host_key
PidFile $lab_dir/sshd.pid
AuthorizedKeysFile $lab_dir/id_ed25519.pub
AllowUsers $(id -un)
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
AuthenticationMethods publickey
PermitRootLogin prohibit-password
AllowTcpForwarding no
AllowAgentForwarding no
X11Forwarding no
PermitTTY no
UsePAM no
StrictModes yes
ForceCommand $(command -v git-upload-pack) $lab_dir/repo.git
EOF
LAB_DIR="$lab_dir" python3 - <<'PY'
import json, os, pathlib, pwd, subprocess
p = pathlib.Path(os.environ['LAB_DIR'])
lab = {'ssh_host_port': 38223,
       'ssh_url': 'ssh://' + pwd.getpwuid(os.getuid()).pw_name + '@127.0.0.1:38222' + str(p / 'repo.git'),
       'expected_commit': subprocess.check_output(['git', '-C', str(p / 'work'), 'rev-parse', 'HEAD'], text=True).strip(),
       'key': str(p / 'id_ed25519'), 'known_hosts': str(p / 'known_hosts')}
(p / 'lab.json').write_text(json.dumps(lab, indent=2) + '\n')
print(p / 'lab.json')
PY
sshd -D -e -f "$lab_dir/sshd_config"
```

Keep that daemon running in its own lab terminal. With one authorized, enforcing
ARM64 Android device connected over ADB, run from another terminal:

```sh
python3 termux-pro-app/ci/run-gh-acceptance.py \
  termux-pro-app/app/build/outputs/apk/debug/app-debug.apk \
  termux-pro-app/app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk \
  /absolute/repository/build/e3-labs/termux-e3-lab.ACTUAL/lab.json
```

The runner verifies the APK's complete package closure, records APK/build identity,
installs both APKs, stages only disposable fixture keys in a unique app-private
directory, and sets two `--no-rebind` reverse mappings. It refuses to replace
existing mappings and removes only mappings it created. The instrumented test
uses an isolated HOME/config, pinned known_hosts, no agent, no password prompts,
and actual managed commands. Original app HOME is untouched.

Evidence is saved under `termux-pro-app/build/evidence/gh-device/<unique-run>/`:

- `environment.json`: APK/test hashes, matching bootstrap/build identity and expected command/manifest hashes, API/page size.
- `instrumentation.log`, `gh.log`, `git-trace.jsonl`, filtered `logcat.log`: actual runner and process output.
- `result.json`: installed command/manifest hashes, GH PID/exit, expected/actual commit, Android model/API/targetSdk/ABI/page size/fingerprint.
- `status.json`: starts NOT RUN and becomes PASS_THIS_DEVICE only after the instrumented clone and independent host evidence validation succeed. Failures remain UNVERIFIED, with raw logs retained.

The Python validator requires a Git clone trace whose managed SSH child and Git
parent both exited zero, as well as matching APK/package evidence. Stale results,
missing traces, failed SSH, wrong commits and foreign ABI are rejected by host
regressions. Those regression fixtures are policy tests, not device evidence.

Negative device probes remain required: stop the lab SSH server, change the
known-host key, remove SSH from an intentionally built negative fixture, and
attempt raw execution of the real writable target. None may produce a PASS.
Keep E2 and general terminal acceptance separate even after a successful E3 run.
Broader APIs/OEMs/16 KB, GH authentication/keyring/extensions/self-update, HTTPS,
credential-helper self-invocation and release security/policy remain separate gates.
