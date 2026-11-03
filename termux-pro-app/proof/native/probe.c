#define _GNU_SOURCE
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/auxv.h>
#include <unistd.h>

/* Diagnostic fixture only: does not authorize or launch package programs. */
static void hex(const char *key, const char *value) {
    printf("%s=", key);
    for (const unsigned char *p = (const unsigned char *)value; *p; ++p)
        printf("%02x", *p);
    putchar('\n');
}

/* Resolve parent aliases consistently, retaining the final command basename. */
static int entry_path(const char *path, char output[PATH_MAX]) {
    char copy[PATH_MAX], parent[PATH_MAX];
    int n = snprintf(copy, sizeof(copy), "%s", path);
    if (n < 0 || (size_t)n >= sizeof(copy)) return -1;
    char *name = strrchr(copy, '/');
    if (name) {
        *name++ = '\0';
        if (!realpath(copy[0] ? copy : "/", parent)) return -1;
    } else {
        name = copy;
        if (!realpath(".", parent)) return -1;
    }
    n = snprintf(output, PATH_MAX, "%s%s%s", parent,
                 strcmp(parent, "/") ? "/" : "", name);
    return n < 0 || n >= PATH_MAX ? -1 : 0;
}

int main(int argc, char **argv) {
    const char *execfn = (const char *)getauxval(AT_EXECFN);
    const char *prefix = getenv("TP_PROOF_PREFIX");
    const char *launcher = getenv("TP_PROOF_LAUNCHER");
    char resolved[PATH_MAX], protected_path[PATH_MAX], invoked[PATH_MAX];
    char entry[PATH_MAX], expected_launcher[PATH_MAX], raw_entry[PATH_MAX];
    if (!execfn || !prefix || !launcher) return 64;
    hex("execfn_hex", execfn);
    hex("argv0_hex", argc ? argv[0] : "");
    int n = snprintf(raw_entry, sizeof(raw_entry), "%s/bin/gh", prefix);
    if (n < 0 || (size_t)n >= sizeof(raw_entry)) return 64;
    if (entry_path(execfn, invoked) || entry_path(launcher, expected_launcher)
        || entry_path(raw_entry, entry)) return 64;
    if (!realpath(invoked, resolved) || !realpath(launcher, protected_path)
        || strcmp(resolved, protected_path)) return 64;
    const char *identity;
    if (!strcmp(invoked, expected_launcher)) identity = "protected";
    else if (!strcmp(invoked, entry)) identity = "gh";
    else return 64;
    printf("identity=%s\n", identity);
    const char *expected_identity = getenv("TP_PROOF_EXPECT_IDENTITY");
    if (expected_identity && strcmp(identity, expected_identity)) return 66;
    const char *expected[] = {"", "a b", "--", "日本語", "'quoted'"};
    if (argc != 6) return 65;
    for (int i = 1; i < argc; ++i)
        if (strcmp(argv[i], expected[i - 1])) return 65;
    puts("arguments=preserved");
    return 0;
}
