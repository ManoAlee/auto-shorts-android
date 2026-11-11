CC ?= clang
CFLAGS ?= -O2 -Wall -Wextra -std=c11

all: ../bin/autoshorts ../bin/media_audit

../bin/autoshorts: autoshorts.c mp4_audit.h
	mkdir -p ../bin
	$(CC) $(CFLAGS) autoshorts.c -o ../bin/autoshorts

../bin/media_audit: media_audit.c mp4_audit.h
	mkdir -p ../bin
	$(CC) $(CFLAGS) media_audit.c -o ../bin/media_audit

install-termux: all
	@if [ -n "$$PREFIX" ] && [ -d "$$PREFIX/bin" ]; then cp ../bin/autoshorts "$$PREFIX/bin/autoshorts" && chmod +x "$$PREFIX/bin/autoshorts"; fi

