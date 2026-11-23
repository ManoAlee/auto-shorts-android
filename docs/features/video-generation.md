# Autonomous Video Generation

AutoShorts generates complete 9:16 vertical short videos through a modular content pipeline supporting multiple niches, automated story packs, and viral hooks.

---

## 1. Supported Content Niches

| Niche Key | Label | Narrative Profile & Strategy |
|---|---|---|
| `mundo` | **Notícias Globais & Brasil** | Fast-paced investigative journalism, breaking news, tech trends, high urgency. |
| `games` | **Games & Curiosidades** | Leaks, industry drama, easter eggs, insider trivia, high gamer audience engagement. |
| `negocios` | **Negócios & Estratégia** | Business case studies, founder stories, market strategies, financial insights. |
| `anime` | **Anime & Mangá** | Lore explanations, character analysis, power scaling, plot twists. |
| `podcast` | **Cortes de Podcast** | Engaging conversational snippets, debate clips, provocative questions. |

---

## 2. Mahoraga 3-Act Narrative Structure

The scripting engine decomposes every short into a proven 3-act viral framework:

1. **Act 1: The Hook (0s – 3s)**
   - Bold claim or unexpected paradox.
   - Designed to break the user's scroll habit on TikTok, Shorts, or Reels.
   - Word count: 12 to 20 words.
2. **Act 2: The Core Tension & Context (3s – 30s)**
   - Unfolds the background details, key developments, and conflict.
   - Paced dynamically with scene transitions every 3 to 5 seconds.
   - Word count: 60 to 90 words.
3. **Act 3: The Climax & Retention Loop (30s – 45s)**
   - Resolution, broader impact, or thought-provoking ending statement.
   - Smoothly loops back into Act 1 for replay retention.
   - Word count: 15 to 25 words.

---

## 3. Anti-Stub Safeguards

To prevent low-value renders (such as 1-sentence RSS echoes), AutoShorts enforces strict anti-stub validation:
- Discards news items where the article body simply repeats the headline.
- Requires minimum 2 complete sentences and at least 45 total spoken words.
- Re-ranks RSS feeds prioritizing content-rich portals (*BBC Brasil, Tecnoblog, Canaltech, Viciados.net*) over generic title aggregators.
