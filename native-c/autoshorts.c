/*
 * AutoShorts Native C11 Aegis Engine — High Availability Watchdog, Health & ISO-BMFF Auditor
 * Conforme o padrao HKUDS/CLI-Anything (JSON-First, Zero-Fork, Self-Healing, High Resilience)
 * Compila no Android/Termux (clang aarch64) e Windows/Linux sem dependencias externas.
 */
#ifndef _WIN32
#define _POSIX_C_SOURCE 200809L
#endif

#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
typedef SOCKET sock_t;
#define CLOSESOCK closesocket
#define SLEEP_SEC(s) Sleep((DWORD)(s) * 1000)
#define SLEEP_MS(ms) Sleep((DWORD)(ms))
#else
#include <arpa/inet.h>
#include <netdb.h>
#include <sys/socket.h>
#include <sys/statvfs.h>
#include <sys/time.h>
#include <sys/types.h>
#include <unistd.h>
typedef int sock_t;
#define INVALID_SOCKET (-1)
#define CLOSESOCK close
#define SLEEP_SEC(s) sleep((unsigned int)(s))
#define SLEEP_MS(ms) usleep((useconds_t)((ms) * 1000))
#endif

#include "mp4_audit.h"

#define DEFAULT_HOST "127.0.0.1"
#define DEFAULT_PORT 8787
#define SSHD_PORT 8022
#define RESP_BUF_SIZE 65536

static void net_init(void) {
#ifdef _WIN32
    WSADATA wsa;
    WSAStartup(MAKEWORD(2, 2), &wsa);
#endif
}

static void net_cleanup(void) {
#ifdef _WIN32
    WSACleanup();
#endif
}

static double get_monotonic_sec(void) {
#ifdef _WIN32
    static LARGE_INTEGER freq;
    static int init = 0;
    if (!init) {
        QueryPerformanceFrequency(&freq);
        init = 1;
    }
    LARGE_INTEGER now;
    QueryPerformanceCounter(&now);
    return (double)now.QuadPart / (double)freq.QuadPart;
#else
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + ((double)ts.tv_nsec / 1e9);
#endif
}

static int is_port_listening(const char *host, int port, int timeout_ms) {
    char port_str[16];
    snprintf(port_str, sizeof(port_str), "%d", port);

    struct addrinfo hints;
    struct addrinfo *res = NULL;
    memset(&hints, 0, sizeof(hints));
    hints.ai_family = AF_INET;
    hints.ai_socktype = SOCK_STREAM;

    if (getaddrinfo(host, port_str, &hints, &res) != 0 || !res) {
        return 0;
    }

    sock_t s = socket(res->ai_family, res->ai_socktype, res->ai_protocol);
    if (s == INVALID_SOCKET) {
        freeaddrinfo(res);
        return 0;
    }

#ifdef _WIN32
    u_long mode = 1;
    ioctlsocket(s, FIONBIO, &mode);
    int rc = connect(s, res->ai_addr, (int)res->ai_addrlen);
    int connected = 0;
    if (rc == 0) {
        connected = 1;
    } else {
        fd_set wfds;
        FD_ZERO(&wfds);
        FD_SET(s, &wfds);
        struct timeval tv;
        tv.tv_sec = timeout_ms / 1000;
        tv.tv_usec = (timeout_ms % 1000) * 1000;
        if (select((int)s + 1, NULL, &wfds, NULL, &tv) > 0) {
            connected = 1;
        }
    }
#else
    int flags = fcntl(s, F_GETFL, 0);
    fcntl(s, F_SETFL, flags | O_NONBLOCK);
    int rc = connect(s, res->ai_addr, (int)res->ai_addrlen);
    int connected = 0;
    if (rc == 0) {
        connected = 1;
    } else if (errno == EINPROGRESS) {
        fd_set wfds;
        FD_ZERO(&wfds);
        FD_SET(s, &wfds);
        struct timeval tv;
        tv.tv_sec = timeout_ms / 1000;
        tv.tv_usec = (timeout_ms % 1000) * 1000;
        if (select(s + 1, NULL, &wfds, NULL, &tv) > 0) {
            int err = 0;
            socklen_t len = sizeof(err);
            if (getsockopt(s, SOL_SOCKET, SO_ERROR, &err, &len) == 0 && err == 0) {
                connected = 1;
            }
        }
    }
#endif

    CLOSESOCK(s);
    freeaddrinfo(res);
    return connected;
}

static int is_internet_online(void) {
    return is_port_listening("1.1.1.1", 53, 1500) || is_port_listening("8.8.8.8", 53, 1500);
}

static int http_call(
    const char *host,
    int port,
    const char *method,
    const char *path,
    const char *json_body,
    char *out_buf,
    size_t out_cap,
    int *out_status
) {
    if (out_buf && out_cap > 0) out_buf[0] = '\0';
    if (out_status) *out_status = 0;

    char port_str[16];
    snprintf(port_str, sizeof(port_str), "%d", port);

    struct addrinfo hints;
    struct addrinfo *res = NULL;
    memset(&hints, 0, sizeof(hints));
    hints.ai_family = AF_INET;
    hints.ai_socktype = SOCK_STREAM;

    if (getaddrinfo(host, port_str, &hints, &res) != 0 || !res) {
        return -1;
    }

    sock_t sock = INVALID_SOCKET;
    for (struct addrinfo *p = res; p != NULL; p = p->ai_next) {
        sock = socket(p->ai_family, p->ai_socktype, p->ai_protocol);
        if (sock == INVALID_SOCKET) continue;

#ifdef _WIN32
        DWORD tv = 4000;
        setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, (const char *)&tv, sizeof(tv));
        setsockopt(sock, SOL_SOCKET, SO_SNDTIMEO, (const char *)&tv, sizeof(tv));
#else
        struct timeval tv;
        tv.tv_sec = 4;
        tv.tv_usec = 0;
        setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
        setsockopt(sock, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof(tv));
#endif
        if (connect(sock, p->ai_addr, (int)p->ai_addrlen) == 0) {
            break;
        }
        CLOSESOCK(sock);
        sock = INVALID_SOCKET;
    }
    freeaddrinfo(res);

    if (sock == INVALID_SOCKET) return -1;

    char req[2048];
    int body_len = json_body ? (int)strlen(json_body) : 0;
    int req_len = snprintf(
        req,
        sizeof(req),
        "%s %s HTTP/1.1\r\n"
        "Host: %s:%d\r\n"
        "User-Agent: AutoShorts-Aegis/2.0\r\n"
        "Accept: application/json\r\n"
        "Connection: close\r\n"
        "%s%s%s%s\r\n",
        method,
        path,
        host,
        port,
        body_len > 0 ? "Content-Type: application/json\r\n" : "",
        body_len > 0 ? "Content-Length: " : "",
        body_len > 0 ? "" : "",
        body_len > 0 ? "\r\n" : ""
    );
    if (body_len > 0) {
        snprintf(req + req_len - 2, sizeof(req) - (size_t)req_len + 2, "Content-Length: %d\r\n\r\n%s", body_len, json_body);
        req_len = (int)strlen(req);
    }

    if (send(sock, req, (int)req_len, 0) < 0) {
        CLOSESOCK(sock);
        return -1;
    }

    char tmp[4096];
    size_t total = 0;
    int received = 0;
    while ((received = (int)recv(sock, tmp, sizeof(tmp) - 1, 0)) > 0) {
        if (out_buf && total + (size_t)received < out_cap) {
            memcpy(out_buf + total, tmp, (size_t)received);
            total += (size_t)received;
            out_buf[total] = '\0';
        }
    }
    CLOSESOCK(sock);

    if (out_buf && total > 0) {
        char *status_line = strstr(out_buf, "HTTP/1.");
        if (status_line) {
            int st = 0;
            if (sscanf(status_line, "HTTP/1.%*d %d", &st) == 1 && out_status) {
                *out_status = st;
            }
        }
        char *body = strstr(out_buf, "\r\n\r\n");
        if (body) {
            body += 4;
            memmove(out_buf, body, strlen(body) + 1);
        }
    }
    return 0;
}

static void read_mem_stats(long *out_total_mb, long *out_avail_mb) {
    if (out_total_mb) *out_total_mb = 0;
    if (out_avail_mb) *out_avail_mb = 0;
#ifndef _WIN32
    FILE *fp = fopen("/proc/meminfo", "r");
    if (!fp) return;
    char line[128];
    long total_kb = 0, avail_kb = 0, free_kb = 0, buffers_kb = 0, cached_kb = 0;
    while (fgets(line, sizeof(line), fp)) {
        if (strncmp(line, "MemTotal:", 9) == 0) sscanf(line + 9, "%ld", &total_kb);
        else if (strncmp(line, "MemAvailable:", 13) == 0) sscanf(line + 13, "%ld", &avail_kb);
        else if (strncmp(line, "MemFree:", 8) == 0) sscanf(line + 8, "%ld", &free_kb);
        else if (strncmp(line, "Buffers:", 8) == 0) sscanf(line + 8, "%ld", &buffers_kb);
        else if (strncmp(line, "Cached:", 7) == 0) sscanf(line + 7, "%ld", &cached_kb);
    }
    fclose(fp);
    if (avail_kb == 0) avail_kb = free_kb + buffers_kb + cached_kb;
    if (out_total_mb) *out_total_mb = total_kb / 1024;
    if (out_avail_mb) *out_avail_mb = avail_kb / 1024;
#else
    MEMORYSTATUSEX ms;
    ms.dwLength = sizeof(ms);
    if (GlobalMemoryStatusEx(&ms)) {
        if (out_total_mb) *out_total_mb = (long)(ms.ullTotalPhys / (1024 * 1024));
        if (out_avail_mb) *out_avail_mb = (long)(ms.ullAvailPhys / (1024 * 1024));
    }
#endif
}

static int ensure_runtime_alive(const char *host, int port) {
    char buf[512];
    int code = 0;
    if (http_call(host, port, "GET", "/api/status", NULL, buf, sizeof(buf), &code) == 0 && code == 200) {
        return 0;
    }

#ifndef _WIN32
    /* Se estamos rodando dentro do Termux localmente */
    if (getenv("PREFIX") != NULL || access("/data/data/com.termux", F_OK) == 0) {
        /* Despertar runit nativamente */
        int _r1 = system("sv up autoshorts-web autoshorts sshd autoshorts-tunnel >/dev/null 2>&1 || true");
        (void)_r1;
        /* Se runsvdir nao estiver rodando, acionar via TermuxService */
        if (access("/data/data/com.termux/files/usr/var/service", F_OK) == 0) {
            int _r2 = system("pgrep -f runsvdir >/dev/null 2>&1 || nohup runsvdir -P /data/data/com.termux/files/usr/var/service </dev/null >/dev/null 2>&1 &");
            (void)_r2;
        }
    } else {
        /* Se estamos em outro host, acionar via SSH com fallback */
        char cmd[512];
        snprintf(
            cmd,
            sizeof(cmd),
            "ssh -p 8022 -o BatchMode=yes -o ConnectTimeout=4 127.0.0.1 "
            "\"termux-wake-lock 2>/dev/null || true; sv up autoshorts-web >/dev/null 2>&1 || true\""
        );
        int _r3 = system(cmd);
        (void)_r3;
    }
#else
    /* No Windows: aciona ADB forward e checa conexao */
    int _r4 = system("adb forward tcp:8787 tcp:8787 >nul 2>&1");
    (void)_r4;
#endif

    for (int i = 0; i < 5; ++i) {
        SLEEP_MS(600);
        if (http_call(host, port, "GET", "/api/status", NULL, buf, sizeof(buf), &code) == 0 && code == 200) {
            return 0;
        }
    }
    return -1;
}

static int cmd_health(const char *host, int port, int json_output) {
    int web_ok = is_port_listening(host, port, 1500);
    int ssh_ok = is_port_listening(host, SSHD_PORT, 1500);

    long total_mb = 0, avail_mb = 0;
    read_mem_stats(&total_mb, &avail_mb);

    const char *pressure = "NORMAL";
    if (avail_mb > 0 && avail_mb < 250) {
        pressure = "CRITICAL";
    } else if (avail_mb > 0 && avail_mb < 500) {
        pressure = "CONSTRAINED";
    }

    int overall_ok = (web_ok && ssh_ok && strcmp(pressure, "CRITICAL") != 0);

    if (json_output) {
        printf("{\n");
        printf("  \"status\": \"%s\",\n", overall_ok ? "HEALTHY" : "DEGRADED");
        printf("  \"timestamp_mono\": %.3f,\n", get_monotonic_sec());
        printf("  \"services\": {\n");
        printf("    \"webapp\": {\"port\": %d, \"alive\": %s},\n", port, web_ok ? "true" : "false");
        printf("    \"sshd\": {\"port\": %d, \"alive\": %s}\n", SSHD_PORT, ssh_ok ? "true" : "false");
        printf("  },\n");
        printf("  \"memory\": {\n");
        printf("    \"total_mb\": %ld,\n", total_mb);
        printf("    \"available_mb\": %ld,\n", avail_mb);
        printf("    \"pressure\": \"%s\"\n", pressure);
        printf("  }\n");
        printf("}\n");
    } else {
        printf("\n=== AUTOSHORTS AEGIS SYSTEM HEALTH ===\n");
        printf(" Status Geral     : %s\n", overall_ok ? "🟢 HEALTHY" : "🔴 DEGRADED");
        printf(" WebApp (:8787)   : %s\n", web_ok ? "UP" : "DOWN");
        printf(" OpenSSH (:8022)  : %s\n", ssh_ok ? "UP" : "DOWN");
        printf(" RAM Disponivel   : %ld MB / %ld MB (Pressao: %s)\n", avail_mb, total_mb, pressure);
        printf(" Monotonic Time   : %.2fs\n", get_monotonic_sec());
        printf("=======================================\n\n");
    }
    return overall_ok ? 0 : 3;
}

static int cmd_watch(const char *host, int port, int interval_sec, int json_output) {
    if (interval_sec < 5) interval_sec = 5;
    if (!json_output) {
        printf("[Aegis C11] Watchdog ativo monitorando %s:%d e sshd a cada %ds...\n", host, port, interval_sec);
    }

    for (;;) {
        double t_start = get_monotonic_sec();
        int web_alive = is_port_listening(host, port, 1000);
        int ssh_alive = is_port_listening(host, SSHD_PORT, 1000);

        long total_mb = 0, avail_mb = 0;
        read_mem_stats(&total_mb, &avail_mb);

        /* Auto-cura proativa se webapp caiu */
        if (!web_alive) {
            if (!json_output) fprintf(stderr, "[Aegis C11] WebApp down! Acionando reerguimento proativo...\n");
            ensure_runtime_alive(host, port);
            web_alive = is_port_listening(host, port, 1500);
        }

        /* Auto-cura proativa se sshd caiu no Android */
        if (!ssh_alive) {
#ifndef _WIN32
            if (access("/data/data/com.termux", F_OK) == 0) {
                int _r = system("sv up sshd >/dev/null 2>&1 || sshd >/dev/null 2>&1 || true");
                (void)_r;
            }
#endif
        }

        if (json_output) {
            printf("{\"event\":\"heartbeat\",\"mono\":%.2f,\"web\":%s,\"ssh\":%s,\"ram_avail_mb\":%ld}\n",
                   t_start, web_alive ? "true" : "false", ssh_alive ? "true" : "false", avail_mb);
            fflush(stdout);
        } else {
            printf("[Aegis C11] Heartbeat | Web=%s | SSH=%s | RAM=%ldMB livre | t=%.1fs\n",
                   web_alive ? "OK" : "DOWN", ssh_alive ? "OK" : "DOWN", avail_mb, t_start);
            fflush(stdout);
        }

        SLEEP_SEC(interval_sec);
    }
    return 0;
}

static void print_usage(const char *prog) {
    printf(
        "AutoShorts Aegis C11 Native Harness\n"
        "Uso:\n"
        "  %s health [--json]       Verifica saude do runtime, portas e memoria\n"
        "  %s watch [sec] [--json]  Watchdog autonomo em tempo real (zero-fork)\n"
        "  %s audit <video.mp4>     Auditoria nativa ISO-BMFF 9:16 vertical\n"
        "  %s start                 Garante subida do Web Studio e servicos\n"
        "Opcoes globais: --host <ip> --port <porta>\n",
        prog, prog, prog, prog
    );
}

int main(int argc, char **argv) {
    const char *env_host = getenv("AUTOSHORT_HOST");
    const char *env_port = getenv("AUTOSHORT_PORT");
    const char *host = (env_host && env_host[0]) ? env_host : DEFAULT_HOST;
    int port = (env_port && env_port[0]) ? atoi(env_port) : DEFAULT_PORT;
    if (port <= 0) port = DEFAULT_PORT;

    int json_mode = 0;
    int argi = 1;

    while (argi < argc) {
        if (strcmp(argv[argi], "--host") == 0 && argi + 1 < argc) {
            host = argv[++argi];
        } else if (strcmp(argv[argi], "--port") == 0 && argi + 1 < argc) {
            port = atoi(argv[++argi]);
        } else if (strcmp(argv[argi], "--json") == 0) {
            json_mode = 1;
        } else {
            break;
        }
        argi++;
    }

    if (argi < argc && (strcmp(argv[argi], "-h") == 0 || strcmp(argv[argi], "--help") == 0)) {
        print_usage(argv[0]);
        return 0;
    }

    net_init();
    int rc = 0;

    if (argi >= argc) {
        rc = cmd_health(host, port, json_mode);
    } else if (strcmp(argv[argi], "health") == 0) {
        if (argi + 1 < argc && strcmp(argv[argi + 1], "--json") == 0) json_mode = 1;
        rc = cmd_health(host, port, json_mode);
    } else if (strcmp(argv[argi], "watch") == 0) {
        int interval = 10;
        if (argi + 1 < argc && atoi(argv[argi + 1]) > 0) {
            interval = atoi(argv[++argi]);
        }
        if (argi + 1 < argc && strcmp(argv[argi + 1], "--json") == 0) json_mode = 1;
        rc = cmd_watch(host, port, interval, json_mode);
    } else if (strcmp(argv[argi], "audit") == 0) {
        if (argi + 1 >= argc) {
            fprintf(stderr, "Uso: %s audit <arquivo.mp4>\n", argv[0]);
            rc = 2;
        } else {
            rc = mp4_audit_and_print(argv[argi + 1]);
        }
    } else if (strcmp(argv[argi], "start") == 0) {
        rc = ensure_runtime_alive(host, port);
        if (rc == 0 && !json_mode) printf("[Aegis C11] Runtime ativo em %s:%d\n", host, port);
    } else {
        print_usage(argv[0]);
        rc = 2;
    }

    net_cleanup();
    return rc;
}
