"""Accessible Cross-Platform Analytics & Global Trends Dashboard HTML (WCAG AA + Bento UI)."""

from __future__ import annotations


def render_analytics_dashboard_html() -> str:
    return """<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>AutoShorts Analytics &amp; Radar Global</title>
  <style>
    :root {
      --bg: #0b0f17;
      --surface: #131a26;
      --surface-2: #1a2333;
      --border: #273449;
      --text: #f8fafc;
      --muted: #94a3b8;
      --cyan: #22d3ee;
      --emerald: #10b981;
      --rose: #fb7185;
      --amber: #fbbf24;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
      font-size: 16px;
    }
    a, button, select {
      min-height: 44px;
      font-family: inherit;
    }
    a:focus-visible, button:focus-visible, select:focus-visible {
      outline: 3px solid var(--cyan);
      outline-offset: 2px;
    }
    .skip-link {
      position: absolute;
      left: -9999px;
      top: 8px;
      background: var(--cyan);
      color: #0b0f17;
      padding: 10px 16px;
      font-weight: 700;
      border-radius: 8px;
    }
    .skip-link:focus { left: 16px; z-index: 100; }
    header {
      border-bottom: 1px solid var(--border);
      background: var(--surface);
      padding: 16px 20px;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }
    header h1 { margin: 0; font-size: 1.25rem; }
    nav { display: flex; gap: 10px; flex-wrap: wrap; }
    .btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 10px 16px;
      border-radius: 10px;
      border: 1px solid var(--border);
      background: var(--surface-2);
      color: var(--text);
      text-decoration: none;
      cursor: pointer;
      font-weight: 600;
      font-size: 0.95rem;
    }
    .btn-primary {
      background: var(--cyan);
      color: #081018;
      border-color: var(--cyan);
    }
    main {
      max-width: 1200px;
      margin: 0 auto;
      padding: 20px 16px 48px;
      display: grid;
      gap: 20px;
    }
    .bento-kpi {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 14px;
    }
    .card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 18px;
    }
    .kpi-label { color: var(--muted); font-size: 0.85rem; margin-bottom: 4px; }
    .kpi-val { font-size: 1.75rem; font-weight: 700; color: var(--text); }
    .tabs {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-bottom: 14px;
    }
    .tab-btn {
      padding: 10px 16px;
      border-radius: 10px;
      border: 1px solid var(--border);
      background: var(--surface-2);
      color: var(--text);
      cursor: pointer;
      font-weight: 600;
    }
    .tab-btn[aria-selected="true"] {
      background: var(--cyan);
      color: #081018;
      border-color: var(--cyan);
    }
    .grid-2 {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
      gap: 16px;
    }
    ul { margin: 8px 0 0; padding-left: 20px; }
    li { margin-bottom: 6px; }
    .badge {
      display: inline-block;
      padding: 3px 10px;
      border-radius: 999px;
      font-size: 0.8rem;
      font-weight: 700;
      background: var(--surface-2);
      border: 1px solid var(--border);
      color: var(--cyan);
    }
    .trend-list {
      display: grid;
      gap: 10px;
      margin-top: 14px;
    }
    .trend-item {
      background: var(--surface-2);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 12px 14px;
    }
    .trend-title { font-weight: 600; color: var(--text); text-decoration: none; display: block; margin-bottom: 4px; }
    .trend-meta { font-size: 0.85rem; color: var(--muted); }
    .sr-status { color: var(--emerald); font-size: 0.9rem; margin: 0; }
  </style>
</head>
<body>
  <a class="skip-link" href="#main-content">Pular para o conteudo principal</a>
  <header>
    <div>
      <h1>AutoShorts Studio — Analytics &amp; Radar Global</h1>
      <p id="live-status" class="sr-status" aria-live="polite">Carregando metricas das 3 plataformas...</p>
    </div>
    <nav aria-label="Navegacao principal">
      <a class="btn" href="/">Voltar ao Studio</a>
      <button id="refresh-all" class="btn btn-primary" type="button">Atualizar Tudo</button>
    </nav>
  </header>

  <main id="main-content">
    <section aria-labelledby="kpi-heading">
      <h2 id="kpi-heading">Visao Geral do Acervo</h2>
      <div class="bento-kpi" id="kpi-grid"></div>
    </section>

    <section class="card" aria-labelledby="platforms-heading">
      <h2 id="platforms-heading">Algoritmo &amp; Performance por Plataforma</h2>
      <div class="tabs" role="tablist" aria-label="Plataformas">
        <button class="tab-btn" role="tab" id="tab-tiktok" aria-selected="true" aria-controls="panel-platform" data-plat="tiktok">TikTok</button>
        <button class="tab-btn" role="tab" id="tab-youtube" aria-selected="false" aria-controls="panel-platform" data-plat="youtube">YouTube Shorts</button>
        <button class="tab-btn" role="tab" id="tab-instagram" aria-selected="false" aria-controls="panel-platform" data-plat="instagram">Instagram Reels</button>
      </div>
      <div id="panel-platform" role="tabpanel" aria-labelledby="tab-tiktok"></div>
    </section>

    <section class="grid-2" aria-label="Recomendacoes e Nichos">
      <article class="card">
        <h2>Acoes Recomendadas</h2>
        <ul id="recs-list"></ul>
      </article>
      <article class="card">
        <h2>Distribuicao por Nicho</h2>
        <ul id="niches-list"></ul>
      </article>
    </section>

    <section class="card" aria-labelledby="trends-heading">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;">
        <h2 id="trends-heading" style="margin:0;">Radar Global (Google Trends, X/Twitter, Reddit, HN)</h2>
        <div>
          <label for="niche-select" style="margin-right:8px;color:var(--muted);">Nicho:</label>
          <select id="niche-select" class="btn" aria-label="Filtrar tendencias por nicho">
            <option value="all">Todos</option>
            <option value="noticias_mundiais">Noticias Mundiais</option>
            <option value="entretenimento_animes">Animes &amp; Entretenimento</option>
            <option value="ia_tech">IA &amp; Tech</option>
            <option value="financas">Financas</option>
          </select>
        </div>
      </div>
      <div id="trends-container" class="trend-list"></div>
    </section>
  </main>

  <script>
    let analyticsData = null;
    let activePlat = "tiktok";

    function renderPlatformPanel() {
      const panel = document.getElementById("panel-platform");
      if (!analyticsData) return;
      const p = analyticsData.platforms[activePlat];
      panel.setAttribute("aria-labelledby", "tab-" + activePlat);
      panel.innerHTML = `
        <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px;">
          <span class="badge">Publicados: ${p.published}</span>
          <span class="badge">Pendentes: ${p.pending}</span>
          <span class="badge">Duracao ideal: ${p.optimal_duration_s}</span>
          <span class="badge">Modo: ${p.mode}</span>
        </div>
        <div class="grid-2">
          <div>
            <h3>Sinais Principais do Algoritmo</h3>
            <ul>${p.primary_signals.map(s => `<li>${s}</li>`).join("")}</ul>
          </div>
          <div>
            <h3>Evitar (Penalizacoes)</h3>
            <ul>${p.avoid.map(s => `<li>${s}</li>`).join("")}</ul>
          </div>
        </div>
        <p style="margin-top:12px;color:var(--emerald);"><strong>CTA recomendado:</strong> ${p.cta_template}</p>
      `;
    }

    async function loadAnalytics() {
      const r = await fetch("/api/analytics/platforms");
      analyticsData = await r.json();
      const s = analyticsData.summary;
      document.getElementById("kpi-grid").innerHTML = [
        ["Total no Acervo", s.total_packs],
        ["Aprovados (Visao)", s.approved_packs],
        ["Quality Score Medio", s.avg_quality_score],
        ["Algo Score Medio", s.avg_algo_score],
        ["Duracao Media", s.avg_duration_s + "s"],
        ["Pendentes Multi-Rede", s.pending_cross_platform]
      ].map(([k, v]) => `<div class="card"><div class="kpi-label">${k}</div><div class="kpi-val">${v}</div></div>`).join("");

      document.getElementById("recs-list").innerHTML = (analyticsData.recommendations || []).map(r => `<li>${r}</li>`).join("") || "<li>Tudo em dia!</li>";
      document.getElementById("niches-list").innerHTML = Object.entries(analyticsData.niches || {}).map(([n, c]) => `<li><strong>${n}</strong>: ${c} videos</li>`).join("");
      renderPlatformPanel();
    }

    async function loadTrends() {
      const niche = document.getElementById("niche-select").value;
      const status = document.getElementById("live-status");
      status.textContent = "Pesquisando tendencias globais...";
      const r = await fetch("/api/trends/global?niche=" + encodeURIComponent(niche));
      const data = await r.json();
      const el = document.getElementById("trends-container");
      el.innerHTML = (data.trends || []).map(t => `
        <article class="trend-item">
          <a class="trend-title" href="${t.url}" target="_blank" rel="noopener noreferrer">${t.title}</a>
          <div class="trend-meta">Fonte: <strong>${t.source}</strong> | Nicho: <strong>${t.niche}</strong> | Hook: ${t.hook_idea}</div>
        </article>
      `).join("") || "<p>Nenhuma tendencia encontrada para este filtro.</p>";
      status.textContent = `Atualizado: ${data.total_trends} tendencias de ${(data.sources_ok || []).length} fontes.`;
    }

    document.querySelectorAll('[role="tab"]').forEach(btn => {
      btn.addEventListener("click", () => {
        activePlat = btn.dataset.plat;
        document.querySelectorAll('[role="tab"]').forEach(b => b.setAttribute("aria-selected", String(b === btn)));
        renderPlatformPanel();
      });
    });
    document.getElementById("niche-select").addEventListener("change", loadTrends);
    document.getElementById("refresh-all").addEventListener("click", () => { loadAnalytics(); loadTrends(); });
    loadAnalytics();
    loadTrends();
  </script>
</body>
</html>
"""

