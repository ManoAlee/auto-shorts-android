/* AutoShorts Studio Frontend Controller — Live Render Stepper, Interactive 9:16 Stage, Segmented Radar & Inspector */
(function () {
  const tabs = Array.from(document.querySelectorAll('[role="tab"]'));
  const panels = Array.from(document.querySelectorAll('[role="tabpanel"]'));
  const renderBar = document.getElementById('render-bar');
  const renderBadge = document.getElementById('render-badge');
  const statusEl = document.getElementById('live-status');
  const renderFill = document.getElementById('render-fill');
  const renderMeta = document.getElementById('render-meta');
  const stageEls = Array.from(document.querySelectorAll('.stage-step'));
  const toastStack = document.getElementById('toast-stack');
  const dlg = document.getElementById('short-inspector-dlg');
  const floatingDock = document.getElementById('floating-render-dock');
  const floatingText = document.getElementById('floating-render-text');

  let _pollTimer = null;
  let _wasRunning = false;
  let _lastStatusData = { running: false };
  const _stageBaseLabels = stageEls.map((el) => el.textContent.trim());

  let _activeRadarMode = 'horizon';
  let _radarVisibleLimit = 6;
  let _horizonItemsCache = [];
  let _animeItemsCache = [];
  let _newsItemsCache = [];
  let _videosCache = [];
  let _acervoFilter = 'all';
  let _karaokeWordIdx = 0;

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
      if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
        e.preventDefault();
        const n = (idx + 1) % tabs.length;
        tabs[n].focus();
        activateTab(n);
      }
      if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
        e.preventDefault();
        const p = (idx - 1 + tabs.length) % tabs.length;
        tabs[p].focus();
        activateTab(p);
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
    if (renderFill) renderFill.style.width = (running ? pct : (data.last_status && data.last_status !== 'Pronto para operar' ? 100 : 0)) + '%';
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
          el.textContent = '✓ ' + base;
        } else if (stepNum === stageIdx) {
          el.classList.add('is-active');
          el.textContent = '● ' + base;
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
      if (tabs.findIndex((t) => t.id === 'tab-videos' && t.getAttribute('aria-selected') === 'true') >= 0) {
        loadVideos();
      }
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

  async function loadChannelTelemetry() {
    const strip = document.getElementById('channel-telemetry');
    try {
      const res = await fetch('/api/channel');
      const d = await res.json();
      if (strip) {
        strip.innerHTML = '';
        const ch = document.createElement('span');
        if (d.channel && d.channel.connected) {
          ch.className = 'pill pill-ok';
          ch.textContent = 'Canal: ' + d.channel.title + ' (' + d.channel.videos + ' videos, ' + d.channel.views + ' views)';
        } else {
          ch.className = 'pill pill-err';
          ch.textContent = 'Canal offline: ' + ((d.channel && d.channel.reason) || 'sem conexao');
        }
        strip.appendChild(ch);

        const tts = document.createElement('span');
        tts.className = 'pill';
        tts.textContent = 'Voz: ' + d.tts_engine;
        strip.appendChild(tts);

        const vid = document.createElement('span');
        vid.className = 'pill';
        vid.textContent = 'Acervo: ' + d.local_videos + ' MP4';
        strip.appendChild(vid);

        const llm = document.createElement('span');
        const hasCloud = d.keys && (d.keys.openrouter || d.keys.gemini || d.keys.openai);
        llm.className = (hasCloud || (d.local_llm && d.local_llm.online)) ? 'pill pill-ok' : 'pill';
        llm.textContent = hasCloud ? 'IA Nuvem Ativa' : ((d.local_llm && d.local_llm.online) ? ('IA Local: ' + d.local_llm.model) : 'Modo Heuristico');
        strip.appendChild(llm);
      }

      const vs = d.video_stats || {};
      const elChV = document.getElementById('kpi-channel-val');
      const elChS = document.getElementById('kpi-channel-sub');
      if (elChV && elChS) {
        elChV.textContent = (d.channel && d.channel.connected) ? (d.channel.views + ' views') : 'Offline';
        elChS.textContent = (d.channel && d.channel.connected) ? (d.channel.title + ' • ' + d.channel.videos + ' publicados') : 'Verifique YouTube OAuth';
      }
      const elQV = document.getElementById('kpi-queue-val');
      const elQS = document.getElementById('kpi-queue-sub');
      if (elQV && elQS) {
        elQV.textContent = (vs.approved || 0) + ' aprovados';
        elQS.textContent = (vs.queued || 0) + ' na fila YouTube • ' + (vs.rejected || 0) + ' reprovados';
      }
      const evo = d.background_evolution || [];
      const elBgV = document.getElementById('kpi-bg-val');
      const elBgS = document.getElementById('kpi-bg-sub');
      if (elBgV && elBgS) {
        elBgV.textContent = (d.gameplay_count || 0) + ' fundos UCB1';
        const topScore = evo.length ? Number(evo[0].avg_quality ?? evo[0].avg_score ?? 0) : 0;
        elBgS.textContent = evo.length
          ? ('Top UCB1: ' + evo[0].style + (topScore > 0 ? (' (' + Math.round(topScore) + '/100)') : ' (ativo)'))
          : 'Rotacao multi-cena 4.2s';
      }
      const elAiV = document.getElementById('kpi-ai-val');
      const elAiS = document.getElementById('kpi-ai-sub');
      if (elAiV && elAiS) {
        elAiV.textContent = (d.tts_engine || 'Kokoro PT-BR').split('(')[0].trim();
        elAiS.textContent = (d.keys && (d.keys.openrouter || d.keys.gemini)) ? 'IA Nuvem + Opus Scorecard' : 'Heuristica Offline';
      }
    } catch (e) {}
  }

  async function loadScheduler() {
    const info = document.getElementById('scheduler-info');
    if (!info) return;
    try {
      const s = await (await fetch('/api/scheduler')).json();
      info.textContent = (s.enabled ? 'Ativo' : 'Pausado') + ' | Nicho: ' + s.niche + ' | A cada ' + s.interval_hours + 'h | Ciclos: ' + s.runs_completed;
    } catch (e) {}
  }

  document.getElementById('btn-toggle-scheduler').addEventListener('click', () => withBusyBtn(document.getElementById('btn-toggle-scheduler'), 'Salvando...', async () => {
    const cur = await (await fetch('/api/scheduler')).json();
    await fetch('/api/scheduler', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ enabled: !cur.enabled }) });
    await loadScheduler();
    showToast(!cur.enabled ? 'Piloto 24/7 ativado!' : 'Piloto 24/7 pausado.', 'ok');
  }));

  document.getElementById('btn-trigger-autopilot').addEventListener('click', () => withBusyBtn(document.getElementById('btn-trigger-autopilot'), 'Enfileirando...', async () => {
    startOptimisticRender('1/5 Iniciando lote automatico multi-nicho...');
    const resp = await fetch('/api/scheduler', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ run_now: true, niche: 'all' }) });
    const data = await resp.json();
    showToast(data.message || 'Lote multi-nicho iniciado!', 'ok');
    refreshStatus();
  }));

  /* Live Interactive 9:16 Studio Preview, Layout Tiles & YouTube Thumb Detection */
  const cutSourceEl = document.getElementById('cut-source');
  const cutNicheEl = document.getElementById('cut-niche');
  const cutLayoutEl = document.getElementById('cut-layout');
  const voiceScriptEl = document.getElementById('voice-script');
  const voiceHookEl = document.getElementById('voice-hook');
  const phoneFrame = document.getElementById('phone-preview-frame');
  const phoneBgImg = document.getElementById('phone-preview-bg');
  const phoneStage = document.getElementById('phone-preview-stage');
  const previewHookBox = document.getElementById('preview-hook-title');
  const previewSubsBox = document.getElementById('preview-subs-line');
  const hookMeterLabel = document.getElementById('hook-meter-label');
  const voicePaceMeta = document.getElementById('voice-pace-meta');
  const layoutTiles = Array.from(document.querySelectorAll('.layout-tile'));

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
      botZ.textContent = 'Base: Gameplay Parkour 9:16';
      phoneStage.appendChild(topZ);
      phoneStage.appendChild(botZ);
    } else if (lay === 'center_crop') {
      const faceZ = document.createElement('div');
      faceZ.className = 'phone-zone-card';
      faceZ.style.borderStyle = 'solid';
      faceZ.style.borderColor = 'rgba(96, 165, 250, 0.75)';
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
        platform: document.getElementById('cut-platform').value,
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

  /* Inspector Modal / Bottom Sheet (<dialog>) */
  function openShortInspector(v) {
    if (!dlg) return;
    document.getElementById('dlg-title').textContent = v.title || v.filename;
    const body = document.getElementById('dlg-body');
    body.innerHTML = '';

    const player = document.createElement('video');
    player.controls = true;
    player.preload = 'metadata';
    player.style.maxHeight = '360px';
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
      const pre = document.createElement('pre');
      pre.className = 'meta-pre';
      pre.textContent = v.caption;
      body.appendChild(pre);
    }

    const acts = document.createElement('div');
    acts.className = 'actions';
    const btnYt = document.createElement('button');
    btnYt.type = 'button';
    btnYt.className = 'btn btn-success btn-sm';
    btnYt.textContent = (v.youtube && v.youtube.url) ? 'Republicar YouTube' : 'Publicar YouTube';
    btnYt.addEventListener('click', () => withBusyBtn(btnYt, 'Enviando...', async () => {
      const r = await fetch('/api/publish', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ filename: v.filename }) });
      const d = await r.json();
      showToast(r.ok ? ('Publicado no YouTube: ' + (d.url || 'OK')) : (d.message || 'Salvo na fila'), r.ok ? 'ok' : 'info');
      await loadVideos();
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
  }

  if (dlg) {
    document.getElementById('dlg-close').addEventListener('click', () => dlg.close());
    dlg.addEventListener('click', (e) => { if (e.target === dlg) dlg.close(); });
  }

  /* Clean Minimalist Acervo Cards + Instant Filter Pills */
  function renderVideosGrid() {
    const box = document.getElementById('videos-list');
    if (!box) return;
    const filterTxt = (document.getElementById('studio-search') ? document.getElementById('studio-search').value : '').trim().toLowerCase();
    const filtered = _videosCache.filter((v) => {
      if (filterTxt && !(v.title + ' ' + v.caption + ' ' + v.filename).toLowerCase().includes(filterTxt)) return false;
      const visOk = v.visual_audit ? !!v.visual_audit.approved : !!(v.validation && v.validation.valid);
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
      const statusPill = document.createElement('span');
      const visOk = v.visual_audit ? !!v.visual_audit.approved : !!(v.validation && v.validation.valid);
      statusPill.className = visOk ? 'pill pill-ok' : 'pill pill-err';
      statusPill.textContent = visOk
        ? ('Pronto' + (v.validation && v.validation.duration ? (' • ' + v.validation.duration + 's') : '') + (v.queued_for_auto_publish ? ' • Fila YT' : ''))
        : ('Reprovado: ' + ((v.visual_audit && v.visual_audit.reject_reasons && v.visual_audit.reject_reasons[0]) || 'verificar'));
      badges.appendChild(statusPill);

      const opus = v.opus_scorecard;
      if (opus) {
        const opPill = document.createElement('span');
        opPill.className = opus.opus_score >= 70 ? 'pill pill-info' : 'pill';
        opPill.textContent = 'Opus ' + opus.opus_score + '/100';
        badges.appendChild(opPill);
      }
      if (v.background_style) {
        const bgP = document.createElement('span');
        bgP.className = 'pill';
        bgP.textContent = v.background_style;
        badges.appendChild(bgP);
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
      const btnInspect = document.createElement('button');
      btnInspect.type = 'button';
      btnInspect.className = 'btn btn-primary btn-sm';
      btnInspect.style.flex = '1';
      btnInspect.textContent = (v.youtube && v.youtube.url) ? 'Ver Detalhes (Publicado)' : 'Inspecionar & Publicar';
      btnInspect.addEventListener('click', () => openShortInspector(v));
      acts.appendChild(btnInspect);
      card.appendChild(acts);
      box.appendChild(card);
    });
  }

  async function loadVideos() {
    const box = document.getElementById('videos-list');
    renderSkeletons(box, 3);
    try {
      const data = await (await fetch('/api/videos')).json();
      _videosCache = data.videos || [];
      renderVideosGrid();
    } catch (e) {
      box.textContent = 'Erro ao carregar acervo: ' + e.message;
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

  /* Rich Editorial Topic Media Builder (Gradient + Crisp SVG fallback instead of flat colors) */
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
            platform: document.getElementById('cut-platform').value,
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
          body: JSON.stringify({ niche: 'entretenimento_animes', platform: document.getElementById('cut-platform').value, layout: cutLayoutEl.value, clips: 1, query: a.youtube_query, playlist: 'Animes e Teorias - Shorts', auto_publish: true }),
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
    withBusyBtn(document.getElementById('btn-generate-brief'), 'Gerando roteiro...', async () => {
      const r = await fetch('/api/team/brief', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          topic: document.getElementById('brief-topic').value.trim() || 'Tendencia',
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
    const urlVal = document.getElementById('innertube-url').value.trim();
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
      ['Disco Livre', d.disk_free_gb + ' GB'],
      ['Endereco Rede Local', d.lan_url || 'http://127.0.0.1:8787/'],
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
  refreshStatus();
  loadHorizonRadar();
})();
