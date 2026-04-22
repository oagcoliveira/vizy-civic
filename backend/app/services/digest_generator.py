"""
Digest Generator Service
========================
Handles all data-gathering, cost estimation, and LLM calls for the
on-demand Digest feature.

Pipeline per deputy:
  1. Gather votes (+ party alignment stats + linked bill context)
  2. Gather speeches
  3. Gather bills authored
  4. Build LLM prompt → internal summary
  5. (optional) Second LLM call with web_search_tool → news enrichment

Pipeline per bill:
  1. Gather tramitações in date range
  2. Gather votes + party breakdown
  3. Build LLM prompt → internal summary
  4. (optional) News enrichment call

Cost estimation:
  - Count tokens in the assembled data package using a rough character-based
    heuristic (1 token ≈ 4 characters for Portuguese text).
  - Add a flat 5 000-token buffer when enrichment=TRUE (placeholder until
    real news-call sizing is implemented).
  - Multiply by the model's per-token price to get USD estimate.
"""

import json
import re
import threading
import uuid
from datetime import date, datetime, timezone
from typing import Optional

import anthropic
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.digest import Digest

# ---------------------------------------------------------------------------
# Model pricing (USD per token, blended input+output estimate)
# ---------------------------------------------------------------------------
MODEL_CONFIGS = {
    "sonnet": {
        "model_id": "claude-sonnet-4-5",
        "price_per_token": 0.000003,   # $3 / 1M tokens blended
        "label": "Claude Sonnet",
    },
    "haiku": {
        "model_id": "claude-haiku-4-5",
        "price_per_token": 0.0000004,  # $0.40 / 1M tokens blended
        "label": "Claude Haiku",
    },
}

COST_BLOCK_THRESHOLD = 0.30  # USD
ENRICHMENT_TOKEN_BUFFER = 5_000  # flat placeholder per item

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _chars_to_tokens(text: str) -> int:
    """Rough token estimate: 1 token ≈ 4 characters for Portuguese text."""
    return max(1, len(text) // 4)


def _date_range_label(date_range: str) -> tuple[date, date]:
    """Convert a preset date-range key to (start_date, end_date)."""
    today = date.today()
    from datetime import timedelta
    mapping = {
        "yesterday": (today - timedelta(days=1), today - timedelta(days=1)),
        "last_7":    (today - timedelta(days=7),  today),
        "last_15":   (today - timedelta(days=15), today),
        "last_30":   (today - timedelta(days=30), today),
        "last_60":   (today - timedelta(days=60), today),
    }
    return mapping.get(date_range, (today - timedelta(days=7), today))


def _fmt_date(d) -> str:
    if d is None:
        return "—"
    if isinstance(d, (datetime, date)):
        return d.strftime("%d/%m/%Y")
    return str(d)


# ---------------------------------------------------------------------------
# Data gathering — deputies
# ---------------------------------------------------------------------------

def gather_deputy_data(db: Session, politician_id: int, start: date, end: date) -> dict:
    """Fetch all relevant data for a deputy in the date range."""

    # Basic info
    pol = db.execute(text("""
        SELECT p.id, p.name, p.short_name, p.state, p.photo_url,
               pa.acronym AS party, pa.id AS party_id
        FROM core.politicians p
        LEFT JOIN core.parties pa ON pa.id = p.party_id
        WHERE p.id = :pid
    """), {"pid": politician_id}).fetchone()
    if not pol:
        return {}
    pol = dict(pol._mapping)

    # Votes in range
    votes = db.execute(text("""
        SELECT iv.vote, iv.party_at_time, iv.party_orientation, iv.followed_orientation,
               v.id AS votacao_id, v.description AS votacao_description,
               v.voted_at, v.result,
               b.id AS bill_id, b.type AS bill_type, b.number AS bill_number,
               b.year AS bill_year, b.ementa AS bill_ementa, b.title AS bill_title,
               b.author_label AS bill_author
        FROM core.individual_votes iv
        JOIN core.votacoes v ON v.id = iv.votacao_id
        LEFT JOIN core.votacao_bills vb ON vb.votacao_id = v.id AND vb.is_primary = TRUE
        LEFT JOIN core.bills b ON b.id = vb.bill_id
        WHERE iv.politician_id = :pid
          AND v.voted_at::date BETWEEN :start AND :end
        ORDER BY v.voted_at DESC
    """), {"pid": politician_id, "start": start, "end": end}).fetchall()
    votes = [dict(r._mapping) for r in votes]

    # Enrich each vote with party alignment %
    for v in votes:
        if v.get("votacao_id"):
            stats = db.execute(text("""
                SELECT
                    COUNT(*) FILTER (WHERE iv2.vote = :vote AND iv2.party_at_time = :party) AS same_vote_count,
                    COUNT(*) FILTER (WHERE iv2.party_at_time = :party) AS party_total
                FROM core.individual_votes iv2
                WHERE iv2.votacao_id = :vid
            """), {
                "vote": v["vote"],
                "party": v.get("party_at_time") or pol["party"],
                "vid": v["votacao_id"],
            }).fetchone()
            if stats and stats[1]:
                pct = round(100 * stats[0] / stats[1])
                v["party_alignment_pct"] = pct
                v["voted_against_party"] = (
                    v.get("followed_orientation") is False or pct < 30
                )
            else:
                v["party_alignment_pct"] = None
                v["voted_against_party"] = False

    # Speeches in range
    speeches = db.execute(text("""
        SELECT s.id, s.delivered_at, s.phase, s.summary, s.transcricao,
               s.keywords, s.policy_tags
        FROM core.speeches s
        WHERE s.politician_id = :pid
          AND s.delivered_at::date BETWEEN :start AND :end
        ORDER BY s.delivered_at DESC
    """), {"pid": politician_id, "start": start, "end": end}).fetchall()
    speeches = [dict(r._mapping) for r in speeches]

    # Bills authored in range
    bills_authored = db.execute(text("""
        SELECT b.id, b.type, b.number, b.year, b.title, b.ementa,
               b.short_title, b.summary, b.status, b.policy_area,
               b.presented_at
        FROM core.bills b
        WHERE b.author_politician_id = :pid
          AND b.presented_at::date BETWEEN :start AND :end
        ORDER BY b.presented_at DESC
    """), {"pid": politician_id, "start": start, "end": end}).fetchall()
    bills_authored = [dict(r._mapping) for r in bills_authored]

    return {
        "politician": pol,
        "votes": votes,
        "speeches": speeches,
        "bills_authored": bills_authored,
    }


def has_deputy_activity(data: dict) -> bool:
    return bool(data.get("votes") or data.get("speeches") or data.get("bills_authored"))


# ---------------------------------------------------------------------------
# Data gathering — bills
# ---------------------------------------------------------------------------

def gather_bill_data(db: Session, bill_id: int, start: date, end: date) -> dict:
    """Fetch all relevant data for a bill in the date range."""

    bill = db.execute(text("""
        SELECT b.id, b.type, b.number, b.year, b.title, b.ementa,
               b.short_title, b.summary, b.status, b.policy_area,
               b.author_label, b.presented_at,
               p.id AS author_politician_id, p.short_name AS author_name,
               pa.acronym AS author_party
        FROM core.bills b
        LEFT JOIN core.politicians p ON p.id = b.author_politician_id
        LEFT JOIN core.parties pa ON pa.id = p.party_id
        WHERE b.id = :bid
    """), {"bid": bill_id}).fetchone()
    if not bill:
        return {}
    bill = dict(bill._mapping)

    # Tramitações in range
    events = db.execute(text("""
        SELECT id, sequence, event_date, stage, description, summary, venue
        FROM core.legislative_events
        WHERE bill_id = :bid
          AND event_date::date BETWEEN :start AND :end
        ORDER BY sequence ASC
    """), {"bid": bill_id, "start": start, "end": end}).fetchall()
    events = [dict(r._mapping) for r in events]

    # Votes in range
    votes = db.execute(text("""
        SELECT v.id, v.description, v.voted_at, v.result, v.vote_type
        FROM core.votacoes v
        JOIN core.votacao_bills vb ON vb.votacao_id = v.id
        WHERE vb.bill_id = :bid
          AND v.voted_at::date BETWEEN :start AND :end
        ORDER BY v.voted_at DESC
    """), {"bid": bill_id, "start": start, "end": end}).fetchall()
    votes = [dict(r._mapping) for r in votes]

    # Party breakdown for each vote
    for v in votes:
        breakdown = db.execute(text("""
            SELECT iv.party_at_time AS party,
                   iv.vote,
                   COUNT(*) AS count
            FROM core.individual_votes iv
            WHERE iv.votacao_id = :vid
              AND iv.party_at_time IS NOT NULL
            GROUP BY iv.party_at_time, iv.vote
            ORDER BY iv.party_at_time, iv.vote
        """), {"vid": v["id"]}).fetchall()
        v["party_breakdown"] = [dict(r._mapping) for r in breakdown]

    return {
        "bill": bill,
        "events": events,
        "votes": votes,
    }


def has_bill_activity(data: dict) -> bool:
    return bool(data.get("events") or data.get("votes"))


# ---------------------------------------------------------------------------
# Token counting for cost estimation
# ---------------------------------------------------------------------------

def estimate_deputy_tokens(data: dict) -> int:
    parts = []
    pol = data.get("politician", {})
    parts.append(f"{pol.get('name')} {pol.get('party')} {pol.get('state')}")
    for v in data.get("votes", []):
        parts.append(
            f"Vote: {v.get('vote')} on {v.get('votacao_description','')} "
            f"Bill: {v.get('bill_ementa','')[:300]}"
        )
    for s in data.get("speeches", []):
        text_content = s.get("transcricao") or s.get("summary") or ""
        parts.append(text_content[:2000])
    for b in data.get("bills_authored", []):
        parts.append(f"{b.get('title','')} {b.get('ementa','')[:500]}")
    combined = " ".join(parts)
    return _chars_to_tokens(combined)


def estimate_bill_tokens(data: dict) -> int:
    parts = []
    bill = data.get("bill", {})
    parts.append(f"{bill.get('title','')} {bill.get('ementa','')[:1000]}")
    for e in data.get("events", []):
        parts.append(f"{e.get('stage','')} {e.get('description','')}")
    for v in data.get("votes", []):
        parts.append(f"Vote: {v.get('description','')} Result: {v.get('result','')}")
    combined = " ".join(parts)
    return _chars_to_tokens(combined)


# ---------------------------------------------------------------------------
# Cost estimation endpoint logic
# ---------------------------------------------------------------------------

def estimate_digest_cost(
    db: Session,
    deputy_ids: list[int],
    bill_ids: list[int],
    date_range: str,
    enrichment: bool,
    model_key: str,
) -> dict:
    """
    Returns:
      {
        "estimated_cost_usd": float,
        "total_tokens": int,
        "blocked": bool,
        "inactive_deputies": [...],
        "inactive_bills": [...],
        "active_deputies": [...],
        "active_bills": [...],
      }
    """
    start, end = _date_range_label(date_range)
    model = MODEL_CONFIGS.get(model_key, MODEL_CONFIGS["haiku"])
    price_per_token = model["price_per_token"]

    active_deputies = []
    inactive_deputies = []
    active_bills = []
    inactive_bills = []
    total_tokens = 0

    for pid in deputy_ids:
        data = gather_deputy_data(db, pid, start, end)
        if not data:
            continue
        pol = data["politician"]
        if has_deputy_activity(data):
            tokens = estimate_deputy_tokens(data)
            total_tokens += tokens
            active_deputies.append({
                "id": pid,
                "name": pol.get("short_name"),
                "tokens": tokens,
            })
        else:
            inactive_deputies.append({
                "id": pid,
                "name": pol.get("short_name"),
            })

    for bid in bill_ids:
        data = gather_bill_data(db, bid, start, end)
        if not data:
            continue
        bill = data["bill"]
        label = f"{bill.get('type','')} {bill.get('number','')}/{bill.get('year','')}"
        if has_bill_activity(data):
            tokens = estimate_bill_tokens(data)
            total_tokens += tokens
            active_bills.append({
                "id": bid,
                "label": label,
                "tokens": tokens,
            })
        else:
            inactive_bills.append({
                "id": bid,
                "label": label,
            })

    # Add enrichment buffer
    n_active = len(active_deputies) + len(active_bills)
    if enrichment and n_active > 0:
        total_tokens += ENRICHMENT_TOKEN_BUFFER * n_active

    estimated_cost = round(total_tokens * price_per_token, 6)
    blocked = estimated_cost > COST_BLOCK_THRESHOLD

    return {
        "estimated_cost_usd": estimated_cost,
        "total_tokens": total_tokens,
        "blocked": blocked,
        "inactive_deputies": inactive_deputies,
        "inactive_bills": inactive_bills,
        "active_deputies": active_deputies,
        "active_bills": active_bills,
    }


# ---------------------------------------------------------------------------
# LLM helpers
# ---------------------------------------------------------------------------

def _get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def _build_deputy_prompt(data: dict, language: str, start: date, end: date) -> str:
    pol = data["politician"]
    lang_instruction = (
        "Respond in English." if language == "en"
        else "Responda em português."
    )
    votes_text = ""
    for v in data["votes"]:
        against = " [VOTED AGAINST PARTY LINE]" if v.get("voted_against_party") else ""
        pct = v.get("party_alignment_pct")
        pct_str = f" ({pct}% of party voted the same)" if pct is not None else ""
        bill_ctx = ""
        if v.get("bill_ementa"):
            bill_ctx = (
                f"\n    [Context — bill not authored by this deputy: "
                f"{v.get('bill_type','')} {v.get('bill_number','')}/{v.get('bill_year','')}: "
                f"{v.get('bill_ementa','')[:400]}]"
            )
        votes_text += (
            f"- {_fmt_date(v.get('voted_at'))}: {v.get('vote','').upper()}{against}{pct_str}"
            f" | {v.get('votacao_description','')[:200]}{bill_ctx}\n"
        )

    speeches_text = ""
    for s in data["speeches"]:
        content = s.get("transcricao") or s.get("summary") or "(no text available)"
        speeches_text += (
            f"- {_fmt_date(s.get('delivered_at'))}: {content[:1500]}\n"
        )

    bills_text = ""
    for b in data["bills_authored"]:
        bills_text += (
            f"- {b.get('type','')} {b.get('number','')}/{b.get('year','')}: "
            f"{b.get('ementa','')[:500]} [Status: {b.get('status','')}]\n"
        )

    return f"""You are an objective civic technology analyst. {lang_instruction}

Analyze the following legislative activity data for the Brazilian federal deputy listed below, covering the period {_fmt_date(start)} to {_fmt_date(end)}.

DEPUTY: {pol.get('name')} | Party: {pol.get('party')} | State: {pol.get('state')}

=== VOTES ({len(data['votes'])} total) ===
{votes_text or '(none in this period)'}

=== SPEECHES ({len(data['speeches'])} total) ===
{speeches_text or '(none in this period)'}

=== BILLS AUTHORED ({len(data['bills_authored'])} total) ===
{bills_text or '(none in this period)'}

Produce a structured JSON response with EXACTLY these keys:
{{
  "intro_paragraph": "A single concise paragraph (3-5 sentences) summarizing the deputy's most notable activity. Written to appear directly below the deputy's header card.",
  "long_text": "A detailed, objective narrative (400-700 words) covering all activity. Organize by theme (votes, speeches, bills). Flag any votes against the party line. Do NOT use bullet points — write in full paragraphs.",
  "key_numbers": {{
    "votes": {len(data['votes'])},
    "speeches": {len(data['speeches'])},
    "bills_authored": {len(data['bills_authored'])}
  }}
}}

Rules:
- Be objective and factual. No political opinion.
- Avoid legal jargon.
- Do not add any text outside the JSON object.
"""


def _build_bill_prompt(data: dict, language: str, start: date, end: date) -> str:
    bill = data["bill"]
    lang_instruction = (
        "Respond in English." if language == "en"
        else "Responda em português."
    )
    author_str = bill.get("author_name") or bill.get("author_label") or "Unknown"
    if bill.get("author_party"):
        author_str += f" ({bill['author_party']})"

    events_text = ""
    for e in data["events"]:
        events_text += (
            f"- {_fmt_date(e.get('event_date'))}: [{e.get('stage','')}] "
            f"{e.get('description','')[:300]}\n"
        )

    votes_text = ""
    for v in data["votes"]:
        breakdown_str = ""
        for row in v.get("party_breakdown", [])[:10]:
            breakdown_str += f"{row['party']}: {row['vote']} ({row['count']}), "
        votes_text += (
            f"- {_fmt_date(v.get('voted_at'))}: {v.get('description','')[:200]} "
            f"| Result: {v.get('result','')} | Party breakdown: {breakdown_str.rstrip(', ')}\n"
        )

    return f"""You are an objective civic technology analyst. {lang_instruction}

Analyze the following legislative data for the Brazilian bill listed below, covering the period {_fmt_date(start)} to {_fmt_date(end)}.

BILL: {bill.get('type','')} {bill.get('number','')}/{bill.get('year','')}
FULL TITLE (ementa): {bill.get('ementa','')[:800]}
AUTHOR: {author_str}
CURRENT STATUS: {bill.get('status','')}

=== TRAMITAÇÕES / LEGISLATIVE EVENTS ({len(data['events'])} in period) ===
{events_text or '(none in this period)'}

=== VOTES ({len(data['votes'])} in period) ===
{votes_text or '(none in this period)'}

Produce a structured JSON response with EXACTLY these keys:
{{
  "intro_paragraph": "A single concise paragraph (3-5 sentences) summarizing the bill's most notable developments in this period.",
  "long_summary": "A detailed, objective narrative (300-600 words) covering the bill's progression, key votes, and party dynamics. Identify key supporters and opponents based on party breakdown data. Do NOT use bullet points — write in full paragraphs."
}}

Rules:
- Be objective and factual. No political opinion.
- Avoid legal jargon.
- Do not add any text outside the JSON object.
"""


def _build_enrichment_prompt(internal_summary: str, subject_name: str, start: date, end: date, language: str) -> str:
    lang_instruction = (
        "Respond in English." if language == "en"
        else "Responda em português."
    )
    return f"""Here is a summary of {subject_name}'s activity over the time frame {_fmt_date(start)}-{_fmt_date(end)}.

{internal_summary}

Search the web for news coverage from major Brazilian outlets (Estadão, Folha de S.Paulo, O Globo, and other reputable sources) that discuss the activities and themes included in the summary attached, and that could be useful to better understand the bill that is the subject of the votes included in the summary, any positions taken by the deputy in their speeches (if any), and any coverage of bills proposed by the deputy (if any). Review the information and only include information that is relevant, timely and that adds depth to the summary attached. The language should be objective, clear and should avoid technical jargon.

{lang_instruction}

Return ONLY a valid JSON object with EXACTLY these keys — no introductory text, no conversational elements:
{{
  "analysis": "A 2-4 paragraph objective synthesis of the relevant news coverage and how it contextualizes the activity summary above.",
  "sources": [
    {{
      "title": "Article headline",
      "outlet": "News outlet name",
      "url": "https://...",
      "date": "DD/MM/YYYY or approximate date"
    }}
  ]
}}

If no relevant news is found, return: {{"analysis": "No relevant news coverage found for this period.", "sources": []}}
"""


def _call_llm(client: anthropic.Anthropic, model_id: str, prompt: str) -> dict:
    """Call the LLM and parse JSON response."""
    msg = client.messages.create(
        model=model_id,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text.strip()
    # Strip markdown code fences if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


def _call_llm_with_search(client: anthropic.Anthropic, model_id: str, prompt: str) -> dict:
    """Call the LLM with web_search tool enabled and parse JSON response."""
    msg = client.messages.create(
        model=model_id,
        max_tokens=2048,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}],
    )
    # Extract text blocks from the response (may include tool_use blocks)
    text_parts = [
        block.text for block in msg.content
        if hasattr(block, "text") and block.text
    ]
    raw = " ".join(text_parts).strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: extract JSON object from the text
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            return json.loads(match.group())
        return {"analysis": raw, "sources": []}


# ---------------------------------------------------------------------------
# Individual report builders
# ---------------------------------------------------------------------------

def build_deputy_report(
    db: Session,
    politician_id: int,
    start: date,
    end: date,
    language: str,
    model_key: str,
    enrichment: bool,
) -> Optional[dict]:
    """Returns a complete deputy report dict, or None if no activity."""
    data = gather_deputy_data(db, politician_id, start, end)
    if not data or not has_deputy_activity(data):
        return None

    pol = data["politician"]
    client = _get_client()
    model_id = MODEL_CONFIGS[model_key]["model_id"]

    # Step 1: Internal summary
    prompt = _build_deputy_prompt(data, language, start, end)
    ai_result = _call_llm(client, model_id, prompt)

    report = {
        "type": "deputy",
        "politician_id": politician_id,
        "name": pol.get("name"),
        "short_name": pol.get("short_name"),
        "party": pol.get("party"),
        "state": pol.get("state"),
        "photo_url": pol.get("photo_url"),
        "key_numbers": ai_result.get("key_numbers", {
            "votes": len(data["votes"]),
            "speeches": len(data["speeches"]),
            "bills_authored": len(data["bills_authored"]),
        }),
        "intro_paragraph": ai_result.get("intro_paragraph", ""),
        "long_text": ai_result.get("long_text", ""),
        "news_enrichment": None,
    }

    # Step 2: Optional news enrichment
    if enrichment:
        internal_summary = f"{report['intro_paragraph']}\n\n{report['long_text']}"
        enrich_prompt = _build_enrichment_prompt(
            internal_summary,
            pol.get("name", ""),
            start,
            end,
            language,
        )
        try:
            enrich_result = _call_llm_with_search(client, model_id, enrich_prompt)
            report["news_enrichment"] = enrich_result
        except Exception as e:
            report["news_enrichment"] = {
                "analysis": f"News enrichment failed: {str(e)}",
                "sources": [],
            }

    return report


def build_bill_report(
    db: Session,
    bill_id: int,
    start: date,
    end: date,
    language: str,
    model_key: str,
    enrichment: bool,
) -> Optional[dict]:
    """Returns a complete bill report dict, or None if no activity."""
    data = gather_bill_data(db, bill_id, start, end)
    if not data or not has_bill_activity(data):
        return None

    bill = data["bill"]
    client = _get_client()
    model_id = MODEL_CONFIGS[model_key]["model_id"]

    # Step 1: Internal summary
    prompt = _build_bill_prompt(data, language, start, end)
    ai_result = _call_llm(client, model_id, prompt)

    bill_label = f"{bill.get('type','')} {bill.get('number','')}/{bill.get('year','')}"
    author_str = bill.get("author_name") or bill.get("author_label") or "Unknown"
    if bill.get("author_party"):
        author_str += f" ({bill['author_party']})"

    report = {
        "type": "bill",
        "bill_id": bill_id,
        "label": bill_label,
        "title": bill.get("title") or bill.get("ementa", "")[:120],
        "ementa": bill.get("ementa", ""),
        "bill_type": bill.get("type"),
        "number": bill.get("number"),
        "year": bill.get("year"),
        "presented_at": _fmt_date(bill.get("presented_at")),
        "author": author_str,
        "status": bill.get("status"),
        "intro_paragraph": ai_result.get("intro_paragraph", ""),
        "long_summary": ai_result.get("long_summary", ""),
        "news_enrichment": None,
    }

    # Step 2: Optional news enrichment
    if enrichment:
        internal_summary = f"{report['intro_paragraph']}\n\n{report['long_summary']}"
        enrich_prompt = _build_enrichment_prompt(
            internal_summary,
            bill_label,
            start,
            end,
            language,
        )
        try:
            enrich_result = _call_llm_with_search(client, model_id, enrich_prompt)
            report["news_enrichment"] = enrich_result
        except Exception as e:
            report["news_enrichment"] = {
                "analysis": f"News enrichment failed: {str(e)}",
                "sources": [],
            }

    return report


# ---------------------------------------------------------------------------
# Main async runner
# ---------------------------------------------------------------------------

def _generate_digest_worker(digest_id: str, params: dict):
    """
    Background worker. Runs in a separate thread.
    Reads params, builds all reports, saves result to DB.
    """
    db = SessionLocal()
    try:
        digest = db.query(Digest).filter(Digest.id == uuid.UUID(digest_id)).first()
        if not digest:
            return

        deputy_ids = params.get("deputy_ids", [])
        bill_ids = params.get("bill_ids", [])
        date_range = params.get("date_range", "last_7")
        language = params.get("language", "pt")
        enrichment = params.get("enrichment", False)
        model_key = params.get("model", "haiku")

        start, end = _date_range_label(date_range)

        reports = []
        errors = []

        # Process deputies
        for pid in deputy_ids:
            try:
                report = build_deputy_report(db, pid, start, end, language, model_key, enrichment)
                if report:
                    reports.append(report)
            except Exception as e:
                errors.append(f"Deputy {pid}: {str(e)}")

        # Process bills
        for bid in bill_ids:
            try:
                report = build_bill_report(db, bid, start, end, language, model_key, enrichment)
                if report:
                    reports.append(report)
            except Exception as e:
                errors.append(f"Bill {bid}: {str(e)}")

        content = {
            "reports": reports,
            "date_range": {"start": str(start), "end": str(end)},
            "language": language,
            "model": model_key,
            "enrichment": enrichment,
            "errors": errors,
        }

        digest.status = "completed" if not errors or reports else "failed"
        if errors and not reports:
            digest.status = "failed"
            digest.error_message = "; ".join(errors)
        digest.content = content
        digest.completed_at = datetime.now(timezone.utc)
        db.commit()

    except Exception as e:
        try:
            digest = db.query(Digest).filter(Digest.id == uuid.UUID(digest_id)).first()
            if digest:
                digest.status = "failed"
                digest.error_message = str(e)
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


def launch_digest_generation(digest_id: str, params: dict):
    """Spawn a background thread to generate the digest asynchronously."""
    t = threading.Thread(
        target=_generate_digest_worker,
        args=(digest_id, params),
        daemon=True,
    )
    t.start()
