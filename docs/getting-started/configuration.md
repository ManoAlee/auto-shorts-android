# Configuration Reference

All operational settings in AutoShorts can be configured via environment variables or a local `.env` file at the root of the repository.

AutoShorts enforces **Zero Secrets in VCS**: never commit `.env` or files containing private API credentials.

---

## 1. Core Engine & AI Scripting

| Variable | Default | Description |
|---|---|---|
| `AUTO_PILOT_ENABLED` | `0` | Set to `1` to enable autonomous background scheduling in Web Studio. |
| `STORAGE_MAX_VIDEOS` | `20` | Maximum number of MP4s kept in `output/` before automated circular pruning. |
| `STORAGE_MAX_MB` | `1200` | Maximum storage ceiling in megabytes allocated to video files. |
| `OPENROUTER_API_KEY` | *(None)* | Optional API key for OpenRouter LLMs. |
| `OPENROUTER_MODEL` | `openrouter/free` | Target model for script generation and hook optimization. |
| `LOCAL_LLM_URL` | *(None)* | URL to local llama-server on phone (`http://127.0.0.1:8080/v1`). |

---

## 2. Neural Voice & Audio Synthesis

AutoShorts defaults to offline **Kokoro-82M PT-BR** or free **Edge-TTS** without requiring any paid API keys.

| Variable | Default | Description |
|---|---|---|
| `TTS_ENGINE` | `kokoro` | Active engine: `kokoro`, `edge-tts`, `openai`, `elevenlabs`, `f5-tts`, `gpt-sovits`. |
| `ELEVENLABS_API_KEY` | *(None)* | ElevenLabs API key for cinematic human voices. |
| `ELEVENLABS_VOICE_ID` | `pNInz6obpgDQGcFmaJgB` | Default voice ID (Portuguese Brazilian Adam/Marcus). |
| `OPENAI_TTS_MODEL` | `gpt-4o-mini-tts` | OpenAI TTS model (`tts-1-hd` or `gpt-4o-mini-tts`). |
| `OPENAI_TTS_VOICE` | `onyx` | Voice style: `onyx`, `ash`, `echo`, `fable`, `nova`, `shimmer`. |
| `GPT_SOVITS_API_URL` | *(None)* | Self-hosted zero-shot voice cloning endpoint (`http://<ip>:9880`). |
| `F5_TTS_API_URL` | *(None)* | Flow Matching voice cloning server endpoint (`http://<ip>:9881`). |

---

## 3. Platform Publishing Channels

### TikTok Content Posting API v2
```dotenv
TIKTOK_CLIENT_KEY=your_client_key
TIKTOK_CLIENT_SECRET=your_client_secret
TIKTOK_ACCESS_TOKEN=your_access_token
TIKTOK_REFRESH_TOKEN=your_refresh_token
TIKTOK_PUBLISH_MODE=inbox
TIKTOK_PRIVACY_LEVEL=SELF_ONLY
```

### YouTube Data API v3
```dotenv
YT_CLIENT_ID=your_client_id.apps.googleusercontent.com
YT_CLIENT_SECRET=your_client_secret
YT_REFRESH_TOKEN=your_refresh_token
YT_PRIVACY_STATUS=public
```

### Instagram Graph API v21.0
```dotenv
IG_USER_ID=your_instagram_business_account_id
IG_ACCESS_TOKEN=your_long_lived_token
REELS_PUBLIC_BASE_URL=https://your-public-cdn.example.com
```

### Universal Publish Webhook (n8n / Postiz / Make)
```dotenv
PUBLISH_WEBHOOK_URL=https://n8n.yourdomain.com/webhook/publish-short
```

---

## 4. Web Studio & Remote Access

| Variable | Default | Description |
|---|---|---|
| `PORT` | `8787` | Port for local Web Studio HTTP daemon. |
| `PUBLIC_STUDIO_URL` | *(None)* | Static public HTTPS URL if behind reverse proxy or Cloudflare Tunnel. |
| `AUTO_PURGE_LOCAL_AFTER_DRIVE` | `0` | If `1`, removes local MP4 once verified on remote storage. |
