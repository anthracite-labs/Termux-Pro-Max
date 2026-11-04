#ifndef TP_EXEC_H
#define TP_EXEC_H
int tp_validate_elf(const char *path);
int tp_exec_elf(const char *path, int argc, char *const argv[]);
#endif
