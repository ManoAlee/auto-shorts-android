# Validação de Título vs Conteúdo — AUTO SHORTS SENTINEL

## 1. Problema Endereçado

Em plataformas de vídeos curtos, o maior causador de queda de retenção e penalização algorítmica é a descontinuidade entre a promessa do título e a realidade do vídeo (**Title-to-Content Mismatch**).

Exemplos detectados e prevenidos pelo Sentinel:
1. **Promessa Numérica Falsa:** Título promete *"5 Erros Fatais..."*, mas o roteiro só lista 2 itens.
2. **Alucinação Tópica:** Vídeo sobre alagamentos e chuvas em São Paulo intitulado com jargão gamer de live: *"Negócios em Mente descobriu esse segredo ao vivo!"*.
3. **Classificação Incorreta:** Queda de serviços de nuvem da Microsoft rotulado como *"Ciência & Natureza"* em vez de *"Tecnologia & IA"*.

---

## 2. Motor de Consistência (`TitleToContentConsistencyEngine`)

Implementado em `src/auto_shorts/sentinel_pre_render/title_consistency.py`, o motor realiza três etapas analíticas complementares:

### A. Extração de Promessas Numéricas
Identifica números declarados como listas de fatos ou dicas através de expressões regulares:
```python
# Padrões reconhecidos:
# "5 passos", "3 erros", "7 segredos", "top 10", "4 dicas"
```
Se o roteiro não entregar pelo menos a mesma quantidade de itens numerados identificáveis, a consistência é imediatamente rebaixada e o Gate 01 reprova o vídeo com a flag `NUMERICAL_PROMISE_UNMET`.

### B. Mapeamento de Entidades Tópicas & Stem Matching
Extrai termos substantivos relevantes do título, excluindo stop words em português e palavras funcionais genéricas (*passos*, *dicas*, *aumentar*, *fácil*, *segredo*).

Em seguida, valida se o radical das entidades (stems com pelo menos 5 caracteres, como `produz` para `produtividade`) está presente na narração ou nas legendas.

### C. Construção da Matriz de Evidências
Cada reivindicação gera uma trilha auditável:
```
TITLE_CLAIM -> SCRIPT_SEGMENT -> VISUAL_EVIDENCE -> TIMESTAMP
```

```json
{
  "title": "3 Dicas para Aumentar sua Produtividade no Computador",
  "claimed_entities": ["produtividade", "computador"],
  "numerical_promises": [3],
  "script_delivered_items": 3,
  "topic_matches": ["produtividade", "computador"],
  "missing_entities": [],
  "clickbait_severity": 0.05,
  "consistency_score": 96.0,
  "is_consistent": true
}
```

---

## 3. Classificação Automática e Retitulação Preventiva

O subsistema conecta-se ao motor `viral_titling.py` para garantir:
1. **Prioridade de Notícias Meteorológicas:** Eventos climáticos ("temporal", "chuva", "alagamento") são classificados estritamente como categoria `mundo`, nunca `esportes`.
2. **Isolamento de Futebol:** Termos como "São Paulo" só disparam categoria `futebol` se acompanhados de qualificadores inequívocos como "são paulo fc", "tricolor paulista", "morumbi" ou "campeonato".
3. **Isolamento de TI / Cloud:** Falhas e apagões cibernéticos ("microsoft", "outlook", "apagao", "ti") são classificados como `tech_ia`.
