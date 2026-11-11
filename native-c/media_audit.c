/* Zero-dependency ISO-BMFF (MP4) fast structural & vertical-short auditor CLI in C11. */
#include <stdio.h>
#include "mp4_audit.h"

int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "Uso: %s <arquivo.mp4>\n", argv[0]);
        return 2;
    }
    return mp4_audit_and_print(argv[1]);
}
