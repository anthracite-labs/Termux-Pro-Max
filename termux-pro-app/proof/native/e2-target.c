#define _GNU_SOURCE
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <termios.h>
#include <unistd.h>

static volatile sig_atomic_t resized;
static void resize_signal(int signal) { (void)signal; resized = 1; }

int main(int argc, char **argv) {
    const char *pid = getenv("TP_E2_PID");
    if (!pid || atoi(pid) != getpid() || argc < 2) return 65;
    if (!strcmp(argv[1], "exit") && argc == 3) return atoi(argv[2]);
    if (!strcmp(argv[1], "echo")) {
        const char *expected[] = {"", "a b", "--", "日本語", "'quoted'"};
        if (argc != 7) return 65;
        for (int i = 2; i < argc; ++i) if (strcmp(argv[i], expected[i - 2])) return 65;
        char cwd[4096], data[32];
        const char *wanted_cwd = getenv("TP_E2_CWD");
        const char *token = getenv("TP_E2_TOKEN");
        const char *fd = getenv("TP_E2_FD");
        if (!wanted_cwd || !token || !fd || strcmp(token, "environment-sentinel")
            || !getcwd(cwd, sizeof(cwd)) || strcmp(cwd, wanted_cwd)
            || read(atoi(fd), data, sizeof(data)) != 5 || memcmp(data, "fd-ok", 5)
            || read(0, data, sizeof(data)) != 8 || memcmp(data, "stdin-ok", 8)) return 66;
        puts("E2 args/env/cwd/pid/fd/stdin=PASS");
        fputs("E2 stderr=preserved\n", stderr);
        return 0;
    }
    if (!strcmp(argv[1], "signal")) {
        const char *ready = getenv("TP_E2_READY");
        if (!ready || write(atoi(ready), "R", 1) != 1) return 67;
        for (;;) pause();
    }
    if (!strcmp(argv[1], "pty")) {
        if (!isatty(0) || !isatty(1) || !isatty(2) || tcgetpgrp(0) != getpgrp()) return 68;
        sigset_t resize_set, previous;
        sigemptyset(&resize_set); sigaddset(&resize_set, SIGWINCH);
        if (sigprocmask(SIG_BLOCK, &resize_set, &previous)) return 68;
        struct sigaction action = {.sa_handler = resize_signal};
        sigemptyset(&action.sa_mask);
        if (sigaction(SIGWINCH, &action, NULL)) return 68;
        puts("E2 PTY READY"); fflush(stdout);
        for (;;) {
            // Atomically unblock/wait: a resize delivered just after READY must not be lost.
            while (!resized) sigsuspend(&previous);
            if (resized) {
                resized = 0;
                struct winsize size;
                if (ioctl(0, TIOCGWINSZ, &size)) return 68;
                printf("E2 resize rows=%d cols=%d\n", size.ws_row, size.ws_col); fflush(stdout);
            }
        }
    }
    return 65;
}
