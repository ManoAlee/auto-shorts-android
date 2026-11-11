# Estudo de Nichos, Retenção e Monetização no Brasil

Mapeamento técnico dos presets de plataforma e perfis de nicho em `src/auto_shorts/config.py`.

## Presets de Plataforma (`PLATFORMS`)

| Preset | Duração Min / Max | Alvo de Retenção (`sweet_spot`) | Proporção |
| :--- | :---: | :--- | :---: |
| `tiktok_rewards` | `62s – 95s` | `62–90s` (obrigatório `>= 60s` para TikTok Creator Rewards) | `9:16` |
| `youtube_shorts` | `30s – 58s` | `35–55s` (máxima taxa de conclusão abaixo de 60s) | `9:16` |
| `instagram_reels` | `25s – 58s` | `30–50s` (foco em salvamentos e compartilhamentos) | `9:16` |

## Nichos PT-BR Configurados (`NICHES`)

- **`financas`** — *Finanças, Investimentos e Renda Extra*: alto RPM publicitário; gatilhos de juros, salário, banco, pix e lucro.
- **`ia_tech`** — *IA, Tecnologia e SaaS*: alta viralização em descobertas de ferramentas gratuitas, automação e IA no celular.
- **`entretenimento_animes`** — *Entretenimento, Animes, Mangás e Teorias*: alto volume de comentários, teorias de episódios e radar automático via AniList/Jikan.
- **`podcast`** — *Cortes de Podcast, Entrevistas e Debates*: cortes com heatmap *Most Replayed* do YouTube InnerTube e enquadramento `split_top_bottom` / `blur_bg`.
- **`desenvolvimento_pessoal`** — *Desenvolvimento Pessoal e Mentalidade*: hábitos, disciplina, foco e salvamentos em WhatsApp/Instagram.
- **`saude_fitness`** — *Saúde, Fitness e Emagrecimento*: sono, proteína, metabolismo e treino.
- **`concursos`** — *Carreira, Concursos e Educação*: edital, método de estudo e resumo rápido.
