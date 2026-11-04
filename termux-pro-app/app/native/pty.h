#ifndef TP_PTY_H
#define TP_PTY_H
#include <sys/types.h>
int tp_pty_start(const char *command, const char *cwd, char *const args[], char *const env[],
                 pid_t *pid, int rows, int columns, int cell_width, int cell_height);
int tp_pty_resize(int fd, int rows, int columns, int cell_width, int cell_height);
#endif
