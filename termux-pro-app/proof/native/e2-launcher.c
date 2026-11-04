#include <stdlib.h>
#include "tp_exec.h"

/* An isolated E2 fixture, not a package-authority mechanism. */
int main(int argc, char **argv) {
    const char *target = getenv("TP_E2_TARGET");
    if (!target) return 126;
    return tp_exec_elf(target, argc, argv);
}
