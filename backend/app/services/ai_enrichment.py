"""
AI enrichment service using Claude Sonnet via the Anthropic API.

Responsibilities:
- Generate plain-language bill summaries and short titles
- Tag bills and speeches with policy areas (fixed 20-item taxonomy)
- Generate speech summaries and extract keywords
- Generate politician AI biographies
"""

import anthropic

from app.config import settings

client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

POLICY_AREAS = [
    "Economia e finanças públicas",
    "Saúde",
    "Educação",
    "Segurança pública",
    "Meio ambiente e clima",
    "Agropecuária",
    "Infraestrutura e transportes",
    "Habitação e urbanismo",
    "Previdência social",
    "Trabalho e emprego",
    "Direitos humanos e minorias",
    "Política externa e defesa",
    "Ciência, tecnologia e inovação",
    "Cultura, esportes e lazer",
    "Comunicações e mídia",
    "Energia",
    "Tributação",
    "Sistema político e eleitoral",
    "Judiciário e legislativo",
    "Outros",
]


def summarise_bill(title: str, author: str, subject: str) -> dict:
    """Returns {'short_title': str, 'summary': str, 'policy_area': str, 'policy_tags': list[str]}."""
    prompt = f"""Você é um assistente de tecnologia cívica. Dado o projeto de lei brasileiro abaixo:

Título: {title}
Autor: {author}
Ementa: {subject}

1. Escreva um título curto (máximo 10 palavras) em português claro, sem jargão jurídico.
2. Escreva um resumo de 2 frases em português simples.
3. Classifique este projeto em UMA área de política pública desta lista:
{chr(10).join(f'- {a}' for a in POLICY_AREAS)}
4. Escolha até 2 áreas secundárias da mesma lista.

Responda APENAS em JSON com as chaves: short_title, summary, policy_area, policy_tags (array)."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    import json
    return json.loads(message.content[0].text)


def summarise_speech(speaker: str, date: str, text: str) -> dict:
    """Returns {'summary': str, 'keywords': list[str], 'policy_tags': list[str]}."""
    prompt = f"""Você é um assistente de tecnologia cívica. Resuma o discurso parlamentar abaixo em 3 frases em português simples.
Extraia também 5-7 palavras-chave e classifique em até 2 áreas de política pública desta lista:
{chr(10).join(f'- {a}' for a in POLICY_AREAS)}

Orador: {speaker}
Data: {date}
Texto: {text[:4000]}

Responda APENAS em JSON com as chaves: summary, keywords (array), policy_tags (array)."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    import json
    return json.loads(message.content[0].text)


def generate_politician_bio(name: str, party: str, state: str, office: str, committees: list[str]) -> str:
    """Returns a 3-sentence AI biography for a politician."""
    committees_str = ", ".join(committees) if committees else "nenhum comitê registrado"
    prompt = f"""Escreva uma biografia de 3 frases em português simples sobre o(a) parlamentar brasileiro(a):

Nome: {name}
Partido: {party}
Estado: {state}
Cargo: {office}
Comitês: {committees_str}

Seja factual e objetivo. Não use jargão político. Responda apenas com o texto da biografia."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()
