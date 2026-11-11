/* AutoShorts Studio Frontend Controller — Copiloto IA, Dual Theme, TikTok/YouTube Delivery & WCAG A11Y */
(function () {
  const tabs = Array.from(document.querySelectorAll('[role="tab"]'));
  const panels = Array.from(document.querySelectorAll('[role="tabpanel"]'));
  const renderBar = document.getElementById('render-bar');
  const renderBadge = document.getElementById('render-badge');
  const statusEl = document.getElementById('live-status');
  const renderFill = document.getElementById('render-fill');
  const renderProgress = document.getElementById('render-progress-bar');
  const renderMeta = document.getElementById('render-meta');
  const stageEls = Array.from(document.querySelectorAll('.stage-step'));
  const toastStack = document.getElementById('toast-stack');
  const dlg = document.getElementById('short-inspector-dlg');
  const floatingDock = document.getElementById('floating-render-dock');
  const floatingText = document.getElementById('floating-render-text');

  let _pollTimer = null;
  let _wasRunning = false;
  let _lastStatusData = { running: false };
  let _lastChannelData = null;
  let _lastSchedulerData = null;
  let _inspectorTriggerEl = null;
  const _stageBaseLabels = stageEls.map((el) => el.textContent.trim());

  let _activeRadarMode = 'horizon';
  let _radarVisibleLimit = 6;
  let _horizonItemsCache = [];
  let _animeItemsCache = [];
  let _newsItemsCache = [];
  let _videosCache = [];
  let _acervoFilter = 'all';
  let _karaokeWordIdx = 0;

  /* Theme Switcher (OLED Dark Default <-> Sunlit Editorial Light) */
  const themeBtn = document.getElementById('btn-theme-toggle');
  const iconSun = document.getElementById('theme-icon-sun');
  const iconMoon = document.getElementById('theme-icon-moon');
  function applyTheme(mode) {
    const isLight = mode === 'light';
    if (isLight) document.documentElement.setAttribute('data-theme', 'light');
    else document.documentElement.removeAttribute('data-theme');
    if (themeBtn) themeBtn.setAttribute('aria-pressed', String(!isLight));
    if (iconSun) iconSun.hidden = isLight;
    if (iconMoon) iconMoon.hidden = !isLight;
    const metaTheme = document.querySelector('meta[name="theme-color"]');
    if (metaTheme) metaTheme.setAttribute('content', isLight ? '#FFFFFF' : '#070B12');
    try { localStorage.setItem('autoshorts_theme', isLight ? 'light' : 'dark'); } catch (e) {}
  }
  applyTheme(document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark');
  if (themeBtn) {
    themeBtn.addEventListener('click', () => {
      const next = document.documentElement.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
      applyTheme(next);
    });
  }

  function showToast(msg, kind = 'info') {
    if (!toastStack || !msg) return;
    const t = document.createElement('div');
    t.className = 'toast ' + kind;
    t.role = 'status';
    t.textContent = msg;
    toastStack.appendChild(t);
    setTimeout(() => {
      t.style.opacity = '0';
      setTimeout(() => t.remove(), 220);
    }, 3600);
  }

  async function copyTextToClipboard(text) {
    if (!text) return false;
    if (navigator.clipboard && window.isSecureContext) {
      try {
        await navigator.clipboard.writeText(text);
        return true;
      } catch (e) {}
    }
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.left = '-9999px';
    ta.style.top = '0';
    ta.setAttribute('readonly', '');
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    let ok = false;
    try {
      ok = document.execCommand('copy');
    } catch (e) {
      ok = false;
    }
    document.body.removeChild(ta);
    return ok;
  }

  function withBusyBtn(btn, labelWhile, fn) {
    if (!btn) return fn();
    const orig = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="btn-spinner" aria-hidden="true"></span><span>' + labelWhile + '</span>';
    return Promise.resolve()
      .then(fn)
      .finally(() => {
        btn.disabled = false;
        btn.innerHTML = orig;
      });
  }

  function renderSkeletons(container, count = 3) {
    if (!container) return;
    container.innerHTML = '';
    for (let i = 0; i < count; i++) {
      const sk = document.createElement('div');
      sk.className = 'skeleton-card';
      sk.setAttribute('aria-hidden', 'true');
      container.appendChild(sk);
    }
  }

  function activateTab(idx) {
    tabs.forEach((tab, i) => {
      const active = i === idx;
      tab.setAttribute('aria-selected', String(active));
      tab.tabIndex = active ? 0 : -1;
      if (panels[i]) panels[i].hidden = !active;
    });
    document.querySelectorAll('.mobile-nav-btn').forEach((btn) => {
      const bIdx = Number(btn.getAttribute('data-tab-idx'));
      if (bIdx === idx) btn.setAttribute('aria-current', 'page');
      else btn.removeAttribute('aria-current');
    });
    if (tabs[idx] && tabs[idx].id === 'tab-equipe') loadTeamAndPlanner();
    if (tabs[idx] && tabs[idx].id === 'tab-videos') loadVideos();
    if (tabs[idx] && tabs[idx].id === 'tab-synapse') loadSynapseStatus();
    if (tabs[idx] && tabs[idx].id === 'tab-sistema') loadSystemDiag();
  }

  tabs.forEach((tab, idx) => {
    tab.addEventListener('click', () => activateTab(idx));
    tab.addEventListener('keydown', (e) => {
      let target = -1;
      if (e.key === 'ArrowRight' || e.key === 'ArrowDown') target = (idx + 1) % tabs.length;
      else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') target = (idx - 1 + tabs.length) % tabs.length;
      else if (e.key === 'Home') target = 0;
      else if (e.key === 'End') target = tabs.length - 1;
      if (target >= 0) {
        e.preventDefault();
        tabs[target].focus();
        activateTab(target);
      }
    });
  });

  document.querySelectorAll('.mobile-nav-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const bIdx = Number(btn.getAttribute('data-tab-idx') || 0);
      activateTab(bIdx);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  });

  function syncFloatingDock() {
    if (!floatingDock || !renderBar) return;
    const isRunning = !!_lastStatusData.running;
    const barOut = renderBar.getBoundingClientRect().bottom < 72;
    floatingDock.hidden = !(isRunning && barOut);
    if (!floatingDock.hidden && floatingText) {
      const pct = Math.max(0, Math.min(100, Number(_lastStatusData.progress_pct || 20)));
      const sec = Number(_lastStatusData.elapsed_sec || 0);
      floatingText.textContent = (_lastStatusData.stage_label || 'Renderizando...') + ' (' + pct + '%' + (sec > 0 ? (' • ' + sec + 's') : '') + ')';
    }
  }
  window.addEventListener('scroll', syncFloatingDock, { passive: true });
  if (floatingDock) {
    floatingDock.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));
  }

  function startOptimisticRender(label) {
    updateRenderStepper({
      running: true,
      progress_pct: 12,
      stage_index: 1,
      stage_label: label || '1/5 Motor iniciado — coletando video e contexto...',
      queued: 1,
      elapsed_sec: 0,
    });
  }

  function updateRenderStepper(data) {
    _lastStatusData = data || { running: false };
    const running = !!data.running;
    const pct = Math.max(0, Math.min(100, Number(data.progress_pct || (running ? 25 : 0))));
    const stageIdx = Number(data.stage_index || (running ? 1 : 0));
    const qCount = Number(data.queued || 0);
    const elSec = Number(data.elapsed_sec || 0);

    if (renderBar) renderBar.classList.toggle('is-running', running);
    if (renderBadge) renderBadge.textContent = running ? 'AO VIVO' : 'Ocioso';
    if (statusEl) {
      const txt = running
        ? (data.stage_label || data.last_status || 'Renderizando...')
        : ('Pronto: ' + (data.last_status || 'Operando normalmente') + (data.last_error ? ' — Erro: ' + data.last_error : ''));
      statusEl.textContent = txt;
    }
    const barPct = running ? pct : (data.last_status && data.last_status !== 'Pronto para operar' ? 100 : 0);
    if (renderFill) renderFill.style.width = barPct + '%';
    if (renderProgress) renderProgress.setAttribute('aria-valuenow', String(barPct));
    if (renderMeta) {
      const parts = [];
      if (running) {
        parts.push(pct + '%');
        if (elSec > 0) parts.push(elSec + 's');
      } else {
        parts.push('Pronto');
      }
      if (qCount > 0) parts.push('Fila: ' + qCount);
      renderMeta.textContent = parts.join(' • ');
    }
    stageEls.forEach((el, idx) => {
      const stepNum = idx + 1;
      const base = _stageBaseLabels[idx] || el.textContent;
      el.classList.remove('is-active', 'is-done');
      if (running) {
        if (stepNum < stageIdx) {
          el.classList.add('is-done');
          el.textContent = 'OK ' + base;
        } else if (stepNum === stageIdx) {
          el.classList.add('is-active');
          el.textContent = '> ' + base;
        } else {
          el.textContent = base;
        }
      } else {
        el.textContent = base;
      }
    });
    syncFloatingDock();

    if (_wasRunning && !running) {
      showToast(data.last_error ? ('Erro: ' + data.last_error) : ('Concluido: ' + (data.last_status || 'Video validado!')), data.last_error ? 'err' : 'ok');
      loadChannelTelemetry();
      loadVideos();
    }
    _wasRunning = running;
  }

  async function refreshStatus() {
    try {
      const res = await fetch('/api/status');
      const data = await res.json();
      updateRenderStepper(data);
      const nextMs = data.running ? 1400 : 5000;
      clearTimeout(_pollTimer);
      _pollTimer = setTimeout(refreshStatus, nextMs);
    } catch (e) {
      if (statusEl) statusEl.textContent = 'Falha ao consultar estado: ' + e.message;
      clearTimeout(_pollTimer);
      _pollTimer = setTimeout(refreshStatus, 5000);
    }
  }

  /* Intelligent Copiloto Recommendation Engine */
  let _copilotFn = null;
  function updateCopilotInsight() {
    const insightEl = document.getElementById('copilot-insight');
    const actBtn = document.getElementById('btn-copilot-action');
    if (!insightEl || !actBtn) return;

    const ch = _lastChannelData || {};
    const sch = _lastSchedulerData || {};
    const vs = ch.video_stats || {};
    const keys = ch.keys || {};
    const ttReadyList = _videosCache.filter((v) => {
      const visOk = v.visual_audit ? !!v.visual_audit.approved : !!(v.validation && v.validation.valid);
      return visOk && !(v.tiktok && v.tiktok.publish_id);
    });

    if (keys.tiktok && ttReadyList.length > 0) {
      const top = ttReadyList[0];
      const sc = top.opus_scorecard ? top.opus_scorecard.opus_score : '--';
      insightEl.textContent = ttReadyList.length + ' Short(s) aprovados aguardando TikTok • Melhor: "' + String(top.title || top.filename).slice(0, 44) + '" (Opus ' + sc + '/100)';
      actBtn.textContent = 'Disparar Proximo Inteligente';
      _copilotFn = () => withBusyBtn(actBtn, 'Publicando...', async () => {
        const r = await fetch('/api/autopublish/run', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ force: true }) });
        const d = await r.json();
        const ttR = (d.results && d.results.tiktok) || {};
        const ytR = (d.results && d.results.youtube) || {};
        showToast(ttR.publish_id ? ('TikTok OK: ' + ttR.filename) : (ytR.video_id ? ('YouTube OK: ' + ytR.filename) : (ttR.reason || ytR.reason || 'Ciclo concluido')), (ttR.publish_id || ytR.video_id) ? 'ok' : 'info');
        await loadVideos();
        await loadChannelTelemetry();
        await loadScheduler();
      });
      return;
    }

    if (!sch.enabled) {
      insightEl.textContent = 'Piloto 24/7 esta pausado — ative para gerar e publicar cortes no TikTok e YouTube a cada 4h.';
      actBtn.textContent = 'Ativar Piloto 24/7';
      _copilotFn = () => withBusyBtn(actBtn, 'Ativando...', async () => {
        await fetch('/api/scheduler', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ enabled: true, platform: 'tiktok_rewards', auto_publish: true }) });
        await loadScheduler();
        showToast('Piloto 24/7 ativado para TikTok + YouTube!', 'ok');
      });
      return;
    }

    insightEl.textContent = 'Piloto 24/7 ativo (' + (sch.platform || 'tiktok_rewards') + ') • Acervo com ' + (vs.approved || 0) + ' Shorts prontos (Top Opus ' + (vs.top_opus || 0) + '/100).';
    actBtn.textContent = 'Gerar Novo Lote Agora';
    _copilotFn = () => withBusyBtn(actBtn, 'Enfileirando...', async () => {
      startOptimisticRender('1/5 Copiloto iniciando geracao multi-nicho...');
      await fetch('/api/scheduler', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ run_now: true, niche: 'all', platform: 'tiktok_rewards' }) });
      showToast('Geracao inteligente iniciada!', 'ok');
      refreshStatus();
    });
  }

  const copilotBtn = document.getElementById('btn-copilot-action');
  if (copilotBtn) {
    copilotBtn.addEventListener('click', () => {
      if (_copilotFn) _copilotFn();
    });
  }

  const copilotForm = document.getElementById('copilot-cmd-form');
  if (copilotForm) {
    copilotForm.addEventListener('submit', (e) => {
      e.preventDefault();
      const inp = document.getElementById('copilot-cmd-input');
      const cmdBtn = document.getElementById('btn-copilot-run');
      const raw = (inp ? inp.value : '').trim();
      if (!raw) return;
      const lower = raw.toLowerCase();
      if (lower.startsWith('gerar ') || lower.startsWith('crie ') || lower.startsWith('criar ') || lower.startsWith('faca ')) {
        activateTab(0);
        const query = raw.replace(/^(gerar|crie|criar|faca)\s+/i, '').trim();
        withBusyBtn(cmdBtn, 'Enfileirando...', async () => {
          startOptimisticRender('1/5 Copiloto produzindo: ' + query.slice(0, 34));
          const plat = lower.includes('youtube') ? 'youtube_shorts' : (lower.includes('reels') ? 'instagram_reels' : 'tiktok_rewards');
          const r = await fetch('/api/run', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ platform: plat, niche: 'all', query: query, clips: 1, auto_publish: true }),
          });
          const d = await r.json();
          showToast(d.message || 'Comando enviado ao motor!', 'ok');
          refreshStatus();
        });
        return;
      }
      withBusyBtn(cmdBtn, 'Consultando...', async () => {
        const d = await (await fetch('/api/ai/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ prompt: raw }) })).json();
        const insightEl = document.getElementById('copilot-insight');
        if (insightEl && d.answer) insightEl.textContent = String(d.answer).split('\n')[0].slice(0, 140);
        const out = document.getElementById('ai-chat-output');
        if (out) { out.hidden = false; out.textContent = '[' + (d.backend || 'offline') + ']\n' + (d.answer || ''); }
        showToast('Resposta do Copiloto pronta!', 'ok');
      });
    });
  }

  async function loadChannelTelemetry() {
    const strip = document.getElementById('channel-telemetry');
    try {
      const res = await fetch('/api/channel');
      const d = await res.json();
      _lastChannelData = d;
      const keys = d.keys || {};
      const vs = d.video_stats || {};
      if (strip) {
        strip.innerHTML = '';

        const tt = document.createElement('span');
        tt.className = keys.tiktok ? 'pill pill-tt' : 'pill';
        tt.textContent = keys.tiktok
          ? ('TikTok API: ' + (keys.tiktok_mode || 'inbox').toUpperCase() + ' (' + (vs.tiktok_sent || 0) + ' env)')
          : 'TikTok: Aguardando OAuth';
        strip.appendChild(tt);

        const ch = document.createElement('span');
        if (d.channel && d.channel.connected) {
          ch.className = 'pill pill-ok';
          ch.textContent = 'YouTube: ' + d.channel.title + ' (' + d.channel.videos + ' vids)';
        } else {
          ch.className = 'pill pill-err';
          ch.textContent = 'YouTube offline';
        }
        strip.appendChild(ch);

        const tts = document.createElement('span');
        tts.className = 'pill';
        tts.textContent = 'Voz: ' + (d.tts_engine || 'Kokoro').split('(')[0].trim();
        strip.appendChild(tts);

        const vid = document.createElement('span');
        vid.className = 'pill pill-info';
        vid.textContent = 'Acervo: ' + d.local_videos + ' MP4';
        strip.appendChild(vid);

        const llm = document.createElement('span');
        const hasCloud = keys.openrouter || keys.gemini || keys.openai;
        llm.className = (hasCloud || (d.local_llm && d.local_llm.online)) ? 'pill pill-ok' : 'pill';
        llm.textContent = hasCloud ? 'IA Nuvem + BM25' : ((d.local_llm && d.local_llm.online) ? ('IA Local: ' + d.local_llm.model) : 'Heuristica Offline');
        strip.appendChild(llm);
      }

      const elChV = document.getElementById('kpi-channel-val');
      const elChS = document.getElementById('kpi-channel-sub');
      if (elChV && elChS) {
        elChV.textContent = (keys.tiktok ? 'TikTok ATIVO' : 'TikTok Pend') + ' • ' + ((d.channel && d.channel.connected) ? (d.channel.videos + ' YT') : 'YT Off');
        elChS.textContent = (vs.tiktok_sent || 0) + ' TikTok env • ' + ((d.channel && d.channel.connected) ? (d.channel.views + ' views YT') : 'Conecte YouTube');
      }
      const elQV = document.getElementById('kpi-queue-val');
      const elQS = document.getElementById('kpi-queue-sub');
      if (elQV && elQS) {
        elQV.textContent = (vs.approved || 0) + ' aprovados';
        elQS.textContent = (vs.tiktok_ready || 0) + ' p/ TikTok • ' + (vs.queued || 0) + ' fila YT';
      }
      const evo = d.background_evolution || [];
      const elBgV = document.getElementById('kpi-bg-val');
      const elBgS = document.getElementById('kpi-bg-sub');
      if (elBgV && elBgS) {
        elBgV.textContent = (d.gameplay_count || 0) + ' fundos UCB1';
        const topScore = evo.length ? Number(evo[0].avg_quality ?? evo[0].avg_score ?? 0) : 0;
        elBgS.textContent = evo.length
          ? ('Top: ' + evo[0].style + (topScore > 0 ? (' (' + Math.round(topScore) + '/100)') : ''))
          : 'Troca multi-cena 4.2s';
      }
      const elAiV = document.getElementById('kpi-ai-val');
      const elAiS = document.getElementById('kpi-ai-sub');
      if (elAiV && elAiS) {
        elAiV.textContent = (d.tts_engine || 'Kokoro PT-BR').split('(')[0].trim();
        elAiS.textContent = (keys.openrouter || keys.gemini) ? 'IA Nuvem + Opus 5D' : 'Heuristica Offline';
      }
      updateCopilotInsight();
    } catch (e) {}
  }

  async function loadScheduler() {
    const info = document.getElementById('scheduler-info');
    if (!info) return;
    try {
      const [s, pl] = await Promise.all([
        fetch('/api/scheduler').then((r) => r.json()),
        fetch('/api/autopublish/plan').then((r) => r.json()).catch(() => null),
      ]);
      _lastSchedulerData = s;
      const ch = (pl && pl.channels) || {};
      const ttTxt = ch.tiktok ? ('TT ' + ch.tiktok.daily_used + '/' + ch.tiktok.daily_cap) : '';
      const ytTxt = ch.youtube ? ('YT ' + ch.youtube.daily_used + '/' + ch.youtube.daily_cap) : '';
      const budget = [ttTxt, ytTxt].filter(Boolean).join(' • ');
      info.textContent = (s.enabled ? 'Ativo' : 'Pausado') + ' | ' + (budget || (s.platform || 'tiktok_rewards')) + ' | ' + s.interval_hours + 'h | Ciclos: ' + s.runs_completed;
      updateCopilotInsight();
    } catch (e) {}
  }

  document.getElementById('btn-toggle-scheduler').addEventListener('click', () => withBusyBtn(document.getElementById('btn-toggle-scheduler'), 'Salvando...', async () => {
    const cur = await (await fetch('/api/scheduler')).json();
    const selPlat = document.getElementById('cut-platform') ? document.getElementById('cut-platform').value : 'tiktok_rewards';
    await fetch('/api/scheduler', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ enabled: !cur.enabled, platform: selPlat, auto_publish: true }) });
    await loadScheduler();
    showToast(!cur.enabled ? 'Piloto 24/7 ativado!' : 'Piloto 24/7 pausado.', 'ok');
  }));

  document.getElementById('btn-trigger-autopilot').addEventListener('click', () => withBusyBtn(document.getElementById('btn-trigger-autopilot'), 'Enfileirando...', async () => {
    const selPlat = document.getElementById('cut-platform') ? document.getElementById('cut-platform').value : 'tiktok_rewards';
    startOptimisticRender('1/5 Iniciando lote automatico (' + selPlat + ')...');
    const resp = await fetch('/api/scheduler', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ run_now: true, niche: 'all', platform: selPlat, auto_publish: true }) });
    const data = await resp.json();
    showToast(data.message || 'Lote multi-nicho iniciado!', 'ok');
    refreshStatus();
  }));

  /* Segmented Platform Pills <-> Select & Live 9:16 Stage Preview */
  const cutSourceEl = document.getElementById('cut-source');
  const cutNicheEl = document.getElementById('cut-niche');
  const cutPlatformEl = document.getElementById('cut-platform');
  const cutLayoutEl = document.getElementById('cut-layout');
  const voiceScriptEl = document.getElementById('voice-script');
  const voiceHookEl = document.getElementById('voice-hook');
  const phoneFrame = document.getElementById('phone-preview-frame');
  const phoneBgImg = document.getElementById('phone-preview-bg');
  const phoneStage = document.getElementById('phone-preview-stage');
  const previewHookBox = document.getElementById('preview-hook-title');
  const previewSubsBox = document.getElementById('preview-subs-line');
  const hookMeterLabel = document.getElementById('hook-meter-label');
  const previewPlatTag = document.getElementById('preview-platform-tag');
  const voicePaceMeta = document.getElementById('voice-pace-meta');
  const layoutTiles = Array.from(document.querySelectorAll('.layout-tile'));
  const platformPills = Array.from(document.querySelectorAll('.platform-pill'));

  const PLATFORM_TAGS = {
    tiktok_rewards: 'TikTok 61–75s',
    youtube_shorts: 'YouTube 15–45s',
    instagram_reels: 'Reels 15–58s',
  };

  function syncPlatformSelection(plat) {
    const val = plat || 'tiktok_rewards';
    if (cutPlatformEl) {
      const opt = Array.from(cutPlatformEl.options).find((o) => o.value === val);
      if (opt) cutPlatformEl.value = val;
    }
    platformPills.forEach((p) => p.setAttribute('aria-pressed', String(p.getAttribute('data-platform') === val)));
    if (previewPlatTag) previewPlatTag.textContent = PLATFORM_TAGS[val] || val;
  }

  platformPills.forEach((p) => {
    p.addEventListener('click', () => syncPlatformSelection(p.getAttribute('data-platform')));
  });
  if (cutPlatformEl) {
    syncPlatformSelection('tiktok_rewards');
    cutPlatformEl.addEventListener('change', () => syncPlatformSelection(cutPlatformEl.value));
  }

  function extractYouTubeId(rawUrl) {
    const s = String(rawUrl || '').trim();
    const m = s.match(/(?:youtube\.com\/(?:watch\?v=|shorts\/|embed\/)|youtu\.be\/)([A-Za-z0-9_-]{11})/);
    return m ? m[1] : '';
  }

  function renderPhonePreviewStage(layoutVal) {
    if (!phoneFrame || !phoneStage) return;
    const lay = layoutVal || 'blur_bg';
    phoneFrame.setAttribute('data-layout', lay);
    phoneStage.innerHTML = '';
    if (lay === 'split_top_bottom') {
      const topZ = document.createElement('div');
      topZ.className = 'phone-zone-card';
      topZ.textContent = 'Topo: Video / Podcast Principal';
      const botZ = document.createElement('div');
      botZ.className = 'phone-zone-card';
      botZ.textContent = 'Base: Gameplay Multi-Cena 9:16';
      phoneStage.appendChild(topZ);
      phoneStage.appendChild(botZ);
    } else if (lay === 'center_crop') {
      const faceZ = document.createElement('div');
      faceZ.className = 'phone-zone-card';
      faceZ.style.borderStyle = 'solid';
      faceZ.style.borderColor = 'rgba(96, 165, 250, 0.85)';
      faceZ.textContent = 'Enquadramento 9:16 com Rastreio Facial';
      phoneStage.appendChild(faceZ);
    } else {
      const midZ = document.createElement('div');
      midZ.className = 'phone-zone-card';
      midZ.textContent = 'Corte 16:9 Centralizado + Fundo Desfocado';
      phoneStage.appendChild(midZ);
    }
    layoutTiles.forEach((tile) => {
      tile.setAttribute('aria-pressed', String(tile.getAttribute('data-layout') === lay));
    });
  }

  function renderKaraokeWords(words) {
    if (!previewSubsBox) return;
    const list = (words && words.length) ? words.slice(0, 3) : ['PALAVRA', 'POR', 'PALAVRA'];
    previewSubsBox.innerHTML = '';
    const active = _karaokeWordIdx % list.length;
    list.forEach((w, idx) => {
      const sp = document.createElement('span');
      sp.textContent = (idx > 0 ? ' ' : '') + String(w).toUpperCase();
      if (idx === active) sp.className = 'kw-on';
      previewSubsBox.appendChild(sp);
    });
  }

  function syncWorkstationPreview() {
    if (cutLayoutEl) renderPhonePreviewStage(cutLayoutEl.value);
    if (cutSourceEl && phoneBgImg) {
      const ytid = extractYouTubeId(cutSourceEl.value);
      if (ytid) {
        phoneBgImg.src = 'https://i.ytimg.com/vi/' + ytid + '/hqdefault.jpg';
        phoneBgImg.hidden = false;
        if (hookMeterLabel) hookMeterLabel.textContent = 'Link YT detectado';
      } else {
        phoneBgImg.hidden = true;
        phoneBgImg.removeAttribute('src');
      }
    }
    if (previewHookBox && voiceHookEl) {
      const hk = voiceHookEl.value.trim().toUpperCase() || 'GANCHO DE RETENCAO 3S';
      previewHookBox.textContent = hk.slice(0, 34);
    }
    let curWords = ['PALAVRA', 'POR', 'PALAVRA'];
    if (voiceScriptEl && voicePaceMeta) {
      const words = voiceScriptEl.value.trim().split(/\s+/).filter(Boolean);
      const estSec = Math.round(words.length / 2.8);
      voicePaceMeta.textContent = words.length + ' palavras • ~' + estSec + 's estimados (ideal: 75-110 palavras)';
      if (words.length) curWords = words;
      if (hookMeterLabel && !extractYouTubeId(cutSourceEl ? cutSourceEl.value : '')) {
        const strong = words.length >= 60 && words.length <= 125;
        hookMeterLabel.textContent = strong ? 'Ritmo Ideal (85+ pts)' : (words.length > 0 ? 'Ajustar duracao' : 'Pronto');
      }
    }
    renderKaraokeWords(curWords);
  }

  layoutTiles.forEach((tile) => {
    tile.addEventListener('click', () => {
      const lay = tile.getAttribute('data-layout') || 'blur_bg';
      if (cutLayoutEl) cutLayoutEl.value = lay;
      renderPhonePreviewStage(lay);
    });
  });
  if (cutLayoutEl) cutLayoutEl.addEventListener('change', () => renderPhonePreviewStage(cutLayoutEl.value));
  if (cutSourceEl) cutSourceEl.addEventListener('input', syncWorkstationPreview);
  if (voiceScriptEl) voiceScriptEl.addEventListener('input', syncWorkstationPreview);
  if (voiceHookEl) voiceHookEl.addEventListener('input', syncWorkstationPreview);
  if (cutNicheEl && hookMeterLabel) {
    cutNicheEl.addEventListener('change', () => {
      if (previewHookBox) previewHookBox.textContent = ('NICHO: ' + cutNicheEl.options[cutNicheEl.selectedIndex].text.split(',')[0]).toUpperCase().slice(0, 32);
    });
  }
  setInterval(() => {
    _karaokeWordIdx += 1;
    const words = voiceScriptEl ? voiceScriptEl.value.trim().split(/\s+/).filter(Boolean) : [];
    renderKaraokeWords(words);
  }, 680);

  document.getElementById('cut-form').addEventListener('submit', (e) => {
    e.preventDefault();
    const btn = document.getElementById('btn-run-cut');
    withBusyBtn(btn, 'Na fila...', async () => {
      startOptimisticRender('1/5 Preparando coleta e cortes 9:16...');
      const body = {
        niche: cutNicheEl.value,
        platform: cutPlatformEl.value,
        layout: cutLayoutEl.value,
        clips: Number(document.getElementById('cut-clips').value || 1),
        source: cutSourceEl.value.trim(),
        playlist: document.getElementById('cut-playlist').value.trim(),
        auto_publish: document.getElementById('cut-auto-publish').checked,
      };
      const res = await fetch('/api/run', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      const data = await res.json();
      showToast(data.message || 'Processamento na fila!', res.ok ? 'ok' : 'err');
      refreshStatus();
    });
  });

  document.getElementById('btn-sync-gameplay').addEventListener('click', () => withBusyBtn(document.getElementById('btn-sync-gameplay'), 'Baixando...', async () => {
    startOptimisticRender('1/5 Buscando novo fundo 9:16 sem copyright...');
    const res = await fetch('/api/gameplay/sync', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ niche: cutNicheEl ? cutNicheEl.value : 'geral' }) });
    const d = await res.json();
    showToast(d.message || 'Novo fundo na fila!', 'ok');
    refreshStatus();
  }));

  document.getElementById('btn-voice-preview').addEventListener('click', () => withBusyBtn(document.getElementById('btn-voice-preview'), 'Sintetizando...', async () => {
    const previewBox = document.getElementById('voice-preview-box');
    const txt = (voiceScriptEl && voiceScriptEl.value.trim()) || 'Esse é um teste de voz em português brasileiro sem distorção.';
    const res = await fetch('/api/voice-preview', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        style: document.getElementById('voice-style').value,
        script: txt,
        humanize: document.getElementById('voice-humanize').checked,
      }),
    });
    const data = await res.json();
    if (!res.ok) { showToast(data.message || 'Erro no preview', 'err'); return; }
    previewBox.innerHTML = '';
    const info = document.createElement('small');
    info.textContent = 'Amostra pronta (' + data.duration + 's):';
    const aud = document.createElement('audio');
    aud.controls = true;
    aud.autoplay = true;
    aud.src = '/media-preview/' + encodeURIComponent(data.audio_file) + '?t=' + Date.now();
    previewBox.appendChild(info);
    previewBox.appendChild(aud);
    showToast('Audio Kokoro PT-BR gerado!', 'ok');
  }));

  document.getElementById('voice-form').addEventListener('submit', (e) => {
    e.preventDefault();
    const bg = document.getElementById('voice-bg');
    const bgErr = document.getElementById('voice-bg-err');
    const scErr = document.getElementById('voice-script-err');
    bgErr.hidden = !!bg.value.trim();
    scErr.hidden = !!(voiceScriptEl && voiceScriptEl.value.trim());
    bg.setAttribute('aria-invalid', String(!bg.value.trim()));
    if (voiceScriptEl) voiceScriptEl.setAttribute('aria-invalid', String(!voiceScriptEl.value.trim()));
    if (!bg.value.trim() || !voiceScriptEl.value.trim()) return;

    withBusyBtn(document.getElementById('btn-run-voice'), 'Na fila...', async () => {
      startOptimisticRender('1/5 Escrevendo roteiro & voz Kokoro PT-BR...');
      const res = await fetch('/api/narrate', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          style: document.getElementById('voice-style').value,
          hook_title: voiceHookEl.value.trim(),
          bg_video: bg.value.trim(),
          script: voiceScriptEl.value.trim(),
          humanize: document.getElementById('voice-humanize').checked,
          auto_publish: document.getElementById('voice-auto-publish').checked,
          playlist: document.getElementById('voice-playlist').value.trim(),
        }),
      });
      const data = await res.json();
      showToast(data.message || 'Narracao na fila!', 'ok');
      refreshStatus();
    });
  });

  /* Accessible Inspector Modal (<dialog>) with Focus Management */
  function openShortInspector(v, triggerEl) {
    if (!dlg) return;
    _inspectorTriggerEl = triggerEl || document.activeElement;
    document.getElementById('dlg-title').textContent = v.title || v.filename;
    const body = document.getElementById('dlg-body');
    body.innerHTML = '';

    const player = document.createElement('video');
    player.controls = true;
    player.preload = 'metadata';
    player.style.maxHeight = '340px';
    player.style.margin = '0 auto';
    player.src = '/media/' + encodeURIComponent(v.filename);
    body.appendChild(player);

    if (v.opus_scorecard) {
      const os = v.opus_scorecard;
      const box = document.createElement('div');
      box.className = 'diag-box';
      const hd = document.createElement('strong');
      hd.textContent = 'Opus Runbook Scorecard: ' + os.opus_score + '/100 — ' + os.band;
      box.appendChild(hd);
      const dims = document.createElement('div');
      dims.className = 'opus-dims';
      dims.style.marginTop = '8px';
      const labels = {
        first_frame_contrast: '1o Frame',
        hook_0_3s: 'Gancho 0-3s',
        rehook_cadence: 'Ritmo/Rehook',
        payoff_no_bloat: 'Payoff Final',
        audio_clarity: 'Audio/Legenda',
      };
      Object.entries(os.dimensions || {}).forEach(([k, val]) => {
        const d = document.createElement('div');
        d.className = 'opus-dim-item';
        d.textContent = (labels[k] || k) + ': ' + val + '/20';
        dims.appendChild(d);
      });
      box.appendChild(dims);
      if (os.flaws && os.flaws.length) {
        const fl = document.createElement('div');
        fl.className = 'topic-meta';
        fl.style.marginTop = '6px';
        fl.textContent = 'Melhorias: ' + os.flaws.join(' • ');
        box.appendChild(fl);
      }
      body.appendChild(box);
    }

    if (v.thumb_16x9) {
      const img = document.createElement('img');
      img.className = 'thumb';
      img.src = '/media/' + encodeURIComponent(v.thumb_16x9);
      img.alt = 'Capa 16:9 ' + (v.title || v.filename);
      body.appendChild(img);
    }
    if (v.caption) {
      const capWrap = document.createElement('div');
      capWrap.style.margin = '12px 0';
      const capHead = document.createElement('div');
      capHead.style.display = 'flex';
      capHead.style.justifyContent = 'space-between';
      capHead.style.alignItems = 'center';
      capHead.style.marginBottom = '6px';
      const capTitle = document.createElement('strong');
      capTitle.textContent = 'Legenda & Hashtags para TikTok / Shorts:';
      capHead.appendChild(capTitle);

      const btnCopyTop = document.createElement('button');
      btnCopyTop.type = 'button';
      btnCopyTop.className = 'btn btn-secondary btn-sm';
      btnCopyTop.textContent = '📋 Copiar Legenda';
      btnCopyTop.addEventListener('click', async () => {
        const ok = await copyTextToClipboard(v.caption);
        showToast(ok ? 'Legenda copiada! Abra o TikTok e cole em "Adicionar descrição".' : 'Selecione e copie o texto abaixo.', ok ? 'ok' : 'info');
      });
      capHead.appendChild(btnCopyTop);
      capWrap.appendChild(capHead);

      const ta = document.createElement('textarea');
      ta.className = 'form-input';
      ta.rows = 4;
      ta.style.width = '100%';
      ta.style.fontFamily = 'monospace';
      ta.style.fontSize = '12px';
      ta.value = v.caption;
      ta.addEventListener('click', () => ta.select());
      capWrap.appendChild(ta);
      body.appendChild(capWrap);
    }

    const acts = document.createElement('div');
    acts.className = 'actions';

    const btnTt = document.createElement('button');
    btnTt.type = 'button';
    btnTt.className = 'btn btn-tiktok btn-sm';
    btnTt.textContent = (v.tiktok && v.tiktok.publish_id) ? 'Reenviar TikTok (Inbox)' : 'Publicar TikTok (Inbox)';
    btnTt.addEventListener('click', () => withBusyBtn(btnTt, 'Enviando TT...', async () => {
      const r = await fetch('/api/publish-tiktok', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ filename: v.filename, mode: 'inbox' }) });
      const d = await r.json();
      if (d.publish_id && v.caption) {
        await copyTextToClipboard(v.caption);
        showToast('Enviado ao TikTok! Legenda copiada — basta colar em "Adicionar descrição" no app.', 'ok');
      } else {
        showToast(d.publish_id ? ('Enviado ao TikTok (' + d.mode + '): ' + d.publish_id) : (d.reason || d.message || d.status), d.publish_id ? 'ok' : 'info');
      }
      if (d.publish_id) { await loadVideos(); await loadChannelTelemetry(); }
    }));
    acts.appendChild(btnTt);

    const btnYt = document.createElement('button');
    btnYt.type = 'button';
    btnYt.className = 'btn btn-success btn-sm';
    btnYt.textContent = (v.youtube && v.youtube.url) ? 'Republicar YouTube' : 'Publicar YouTube';
    btnYt.addEventListener('click', () => withBusyBtn(btnYt, 'Enviando...', async () => {
      const r = await fetch('/api/publish', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ filename: v.filename }) });
      const d = await r.json();
      showToast(r.ok ? ('Publicado no YouTube: ' + (d.url || 'OK')) : (d.message || 'Salvo na fila'), r.ok ? 'ok' : 'info');
      await loadVideos();
      await loadChannelTelemetry();
    }));
    acts.appendChild(btnYt);

    const btnIg = document.createElement('button');
    btnIg.type = 'button';
    btnIg.className = 'btn btn-secondary btn-sm';
    btnIg.textContent = 'Instagram Reels';
    btnIg.addEventListener('click', () => withBusyBtn(btnIg, 'Postando...', async () => {
      const r = await fetch('/api/publish-instagram', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ filename: v.filename }) });
      const d = await r.json();
      showToast(d.url ? ('Publicado no IG: ' + d.url) : (d.reason || d.status), d.url ? 'ok' : 'info');
    }));
    acts.appendChild(btnIg);

    const btnDel = document.createElement('button');
    btnDel.type = 'button';
    btnDel.className = 'btn btn-danger btn-sm';
    btnDel.textContent = 'Excluir';
    btnDel.addEventListener('click', () => withBusyBtn(btnDel, 'Excluindo...', async () => {
      await fetch('/api/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ filename: v.filename }) });
      dlg.close();
      showToast('Video removido do acervo.', 'info');
      await loadVideos();
      await loadChannelTelemetry();
    }));
    acts.appendChild(btnDel);
    body.appendChild(acts);
    dlg.showModal();
    const closeBtn = document.getElementById('dlg-close');
    if (closeBtn) closeBtn.focus();
  }

  if (dlg) {
    document.getElementById('dlg-close').addEventListener('click', () => dlg.close());
    dlg.addEventListener('click', (e) => { if (e.target === dlg) dlg.close(); });
    dlg.addEventListener('close', () => {
      if (_inspectorTriggerEl && typeof _inspectorTriggerEl.focus === 'function') {
        _inspectorTriggerEl.focus();
      }
      _inspectorTriggerEl = null;
    });
  }

  /* Clean Acervo Cards + Fast TikTok/YouTube Delivery & Filter Pills */
  function renderVideosGrid() {
    const box = document.getElementById('videos-list');
    if (!box) return;
    const filterTxt = (document.getElementById('studio-search') ? document.getElementById('studio-search').value : '').trim().toLowerCase();
    const filtered = _videosCache.filter((v) => {
      if (filterTxt && !(v.title + ' ' + v.caption + ' ' + v.filename).toLowerCase().includes(filterTxt)) return false;
      const visOk = v.visual_audit ? !!v.visual_audit.approved : !!(v.validation && v.validation.valid);
      const ttSent = !!(v.tiktok && v.tiktok.publish_id);
      if (_acervoFilter === 'tiktok_ready') return visOk && !ttSent;
      if (_acervoFilter === 'tiktok_sent') return ttSent;
      if (_acervoFilter === 'approved') return visOk;
      if (_acervoFilter === 'queued') return !!v.queued_for_auto_publish;
      if (_acervoFilter === 'published') return !!(v.youtube && v.youtube.url);
      return true;
    });
    if (!filtered.length) {
      box.innerHTML = '';
      const empty = document.createElement('div');
      empty.className = 'empty-state';
      empty.textContent = filterTxt ? 'Nenhum Short corresponde ao filtro.' : 'Nenhum video nesta categoria. Use Criar & Radar ou ajuste o filtro.';
      box.appendChild(empty);
      return;
    }
    box.innerHTML = '';
    filtered.forEach((v) => {
      const card = document.createElement('article');
      card.className = 'video-card';
      const h3 = document.createElement('h3');
      h3.textContent = v.title || v.filename;
      card.appendChild(h3);

      const badges = document.createElement('div');
      badges.className = 'telemetry-strip';
      const visOk = v.visual_audit ? !!v.visual_audit.approved : !!(v.validation && v.validation.valid);
      const statusPill = document.createElement('span');
      statusPill.className = visOk ? 'pill pill-ok' : 'pill pill-err';
      statusPill.textContent = visOk
        ? ('Pronto' + (v.validation && v.validation.duration ? (' • ' + v.validation.duration + 's') : ''))
        : ('Reprovado: ' + ((v.visual_audit && v.visual_audit.reject_reasons && v.visual_audit.reject_reasons[0]) || 'verificar'));
      badges.appendChild(statusPill);

      const ttPill = document.createElement('span');
      if (v.tiktok && v.tiktok.publish_id) {
        ttPill.className = 'pill pill-tt';
        ttPill.textContent = 'TikTok: ' + (v.tiktok.mode || 'inbox').toUpperCase();
        badges.appendChild(ttPill);
      } else if (visOk) {
        ttPill.className = 'pill';
        ttPill.textContent = 'TikTok: Pronto';
        badges.appendChild(ttPill);
      }

      if (v.youtube && v.youtube.url) {
        const ytPill = document.createElement('span');
        ytPill.className = 'pill pill-yt';
        ytPill.textContent = 'YouTube: OK';
        badges.appendChild(ytPill);
      }

      const opus = v.opus_scorecard;
      if (opus) {
        const opPill = document.createElement('span');
        opPill.className = opus.opus_score >= 70 ? 'pill pill-info' : 'pill';
        opPill.textContent = 'Opus ' + opus.opus_score + '/100';
        badges.appendChild(opPill);
      }
      card.appendChild(badges);

      if (opus && typeof opus.opus_score === 'number') {
        const trk = document.createElement('div');
        trk.className = 'opus-mini-track';
        trk.title = 'Opus Runbook Score: ' + opus.opus_score + '/100';
        const fl = document.createElement('div');
        fl.className = 'opus-mini-fill';
        fl.style.width = Math.max(5, Math.min(100, opus.opus_score)) + '%';
        trk.appendChild(fl);
        card.appendChild(trk);
      }

      const vid = document.createElement('video');
      vid.controls = true;
      vid.preload = 'metadata';
      vid.src = '/media/' + encodeURIComponent(v.filename);
      card.appendChild(vid);

      if (v.caption || v.thumb_16x9) {
        const det = document.createElement('details');
        det.className = 'meta-fold';
        const sm = document.createElement('summary');
        sm.textContent = 'Ver roteiro & hashtags SEO';
        det.appendChild(sm);
        if (v.caption) {
          const pr = document.createElement('pre');
          pr.className = 'meta-pre';
          pr.textContent = v.caption;
          det.appendChild(pr);
        }
        card.appendChild(det);
      }

      const acts = document.createElement('div');
      acts.className = 'actions';
      if (visOk && !(v.tiktok && v.tiktok.publish_id)) {
        const btnFastTt = document.createElement('button');
        btnFastTt.type = 'button';
        btnFastTt.className = 'btn btn-tiktok btn-sm';
        btnFastTt.textContent = 'Postar TikTok';
        btnFastTt.addEventListener('click', () => withBusyBtn(btnFastTt, 'Enviando TT...', async () => {
          const r = await fetch('/api/publish-tiktok', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ filename: v.filename, mode: 'inbox' }) });
          const d = await r.json();
          if (d.publish_id && v.caption) {
            await copyTextToClipboard(v.caption);
            showToast('Enviado ao TikTok! Legenda copiada — basta colar em "Adicionar descrição" no app.', 'ok');
          } else {
            showToast(d.publish_id ? ('Enviado ao TikTok (' + d.mode + '): ' + d.publish_id) : (d.reason || d.message || d.status), d.publish_id ? 'ok' : 'info');
          }
          if (d.publish_id) { await loadVideos(); await loadChannelTelemetry(); }
        }));
        acts.appendChild(btnFastTt);
      }

      if (v.caption) {
        const btnCopyCap = document.createElement('button');
        btnCopyCap.type = 'button';
        btnCopyCap.className = 'btn btn-secondary btn-sm';
        btnCopyCap.title = 'Copiar título e hashtags para colar no TikTok';
        btnCopyCap.textContent = '📋 Legenda';
        btnCopyCap.addEventListener('click', async () => {
          const ok = await copyTextToClipboard(v.caption);
          showToast(ok ? 'Legenda e hashtags copiadas! Abra o TikTok e cole no campo "Adicionar descrição".' : 'Erro ao copiar legenda.', ok ? 'ok' : 'err');
        });
        acts.appendChild(btnCopyCap);
      }

      const btnInspect = document.createElement('button');
      btnInspect.type = 'button';
      btnInspect.className = 'btn btn-primary btn-sm';
      btnInspect.style.flex = '1';
      btnInspect.textContent = 'Inspecionar & Publicar';
      btnInspect.addEventListener('click', () => openShortInspector(v, btnInspect));
      acts.appendChild(btnInspect);
      card.appendChild(acts);
      box.appendChild(card);
    });
  }

  async function loadVideos() {
    const box = document.getElementById('videos-list');
    if (box && !_videosCache.length) renderSkeletons(box, 3);
    try {
      const data = await (await fetch('/api/videos')).json();
      _videosCache = data.videos || [];
      renderVideosGrid();
      updateCopilotInsight();
    } catch (e) {
      if (box) box.textContent = 'Erro ao carregar acervo: ' + e.message;
    }
  }
  document.querySelectorAll('.acervo-chip').forEach((chip) => {
    chip.addEventListener('click', () => {
      _acervoFilter = chip.getAttribute('data-acervo-filter') || 'all';
      document.querySelectorAll('.acervo-chip').forEach((c) => c.setAttribute('aria-pressed', String(c === chip)));
      renderVideosGrid();
    });
  });
  document.getElementById('btn-refresh-videos').addEventListener('click', loadVideos);

  document.getElementById('btn-auto-validate-all').addEventListener('click', () => withBusyBtn(document.getElementById('btn-auto-validate-all'), 'Validando frames...', async () => {
    const r = await fetch('/api/auto-validate-all', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ auto_publish: true }) });
    const d = await r.json();
    showToast('Auditoria: ' + (d.approved || 0) + ' aprovados, ' + (d.rejected || 0) + ' reprovados', d.rejected ? 'err' : 'ok');
    await loadVideos();
    await loadChannelTelemetry();
  }));

  document.getElementById('btn-optimize-all').addEventListener('click', () => withBusyBtn(document.getElementById('btn-optimize-all'), 'Otimizando IA...', async () => {
    const r = await fetch('/api/optimize', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
    const d = await r.json();
    showToast((d.optimized_count || 0) + ' videos otimizados!', 'ok');
    await loadVideos();
  }));

  /* Editorial Topic Media Builder */
  const KIND_ART = {
    noticia: { bg: 'linear-gradient(135deg, #7F1D1D 0%, #B91C1C 100%)', label: 'Jornalismo ao vivo', sub: 'Manchete pronta para roteiro' },
    ciencia: { bg: 'linear-gradient(135deg, #1E3A8A 0%, #2563EB 100%)', label: 'Ciencia & Mundo', sub: 'Fato viral validado' },
    anime: { bg: 'linear-gradient(135deg, #831843 0%, #DB2777 100%)', label: 'Anime & Teorias', sub: 'Tendencia global' },
    cultura: { bg: 'linear-gradient(135deg, #701A75 0%, #A21CAF 100%)', label: 'Cultura Pop', sub: 'Analise e curiosidade' },
    podcast: { bg: 'linear-gradient(135deg, #4C1D95 0%, #6D28D9 100%)', label: 'Podcasts & Cortes', sub: 'Clipe de debate' },
    financas: { bg: 'linear-gradient(135deg, #134E4A 0%, #0D9488 100%)', label: 'Dinheiro & IA', sub: 'Nicho alto RPM' },
    psicologia: { bg: 'linear-gradient(135deg, #78350F 0%, #D97706 100%)', label: 'Psicologia', sub: 'Mente & comportamento' },
    saude: { bg: 'linear-gradient(135deg, #0C4A6E 0%, #0284C7 100%)', label: 'Saude & Neuro', sub: 'Habitos & performance' },
  };
  function createFallbackCover(art) {
    const inner = document.createElement('div');
    inner.className = 'topic-fallback-art';
    inner.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><polygon points="5 3 19 12 5 21 5 3"/></svg><span></span><small></small>';
    inner.querySelector('span').textContent = art.label;
    inner.querySelector('small').textContent = art.sub;
    return inner;
  }
  function buildTopicMediaNode(kind, label, imageUrl, statText) {
    const art = KIND_ART[kind] || KIND_ART.podcast;
    const wrap = document.createElement('div');
    wrap.className = 'topic-media';
    wrap.style.background = art.bg;
    if (imageUrl) {
      const img = document.createElement('img');
      img.className = 'topic-thumb';
      img.loading = 'lazy';
      img.src = imageUrl;
      img.alt = label || 'Capa';
      img.onerror = () => {
        img.remove();
        wrap.appendChild(createFallbackCover(art));
      };
      wrap.appendChild(img);
    } else {
      wrap.appendChild(createFallbackCover(art));
    }
    const tag = document.createElement('span');
    tag.className = 'topic-tag';
    tag.textContent = label || art.label;
    wrap.appendChild(tag);
    if (statText) {
      const sb = document.createElement('span');
      sb.className = 'topic-stat';
      sb.textContent = statText;
      wrap.appendChild(sb);
    }
    return wrap;
  }

  /* Segmented Explorer Radars with Top-6 Pagination */
  function setRadarMode(mode) {
    _activeRadarMode = mode || 'horizon';
    _radarVisibleLimit = 6;
    document.querySelectorAll('.radar-mode-btn').forEach((b) => {
      b.setAttribute('aria-pressed', String(b.getAttribute('data-radar-mode') === _activeRadarMode));
    });
    const hBox = document.getElementById('horizon-radar-box');
    const aBox = document.getElementById('anime-radar-box');
    const nBox = document.getElementById('world-news-box');
    const hChips = document.getElementById('horizon-cat-chips');
    const aChips = document.getElementById('anime-cat-chips');
    if (hBox) hBox.hidden = _activeRadarMode !== 'horizon';
    if (aBox) aBox.hidden = _activeRadarMode !== 'anime';
    if (nBox) nBox.hidden = _activeRadarMode !== 'news';
    if (hChips) hChips.hidden = _activeRadarMode !== 'horizon';
    if (aChips) aChips.hidden = _activeRadarMode !== 'anime';
  }

  function updateRadarMoreBtn(totalCount) {
    const moreBtn = document.getElementById('btn-radar-more');
    if (!moreBtn) return;
    const rem = totalCount - _radarVisibleLimit;
    if (rem > 0) {
      moreBtn.hidden = false;
      moreBtn.textContent = 'Ver mais pautas (+' + rem + ')';
    } else {
      moreBtn.hidden = true;
    }
  }

  function renderHorizonSlice() {
    const box = document.getElementById('horizon-radar-box');
    if (!box) return;
    const items = _horizonItemsCache;
    if (!items.length) {
      box.innerHTML = '';
      const empty = document.createElement('div');
      empty.className = 'empty-state';
      empty.textContent = 'Nenhuma pauta disponivel neste filtro agora.';
      box.appendChild(empty);
      updateRadarMoreBtn(0);
      return;
    }
    box.innerHTML = '';
    items.slice(0, _radarVisibleLimit).forEach((item) => {
      const kind = item.category_kind || 'geral';
      const card = document.createElement('article');
      card.className = 'topic-card kind-' + kind;
      card.appendChild(buildTopicMediaNode(kind, item.kind_label || item.badge, item.image_url || '', item.metric_badge || ''));
      const body = document.createElement('div');
      body.className = 'topic-body';
      const h3 = document.createElement('h3');
      h3.textContent = item.title_pt || '';
      body.appendChild(h3);
      const meta = document.createElement('div');
      meta.className = 'topic-meta';
      meta.textContent = (item.source ? (item.source + ' • ') : '') + (item.why_viral || '');
      body.appendChild(meta);
      card.appendChild(body);

      const acts = document.createElement('div');
      acts.className = 'topic-actions';
      const btnCut = document.createElement('button');
      btnCut.type = 'button';
      btnCut.className = 'btn btn-primary btn-sm';
      btnCut.textContent = 'Cortar';
      btnCut.addEventListener('click', () => withBusyBtn(btnCut, 'Na fila...', async () => {
        startOptimisticRender('1/5 Coletando corte: ' + (item.title_pt || 'pauta').slice(0, 32));
        const r = await fetch('/api/run', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            niche: item.niche || 'podcast',
            platform: cutPlatformEl.value,
            layout: cutLayoutEl.value,
            clips: Number(document.getElementById('cut-clips').value || 1),
            query: item.youtube_query || item.title_pt,
            playlist: item.playlist || '',
            auto_publish: document.getElementById('cut-auto-publish').checked,
          }),
        });
        const d = await r.json();
        showToast(d.message || 'Corte na fila!', 'ok');
        refreshStatus();
      }));
      const btnNarr = document.createElement('button');
      btnNarr.type = 'button';
      btnNarr.className = 'btn btn-success btn-sm';
      btnNarr.textContent = 'Narrar B-Roll';
      btnNarr.addEventListener('click', () => withBusyBtn(btnNarr, 'Na fila...', async () => {
        startOptimisticRender('1/5 Roteiro + Voz Kokoro: ' + (item.title_pt || 'pauta').slice(0, 28));
        const r = await fetch('/api/narrate', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            horizon_item: item,
            hook_title: item.hook_suggestion || 'DESTAQUE DO DIA',
            style: 'kokoro_alex',
            niche: item.niche || 'podcast',
            bg_video: 'gameplay',
            humanize: true,
          }),
        });
        const d = await r.json();
        showToast(d.message || 'Narracao na fila!', 'ok');
        refreshStatus();
      }));
      acts.appendChild(btnCut);
      acts.appendChild(btnNarr);
      card.appendChild(acts);
      box.appendChild(card);
    });
    updateRadarMoreBtn(items.length);
  }

  async function loadHorizonRadar() {
    setRadarMode('horizon');
    const box = document.getElementById('horizon-radar-box');
    const topic = (document.getElementById('horizon-topic') && document.getElementById('horizon-topic').value) || 'todos';
    renderSkeletons(box, 3);
    try {
      const data = await (await fetch('/api/horizon?topic=' + encodeURIComponent(topic))).json();
      _horizonItemsCache = data.items || [];
      renderHorizonSlice();
    } catch (e) {
      box.textContent = 'Erro ao carregar horizontes: ' + e.message;
      updateRadarMoreBtn(0);
    }
  }

  function renderAnimeSlice() {
    const box = document.getElementById('anime-radar-box');
    if (!box) return;
    const items = _animeItemsCache;
    if (!items.length) {
      box.innerHTML = '';
      const empty = document.createElement('div');
      empty.className = 'empty-state';
      empty.textContent = 'Nenhum anime encontrado nesta frente.';
      box.appendChild(empty);
      updateRadarMoreBtn(0);
      return;
    }
    box.innerHTML = '';
    items.slice(0, _radarVisibleLimit).forEach((a) => {
      const favTxt = a.favourites ? (a.favourites >= 1000 ? Math.round(a.favourites / 1000) + 'k curtidas' : a.favourites + ' curtidas') : '';
      const statTxt = [a.score ? ('Nota ' + a.score + '%') : '', favTxt, a.next_episode ? ('Ep ' + a.next_episode) : ''].filter(Boolean).join(' • ');
      const row = document.createElement('article');
      row.className = 'topic-card kind-anime';
      row.appendChild(buildTopicMediaNode('anime', a.anime_category_label || 'Anime', a.image_url || '', statTxt));
      const body = document.createElement('div');
      body.className = 'topic-body';
      const strong = document.createElement('h3');
      strong.textContent = a.title;
      body.appendChild(strong);
      const meta = document.createElement('div');
      meta.className = 'topic-meta';
      meta.textContent = ((a.genres || []).slice(0, 3).join(', ') || 'Teorias') + (a.season_year ? (' • ' + a.season_year) : '');
      body.appendChild(meta);
      row.appendChild(body);
      const acts = document.createElement('div');
      acts.className = 'topic-actions';
      const btnGo = document.createElement('button');
      btnGo.type = 'button';
      btnGo.className = 'btn btn-primary btn-sm';
      btnGo.textContent = 'Cortar Teoria';
      btnGo.addEventListener('click', () => withBusyBtn(btnGo, 'Na fila...', async () => {
        startOptimisticRender('1/5 Coletando corte de anime: ' + (a.title || '').slice(0, 26));
        const r = await fetch('/api/run', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ niche: 'entretenimento_animes', platform: cutPlatformEl.value, layout: cutLayoutEl.value, clips: 1, query: a.youtube_query, playlist: 'Animes e Teorias - Shorts', auto_publish: true }),
        });
        const d = await r.json();
        showToast(d.message || 'Corte de anime na fila!', 'ok');
        refreshStatus();
      }));
      const btnNarr = document.createElement('button');
      btnNarr.type = 'button';
      btnNarr.className = 'btn btn-success btn-sm';
      btnNarr.textContent = 'Narrar';
      btnNarr.addEventListener('click', () => withBusyBtn(btnNarr, 'Na fila...', async () => {
        startOptimisticRender('1/5 Narrando teoria anime: ' + (a.title || '').slice(0, 26));
        const r = await fetch('/api/narrate', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ horizon_item: { horizon: 'entretenimento_cultura', title_pt: 'Teoria de ' + a.title, hook_suggestion: a.title.toUpperCase().slice(0, 28) }, hook_title: a.title.toUpperCase().slice(0, 28), style: 'kokoro_alex', niche: 'entretenimento_animes', bg_video: 'gameplay', humanize: true }),
        });
        const d = await r.json();
        showToast(d.message || 'Teoria na fila!', 'ok');
        refreshStatus();
      }));
      acts.appendChild(btnGo);
      acts.appendChild(btnNarr);
      row.appendChild(acts);
      box.appendChild(row);
    });
    updateRadarMoreBtn(items.length);
  }

  async function loadAnimes(cat = 'all') {
    setRadarMode('anime');
    const box = document.getElementById('anime-radar-box');
    renderSkeletons(box, 3);
    try {
      const data = await (await fetch('/api/anime/trending?category=' + encodeURIComponent(cat || 'all'))).json();
      _animeItemsCache = data.anime || [];
      renderAnimeSlice();
    } catch (e) {
      box.textContent = 'Erro ao carregar radar anime: ' + e.message;
      updateRadarMoreBtn(0);
    }
  }

  function renderWorldNewsSlice() {
    const box = document.getElementById('world-news-box');
    if (!box) return;
    const items = _newsItemsCache;
    if (!items.length) {
      box.innerHTML = '';
      const empty = document.createElement('div');
      empty.className = 'empty-state';
      empty.textContent = 'Nenhuma manchete retornada agora.';
      box.appendChild(empty);
      updateRadarMoreBtn(0);
      return;
    }
    box.innerHTML = '';
    items.slice(0, _radarVisibleLimit).forEach((n) => {
      const card = document.createElement('article');
      card.className = 'topic-card kind-noticia';
      card.appendChild(buildTopicMediaNode('noticia', n.source || 'Mundo', n.image_url || '', n.category || ''));
      const body = document.createElement('div');
      body.className = 'topic-body';
      const h3 = document.createElement('h3');
      h3.textContent = n.title;
      body.appendChild(h3);
      card.appendChild(body);
      const acts = document.createElement('div');
      acts.className = 'topic-actions';
      const genBtn = document.createElement('button');
      genBtn.type = 'button';
      genBtn.className = 'btn btn-success btn-sm';
      genBtn.textContent = 'Gerar Noticia Kokoro';
      genBtn.addEventListener('click', () => withBusyBtn(genBtn, 'Na fila...', async () => {
        startOptimisticRender('1/5 Gerando Short jornalismo Kokoro PT-BR...');
        const r = await fetch('/api/world-news', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ topic: 'world', auto_publish: true }) });
        const d = await r.json();
        showToast(d.message || 'Noticia na fila!', 'ok');
        refreshStatus();
      }));
      acts.appendChild(genBtn);
      card.appendChild(acts);
      box.appendChild(card);
    });
    updateRadarMoreBtn(items.length);
  }

  async function loadWorldNews() {
    setRadarMode('news');
    const box = document.getElementById('world-news-box');
    renderSkeletons(box, 3);
    try {
      const data = await (await fetch('/api/world-news')).json();
      _newsItemsCache = data.headlines || [];
      renderWorldNewsSlice();
    } catch (e) {
      box.textContent = 'Erro ao buscar noticias: ' + e.message;
      updateRadarMoreBtn(0);
    }
  }

  document.querySelectorAll('.filter-chip:not(.anime-chip):not(.acervo-chip)').forEach((chip) => {
    chip.addEventListener('click', () => {
      const val = chip.getAttribute('data-horizon') || 'todos';
      document.querySelectorAll('.filter-chip:not(.anime-chip):not(.acervo-chip)').forEach((c) => c.setAttribute('aria-pressed', String(c === chip)));
      const sel = document.getElementById('horizon-topic');
      if (sel) sel.value = val;
      loadHorizonRadar();
    });
  });
  document.querySelectorAll('.anime-chip').forEach((chip) => {
    chip.addEventListener('click', () => {
      const cat = chip.getAttribute('data-anime-cat') || 'all';
      document.querySelectorAll('.anime-chip').forEach((c) => c.setAttribute('aria-pressed', String(c === chip)));
      loadAnimes(cat);
    });
  });
  document.getElementById('mode-radar-horizon').addEventListener('click', loadHorizonRadar);
  document.getElementById('mode-radar-anime').addEventListener('click', () => loadAnimes('all'));
  document.getElementById('mode-radar-news').addEventListener('click', loadWorldNews);
  document.getElementById('btn-horizon-radar').addEventListener('click', loadHorizonRadar);
  document.getElementById('horizon-topic').addEventListener('change', loadHorizonRadar);
  document.getElementById('btn-anime-radar').addEventListener('click', () => loadAnimes('all'));
  document.getElementById('btn-world-news').addEventListener('click', () => withBusyBtn(document.getElementById('btn-world-news'), 'Buscando...', loadWorldNews));

  const radarMoreBtn = document.getElementById('btn-radar-more');
  if (radarMoreBtn) {
    radarMoreBtn.addEventListener('click', () => {
      _radarVisibleLimit += 9;
      if (_activeRadarMode === 'horizon') renderHorizonSlice();
      else if (_activeRadarMode === 'anime') renderAnimeSlice();
      else renderWorldNewsSlice();
    });
  }

  /* Equipe, Planner, Synapse RE & Sistema */
  async function loadTeamAndPlanner() {
    const grid = document.getElementById('team-personas-grid');
    if (grid && grid.dataset.loaded !== '1') {
      try {
        const data = await (await fetch('/api/team/personas')).json();
        grid.innerHTML = '';
        (data.personas || []).forEach((p) => {
          const card = document.createElement('div');
          card.className = 'video-card';
          const h3 = document.createElement('h3');
          h3.textContent = p.name + ' (' + p.role + ')';
          const sp = document.createElement('div');
          sp.className = 'topic-meta';
          sp.textContent = p.specialty;
          card.appendChild(h3);
          card.appendChild(sp);
          grid.appendChild(card);
        });
        grid.dataset.loaded = '1';
      } catch (e) {}
    }
  }

  document.getElementById('brief-form').addEventListener('submit', (e) => {
    e.preventDefault();
    const topicEl = document.getElementById('brief-topic');
    const errEl = document.getElementById('brief-topic-err');
    const ok = !!(topicEl && topicEl.value.trim());
    if (errEl) errEl.hidden = ok;
    if (topicEl) topicEl.setAttribute('aria-invalid', String(!ok));
    if (!ok) return;
    withBusyBtn(document.getElementById('btn-generate-brief'), 'Gerando roteiro...', async () => {
      const r = await fetch('/api/team/brief', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          topic: topicEl.value.trim(),
          niche: document.getElementById('brief-niche').value,
          platform: document.getElementById('brief-platform').value,
        }),
      });
      const b = await r.json();
      const box = document.getElementById('brief-output');
      box.hidden = false;
      box.textContent = 'GANCHO: ' + (b.acts && b.acts['0_a_3s_gancho'] ? b.acts['0_a_3s_gancho'].line : '') + '\nCONFLITO: ' + (b.acts && b.acts['3_a_20s_conflito'] ? b.acts['3_a_20s_conflito'].line : '') + '\nPAYOFF: ' + (b.acts && b.acts['payoff_final'] ? b.acts['payoff_final'].line : '');
      showToast('Roteiro em 3 atos pronto!', 'ok');
    });
  });

  document.getElementById('btn-load-planner').addEventListener('click', () => withBusyBtn(document.getElementById('btn-load-planner'), 'Montando...', async () => {
    const d = await (await fetch('/api/team/planner')).json();
    const pgrid = document.getElementById('team-planner-grid');
    pgrid.innerHTML = '';
    (d.schedule || []).forEach((slot) => {
      const c = document.createElement('div');
      c.className = 'video-card';
      const h3 = document.createElement('h3');
      h3.textContent = slot.day + ' — ' + slot.topic;
      const m = document.createElement('div');
      m.className = 'topic-meta';
      m.textContent = slot.niche + ' • ' + slot.best_time;
      c.appendChild(h3);
      c.appendChild(m);
      pgrid.appendChild(c);
    });
  }));

  async function loadSynapseStatus() {
    const ov = document.getElementById('synapse-overview-grid');
    const box = document.getElementById('synapse-immunities-box');
    if (!ov || !box) return;
    const d = await (await fetch('/api/synapse/status')).json();
    const bin = d.native_binary || {};
    ov.innerHTML = '';
    [
      ['Protocolo', d.protocol || 'OMEGA-SYNAPSE v3.0'],
      ['Roda do Dharma', d.wheel_state + ' • ' + (d.immunity_count || 0) + ' Defesas'],
      ['Binario C11', bin.exists ? ((bin.architecture || 'ELF') + ' • ' + Math.round((bin.size_bytes || 0) / 1024) + ' KB') : 'AST + C11'],
    ].forEach(([lbl, val]) => {
      const el = document.createElement('div');
      el.className = 'diag-box';
      el.innerHTML = '<strong></strong><span></span>';
      el.querySelector('strong').textContent = lbl;
      el.querySelector('span').textContent = val;
      ov.appendChild(el);
    });
    box.innerHTML = '';
    (d.immunities || []).forEach((im) => {
      const card = document.createElement('div');
      card.className = 'video-card';
      const h3 = document.createElement('h3');
      h3.textContent = '[' + (im.status || 'ACTIVE') + '] ' + (im.spoke || im.id);
      const p1 = document.createElement('div');
      p1.className = 'topic-meta';
      p1.textContent = im.mitigation || im.signature || '';
      card.appendChild(h3);
      card.appendChild(p1);
      box.appendChild(card);
    });
  }

  document.getElementById('synapse-innertube-form').addEventListener('submit', (e) => {
    e.preventDefault();
    const urlEl = document.getElementById('innertube-url');
    const errEl = document.getElementById('innertube-err');
    const urlVal = urlEl.value.trim();
    if (errEl) errEl.hidden = !!urlVal;
    urlEl.setAttribute('aria-invalid', String(!urlVal));
    const box = document.getElementById('innertube-result');
    if (!urlVal) return;
    withBusyBtn(document.getElementById('btn-innertube-scan'), 'Extraindo...', async () => {
      box.hidden = false;
      const res = await fetch('/api/synapse/innertube', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url: urlVal }) });
      const d = await res.json();
      if (!d.ok) { box.textContent = d.error || 'Erro InnerTube'; return; }
      box.innerHTML = '';
      const h3 = document.createElement('h3');
      h3.textContent = d.title + ' (' + d.channel + ')';
      box.appendChild(h3);
      (d.peaks || []).forEach((pk) => {
        const row = document.createElement('div');
        row.className = 'heat-bar-row';
        row.innerHTML = '<span></span><div class="heat-track"><div class="heat-fill"></div></div><button type="button" class="btn btn-primary btn-sm"></button>';
        row.querySelector('span').textContent = Math.round(pk.start_sec) + 's';
        row.querySelector('.heat-fill').style.width = Math.min(100, Math.max(8, pk.intensity_pct)) + '%';
        const btn = row.querySelector('button');
        btn.textContent = Math.round(pk.intensity_pct) + '%';
        btn.addEventListener('click', () => {
          cutSourceEl.value = d.url;
          syncWorkstationPreview();
          activateTab(0);
          showToast('Pico InnerTube selecionado: ' + pk.label, 'ok');
        });
        box.appendChild(row);
      });
    });
  });

  document.getElementById('synapse-trace-form').addEventListener('submit', (e) => {
    e.preventDefault();
    const q = document.getElementById('rea-trace-query').value.trim();
    const out = document.getElementById('rea-trace-result');
    if (!q) return;
    withBusyBtn(document.getElementById('btn-rea-trace'), 'Rastreando...', async () => {
      out.hidden = false;
      const d = await (await fetch('/api/synapse/trace?q=' + encodeURIComponent(q))).json();
      out.textContent = ['QUERY: ' + d.query + ' | Matches: ' + d.total_hits].concat(
        (d.matches || []).map((m) => '[' + m.layer + '] ' + m.file + ':' + m.line + ' (' + m.symbol + ')')
      ).join('\n');
    });
  });
  document.getElementById('btn-refresh-synapse').addEventListener('click', loadSynapseStatus);

  async function loadSystemDiag() {
    const box = document.getElementById('system-diag');
    const d = await (await fetch('/api/system')).json();
    const oa = d.offline_ai || {};
    const isa = (oa.isa_features && oa.isa_features.length) ? oa.isa_features.join(', ') : (oa.arch || 'CPU');
    box.innerHTML = '';
    [
      ['Disco Livre', d.disk_free_gb + ' GB (' + (d.output_used_mb || 0) + ' MB em output/)'],
      ['Endereco Rede Local', d.lan_url || 'http://127.0.0.1:8787/'],
      ['Canais API', (d.keys && d.keys.tiktok ? 'TikTok ATIVO' : 'TikTok Pend.') + ' • ' + (d.keys && d.keys.youtube ? 'YouTube OK' : 'YouTube Pend.')],
      ['Persistencia Boot/SSH', d.tools.boot_ready ? 'Termux:Boot + Watchdog' : 'Watchdog C11'],
      ['FFmpeg / Whisper', (d.tools.ffmpeg ? 'FFmpeg OK' : 'Sem FFmpeg') + ' • ' + (d.tools.whisper ? 'Whisper OK' : 'Sem Whisper')],
      ['Voz TTS', d.tts_engine || 'Kokoro PT-BR'],
      ['SoC & IA Offline', (oa.arch || 'CPU') + ' • ' + isa + (oa.total_ram_gb ? (' • ' + oa.total_ram_gb + ' GB RAM') : '')],
      ['Modelo Local / Tier', (oa.active_model || 'Heuristica') + (oa.recommended_tier ? (' (' + oa.recommended_tier.label + ')') : '')],
    ].forEach(([k, val]) => {
      const cell = document.createElement('div');
      cell.className = 'diag-box';
      cell.innerHTML = '<strong></strong><span></span>';
      cell.querySelector('strong').textContent = k;
      cell.querySelector('span').textContent = val;
      box.appendChild(cell);
    });
  }
  document.getElementById('btn-refresh-system').addEventListener('click', loadSystemDiag);
  const benchBtn = document.getElementById('btn-ai-benchmark');
  if (benchBtn) {
    benchBtn.addEventListener('click', () => withBusyBtn(benchBtn, 'Medindo...', async () => {
      const r = await (await fetch('/api/ai/benchmark', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' })).json();
      const info = document.getElementById('tunnel-info');
      info.textContent = 'Benchmark (' + r.mode + '): ' + r.latency_ms + ' ms' + (r.tokens_per_sec ? (' • ' + r.tokens_per_sec + ' tok/s') : '') + ' | ISA: ' + ((r.isa_features || []).join(', ') || 'baseline');
      showToast('Benchmark IA concluido!', 'ok');
    }));
  }
  const pruneBtn = document.getElementById('btn-prune-storage');
  if (pruneBtn) {
    pruneBtn.addEventListener('click', () => withBusyBtn(pruneBtn, 'Limpando...', async () => {
      const r = await (await fetch('/api/system/prune', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' })).json();
      document.getElementById('tunnel-info').textContent = 'Retencao: ' + r.freed_mb + ' MB liberados (' + r.removed_dirs + ' pastas temp, ' + (r.removed_videos || []).length + ' videos antigos). Restam ' + r.remaining_videos + ' MP4 (' + r.total_mb + ' MB).';
      showToast('Espaco liberado: ' + r.freed_mb + ' MB!', 'ok');
      loadSystemDiag();
      loadChannelTelemetry();
    }));
  }
  const aiChatForm = document.getElementById('ai-chat-form');
  if (aiChatForm) {
    aiChatForm.addEventListener('submit', (e) => {
      e.preventDefault();
      const q = document.getElementById('ai-chat-input').value.trim();
      const out = document.getElementById('ai-chat-output');
      if (!q) return;
      withBusyBtn(document.getElementById('btn-ai-chat'), 'Buscando...', async () => {
        const d = await (await fetch('/api/ai/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ prompt: q }) })).json();
        out.hidden = false;
        out.textContent = '[' + (d.backend || 'offline') + ']\n' + (d.answer || '');
      });
    });
  }
  document.getElementById('btn-start-tunnel').addEventListener('click', () => withBusyBtn(document.getElementById('btn-start-tunnel'), 'Abrindo tunel...', async () => {
    const d = await (await fetch('/api/tunnel', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' })).json();
    document.getElementById('tunnel-info').textContent = d.url ? ('Link 4G Seguro: ' + d.url) : (d.message || 'Indisponivel');
  }));
  document.getElementById('trim-form').addEventListener('submit', (e) => {
    e.preventDefault();
    withBusyBtn(document.getElementById('btn-run-trim'), 'Exportando...', async () => {
      const resp = await fetch('/api/trim', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          filename: document.getElementById('trim-file').value.trim(),
          start: Number(document.getElementById('trim-start').value || 0),
          end: Number(document.getElementById('trim-end').value || 30),
          normalize: document.getElementById('trim-normalize').checked,
        }),
      });
      const data = await resp.json();
      showToast(resp.ok ? ('Trecho salvo: ' + data.output) : ('Erro: ' + data.message), resp.ok ? 'ok' : 'err');
      loadVideos();
    });
  });

  document.getElementById('btn-quick-create').addEventListener('click', () => activateTab(0));
  document.getElementById('studio-search').addEventListener('input', (e) => {
    if (String(e.target.value || '').trim().length > 0) activateTab(3);
    if (_videosCache.length) renderVideosGrid();
    else loadVideos();
  });

  syncWorkstationPreview();
  loadChannelTelemetry();
  loadScheduler();
  loadVideos();
  refreshStatus();
  loadHorizonRadar();
})();
