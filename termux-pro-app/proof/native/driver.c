#define _GNU_SOURCE
#include <errno.h>
#include <limits.h>
#include <spawn.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

extern char **environ;

static volatile sig_atomic_t interrupted;

static void stop(int signum) { interrupted = signum; }

static double now(void) {
    struct timespec time;
    if (clock_gettime(CLOCK_MONOTONIC, &time)) return -1;
    return time.tv_sec + time.tv_nsec / 1e9;
}

/* Each fixture owns a process group; kill descendants and reap the direct child. */
static int wait_case(pid_t pid, const char *name) {
    double start = now();
    int status = 0, error = start < 0, reaped = 0, timed_out = 0;
    while (!interrupted && !error) {
        pid_t result = waitpid(pid, &status, WNOHANG);
        if (result == pid) { reaped = 1; break; }
        if (result < 0 && errno != EINTR) { error = 1; break; }
        double current = now();
        if (current < 0) { error = 1; break; }
        if (current - start >= 1.0) { timed_out = 1; break; }
        struct timespec delay = {.tv_nsec = 10000000};
        nanosleep(&delay, NULL);
    }
    kill(-pid, SIGKILL);
    if (!reaped) {
        /* Also covers interruption before a forked child establishes its group. */
        kill(pid, SIGKILL);
        pid_t result;
        do { result = waitpid(pid, &status, 0); } while (result < 0 && errno == EINTR);
        if (result != pid) error = 1;
    }
    if (interrupted) {
        printf("case=%s interrupted=%d\n", name, interrupted);
        return 128 + interrupted;
    }
    if (timed_out) {
        printf("case=%s timeout=1\n", name);
        return 124;
    }
    if (error) return 70;
    return WIFEXITED(status) ? WEXITSTATUS(status) : 128 + WTERMSIG(status);
}

int main(void) {
    struct sigaction action = {.sa_handler = stop};
    sigemptyset(&action.sa_mask);
    if (sigaction(SIGTERM, &action, NULL) || sigaction(SIGINT, &action, NULL)) return 70;
    const char *prefix = getenv("TP_PROOF_PREFIX");
    const char *launcher = getenv("TP_PROOF_LAUNCHER");
    char entry[PATH_MAX], bin[PATH_MAX], unregistered[PATH_MAX];
    if (!prefix || !launcher) return 64;
    int n = snprintf(entry, sizeof(entry), "%s/bin/gh", prefix);
    if (n < 0 || (size_t)n >= sizeof(entry)) return 64;
    n = snprintf(bin, sizeof(bin), "%s/bin", prefix);
    if (n < 0 || (size_t)n >= sizeof(bin)) return 64;
    n = snprintf(unregistered, sizeof(unregistered), "%s/bin/unregistered", prefix);
    if (n < 0 || (size_t)n >= sizeof(unregistered)) return 64;
    const char *cases[] = {"protected", "execve", "execvp", "spawnp", "raw", "relative",
                           "unregistered", "bad-arguments"};
    int failures = 0;
    setbuf(stdout, NULL);
    for (int i = 0; i < 8; ++i) {
        if (interrupted) return 128 + interrupted;
        if (setenv("TP_PROOF_EXPECT_IDENTITY", i == 0 || i == 7 ? "protected" : "gh", 1))
            return 70;
        char *args[] = {"forged-git", "", "a b", "--", "日本語", "'quoted'", NULL};
        if (i == 7) args[1] = "changed";
        pid_t pid;
        if (i == 3) {
            posix_spawnattr_t attributes;
            int error = posix_spawnattr_init(&attributes);
            if (error) return 70;
            error = posix_spawnattr_setflags(&attributes, POSIX_SPAWN_SETPGROUP);
            if (!error) error = posix_spawnattr_setpgroup(&attributes, 0);
            if (!error) error = posix_spawnp(&pid, "gh", NULL, &attributes, args, environ);
            posix_spawnattr_destroy(&attributes);
            if (error) {
                printf("case=%s spawn_errno=%d\n", cases[i], error);
                ++failures;
                continue;
            }
        } else {
            pid = fork();
            if (pid == 0) {
                if (setpgid(0, 0)) _exit(70);
                switch (i) {
                    case 0: execve(launcher, args, environ); break;
                    case 1: execve(entry, args, environ); break;
                    case 2: execvp("gh", args); break;
                    case 4: syscall(SYS_execve, entry, args, environ); break;
                    case 5:
                        if (chdir(bin)) _exit(126);
                        execve("./gh", args, environ); break;
                    case 6: execve(unregistered, args, environ); break;
                    case 7: execve(launcher, args, environ); break;
                }
                fprintf(stderr, "case=%s exec_errno=%d\n", cases[i], errno);
                _exit(126);
            }
        }
        if (pid < 0) return 70;
        int code = wait_case(pid, cases[i]);
        if (code == 124 || interrupted) return code;
        int expected = i == 6 ? 64 : (i == 7 ? 65 : 0);
        printf("case=%s exit=%d expected=%d\n", cases[i], code, expected);
        if (code != expected) ++failures;
    }
    return failures ? 1 : 0;
}
