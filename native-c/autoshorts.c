/*
 * AutoShorts Native C11 Runner, Watchdog & ISO-BMFF Auditor
 * Compila no Termux/Android (clang) e Windows/Linux sem dependencias externas.
 */
#ifndef _WIN32
#define _POSIX_C_SOURCE 200809L
#endif

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
typedef SOCKET sock_t;
#define CLOSESOCK closesocket
#define SLEEP_SEC(s) Sleep((DWORD)(s) * 1000)
#else
#include <arpa/inet.h>
#include <netdb.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <sys/types.h>
#include <unistd.h>
typedef int sock_t;
#define INVALID_SOCKET (-1)
#define CLOSESOCK close
#define SLEEP_SEC(s) sleep((unsigned int)(s))
#endif

#include "mp4_audit.h"

#define DEFAULT_HOST "127.0.0.1"
#define DEFAULT_PORT 8787
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
    hints.ai_family = AF_UNSPEC;
    hints.ai_socktype = SOCK_STREAM;

    if (getaddrinfo(host, port_str, &hints, &res) != 0 || !res) {
        return -1;
    }

    sock_t sock = INVALID_SOCKET;
    for (struct addrinfo *p = res; p != NULL; p = p->ai_next) {
        sock = socket(p->ai_family, p->ai_socktype, p->ai_protocol);
        if (sock == INVALID_SOCKET) continue;

#ifdef _WIN32
        DWORD tv = 5000;
        setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, (const char *)&tv, sizeof(tv));
        setsockopt(sock, SOL_SOCKET, SO_SNDTIMEO, (const char *)&tv, sizeof(tv));
#else
        struct timeval tv;
        tv.tv_sec = 5;
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
    if (sock == INVALID_SOCKET) {
        return -1;
    }

    size_t body_len = json_body ? strlen(json_body) : 0;
    char req[4096];
    int req_len = snprintf(
        req,
        sizeof(req),
        "%s %s HTTP/1.1\r\n"
        "Host: %s:%d\r\n"
        "User-Agent: AutoShorts-C/1.0\r\n"
        "Connection: close\r\n"
        "%s%s"
        "Content-Length: %zu\r\n\r\n",
        method,
        path,
        host,
        port,
        json_body ? "Content-Type: application/json\r\n" : "",
        json_body ? "" : "",
        body_len
    );
    if (req_len <= 0 || (size_t)req_len >= sizeof(req)) {
        CLOSESOCK(sock);
        return -2;
    }

    if (send(sock, req, req_len, 0) < 0) {
        CLOSESOCK(sock);
        return -3;
    }
    if (json_body && body_len > 0) {
        if (send(sock, json_body, (int)body_len, 0) < 0) {
            CLOSESOCK(sock);
            return -3;
        }
    }

    char *raw = (char *)malloc(RESP_BUF_SIZE);
    if (!raw) {
        CLOSESOCK(sock);
        return -4;
    }
    size_t total = 0;
    while (total + 1 < RESP_BUF_SIZE) {
        int n = recv(sock, raw + total, (int)(RESP_BUF_SIZE - 1 - total), 0);
        if (n <= 0) break;
        total += (size_t)n;
    }
    raw[total] = '\0';
    CLOSESOCK(sock);

    int status = 0;
    if (sscanf(raw, "HTTP/%*d.%*d %d", &status) == 1 && out_status) {
        *out_status = status;
    }

    char *body_sep = strstr(raw, "\r\n\r\n");
    const char *body_src = body_sep ? (body_sep + 4) : raw;
    if (out_buf && out_cap > 0) {
        snprintf(out_buf, out_cap, "%s", body_src);
    }
    free(raw);
    return 0;
}

static int is_local_host(const char *host) {
    return strcmp(host, "127.0.0.1") == 0 || strcmp(host, "localhost") == 0;
}

static int ensure_runtime_alive(const char *host, int port) {
    char buf[4096];
    int code = 0;
    if (http_call(host, port, "GET", "/api/status", NULL, buf, sizeof(buf), &code) == 0 && code == 200) {
        return 0;
    }

    if (is_local_host(host)) {
        printf("[AutoShorts C] Servidor :%d offline — iniciando wake-lock, sshd e Web Studio...\n", port);
#ifndef _WIN32
        char cmd[512];
        snprintf(
            cmd,
            sizeof(cmd),
            "command -v termux-wake-lock >/dev/null 2>&1 && timeout 3 termux-wake-lock >/dev/null 2>&1 || true; "
            "command -v sshd >/dev/null 2>&1 && (pgrep -x sshd >/dev/null 2>&1 || sshd) || true; "
            "bash \"$HOME/auto-shorts-android/scripts/start_webapp.sh\" %d >/dev/null 2>&1",
            port
        );
        int rc = system(cmd);
        (void)rc;
#else
        printf("[AutoShorts C] Dica: no Windows, inicie o servidor no celular ou defina AUTOSHORT_HOST=192.168.10.210.\n");
#endif
    } else {
        printf("[AutoShorts C] Tentando acordar servidor remoto em %s:%d via ssh termux...\n", host, port);
        char cmd[512];
        snprintf(
            cmd,
            sizeof(cmd),
            "ssh -o BatchMode=yes -o ConnectTimeout=5 termux "
            "\"termux-wake-lock 2>/dev/null || true; bash ~/auto-shorts-android/scripts/start_webapp.sh %d\"",
            port
        );
        int rc = system(cmd);
        (void)rc;
    }

    for (int i = 0; i < 6; ++i) {
        SLEEP_SEC(1);
        if (http_call(host, port, "GET", "/api/status", NULL, buf, sizeof(buf), &code) == 0 && code == 200) {
            return 0;
        }
    }
    return -1;
}

static int extract_json_str(const char *json, const char *key, char *out, size_t out_sz) {
    if (!json || !key || !out || out_sz == 0) return -1;
    out[0] = '\0';
    char pat[128];
    snprintf(pat, sizeof(pat), "\"%s\"", key);
    const char *p = strstr(json, pat);
    if (!p) return -1;
    p = strchr(p + strlen(pat), ':');
    if (!p) return -1;
    p++;
    while (*p == ' ' || *p == '\t') p++;
    if (*p != '"') {
        size_t i = 0;
        while (*p && *p != ',' && *p != '}' && *p != '\r' && *p != '\n' && i + 1 < out_sz) {
            out[i++] = *p++;
        }
        out[i] = '\0';
        return 0;
    }
    p++;
    size_t i = 0;
    while (*p && *p != '"' && i + 1 < out_sz) {
        if (*p == '\\' && *(p + 1)) p++;
        out[i++] = *p++;
    }
    out[i] = '\0';
    return 0;
}

static int cmd_status(const char *host, int port) {
    char *status_buf = (char *)malloc(RESP_BUF_SIZE);
    char *sched_buf = (char *)malloc(RESP_BUF_SIZE);
    char *chan_buf = (char *)malloc(RESP_BUF_SIZE);
    if (!status_buf || !sched_buf || !chan_buf) {
        free(status_buf);
        free(sched_buf);
        free(chan_buf);
        return 1;
    }

    int c1 = 0, c2 = 0, c3 = 0;
    int r1 = http_call(host, port, "GET", "/api/status", NULL, status_buf, RESP_BUF_SIZE, &c1);
    int r2 = http_call(host, port, "GET", "/api/scheduler", NULL, sched_buf, RESP_BUF_SIZE, &c2);
    int r3 = http_call(host, port, "GET", "/api/channel", NULL, chan_buf, RESP_BUF_SIZE, &c3);

    if (r1 != 0 || c1 != 200) {
        printf("[OFFLINE] AutoShorts em http://%s:%d nao respondeu.\n", host, port);
        free(status_buf);
        free(sched_buf);
        free(chan_buf);
        return 1;
    }

    char running[32], last_st[256], ch_name[128], views[32], vids[32];
    char enabled[32], niche[64], runs[32], last_at[64];
    extract_json_str(status_buf, "running", running, sizeof(running));
    extract_json_str(status_buf, "last_status", last_st, sizeof(last_st));
    extract_json_str(chan_buf, "title", ch_name, sizeof(ch_name));
    extract_json_str(chan_buf, "views", views, sizeof(views));
    extract_json_str(chan_buf, "videos", vids, sizeof(vids));
    extract_json_str(sched_buf, "enabled", enabled, sizeof(enabled));
    extract_json_str(sched_buf, "niche", niche, sizeof(niche));
    extract_json_str(sched_buf, "runs_completed", runs, sizeof(runs));
    extract_json_str(sched_buf, "last_run_at", last_at, sizeof(last_at));

    printf("\n====================================================\n");
    printf(" AutoShorts Studio (Runner Nativo C11)\n");
    printf(" Painel Web : http://%s:%d/\n", host, port);
    if (r3 == 0 && c3 == 200 && ch_name[0]) {
        printf(" Canal YT   : %s (%s videos | %s views)\n", ch_name, vids, views);
    }
    printf(" Tarefa     : %s | %s\n", strcmp(running, "true") == 0 ? "EM EXECUCAO" : "PRONTA", last_st);
    if (r2 == 0 && c2 == 200) {
        printf(" Piloto 24/7: %s | Nicho: %s | Ciclos: %s | Ultimo: %s\n",
               strcmp(enabled, "true") == 0 ? "ATIVO" : "PAUSADO",
               niche[0] ? niche : "all",
               runs[0] ? runs : "0",
               last_at[0] ? last_at : "-");
    }
    printf("====================================================\n");

    free(status_buf);
    free(sched_buf);
    free(chan_buf);
    return 0;
}

static int cmd_scheduler_post(const char *host, int port, const char *niche, int enabled, int run_now) {
    if (ensure_runtime_alive(host, port) != 0) {
        fprintf(stderr, "[Erro] Nao foi possivel conectar em %s:%d.\n", host, port);
        return 1;
    }
    char body[512];
    snprintf(
        body,
        sizeof(body),
        "{\"enabled\":%s,\"interval_hours\":4,\"niche\":\"%s\",\"auto_publish\":true,\"run_now\":%s}",
        enabled ? "true" : "false",
        (niche && niche[0]) ? niche : "all",
        run_now ? "true" : "false"
    );
    char *resp = (char *)malloc(RESP_BUF_SIZE);
    if (!resp) return 1;
    int code = 0;
    int rc = http_call(host, port, "POST", "/api/scheduler", body, resp, RESP_BUF_SIZE, &code);
    printf("[HTTP %d] %s\n", code, (rc == 0 && resp[0]) ? resp : "sem resposta");
    free(resp);
    return (rc == 0 && (code == 200 || code == 202 || code == 409)) ? 0 : 1;
}

static int is_internet_online(void) {
    struct addrinfo hints;
    struct addrinfo *res = NULL;
    memset(&hints, 0, sizeof(hints));
    hints.ai_family = AF_INET;
    hints.ai_socktype = SOCK_STREAM;
    if (getaddrinfo("1.1.1.1", "443", &hints, &res) != 0 || !res) {
        return 0;
    }
    int online = 0;
    sock_t s = socket(res->ai_family, res->ai_socktype, res->ai_protocol);
    if (s != INVALID_SOCKET) {
#ifdef _WIN32
        DWORD tv = 2000;
        setsockopt(s, SOL_SOCKET, SO_RCVTIMEO, (const char *)&tv, sizeof(tv));
        setsockopt(s, SOL_SOCKET, SO_SNDTIMEO, (const char *)&tv, sizeof(tv));
#else
        struct timeval tv;
        tv.tv_sec = 2;
        tv.tv_usec = 0;
        setsockopt(s, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
        setsockopt(s, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof(tv));
#endif
        if (connect(s, res->ai_addr, (int)res->ai_addrlen) == 0) {
            online = 1;
        }
        CLOSESOCK(s);
    }
    freeaddrinfo(res);
    return online;
}

static int cmd_watch(const char *host, int port, int interval_sec) {
    if (interval_sec < 10) interval_sec = 10;
    printf("[Watchdog C] Monitorando %s:%d, sshd, wake-lock e Wi-Fi a cada %ds...\n", host, port, interval_sec);
    int was_offline = !is_internet_online();
    unsigned int tick = 0;
    for (;;) {
#ifndef _WIN32
        /* Keep sshd alive independently of :8787 state and refresh wake-lock every ~5 min */
        int _ignored_rc = system("command -v sshd >/dev/null 2>&1 && (pgrep -x sshd >/dev/null 2>&1 || sshd >/dev/null 2>&1) || true");
        (void)_ignored_rc;
        if ((tick % 10U) == 0U) {
            _ignored_rc = system("command -v termux-wake-lock >/dev/null 2>&1 && timeout 3 termux-wake-lock >/dev/null 2>&1 || true");
            (void)_ignored_rc;
        }
#endif
        tick++;
        if (ensure_runtime_alive(host, port) != 0) {
            fprintf(stderr, "[Watchdog C] Alerta: falha ao reerguer %s:%d\n", host, port);
        } else {
            int online_now = is_internet_online();
            char buf[4096];
            int code = 0;
            if (http_call(host, port, "GET", "/api/scheduler", NULL, buf, sizeof(buf), &code) == 0 && code == 200) {
                char runs[32], en[16];
                extract_json_str(buf, "runs_completed", runs, sizeof(runs));
                extract_json_str(buf, "enabled", en, sizeof(en));
                printf("[Watchdog C] Studio OK (%s:%d) | Wi-Fi=%s | Piloto=%s | Ciclos=%s\n",
                       host, port, online_now ? "ONLINE" : "SEM REDE", en, runs);
                if (was_offline && online_now && strcmp(en, "true") == 0) {
                    printf("[Watchdog C] Wi-Fi reconectado! Disparando ciclo pendente agora...\n");
                    char *post_resp = (char *)malloc(RESP_BUF_SIZE);
                    if (post_resp) {
                        int pc = 0;
                        http_call(host, port, "POST", "/api/scheduler", "{\"run_now\":true}", post_resp, RESP_BUF_SIZE, &pc);
                        free(post_resp);
                    }
                }
                was_offline = !online_now;
                fflush(stdout);
            }
        }
        SLEEP_SEC(interval_sec);
    }
    return 0;
}

static void print_usage(const char *prog) {
    printf(
        "AutoShorts Studio C11 Runner\n"
        "Uso:\n"
        "  %s                    Abre painel e menu interativo\n"
        "  %s post [nicho]       Inicia runtime se preciso e posta agora (padrao: all)\n"
        "  %s start              Liga wake-lock, sshd, Web Studio (:8787) e piloto 24/7\n"
        "  %s stop               Pausa o piloto automatico 24/7\n"
        "  %s status             Mostra canal, tarefa atual e agenda\n"
        "  %s watch [segundos]   Daemon watchdog 24/7\n"
        "  %s audit <video.mp4>  Auditoria estrutural ISO-BMFF 9:16 em C\n"
        "Variaveis de ambiente opcionais: AUTOSHORT_HOST (padrao 127.0.0.1) e AUTOSHORT_PORT (8787).\n",
        prog, prog, prog, prog, prog, prog, prog
    );
}

static int run_menu(const char *host, int port) {
    ensure_runtime_alive(host, port);
    for (;;) {
        cmd_status(host, port);
        printf(
            "\nEscolha uma acao:\n"
            "  [1] Comecar a postar agora (ciclo multi-nicho automatico)\n"
            "  [2] Postar nicho especifico (podcast / entretenimento_animes / ia_tech / financas)\n"
            "  [3] Ligar piloto automatico 24/7 (a cada 4h)\n"
            "  [4] Pausar piloto automatico\n"
            "  [5] Atualizar status\n"
            "  [6] Iniciar Watchdog 24/7\n"
            "  [7] Auditar arquivo MP4 local\n"
            "  [0] Sair (mantem servidor rodando em segundo plano)\n"
            "> "
        );
        fflush(stdout);
        char line[256];
        if (!fgets(line, sizeof(line), stdin)) break;
        int opt = atoi(line);
        if (opt == 0) break;
        if (opt == 1) {
            cmd_scheduler_post(host, port, "all", 1, 1);
        } else if (opt == 2) {
            printf("Digite o nicho (ex: podcast, entretenimento_animes, ia_tech, financas): ");
            fflush(stdout);
            char nbuf[128];
            if (fgets(nbuf, sizeof(nbuf), stdin)) {
                size_t len = strcspn(nbuf, "\r\n");
                nbuf[len] = '\0';
                cmd_scheduler_post(host, port, nbuf[0] ? nbuf : "podcast", 1, 1);
            }
        } else if (opt == 3) {
            cmd_scheduler_post(host, port, "all", 1, 0);
        } else if (opt == 4) {
            cmd_scheduler_post(host, port, "all", 0, 0);
        } else if (opt == 5) {
            continue;
        } else if (opt == 6) {
            cmd_watch(host, port, 60);
        } else if (opt == 7) {
            printf("Caminho do MP4: ");
            fflush(stdout);
            char fbuf[512];
            if (fgets(fbuf, sizeof(fbuf), stdin)) {
                size_t len = strcspn(fbuf, "\r\n");
                fbuf[len] = '\0';
                if (fbuf[0]) mp4_audit_and_print(fbuf);
            }
        }
    }
    return 0;
}

int main(int argc, char **argv) {
    const char *env_host = getenv("AUTOSHORT_HOST");
    const char *env_port = getenv("AUTOSHORT_PORT");
    const char *host = (env_host && env_host[0]) ? env_host : DEFAULT_HOST;
    int port = (env_port && env_port[0]) ? atoi(env_port) : DEFAULT_PORT;
    if (port <= 0) port = DEFAULT_PORT;

    int argi = 1;
    while (argi < argc) {
        if (strcmp(argv[argi], "--host") == 0 && argi + 1 < argc) {
            host = argv[++argi];
        } else if (strcmp(argv[argi], "--port") == 0 && argi + 1 < argc) {
            port = atoi(argv[++argi]);
        } else {
            break;
        }
        argi++;
    }

    if (argi < argc && (strcmp(argv[argi], "-h") == 0 || strcmp(argv[argi], "--help") == 0)) {
        print_usage(argv[0]);
        return 0;
    }

    if (argi < argc && strcmp(argv[argi], "audit") == 0) {
        if (argi + 1 >= argc) {
            fprintf(stderr, "Uso: %s audit <arquivo.mp4>\n", argv[0]);
            return 2;
        }
        return mp4_audit_and_print(argv[argi + 1]);
    }

    net_init();
    int rc = 0;

    if (argi >= argc) {
        rc = run_menu(host, port);
    } else if (strcmp(argv[argi], "post") == 0) {
        const char *niche = (argi + 1 < argc) ? argv[argi + 1] : "all";
        rc = cmd_scheduler_post(host, port, niche, 1, 1);
    } else if (strcmp(argv[argi], "start") == 0) {
        rc = cmd_scheduler_post(host, port, "all", 1, 0);
        if (rc == 0) cmd_status(host, port);
    } else if (strcmp(argv[argi], "stop") == 0) {
        rc = cmd_scheduler_post(host, port, "all", 0, 0);
    } else if (strcmp(argv[argi], "status") == 0) {
        rc = cmd_status(host, port);
    } else if (strcmp(argv[argi], "watch") == 0) {
        int interval = (argi + 1 < argc) ? atoi(argv[argi + 1]) : 60;
        rc = cmd_watch(host, port, interval);
    } else {
        print_usage(argv[0]);
        rc = 2;
    }

    net_cleanup();
    return rc;
}
