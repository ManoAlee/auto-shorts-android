/* Shared ISO-BMFF (MP4) structural & vertical-short auditor in C11. */
#ifndef AUTOSHORTS_MP4_AUDIT_H
#define AUTOSHORTS_MP4_AUDIT_H

#include <stdint.h>
#include <stdio.h>
#include <string.h>

typedef struct {
    int has_ftyp;
    int has_moov;
    uint32_t timescale;
    double duration_sec;
    uint32_t width;
    uint32_t height;
    int is_vertical;
} Mp4Summary;

static inline uint32_t mp4_read_be32(const unsigned char *b) {
    return ((uint32_t)b[0] << 24) | ((uint32_t)b[1] << 16) |
           ((uint32_t)b[2] << 8) | (uint32_t)b[3];
}

static inline uint64_t mp4_read_be64(const unsigned char *b) {
    return ((uint64_t)mp4_read_be32(b) << 32) | (uint64_t)mp4_read_be32(b + 4);
}

static inline int mp4_parse_container(FILE *fp, uint64_t start, uint64_t end, Mp4Summary *out) {
    uint64_t pos = start;
    unsigned char hdr[16];
    while (pos + 8 <= end) {
        if (fseek(fp, (long)pos, SEEK_SET) != 0) break;
        if (fread(hdr, 1, 8, fp) != 8) break;
        uint64_t size = mp4_read_be32(hdr);
        uint64_t hdr_len = 8;
        if (size == 1) {
            if (fread(hdr + 8, 1, 8, fp) != 8) break;
            size = mp4_read_be64(hdr + 8);
            hdr_len = 16;
        } else if (size == 0) {
            size = end - pos;
        }
        if (size < hdr_len || pos + size > end) break;

        char tag[5];
        memcpy(tag, hdr + 4, 4);
        tag[4] = '\0';

        uint64_t body_start = pos + hdr_len;
        uint64_t body_end = pos + size;

        if (strcmp(tag, "ftyp") == 0) {
            out->has_ftyp = 1;
        } else if (strcmp(tag, "moov") == 0) {
            out->has_moov = 1;
            mp4_parse_container(fp, body_start, body_end, out);
        } else if (strcmp(tag, "trak") == 0) {
            mp4_parse_container(fp, body_start, body_end, out);
        } else if (strcmp(tag, "mvhd") == 0 && size - hdr_len >= 20) {
            unsigned char buf[32];
            size_t to_read = (size - hdr_len) < sizeof(buf) ? (size_t)(size - hdr_len) : sizeof(buf);
            if (fread(buf, 1, to_read, fp) >= 20) {
                uint8_t ver = buf[0];
                if (ver == 0 && to_read >= 20) {
                    uint32_t ts = mp4_read_be32(buf + 12);
                    uint32_t dur = mp4_read_be32(buf + 16);
                    if (ts > 0) {
                        out->timescale = ts;
                        out->duration_sec = (double)dur / (double)ts;
                    }
                } else if (ver == 1 && to_read >= 32) {
                    uint32_t ts = mp4_read_be32(buf + 20);
                    uint64_t dur = mp4_read_be64(buf + 24);
                    if (ts > 0) {
                        out->timescale = ts;
                        out->duration_sec = (double)dur / (double)ts;
                    }
                }
            }
        } else if (strcmp(tag, "tkhd") == 0 && size - hdr_len >= 84) {
            unsigned char buf[100];
            size_t to_read = (size - hdr_len) < sizeof(buf) ? (size_t)(size - hdr_len) : sizeof(buf);
            if (fread(buf, 1, to_read, fp) >= 84) {
                uint8_t ver = buf[0];
                size_t w_off = (ver == 1) ? 88 : 76;
                if (to_read >= w_off + 8) {
                    uint32_t w = mp4_read_be32(buf + w_off) >> 16;
                    uint32_t h = mp4_read_be32(buf + w_off + 4) >> 16;
                    if (w > 0 && h > 0) {
                        out->width = w;
                        out->height = h;
                        out->is_vertical = (h > w);
                    }
                }
            }
        }
        pos = body_end;
    }
    return 0;
}

static inline int mp4_audit_and_print(const char *path) {
    FILE *fp = fopen(path, "rb");
    if (!fp) {
        fprintf(stderr, "{\"valid\":false,\"error\":\"nao foi possivel abrir arquivo\"}\n");
        return 1;
    }
    fseek(fp, 0, SEEK_END);
    long fsz = ftell(fp);
    fseek(fp, 0, SEEK_SET);
    if (fsz <= 0) {
        fclose(fp);
        fprintf(stderr, "{\"valid\":false,\"error\":\"arquivo vazio\"}\n");
        return 1;
    }

    Mp4Summary sum;
    memset(&sum, 0, sizeof(sum));
    mp4_parse_container(fp, 0, (uint64_t)fsz, &sum);
    fclose(fp);

    int ok = sum.has_ftyp && sum.has_moov && sum.width > 0 && sum.height > 0 &&
             sum.is_vertical && sum.duration_sec >= 4.0 && sum.duration_sec <= 60.5;

    printf(
        "{\"valid\":%s,\"has_ftyp\":%s,\"has_moov\":%s,\"width\":%u,\"height\":%u,"
        "\"vertical\":%s,\"duration_sec\":%.2f,\"size_bytes\":%ld}\n",
        ok ? "true" : "false",
        sum.has_ftyp ? "true" : "false",
        sum.has_moov ? "true" : "false",
        sum.width,
        sum.height,
        sum.is_vertical ? "true" : "false",
        sum.duration_sec,
        fsz
    );
    return ok ? 0 : 1;
}

#endif

