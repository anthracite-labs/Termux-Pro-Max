# Terminal renderer provenance

Only terminal-emulator Java and terminal-view Java/resources are reused from
termux/termux-app v0.118.3, commit 5b657c6adf4304e5198951ce815fe0205dcac29c.
Official archive SHA-256: a79a8ae388caab56d4d6df8f80aa213c21090e3a1f605c28d7f93fb466d6e7ca.
Upstream LICENSE.md explicitly identifies these libraries as Apache 2.0 exceptions;
see UPSTREAM-LICENSE.md and LICENSE-APACHE-2.0.txt. Original source notices remain.
The GPL app and termux-shared are not included.

Local changes: trailing whitespace removed from one cursor-controller line; standalone Gradle configuration/min API 30; JNI loads tp-pty;
TerminalSession uses public ParcelFileDescriptor-owned duplicated descriptors
instead of hidden FileDescriptor reflection, handles native startup failure and
guards process signaling against PID zero, reaps failed-start children and
skips native resize after process exit.
The original compile-only AndroidX annotation 1.3.0 is retained; it adds no
runtime Kotlin dependency. Native PTY implementation is our own.
Android rendering, keyboard, lifecycle and accessibility acceptance is pending.
