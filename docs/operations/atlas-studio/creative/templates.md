# TEMPLATES E ESPECIFICAÇÃO DE ASS (SUBTITLES)

## 1. Estrutura de Estilo ASS (.ass)
As legendas são renderizadas utilizando o padrão Advanced SubStation Alpha para permitir animações precisas de palavra por palavra (*kinetic highlighting*) e posicionamento absoluto acima das barras de interface.

```ini
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Montserrat,72,&H00FFFFFF&,&H000000FF&,&H00000000&,&H80000000&,-1,0,0,0,100,100,1,0,1,3,1,2,60,60,380,1
Style: Highlight,Montserrat,76,&H004639E6&,&H000000FF&,&H00000000&,&H80000000&,-1,0,0,0,105,105,2,0,1,4,2,2,60,60,380,1
Style: TopBanner,Montserrat,48,&H00FFFFFF&,&H000000FF&,&H00000000&,&HCC0A1128&,-1,0,0,0,100,100,0,0,1,2,0,8,60,60,220,1
```

## 2. Parâmetros de Temporização
- **Máximo de palavras por tela**: 3 a 4 palavras.
- **Duração mínima de exibição**: 0.4s por frame de texto para evitar leitura acelerada inviável.
- **Sincronia com Whisper**: Deslocamento de -60ms para compensar a latência auditiva humana.
