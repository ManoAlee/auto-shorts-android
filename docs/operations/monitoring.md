# Operations: Monitoring & Observability

AutoShorts provides comprehensive runtime observability for both local mobile environments and remote production pipelines.

---

## 1. System Health Telemetry

The Web Studio exposes a dedicated REST telemetry endpoint at `/api/system` and `/api/status` returning structured machine-readable JSON:

```bash
curl -s http://127.0.0.1:8787/api/system | jq .
```

### Telemetry Payload Schema:
```json
{
  "status": "healthy",
  "engine": "AutoShorts Android",
  "version": "1.0.0",
  "hardware": {
    "platform": "Linux-aarch64",
    "cpu_cores": 8,
    "memory_available_mb": 4512
  },
  "tts": {
    "active_engine": "Kokoro-82M PT-BR Offline",
    "onnx_available": true
  },
  "storage": {
    "total_videos": 18,
    "used_mb": 420.5,
    "max_mb": 1200,
    "quota_healthy": true
  },
  "autopilot": {
    "enabled": false,
    "next_run": null
  }
}
```

---

## 2. Storage Guards & Retention Engine

AutoShorts runs automated storage checks before and after every video generation job:
- **Max Video Count (`STORAGE_MAX_VIDEOS`):** Defaults to 20 files. When exceeded, the oldest unstarred video is purged.
- **Max Disk Space (`STORAGE_MAX_MB`):** Defaults to 1200 MB. When total directory volume exceeds the limit, the cleanup worker prunes non-essential assets until within quota.
- **Temporary Asset Sanitization:** Orphaned `.wav`, `.raw_chunk`, and partial `.mp4.part` files are removed automatically if older than 10 minutes.
