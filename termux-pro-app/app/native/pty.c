#define _GNU_SOURCE
#include "pty.h"
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <poll.h>
#include <signal.h>
#include <stdlib.h>
#include <sys/ioctl.h>
#include <sys/resource.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <termios.h>
#include <unistd.h>

int tp_pty_resize(int fd, int rows, int columns, int cell_width, int cell_height) {
    if (rows < 1 || rows > 2000 || columns < 1 || columns > 2000
        || cell_width < 0 || cell_width > 1000 || cell_height < 0 || cell_height > 1000) {
        errno = EINVAL; return -1;
    }
    struct winsize size = {.ws_row = (unsigned short)rows, .ws_col = (unsigned short)columns,
        .ws_xpixel = (unsigned short)(columns * cell_width > USHRT_MAX ? 0 : columns * cell_width),
        .ws_ypixel = (unsigned short)(rows * cell_height > USHRT_MAX ? 0 : rows * cell_height)};
    return ioctl(fd, TIOCSWINSZ, &size);
}
static int above_stdio(int fd) {
    if (fd < 0 || fd > 2) return fd;
    int duplicate = fcntl(fd, F_DUPFD_CLOEXEC, 3);
    int error = errno; close(fd); errno = error; return duplicate;
}
static void child_error(int fd) {
    int error = errno;
    ssize_t ignored = write(fd, &error, sizeof(error)); (void)ignored;
    _exit(126);
}
static void close_inherited(int keep, rlim_t limit) {
#ifdef __NR_close_range
    int first = keep <= 3 ? 0 : (int)syscall(__NR_close_range, 3u, (unsigned int)keep - 1u, 0u);
    int last = (int)syscall(__NR_close_range, (unsigned int)keep + 1u, ~0u, 0u);
    if (!first && !last) return;
#endif
    for (int fd = 3; (rlim_t)fd < limit; fd++) if (fd != keep) close(fd);
}
int tp_pty_start(const char *command, const char *cwd, char *const args[], char *const env[],
                 pid_t *pid, int rows, int columns, int cell_width, int cell_height) {
    int master = -1, slave = -1, errors[2] = {-1, -1}, saved;
    char name[PATH_MAX]; struct rlimit limit;
    if (getrlimit(RLIMIT_NOFILE, &limit) || limit.rlim_cur > INT_MAX) { errno = EINVAL; return -1; }
    master = above_stdio(posix_openpt(O_RDWR | O_NOCTTY | O_CLOEXEC));
    if (master < 0 || grantpt(master) || unlockpt(master) || ptsname_r(master, name, sizeof(name))) goto fail;
    slave = above_stdio(open(name, O_RDWR | O_NOCTTY | O_CLOEXEC));
    if (slave < 0 || tp_pty_resize(slave, rows, columns, cell_width, cell_height)) goto fail;
    struct termios tty;
    if (tcgetattr(slave, &tty)) goto fail;
    tty.c_iflag |= ICRNL | IXON | IUTF8;
    tty.c_oflag |= OPOST | ONLCR;
    tty.c_lflag |= ISIG | ICANON | ECHO | ECHOE | ECHOK;
    if (tcsetattr(slave, TCSANOW, &tty) || pipe2(errors, O_CLOEXEC)) goto fail;
    errors[0] = above_stdio(errors[0]); errors[1] = above_stdio(errors[1]);
    if (errors[0] < 0 || errors[1] < 0) goto fail;
    pid_t child = fork();
    if (child < 0) goto fail;
    if (!child) {
        close(errors[0]);
        struct sigaction action = {.sa_handler = SIG_DFL}; sigemptyset(&action.sa_mask);
        for (int signal = 1; signal < NSIG; signal++) sigaction(signal, &action, NULL);
        sigset_t mask; sigemptyset(&mask); sigprocmask(SIG_SETMASK, &mask, NULL);
        if (setsid() < 0 || ioctl(slave, TIOCSCTTY, 0) < 0 || tcsetpgrp(slave, getpid()) < 0 || chdir(cwd)) child_error(errors[1]);
        for (int fd = 0; fd < 3; fd++) if (dup2(slave, fd) < 0) child_error(errors[1]);
        close_inherited(errors[1], limit.rlim_cur);
        execve(command, args, env);
        child_error(errors[1]);
    }
    close(slave); slave = -1; close(errors[1]); errors[1] = -1;
    struct pollfd ready = {.fd = errors[0], .events = POLLIN | POLLHUP};
    int status;
    do { status = poll(&ready, 1, 5000); } while (status < 0 && errno == EINTR);
    int error = 0; ssize_t count = status > 0 ? read(errors[0], &error, sizeof(error)) : -1;
    if (count != 0) {
        kill(child, SIGKILL);
        while (waitpid(child, NULL, 0) < 0 && errno == EINTR) {}
        errno = count > 0 ? error : ETIMEDOUT; goto fail;
    }
    close(errors[0]); *pid = child; return master;
fail:
    saved = errno;
    if (master >= 0) close(master);
    if (slave >= 0) close(slave);
    if (errors[0] >= 0) close(errors[0]);
    if (errors[1] >= 0) close(errors[1]);
    errno = saved; return -1;
}
