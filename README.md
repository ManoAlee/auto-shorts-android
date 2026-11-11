# auto-shorts-android

Pipeline automatizado de cortes verticais `9:16` projetado por engenharia reversa para rodar direto no **Android (Termux `aarch64`)** sem depender de PyTorch/Docker.

## Documentação e Estudos
- [Arquitetura Completa, Motor V2 e Guia de Produção](docs/ARQUITETURA_E_PRODUCAO.md) — fluxo completo do servidor Web `:8787`, fila FIFO autônoma, reenvio automático pós-cota (`uploadLimitExceeded`), Motor V2 PT-BR, binários C11 (`autoshorts` / `media_audit`) e persistência em segundo plano no Android.
- [Estudo de Engenharia Reversa e Arquitetura](docs/ESTUDO_ENGENHARIA_REVERSA.md) — análise técnica dos repositórios de referência em `refs/`.
- [Estudo de Nichos, Views e Monetização no Brasil](docs/ESTUDO_NICHOS_MONETIZACAO_BRASIL.md) — requisitos reais (`TikTok Creator Rewards >=60s`, YouTube Shorts, Reels), nichos e métricas.

## Como instalar no Termux (celular)
```bash
bash scripts/install_termux.sh
# Opcional: para compilar whisper.cpp offline no celular (ARM64 NEON)
INSTALL_WHISPER_CPP=1 bash scripts/install_termux.sh
```

## Uso rápido
```bash
# Modo 100% offline/gratuito (usa legendas do YouTube + heurística de nicho BR)
python main.py "https://www.youtube.com/watch?v=VIDEO_ID" --niche financas --platform tiktok_rewards --offline

# Usando LLM (Gemini ou OpenAI) para ranking viral + hooks em PT-BR
export GEMINI_API_KEY="sua_chave"
python main.py "https://www.youtube.com/watch?v=VIDEO_ID" --niche ia_tech --platform youtube_shorts --layout split_top_bottom

# Vídeo local já baixado
python main.py /sdcard/Download/podcast.mp4 --srt /sdcard/Download/podcast.srt --niche desenvolvimento_pessoal
```

