#define _GNU_SOURCE
#include <errno.h>
#include <limits.h>
#include <spawn.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <unistd.h>

extern char **environ;

int main(void) {
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
        if (setenv("TP_PROOF_EXPECT_IDENTITY", i == 0 || i == 7 ? "protected" : "gh", 1))
            return 70;
        char *args[] = {"forged-git", "", "a b", "--", "日本語", "'quoted'", NULL};
        if (i == 7) args[1] = "changed";
        pid_t pid;
        if (i == 3) {
            int error = posix_spawnp(&pid, "gh", NULL, NULL, args, environ);
            if (error) {
                printf("case=%s spawn_errno=%d\n", cases[i], error);
                ++failures;
                continue;
            }
        } else {
            pid = fork();
            if (pid == 0) {
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
        int status;
        if (pid < 0 || waitpid(pid, &status, 0) < 0) return 70;
        int code = WIFEXITED(status) ? WEXITSTATUS(status) : 128 + WTERMSIG(status);
        int expected = i == 6 ? 64 : (i == 7 ? 65 : 0);
        printf("case=%s exit=%d expected=%d\n", cases[i], code, expected);
        if (code != expected) ++failures;
    }
    return failures ? 1 : 0;
}
