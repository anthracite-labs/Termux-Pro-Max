#define _GNU_SOURCE
#include <elf.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>
#include "tp_exec.h"

static volatile sig_atomic_t interrupted;
static void stop(int value) { interrupted = value; }

static double now(void) {
    struct timespec value;
    clock_gettime(CLOCK_MONOTONIC, &value);
    return value.tv_sec + value.tv_nsec / 1e9;
}

static int wait_child(pid_t pid) {
    double deadline = now() + 5;
    int status;
    for (;;) {
        pid_t result = waitpid(pid, &status, WNOHANG);
        if (result == pid) {
            kill(-pid, SIGKILL);
            return WIFEXITED(status) ? WEXITSTATUS(status) : 128 + WTERMSIG(status);
        }
        if (result < 0 && errno != EINTR) return 70;
        if (now() >= deadline || interrupted) {
            kill(-pid, SIGKILL); kill(pid, SIGKILL);
            while (waitpid(pid, &status, 0) < 0 && errno == EINTR) {}
            return interrupted ? 128 + interrupted : 124;
        }
        struct timespec delay = {.tv_nsec = 10000000};
        nanosleep(&delay, NULL);
    }
}

static void number_env(const char *name, int value) {
    char data[32];
    snprintf(data, sizeof(data), "%d", value);
    if (setenv(name, data, 1)) _exit(70);
}

static void reset_signals(void) {
    sigset_t mask;
    sigemptyset(&mask); sigprocmask(SIG_SETMASK, &mask, NULL);
    signal(SIGINT, SIG_DFL); signal(SIGTERM, SIG_DFL); signal(SIGHUP, SIG_DFL);
    signal(SIGQUIT, SIG_DFL); signal(SIGPIPE, SIG_DFL);
}

static int pipe_case(const char *launcher, const char *mode, const char *exit_value) {
    int input[2], inherited[2], ready[2];
    if (pipe(input) || pipe(inherited) || pipe(ready)) return 70;
    pid_t pid = fork();
    if (pid == 0) {
        if (setsid() < 0) _exit(70);
        reset_signals();
        number_env("TP_E2_PID", getpid()); number_env("TP_E2_FD", inherited[0]);
        number_env("TP_E2_READY", ready[1]);
        close(input[1]); close(inherited[1]); close(ready[0]);
        if (dup2(input[0], 0) < 0) _exit(70);
        close(input[0]);
        char *echo[] = {"forged-e2", "echo", "", "a b", "--", "日本語", "'quoted'", NULL};
        char *simple[] = {"forged-e2", (char *)mode, (char *)exit_value, NULL};
        execv(launcher, !strcmp(mode, "echo") ? echo : simple);
        perror("E2 launcher exec"); _exit(126);
    }
    close(input[0]); close(inherited[0]); close(ready[1]);
    if (pid < 0) return 70;
    (void)write(input[1], "stdin-ok", 8); close(input[1]);
    (void)write(inherited[1], "fd-ok", 5); close(inherited[1]);
    if (!strcmp(mode, "signal")) {
        struct pollfd descriptor = {.fd = ready[0], .events = POLLIN};
        char byte;
        if (poll(&descriptor, 1, 3000) != 1 || read(ready[0], &byte, 1) != 1 || byte != 'R') {
            kill(-pid, SIGKILL); kill(pid, SIGKILL); close(ready[0]);
            (void)wait_child(pid); return 124;
        }
        kill(-pid, SIGTERM);
    }
    close(ready[0]);
    return wait_child(pid);
}

static int wait_text(int fd, const char *expected) {
    char data[4096] = {0};
    size_t used = 0;
    double deadline = now() + 5;
    while (!interrupted && now() < deadline && used + 1 < sizeof(data)) {
        struct pollfd descriptor = {.fd = fd, .events = POLLIN};
        if (poll(&descriptor, 1, 100) <= 0) continue;
        ssize_t count = read(fd, data + used, sizeof(data) - used - 1);
        if (count <= 0) break;
        used += (size_t)count; data[used] = 0;
        if (strstr(data, expected)) { printf("%s", data); return 0; }
    }
    printf("E2 PTY output: %s\n", data);
    return -1;
}

static int pty_case(const char *launcher) {
    int master = posix_openpt(O_RDWR | O_CLOEXEC);
    char slave[128];
    if (master < 0 || grantpt(master) || unlockpt(master) || ptsname_r(master, slave, sizeof(slave))) return 70;
    pid_t pid = fork();
    if (pid == 0) {
        close(master);
        if (setsid() < 0) _exit(70);
        reset_signals();
        int fd = open(slave, O_RDWR);
        if (fd < 0 || ioctl(fd, TIOCSCTTY, 0) || tcsetpgrp(fd, getpgrp())) _exit(70);
        for (int i = 0; i < 3; ++i) if (dup2(fd, i) < 0) _exit(70);
        if (fd > 2) close(fd);
        number_env("TP_E2_PID", getpid());
        char *args[] = {"forged-e2", "pty", NULL};
        execv(launcher, args); _exit(126);
    }
    if (pid < 0) { close(master); return 70; }
    int ok = wait_text(master, "E2 PTY READY") == 0;
    struct winsize size = {.ws_row = 37, .ws_col = 103};
    if (ok && ioctl(master, TIOCSWINSZ, &size) == 0)
        ok = wait_text(master, "E2 resize rows=37 cols=103") == 0;
    else ok = 0;
    if (!ok || write(master, "\003", 1) != 1) { kill(-pid, SIGKILL); kill(pid, SIGKILL); }
    int result = wait_child(pid);
    close(master);
    return ok && result == 128 + SIGINT ? 0 : 1;
}

static int malformed(const char *target, const char *bad, int foreign) {
    if (tp_validate_elf(target)) return -1;
    int fd = open(target, O_RDONLY);
    struct stat st;
    if (fd < 0 || fstat(fd, &st) || st.st_size < 64 || st.st_size > 1024 * 1024) return -1;
    char *data = malloc((size_t)st.st_size);
    if (!data || read(fd, data, (size_t)st.st_size) != st.st_size) { close(fd); free(data); return -1; }
    close(fd);
    Elf64_Ehdr *header = (Elf64_Ehdr *)data;
    if (foreign) header->e_machine = EM_NONE;
    else for (int i = 0; i < header->e_phnum; ++i) {
        Elf64_Phdr *segment = (Elf64_Phdr *)(data + header->e_phoff + i * sizeof(Elf64_Phdr));
        if (segment->p_type == PT_INTERP) segment->p_type = PT_NULL;
    }
    fd = open(bad, O_WRONLY | O_CREAT | O_TRUNC | O_NOFOLLOW, 0600);
    int result = fd >= 0 && write(fd, data, (size_t)st.st_size) == st.st_size ? 0 : -1;
    if (fd >= 0) close(fd);
    free(data);
    return result;
}

int main(void) {
    setbuf(stdout, NULL);
    signal(SIGPIPE, SIG_IGN);
    struct sigaction action = {.sa_handler = stop};
    sigemptyset(&action.sa_mask);
    if (sigaction(SIGTERM, &action, NULL) || sigaction(SIGINT, &action, NULL)) return 70;
    const char *launcher = getenv("TP_E2_LAUNCHER"), *target = getenv("TP_E2_TARGET");
    char cwd[PATH_MAX], saved[PATH_MAX], bad[PATH_MAX];
    if (!launcher || !target || !getcwd(cwd, sizeof(cwd)) || strlen(target) + 9 >= sizeof(saved)) return 70;
    strcpy(saved, target); snprintf(bad, sizeof(bad), "%s.invalid", target);
    setenv("TP_E2_CWD", cwd, 1); setenv("TP_E2_TOKEN", "environment-sentinel", 1);
    int failures = 0;
    const char *names[] = {"echo", "exit-1", "exit-127", "sigterm", "static-reject", "wrong-abi", "pty-control"};
    const int expected[] = {0, 1, 127, 128 + SIGTERM, 126, 126, 0};
    for (int i = 0; i < 7; ++i) {
        if (interrupted) return 128 + interrupted;
        int result;
        if (i == 4 || i == 5) {
            if (malformed(saved, bad, i == 5)) return 70;
            setenv("TP_E2_TARGET", bad, 1);
            result = pipe_case(launcher, "exit", "0");
            setenv("TP_E2_TARGET", saved, 1); unlink(bad);
        } else if (i == 6) result = pty_case(launcher);
        else result = pipe_case(launcher, i == 0 ? "echo" : i == 3 ? "signal" : "exit", i == 1 ? "1" : i == 2 ? "127" : NULL);
        printf("e2case=%s exit=%d expected=%d\n", names[i], result, expected[i]);
        if (result != expected[i]) ++failures;
    }
    printf("E2 candidate probes=%s failures=%d; E3=NOT RUN\n", failures ? "FAIL" : "PASS", failures);
    return failures ? 1 : 0;
}
