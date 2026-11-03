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

int main(int argc, char **argv) {
    const char *execfn = (const char *)getauxval(AT_EXECFN);
    const char *prefix = getenv("TP_PROOF_PREFIX");
    const char *launcher = getenv("TP_PROOF_LAUNCHER");
    char resolved[PATH_MAX], protected_path[PATH_MAX], invoked[PATH_MAX];
    char entry[PATH_MAX], cwd[PATH_MAX];
    if (!execfn || !prefix || !launcher || !getcwd(cwd, sizeof(cwd))) return 64;
    hex("execfn_hex", execfn);
    hex("argv0_hex", argc ? argv[0] : "");
    int n = execfn[0] == '/' ? snprintf(invoked, sizeof(invoked), "%s", execfn)
        : snprintf(invoked, sizeof(invoked), "%s/%s", cwd, execfn);
    if (n < 0 || (size_t)n >= sizeof(invoked)) return 64;
    /* Normalize the directory only, preserving the invoked symlink's name. */
    char *name = strrchr(invoked, '/');
    if (!name) return 64;
    *name++ = '\0';
    if (!realpath(invoked, resolved)) return 64;
    n = snprintf(entry, sizeof(entry), "%s/%s", resolved, name);
    if (n < 0 || (size_t)n >= sizeof(entry)) return 64;
    strcpy(invoked, entry);
    n = snprintf(entry, sizeof(entry), "%s/bin/gh", prefix);
    if (n < 0 || (size_t)n >= sizeof(entry)) return 64;
    if (!realpath(invoked, resolved) || !realpath(launcher, protected_path)
        || strcmp(resolved, protected_path)) return 64;
    const char *identity;
    if (!strcmp(invoked, launcher)) identity = "protected";
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
