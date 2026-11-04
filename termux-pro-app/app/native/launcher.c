#define _GNU_SOURCE
#include "tp_exec.h"
#include <fcntl.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/auxv.h>
#include <sys/stat.h>
#include <unistd.h>
#include <ctype.h>
#ifndef TP_PREFIX
#error TP_PREFIX must come from shared/target.json
#endif

static int entry(const char *path, char output[PATH_MAX]) {
    char copy[PATH_MAX], parent[PATH_MAX];
    if (snprintf(copy, sizeof(copy), "%s", path) >= (int)sizeof(copy)) return -1;
    char *name = strrchr(copy, '/');
    if (name) { *name++ = 0; if (!realpath(*copy ? copy : "/", parent)) return -1; }
    else { name = copy; if (!realpath(".", parent)) return -1; }
    int length = snprintf(output, PATH_MAX, "%s/%s", parent, name);
    return length < 0 || length >= PATH_MAX ? -1 : 0;
}
static int identifier(const char *name) {
    size_t length = strlen(name);
    if (!length || length > 64 || !isalnum((unsigned char)*name) || strstr(name, "..")) return 0;
    for (const unsigned char *p = (const unsigned char *)name; *p; p++)
        if (!isalnum(*p) && !strchr("+_.-", *p)) return 0;
    return 1;
}
int main(int argc, char **argv) {
    char invoked[PATH_MAX], self[PATH_MAX], resolved[PATH_MAX];
    const char *execfn = (const char *)getauxval(AT_EXECFN);
    if (!execfn || entry(execfn, invoked) || !realpath("/proc/self/exe", self)
        || !realpath(invoked, resolved) || strcmp(resolved, self)) goto rejected;
    const char *name;
    if (!strcmp(invoked, self)) {
        if (argc < 3 || strcmp(argv[1], "--tp-command")) goto rejected;
        name = argv[2]; argc -= 2; argv += 2;
    } else {
        const char *bin = TP_PREFIX "/bin/";
        if (strncmp(invoked, bin, strlen(bin))) goto rejected;
        name = invoked + strlen(bin);
    }
    if (!identifier(name)) goto rejected;
    char record[PATH_MAX], expected[128], contents[129], target[PATH_MAX], canonical[PATH_MAX];
    if (snprintf(record, sizeof(record), TP_PREFIX "/var/lib/termux-pro/commands/%s", name) >= (int)sizeof(record)) goto rejected;
    int fd = open(record, O_RDONLY | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK);
    if (fd < 0) goto rejected;
    struct stat metadata;
    if (fstat(fd, &metadata) || !S_ISREG(metadata.st_mode)) { close(fd); goto rejected; }
    ssize_t count = read(fd, contents, sizeof(contents)); close(fd);
    int size = snprintf(expected, sizeof(expected), "libexec/tp-real/%s\n", name);
    if (count != size || memcmp(contents, expected, (size_t)size)) goto rejected;
    if (snprintf(target, sizeof(target), TP_PREFIX "/libexec/tp-real/%s", name) >= (int)sizeof(target)
        || !realpath(target, canonical) || strcmp(canonical, target)) goto rejected;
    // Packages use their fixed RUNPATH; inherited loader injection is unsupported.
    unsetenv("LD_PRELOAD"); unsetenv("LD_LIBRARY_PATH"); unsetenv("LD_AUDIT");
    return tp_exec_elf(target, argc, argv);
rejected:
    fputs("termux-pro: unregistered or invalid command entry\n", stderr);
    return 64;
}
