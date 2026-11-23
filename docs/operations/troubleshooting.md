# Operations: Troubleshooting & Recovery

This guide covers common issues encountered during Android mobile execution and their immediate technical resolutions.

---

## 1. FFmpeg Render Failures / Code 137 (OOM)

### Symptom:
FFmpeg terminates abruptly during video encoding with returncode `137` or `SIGKILL`.

### Root Cause:
Android's Low Memory Killer (LMK) killed the process because memory usage spiked.

### Resolution:
1. Ensure no other memory-heavy apps are running in the background.
2. In `src/auto_shorts/config.py` or `.env`, verify `-preset veryfast` or `-preset ultrafast` is used for H.264 encoding.
3. Lower concurrent worker threads to 2 by adding `-threads 2` to FFmpeg arguments.

---

## 2. Background Process Freezing in Termux

### Symptom:
Generation stops or Web Studio disconnects when the phone screen is turned off.

### Root Cause:
Android OS battery optimization (Doze Mode) paused Termux CPU execution.

### Resolution:
1. Run `termux-wake-lock` in the Termux shell before launching the server.
2. In Android Settings -> Apps -> Termux -> Battery -> Set to **Unrestricted**.

---

## 3. Port Already in Use (Port 8787)

### Symptom:
`OSError: [Errno 98] Address already in use: ('0.0.0.0', 8787)`

### Resolution:
Identify and terminate the lingering process:
```bash
# On Termux / Linux:
fuser -k 8787/tcp

# Or find PID:
netstat -tlpn | grep 8787
kill -9 <PID>
```

---

## 4. TTS Timeout / Audio Failure

### Symptom:
`RuntimeError: TTS synthesis failed or returned 0 bytes`

### Resolution:
1. If using Kokoro-82M, verify model files exist in `assets/models/kokoro/`.
2. If using Edge-TTS, verify active internet connectivity.
3. Check fallback behavior: AutoShorts will automatically attempt Edge-TTS if local Kokoro fails.
