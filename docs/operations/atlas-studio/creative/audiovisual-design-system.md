# DESIGN SYSTEM AUDIOVISUAL E PRESETS POR NICHO

## 1. Safe Zones para Telas Verticais 9:16 (1080x1920)
No consumo móvel em plataformas verticais, diversas áreas da tela são sobrepostas por interfaces de usuário nativas do aplicativo.
O AutoShorts define o seguinte retângulo seguro via `SafeZoneSpec`:
- **Topo**: Margem de 220px (status bar, busca e botão fechar).
- **Rodapé**: Margem de 380px (título do som, descrição expansível e botões de interação primária).
- **Direita**: Margem de 140px (coluna de botões: Curtir, Comentários, Compartilhar, Áudio/Remix).
- **Esquerda**: Margem de 60px (respiro de leitura).
- **Área Útil Central**: `x ∈ [60, 940]`, `y ∈ [220, 1540]`.

## 2. Presets Estéticos por Nicho

| Nicho | Fonte Primária | Cor de Destaque | Fundo | Estilo de Legenda | Ducking | Loudness |
|---|---|---|---|---|---|---|
| **Notícias** | Montserrat-Bold | `#E63946` (Vermelho) | `#0A1128` (Navy) | Two-line Box | -18.0 dB | -14.0 LUFS |
| **Tecnologia & IA** | Inter-Bold | `#00F5D4` (Ciano Neon) | `#0B090A` (Preto) | Kinetic Word | -16.0 dB | -14.0 LUFS |
| **Games & GTA 6** | Impact / Arial-Black | `#FF006E` (Rosa Neon) | `#140152` (Roxo) | Kinetic Word | -14.0 dB | -14.0 LUFS |
| **Storytelling** | Playfair / Georgia | `#F4A261` (Âmbar) | `#1D2D44` (Ardósia) | Minimal Clean | -20.0 dB | -14.0 LUFS |
| **Educacional** | Plus Jakarta Sans | `#06D6A0` (Verde Menta) | `#001219` (Verde Noite) | Two-line Box | -16.0 dB | -14.0 LUFS |
| **Podcast / Cortes** | Open Sans / Roboto | `#FF9E00` (Laranja) | `#1B1B1E` (Cinza Escuro) | Lower Third | -16.0 dB | -14.0 LUFS |
