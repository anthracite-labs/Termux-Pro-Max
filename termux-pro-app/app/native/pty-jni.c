#include "pty.h"
#include <errno.h>
#include <jni.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>

static void exception(JNIEnv *env, const char *message) {
    if (!(*env)->ExceptionCheck(env)) (*env)->ThrowNew(env, (*env)->FindClass(env, "java/lang/IllegalStateException"), message);
}
// Java UTF-16 -> standard UTF-8, not JNI's modified UTF-8 (NUL/supplementary chars).
static char *utf8(JNIEnv *env, jstring string) {
    if (!string) { exception(env, "Null PTY argument"); return NULL; }
    jsize length = (*env)->GetStringLength(env, string);
    if (length > 1048576) { exception(env, "PTY argument too long"); return NULL; }
    const jchar *chars = (*env)->GetStringChars(env, string, NULL);
    if (!chars) return NULL;
    char *bytes = malloc((size_t)length * 3 + 1), *out = bytes;
    if (!bytes) { (*env)->ReleaseStringChars(env, string, chars); exception(env, "PTY allocation failed"); return NULL; }
    for (jsize i = 0; i < length; i++) {
        unsigned int c = chars[i];
        if (c >= 0xd800 && c <= 0xdbff && i + 1 < length && chars[i + 1] >= 0xdc00 && chars[i + 1] <= 0xdfff)
            c = 0x10000 + ((c - 0xd800) << 10) + (chars[++i] - 0xdc00);
        if (!c || (c >= 0xd800 && c <= 0xdfff)) {
            free(bytes); (*env)->ReleaseStringChars(env, string, chars); exception(env, "Invalid PTY string"); return NULL;
        }
        if (c < 0x80) *out++ = (char)c;
        else if (c < 0x800) { *out++ = (char)(0xc0 | c >> 6); *out++ = (char)(0x80 | (c & 63)); }
        else if (c < 0x10000) { *out++ = (char)(0xe0 | c >> 12); *out++ = (char)(0x80 | ((c >> 6) & 63)); *out++ = (char)(0x80 | (c & 63)); }
        else { *out++ = (char)(0xf0 | c >> 18); *out++ = (char)(0x80 | ((c >> 12) & 63)); *out++ = (char)(0x80 | ((c >> 6) & 63)); *out++ = (char)(0x80 | (c & 63)); }
    }
    *out = 0; (*env)->ReleaseStringChars(env, string, chars); return bytes;
}
static void release(char **array) { if (array) { for (char **p = array; *p; p++) free(*p); free(array); } }
static char **strings(JNIEnv *env, jobjectArray array) {
    if (!array) { exception(env, "Null PTY array"); return NULL; }
    jsize size = (*env)->GetArrayLength(env, array);
    if (size > 4096) { exception(env, "PTY argument count limit"); return NULL; }
    char **out = calloc((size_t)size + 1, sizeof(char *));
    if (!out) { exception(env, "PTY allocation failed"); return NULL; }
    for (jsize i = 0; i < size; i++) {
        jstring string = (jstring)(*env)->GetObjectArrayElement(env, array, i);
        out[i] = utf8(env, string); (*env)->DeleteLocalRef(env, string);
        if (!out[i]) { release(out); return NULL; }
    }
    return out;
}
JNIEXPORT jint JNICALL Java_com_termux_terminal_JNI_createSubprocess(JNIEnv *env, jclass type,
    jstring command, jstring cwd, jobjectArray args, jobjectArray variables, jintArray process,
    jint rows, jint columns, jint width, jint height) {
    (void)type;
    int fd = -1; pid_t pid = -1;
    char *cmd = NULL, *dir = NULL;
    char **argv = NULL, **environ = NULL;
    cmd = utf8(env, command); if (!cmd) goto cleanup;
    dir = utf8(env, cwd); if (!dir) goto cleanup;
    argv = strings(env, args); if (!argv) goto cleanup;
    environ = strings(env, variables); if (!environ) goto cleanup;
    if (cmd && dir && argv && argv[0] && environ && process && (*env)->GetArrayLength(env, process) >= 1
        && !(*env)->ExceptionCheck(env)) {
        fd = tp_pty_start(cmd, dir, argv, environ, &pid, rows, columns, width, height);
        if (fd < 0) exception(env, strerror(errno));
        else { jint value = (jint)pid; (*env)->SetIntArrayRegion(env, process, 0, 1, &value); }
    } else exception(env, "Invalid PTY launch arguments");
cleanup:
    free(cmd); free(dir); release(argv); release(environ); return fd;
}
JNIEXPORT void JNICALL Java_com_termux_terminal_JNI_setPtyWindowSize(JNIEnv *env, jclass type,
    jint fd, jint rows, jint columns, jint width, jint height) {
    (void)type;
    if (tp_pty_resize(fd, rows, columns, width, height)) exception(env, strerror(errno));
}
JNIEXPORT jint JNICALL Java_com_termux_terminal_JNI_waitFor(JNIEnv *env, jclass type, jint pid) {
    (void)env; (void)type;
    if (pid <= 0) return -1;
    int status;
    pid_t result;
    do { result = waitpid(pid, &status, 0); } while (result < 0 && errno == EINTR);
    if (result != pid) return -1;
    return WIFEXITED(status) ? WEXITSTATUS(status) : (WIFSIGNALED(status) ? -WTERMSIG(status) : -1);
}
JNIEXPORT void JNICALL Java_com_termux_terminal_JNI_close(JNIEnv *env, jclass type, jint fd) {
    (void)env; (void)type; if (fd >= 0) close(fd);
}
