// Dev-sandbox shim: report a raised RLIMIT_NOFILE so TigerGraph's GSE startup check passes in
// containers whose host caps file descriptors at 20000. Not needed on a normal Docker host.
#define _GNU_SOURCE
#include <dlfcn.h>
#include <sys/resource.h>
#include <sys/types.h>

static void bump(int res, struct rlimit *r) {
  if (res == RLIMIT_NOFILE && r) { if (r->rlim_cur < 1048576) r->rlim_cur = 1048576; if (r->rlim_max < 1048576) r->rlim_max = 1048576; }
}
int getrlimit(__rlimit_resource_t res, struct rlimit *r) {
  static int (*real)(__rlimit_resource_t, struct rlimit *) = 0;
  if (!real) real = dlsym(RTLD_NEXT, "getrlimit");
  int rc = real(res, r); if (rc == 0) bump(res, r); return rc;
}
int getrlimit64(__rlimit_resource_t res, struct rlimit64 *r) {
  static int (*real)(__rlimit_resource_t, struct rlimit64 *) = 0;
  if (!real) real = dlsym(RTLD_NEXT, "getrlimit64");
  int rc = real(res, r); if (rc == 0) bump(res, (struct rlimit *)r); return rc;
}
int prlimit(pid_t pid, __rlimit_resource_t res, const struct rlimit *n, struct rlimit *o) {
  static int (*real)(pid_t, __rlimit_resource_t, const struct rlimit *, struct rlimit *) = 0;
  if (!real) real = dlsym(RTLD_NEXT, "prlimit");
  if (n) return 0;  /* ignore attempts to raise */
  int rc = real(pid, res, n, o); if (rc == 0) bump(res, o); return rc;
}
int prlimit64(pid_t pid, __rlimit_resource_t res, const struct rlimit64 *n, struct rlimit64 *o) {
  static int (*real)(pid_t, __rlimit_resource_t, const struct rlimit64 *, struct rlimit64 *) = 0;
  if (!real) real = dlsym(RTLD_NEXT, "prlimit64");
  if (n) return 0;
  int rc = real(pid, res, n, o); if (rc == 0) bump(res, (struct rlimit *)o); return rc;
}
int setrlimit(__rlimit_resource_t res, const struct rlimit *r) {
  static int (*real)(__rlimit_resource_t, const struct rlimit *) = 0;
  if (!real) real = dlsym(RTLD_NEXT, "setrlimit");
  int rc = real(res, r); return (res == RLIMIT_NOFILE) ? 0 : rc;
}
