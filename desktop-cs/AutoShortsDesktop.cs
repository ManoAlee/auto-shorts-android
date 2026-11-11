// AutoShorts Studio Desktop (C# / .NET Framework 4 WinForms + P/Invoke Win32)
// Controls the Android Termux AutoShorts server and provides local FFmpeg /video-editing tools.

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Net;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;

namespace AutoShortsDesktop
{
    internal static class NativeWin32
    {
        [DllImport("user32.dll")]
        internal static extern bool MessageBeep(uint uType);

        [DllImport("kernel32.dll")]
        internal static extern ulong GetTickCount64();
    }

    public sealed class StudioForm : Form
    {
        private static readonly Color Canvas = Color.FromArgb(243, 246, 250);
        private static readonly Color Surface = Color.White;
        private static readonly Color Ink = Color.FromArgb(15, 23, 42);
        private static readonly Color InkMuted = Color.FromArgb(71, 85, 105);
        private static readonly Color Primary = Color.FromArgb(15, 82, 186);
        private static readonly Color OkGreen = Color.FromArgb(21, 128, 61);

        private readonly JavaScriptSerializer _json = new JavaScriptSerializer();
        private readonly TextBox _serverUrlBox;
        private readonly Label _channelBadge;
        private readonly Label _statusBar;
        private readonly ComboBox _nicheCombo;
        private readonly ComboBox _platformCombo;
        private readonly ComboBox _layoutCombo;
        private readonly NumericUpDown _clipsNum;
        private readonly TextBox _sourceUrlBox;
        private readonly TextBox _playlistBox;
        private readonly CheckBox _autoPublishChk;
        private readonly ListBox _animeListBox;
        private readonly ListBox _videosListBox;
        private readonly TextBox _videoDetailBox;
        private readonly TextBox _localMp4Box;
        private readonly NumericUpDown _trimStartNum;
        private readonly NumericUpDown _trimEndNum;
        private readonly CheckBox _trimProxyChk;
        private readonly TextBox _editorLogBox;

        private readonly List<Dictionary<string, object>> _animeItems = new List<Dictionary<string, object>>();
        private readonly List<Dictionary<string, object>> _videoItems = new List<Dictionary<string, object>>();

        public StudioForm()
        {
            Text = "AutoShorts Studio Desktop (C# + FFmpeg + Android Controller)";
            Size = new Size(980, 680);
            MinimumSize = new Size(820, 560);
            BackColor = Canvas;
            ForeColor = Ink;
            Font = new Font("Segoe UI", 9.5f, FontStyle.Regular);

            var topBar = new Panel { Dock = DockStyle.Top, Height = 86, BackColor = Surface, Padding = new Padding(14, 10, 14, 10) };
            var titleLbl = new Label
            {
                Text = "AutoShorts Studio Desktop",
                Font = new Font("Segoe UI", 14f, FontStyle.Bold),
                AutoSize = true,
                Location = new Point(14, 10),
                ForeColor = Ink
            };
            _channelBadge = new Label
            {
                Text = "Canal: aguardando sincronia...",
                Font = new Font("Segoe UI", 9f, FontStyle.Bold),
                AutoSize = true,
                Location = new Point(14, 42),
                ForeColor = OkGreen
            };
            var urlLbl = new Label { Text = "Servidor Android:", Location = new Point(470, 14), AutoSize = true, ForeColor = InkMuted };
            _serverUrlBox = new TextBox { Text = "http://192.168.10.210:8787", Location = new Point(470, 36), Width = 280 };
            var syncBtn = MakeButton("Sincronizar", Primary, Color.White, new Point(762, 34), 120);
            syncBtn.Click += async delegate { await RefreshAllAsync(); };
            topBar.Controls.AddRange(new Control[] { titleLbl, _channelBadge, urlLbl, _serverUrlBox, syncBtn });

            _statusBar = new Label
            {
                Dock = DockStyle.Bottom,
                Height = 32,
                BackColor = Surface,
                ForeColor = Ink,
                TextAlign = ContentAlignment.MiddleLeft,
                Padding = new Padding(12, 0, 12, 0),
                Text = "Pronto para operar."
            };

            var tabs = new TabControl { Dock = DockStyle.Fill, Padding = new Point(12, 6) };

            // Tab 1: Cortes Reais & Radar AniList
            var tabCuts = new TabPage("Cortes Reais e Autopilot") { BackColor = Canvas, Padding = new Padding(14) };
            _nicheCombo = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Location = new Point(20, 42), Width = 280 };
            _nicheCombo.Items.AddRange(new object[] { "podcast", "entretenimento_animes", "ia_tech", "financas", "desenvolvimento_pessoal", "saude_fitness", "concursos", "all" });
            _nicheCombo.SelectedIndex = 0;

            _platformCombo = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Location = new Point(320, 42), Width = 220 };
            _platformCombo.Items.AddRange(new object[] { "youtube_shorts", "tiktok_rewards", "instagram_reels" });
            _platformCombo.SelectedIndex = 0;

            _layoutCombo = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Location = new Point(560, 42), Width = 200 };
            _layoutCombo.Items.AddRange(new object[] { "blur_bg", "split_top_bottom", "center_crop" });
            _layoutCombo.SelectedIndex = 0;

            _clipsNum = new NumericUpDown { Minimum = 1, Maximum = 5, Value = 1, Location = new Point(780, 42), Width = 80 };
            _sourceUrlBox = new TextBox { Location = new Point(20, 102), Width = 480 };
            _playlistBox = new TextBox { Location = new Point(520, 102), Width = 340, Text = "Cortes de Podcast - Brasil" };
            _autoPublishChk = new CheckBox { Text = "Validar midia e publicar no YouTube automaticamente (AleplayTV)", Checked = true, Location = new Point(20, 140), Width = 520 };

            var runBtn = MakeButton("Gerar, Validar e Postar no Celular", Primary, Color.White, new Point(20, 176), 290);
            runBtn.Click += async delegate { await TriggerRemoteCutAsync(null); };
            var radarBtn = MakeButton("Carregar Animes em Lancamento (AniList)", Color.White, Ink, new Point(324, 176), 300);
            radarBtn.Click += async delegate { await LoadAnimeRadarAsync(); };
            var cutAnimeBtn = MakeButton("Cortar Anime Selecionado", OkGreen, Color.White, new Point(636, 176), 224);
            cutAnimeBtn.Click += async delegate
            {
                if (_animeListBox.SelectedIndex >= 0 && _animeListBox.SelectedIndex < _animeItems.Count)
                {
                    var item = _animeItems[_animeListBox.SelectedIndex];
                    _nicheCombo.SelectedItem = "entretenimento_animes";
                    _playlistBox.Text = "Animes e Teorias - Shorts";
                    await TriggerRemoteCutAsync(Convert.ToString(item["youtube_query"]));
                }
            };

            _animeListBox = new ListBox { Location = new Point(20, 226), Width = 840, Height = 240, BackColor = Surface, ForeColor = Ink };
            tabCuts.Controls.AddRange(new Control[]
            {
                MakeLabel("Nicho", 20, 20), _nicheCombo,
                MakeLabel("Plataforma", 320, 20), _platformCombo,
                MakeLabel("Enquadramento 9:16", 560, 20), _layoutCombo,
                MakeLabel("Qtd", 780, 20), _clipsNum,
                MakeLabel("URL YouTube opcional (vazio = descoberta automatica)", 20, 80), _sourceUrlBox,
                MakeLabel("Playlist YouTube", 520, 80), _playlistBox,
                _autoPublishChk, runBtn, radarBtn, cutAnimeBtn, _animeListBox
            });

            // Tab 2: Acervo & Publicacao YouTube
            var tabVideos = new TabPage("Acervo, Validacao e Publicacao YouTube") { BackColor = Canvas, Padding = new Padding(14) };
            _videosListBox = new ListBox { Location = new Point(20, 44), Width = 440, Height = 360, BackColor = Surface, ForeColor = Ink };
            _videosListBox.SelectedIndexChanged += delegate { ShowSelectedVideoDetail(); };
            _videoDetailBox = new TextBox { Multiline = true, ReadOnly = true, ScrollBars = ScrollBars.Vertical, Location = new Point(478, 44), Width = 420, Height = 360, BackColor = Surface, ForeColor = Ink };

            var reloadVidsBtn = MakeButton("Atualizar Acervo", Color.White, Ink, new Point(20, 418), 160);
            reloadVidsBtn.Click += async delegate { await LoadVideosAsync(); };
            var valBtn = MakeButton("Validar Selecionado", Primary, Color.White, new Point(192, 418), 166);
            valBtn.Click += async delegate { await ValidateSelectedVideoAsync(); };
            var valAllBtn = MakeButton("Otimizar & Auditar Tudo", Color.FromArgb(109, 40, 217), Color.White, new Point(368, 418), 186);
            valAllBtn.Click += async delegate { await OptimizeAndValidateAllAsync(); };
            var pubBtn = MakeButton("Publicar AleplayTV", OkGreen, Color.White, new Point(564, 418), 166);
            pubBtn.Click += async delegate { await PublishSelectedVideoAsync(); };
            var openWebBtn = MakeButton("Abrir Web", Color.White, Ink, new Point(740, 418), 130);
            openWebBtn.Click += delegate { Process.Start(_serverUrlBox.Text.Trim()); };

            tabVideos.Controls.AddRange(new Control[]
            {
                MakeLabel("Videos gerados no celular (output/)", 20, 20), _videosListBox,
                MakeLabel("Detalhes de validacao, Opus Scorecard e link YouTube", 478, 20), _videoDetailBox,
                reloadVidsBtn, valBtn, valAllBtn, pubBtn, openWebBtn
            });

            // Tab 3: Editor FFmpeg Local (/video-editing Layer 3)
            var tabEditor = new TabPage("Editor Local FFmpeg (Cortes e Proxy)") { BackColor = Canvas, Padding = new Padding(14) };
            _localMp4Box = new TextBox { Location = new Point(20, 42), Width = 680 };
            var browseBtn = MakeButton("Escolher MP4...", Color.White, Ink, new Point(712, 40), 160);
            browseBtn.Click += delegate
            {
                using (var dlg = new OpenFileDialog { Filter = "MP4 Video|*.mp4|Todos|*.*" })
                {
                    if (dlg.ShowDialog() == DialogResult.OK) _localMp4Box.Text = dlg.FileName;
                }
            };
            _trimStartNum = new NumericUpDown { Minimum = 0, Maximum = 36000, DecimalPlaces = 1, Value = 0, Location = new Point(20, 102), Width = 140 };
            _trimEndNum = new NumericUpDown { Minimum = 2, Maximum = 36000, DecimalPlaces = 1, Value = 30, Location = new Point(180, 102), Width = 140 };
            _trimProxyChk = new CheckBox { Text = "Gerar proxy 960p rapido (em vez de corte por timestamp)", Location = new Point(340, 104), Width = 440 };
            var execLocalBtn = MakeButton("Executar FFmpeg Local", Primary, Color.White, new Point(20, 146), 220);
            execLocalBtn.Click += async delegate { await RunLocalFfmpegAsync(); };
            _editorLogBox = new TextBox { Multiline = true, ReadOnly = true, ScrollBars = ScrollBars.Vertical, Location = new Point(20, 204), Width = 852, Height = 260, BackColor = Surface, ForeColor = Ink };

            tabEditor.Controls.AddRange(new Control[]
            {
                MakeLabel("Arquivo MP4 local no Windows", 20, 20), _localMp4Box, browseBtn,
                MakeLabel("Inicio (s)", 20, 80), _trimStartNum,
                MakeLabel("Fim (s)", 180, 80), _trimEndNum,
                _trimProxyChk, execLocalBtn, _editorLogBox
            });

            tabs.TabPages.AddRange(new TabPage[] { tabCuts, tabVideos, tabEditor });
            Controls.Add(tabs);
            Controls.Add(topBar);
            Controls.Add(_statusBar);

            Shown += async delegate { await RefreshAllAsync(); };
        }

        private static Label MakeLabel(string text, int x, int y)
        {
            return new Label { Text = text, Location = new Point(x, y), AutoSize = true, ForeColor = InkMuted };
        }

        private static Button MakeButton(string text, Color back, Color fore, Point loc, int width)
        {
            return new Button
            {
                Text = text,
                BackColor = back,
                ForeColor = fore,
                FlatStyle = FlatStyle.Flat,
                Location = loc,
                Size = new Size(width, 38),
                Font = new Font("Segoe UI", 9.2f, FontStyle.Bold),
                Cursor = Cursors.Hand
            };
        }

        private sealed class TimeoutWebClient : WebClient
        {
            private readonly int _timeoutMs;
            public TimeoutWebClient(int timeoutMs = 15000) { _timeoutMs = timeoutMs; Encoding = Encoding.UTF8; }
            protected override WebRequest GetWebRequest(Uri address)
            {
                var req = base.GetWebRequest(address);
                if (req != null) req.Timeout = _timeoutMs;
                return req;
            }
        }

        private string BaseUrl()
        {
            return _serverUrlBox.Text.Trim().TrimEnd('/');
        }

        private async Task<Dictionary<string, object>> HttpJsonAsync(string method, string path, object payload)
        {
            return await Task.Run(() =>
            {
                using (var wc = new TimeoutWebClient(25000))
                {
                    wc.Headers[HttpRequestHeader.ContentType] = "application/json";
                    try
                    {
                        string raw = method == "GET"
                            ? wc.DownloadString(BaseUrl() + path)
                            : wc.UploadString(BaseUrl() + path, method, _json.Serialize(payload ?? new object()));
                        return _json.Deserialize<Dictionary<string, object>>(raw);
                    }
                    catch (WebException ex)
                    {
                        string msg = ex.Message;
                        if (ex.Response != null)
                        {
                            using (var sr = new StreamReader(ex.Response.GetResponseStream(), Encoding.UTF8))
                            {
                                string errBody = sr.ReadToEnd();
                                try
                                {
                                    var ed = _json.Deserialize<Dictionary<string, object>>(errBody);
                                    if (ed != null && ed.ContainsKey("message")) msg = Convert.ToString(ed["message"]);
                                }
                                catch { }
                            }
                        }
                        throw new InvalidOperationException(msg, ex);
                    }
                }
            });
        }

        private async Task RefreshAllAsync()
        {
            try
            {
                var chResp = await HttpJsonAsync("GET", "/api/channel", null);
                var ch = chResp["channel"] as Dictionary<string, object>;
                if (ch != null && Convert.ToBoolean(ch["connected"]))
                {
                    _channelBadge.Text = string.Format(
                        "Canal: {0} ({1} videos | {2} views) | Acervo: {3} MP4",
                        ch["title"], ch["videos"], ch["views"], chResp["local_videos"]);
                    _channelBadge.ForeColor = OkGreen;
                }
                else
                {
                    _channelBadge.Text = "Canal desconectado";
                    _channelBadge.ForeColor = Color.Firebrick;
                }
                await LoadVideosAsync();
                var st = await HttpJsonAsync("GET", "/api/status", null);
                _statusBar.Text = "Estado do motor: " + Convert.ToString(st["last_status"]);
            }
            catch (Exception ex)
            {
                _statusBar.Text = "Erro de conexao com celular: " + ex.Message;
            }
        }

        private async Task LoadAnimeRadarAsync()
        {
            _statusBar.Text = "Consultando AniList / Jikan...";
            var res = await HttpJsonAsync("GET", "/api/anime/trending", null);
            _animeItems.Clear();
            _animeListBox.Items.Clear();
            var list = res["anime"] as object[];
            if (list != null)
            {
                foreach (var obj in list)
                {
                    var d = obj as Dictionary<string, object>;
                    if (d == null) continue;
                    _animeItems.Add(d);
                    _animeListBox.Items.Add(string.Format("{0} (Ep {1}) -> {2}", d["title"], d["next_episode"], d["youtube_query"]));
                }
            }
            _statusBar.Text = string.Format("Radar AniList atualizado ({0} animes).", _animeItems.Count);
        }

        private async Task TriggerRemoteCutAsync(string queryOverride)
        {
            var payload = new Dictionary<string, object>
            {
                { "niche", _nicheCombo.SelectedItem.ToString() },
                { "platform", _platformCombo.SelectedItem.ToString() },
                { "layout", _layoutCombo.SelectedItem.ToString() },
                { "clips", (int)_clipsNum.Value },
                { "source", string.IsNullOrEmpty(queryOverride) ? _sourceUrlBox.Text.Trim() : "" },
                { "query", queryOverride ?? "" },
                { "playlist", _playlistBox.Text.Trim() },
                { "auto_publish", _autoPublishChk.Checked }
            };
            var res = await HttpJsonAsync("POST", "/api/run", payload);
            _statusBar.Text = Convert.ToString(res["message"]);
            NativeWin32.MessageBeep(0x00000040);
        }

        private async Task LoadVideosAsync()
        {
            var res = await HttpJsonAsync("GET", "/api/videos", null);
            _videoItems.Clear();
            _videosListBox.Items.Clear();
            var arr = res["videos"] as object[];
            if (arr != null)
            {
                foreach (var obj in arr)
                {
                    var d = obj as Dictionary<string, object>;
                    if (d == null) continue;
                    _videoItems.Add(d);
                    var val = d["validation"] as Dictionary<string, object>;
                    var yt = d["youtube"] as Dictionary<string, object>;
                    string tag = (yt != null && yt.ContainsKey("video_id")) ? "[YT] " : ((val != null && Convert.ToBoolean(val["valid"])) ? "[OK] " : "[?] ");
                    _videosListBox.Items.Add(tag + Convert.ToString(d["filename"]));
                }
            }
            if (_videosListBox.Items.Count > 0) _videosListBox.SelectedIndex = 0;
        }

        private void ShowSelectedVideoDetail()
        {
            if (_videosListBox.SelectedIndex < 0 || _videosListBox.SelectedIndex >= _videoItems.Count) return;
            var d = _videoItems[_videosListBox.SelectedIndex];
            var sb = new StringBuilder();
            sb.AppendLine("Arquivo: " + d["filename"]);
            sb.AppendLine("Titulo: " + d["title"]);
            sb.AppendLine("Gancho: " + (d.ContainsKey("hook_title") ? d["hook_title"] : ""));
            sb.AppendLine("Tamanho: " + d["size_mb"] + " MB");
            if (d.ContainsKey("opus_scorecard") && d["opus_scorecard"] != null)
            {
                sb.AppendLine("Opus Scorecard: " + _json.Serialize(d["opus_scorecard"]));
            }
            if (d.ContainsKey("duplicate_of") && d["duplicate_of"] != null)
            {
                sb.AppendLine("Duplicata de: " + d["duplicate_of"]);
            }
            sb.AppendLine();
            sb.AppendLine("Validacao: " + _json.Serialize(d["validation"]));
            sb.AppendLine();
            sb.AppendLine("YouTube: " + _json.Serialize(d["youtube"]));
            sb.AppendLine();
            sb.AppendLine("Legenda/Descricao:");
            sb.AppendLine(Convert.ToString(d["caption"]));
            _videoDetailBox.Text = sb.ToString();
        }

        private async Task OptimizeAndValidateAllAsync()
        {
            _statusBar.Text = "Otimizando titulos/ganchos e reauditando todo o acervo...";
            var opt = await HttpJsonAsync("POST", "/api/optimize", new Dictionary<string, object>());
            var res = await HttpJsonAsync("POST", "/api/auto-validate-all", new Dictionary<string, object> { { "auto_publish", false } });
            await LoadVideosAsync();
            _statusBar.Text = string.Format(
                "Otimizados: {0} | Aprovados: {1} | Reprovados: {2} | Duplicados: {3}",
                opt.ContainsKey("optimized_count") ? opt["optimized_count"] : 0,
                res.ContainsKey("approved") ? res["approved"] : 0,
                res.ContainsKey("rejected") ? res["rejected"] : 0,
                res.ContainsKey("duplicates_skipped") ? res["duplicates_skipped"] : 0);
            NativeWin32.MessageBeep(0x00000040);
        }

        private async Task ValidateSelectedVideoAsync()
        {
            if (_videosListBox.SelectedIndex < 0) return;
            string fname = Convert.ToString(_videoItems[_videosListBox.SelectedIndex]["filename"]);
            _statusBar.Text = "Validando " + fname + "...";
            await HttpJsonAsync("POST", "/api/validate", new Dictionary<string, object> { { "filename", fname } });
            await LoadVideosAsync();
            _statusBar.Text = "Validacao concluida para " + fname;
        }

        private async Task PublishSelectedVideoAsync()
        {
            if (_videosListBox.SelectedIndex < 0) return;
            string fname = Convert.ToString(_videoItems[_videosListBox.SelectedIndex]["filename"]);
            _statusBar.Text = "Publicando " + fname + " no YouTube (AleplayTV)...";
            try
            {
                var res = await HttpJsonAsync("POST", "/api/publish", new Dictionary<string, object> { { "filename", fname } });
                _statusBar.Text = "Publicado: " + Convert.ToString(res["url"]);
                NativeWin32.MessageBeep(0x00000040);
                await RefreshAllAsync();
            }
            catch (Exception ex)
            {
                _statusBar.Text = "Erro ao publicar: " + ex.Message;
            }
        }

        private async Task RunLocalFfmpegAsync()
        {
            string input = _localMp4Box.Text.Trim();
            if (!File.Exists(input))
            {
                _editorLogBox.AppendText("Arquivo nao encontrado.\r\n");
                return;
            }
            ulong t0 = NativeWin32.GetTickCount64();
            string outFile = Path.Combine(
                Path.GetDirectoryName(input) ?? ".",
                Path.GetFileNameWithoutExtension(input) + (_trimProxyChk.Checked ? "_proxy.mp4" : "_cut.mp4")
            );
            string args = _trimProxyChk.Checked
                ? string.Format("-y -i \"{0}\" -vf \"scale=960:-2\" -c:v libx264 -preset ultrafast -crf 28 \"{1}\"", input, outFile)
                : string.Format("-y -i \"{0}\" -ss {1:F1} -to {2:F1} -c copy \"{3}\"", input, _trimStartNum.Value, _trimEndNum.Value, outFile);

            _editorLogBox.AppendText("ffmpeg " + args + "\r\n");
            await Task.Run(() =>
            {
                using (var p = Process.Start(new ProcessStartInfo("ffmpeg", args) { UseShellExecute = false, CreateNoWindow = true }))
                {
                    if (p != null) p.WaitForExit();
                }
            });
            ulong elapsed = NativeWin32.GetTickCount64() - t0;
            _editorLogBox.AppendText(string.Format("Exportado ({0} ms): {1}\r\n", elapsed, outFile));
        }

        [STAThread]
        public static void Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new StudioForm());
        }
    }
}

