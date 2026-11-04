#define _GNU_SOURCE
#include "tp_exec.h"
#include <elf.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#ifndef TP_ELF_MACHINE
#define TP_ELF_MACHINE EM_AARCH64
#endif
#ifndef TP_SYSTEM_LINKER
#define TP_SYSTEM_LINKER "/system/bin/linker64"
#endif

int tp_validate_elf(const char *path) {
    int fd = open(path, O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
    if (fd < 0) return -1;
    struct stat st;
    Elf64_Ehdr header;
    int valid = fstat(fd, &st) == 0 && S_ISREG(st.st_mode)
        && pread(fd, &header, sizeof(header), 0) == sizeof(header)
        && memcmp(header.e_ident, "\177ELF\002\001\001", 7) == 0
        && header.e_machine == TP_ELF_MACHINE && header.e_type == ET_DYN
        && header.e_phentsize == sizeof(Elf64_Phdr) && header.e_phnum > 0 && header.e_phnum <= 128
        && header.e_phoff <= (unsigned long long)st.st_size
        && header.e_phnum * sizeof(Elf64_Phdr) <= (unsigned long long)st.st_size - header.e_phoff;
    int interpreter = 0, dynamic = 0, executable_entry = 0;
    for (int i = 0; valid && i < header.e_phnum; ++i) {
        Elf64_Phdr segment;
        if (pread(fd, &segment, sizeof(segment), header.e_phoff + i * sizeof(segment)) != sizeof(segment)
            || segment.p_offset > (unsigned long long)st.st_size
            || segment.p_filesz > (unsigned long long)st.st_size - segment.p_offset
            || segment.p_memsz < segment.p_filesz) { valid = 0; break; }
        if (segment.p_type == PT_INTERP) {
            char name[sizeof(TP_SYSTEM_LINKER)];
            if (segment.p_filesz != sizeof(name) || pread(fd, name, sizeof(name), segment.p_offset) != sizeof(name)
                || memcmp(name, TP_SYSTEM_LINKER, sizeof(name))) { valid = 0; break; }
            ++interpreter;
        } else if (segment.p_type == PT_DYNAMIC) {
            ++dynamic;
        } else if (segment.p_type == PT_LOAD) {
            if (segment.p_align < 16384 || (segment.p_align & (segment.p_align - 1))
                || (segment.p_offset - segment.p_vaddr) % 16384
                || (segment.p_flags & (PF_W | PF_X)) == (PF_W | PF_X)) { valid = 0; break; }
            if ((segment.p_flags & PF_X) && header.e_entry >= segment.p_vaddr
                && header.e_entry - segment.p_vaddr < segment.p_memsz) executable_entry = 1;
        }
    }
    close(fd);
    return valid && interpreter == 1 && dynamic == 1 && header.e_entry && executable_entry ? 0 : -1;
}

int tp_exec_elf(const char *path, int argc, char *const argv[]) {
    if (path[0] != '/' || argc < 1 || argc > 4096 || tp_validate_elf(path)) {
        fprintf(stderr, "termux-pro: rejected unsupported ELF target\n");
        return 126;
    }
    char **args = calloc((size_t)argc + 2, sizeof(char *));
    if (!args) return 126;
    args[0] = TP_SYSTEM_LINKER;
    args[1] = (char *)path;
    for (int i = 1; i < argc; ++i) args[i + 1] = argv[i];
    execv(TP_SYSTEM_LINKER, args);
    perror("termux-pro: exec system linker");
    free(args);
    return 126;
}
