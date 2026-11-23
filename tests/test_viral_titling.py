from auto_shorts.viral_titling import detect_accurate_category, generate_smart_clip_title


def test_detect_accurate_category():
    # 1. Sports: Carlos Alcaraz
    cat1 = detect_accurate_category(
        "Carlos Alcaraz vence Zverev e conquista título inédito do ATP",
        summary="O título foi conquistado neste domingo em Turim, na Itália, após superar o alemão Alexander Zverev.",
        hint_category="mundo",
    )
    assert cat1 == "esportes"

    # 2. Science: Frog species discovery
    cat2 = detect_accurate_category(
        "Nova espécie de perereca é descoberta em Minas Gerais",
        summary="Pesquisadores e biólogos identificaram a Ololygon cataguas na Zona da Mata.",
        hint_category="economia",  # Mistakenly from an economy RSS feed
    )
    assert cat2 == "ciencia_natureza"

    # 3. Economy: Real inflation / interest rates
    cat3 = detect_accurate_category(
        "Banco Central eleva Selic e mercado financeiro projeta inflação",
        summary="O Copom decidiu subir a taxa básica de juros em 0,5 ponto percentual.",
    )
    assert cat3 == "economia"

    # 4. Tech: Samsung App Lock
    cat4 = detect_accurate_category(
        "Samsung agora permite bloquear apps individualmente na One UI",
        summary="Recurso da One UI protege aplicativos com biometria, PIN e senha no Galaxy S26.",
    )
    assert cat4 == "tech_ia"


def test_generate_smart_clip_title_news_fixes_mismatches():
    # Frog news previously tagged as Plantão Economia
    fixed1 = generate_smart_clip_title(
        clip_text="Pesquisadores e biólogos encontraram nova espécie de perereca na floresta de Minas Gerais.",
        source_title="Nova espécie de perereca é descoberta em Minas Gerais | Plantão Economia",
        niche="noticias_mundiais",
    )
    assert "Ciência & Natureza" in fixed1
    assert "Plantão Economia" not in fixed1

    # Tennis news previously tagged as Plantão Tech
    fixed2 = generate_smart_clip_title(
        clip_text="Carlos Alcaraz derrotou Alexander Zverev na final do ATP Finals em Turim.",
        source_title="Carlos Alcaraz vence Zverev e conquista título inédito do ATP | Plantão Tech",
        niche="noticias_mundiais",
    )
    assert "Plantão Esportes" in fixed2
    assert "Plantão Tech" not in fixed2


def test_generate_smart_clip_title_reddit_nosleep():
    # Part 10: Forest creature
    text10 = "Além disso, também lembro da última vez que vi a coisa antes de fugir Quando ela sorriu de volta para mim através da floresta..."
    title10 = generate_smart_clip_title(
        clip_text=text10,
        source_title="Histórias Bizarras e Assustadoras do Reddit (r/nosleep)",
        part_num=10,
    )
    assert "Histórias Bizarras e Assustadoras do Reddit (r/nosleep) (Parte 10)" != title10
    assert ("Floresta" in title10 or "Sorriu" in title10 or "Reddit" in title10)

    # Part 6: Phone contact
    text6 = "Mas aí eu me pegava clicando no nome dela na lista de contatos, antes da minha voz interior avisar que ela ia se assustar..."
    title6 = generate_smart_clip_title(
        clip_text=text6,
        source_title="Histórias Bizarras e Assustadoras do Reddit (r/nosleep)",
        part_num=6,
    )
    assert title6 != title10
    assert "Histórias Bizarras e Assustadoras do Reddit (r/nosleep) (Parte 6)" != title6


def test_generate_smart_clip_title_streamers():
    # Gaules clip
    title_g1 = generate_smart_clip_title(
        clip_text="Mano do céu, olha isso aqui no jogo! Que loucura!",
        source_title="GTA 6 Ao Vivo: Gaules",
        streamer_or_speaker="Gaules",
        part_num=1,
    )
    assert title_g1 != "GTA 6 Ao Vivo: Gaules (Parte 1) | Gameplay #Shorts"
    assert "Gaules" in title_g1

    # Lipao clip part 2
    title_l2 = generate_smart_clip_title(
        clip_text="A polícia tá vindo de tanque! Olha o caos nessa missão!",
        source_title="GTA 6 Ao Vivo: LipaoGamer",
        streamer_or_speaker="LipaoGamer",
        part_num=2,
    )
    assert title_l2 != "GTA 6 Ao Vivo: LipaoGamer (Parte 2) | Gameplay #Shorts"
    assert "LipaoGamer" in title_l2
