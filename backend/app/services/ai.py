"""AI assistant (Anthropic Claude) for report commentary and data analysis.

Two capabilities, both opt-in (gated by settings.ai_enabled AND an API key):

  * generate_commentary(data)      -> a manager-facing written analysis of a
                                      month's figures, embedded in the Month End
                                      Report and shown on the dashboard.
  * answer_question(question, db)   -> a plain-English answer to an ad-hoc
                                      question, grounded in a compact digest of
                                      the plant's own production history.

Design notes:
  * ai_available() is the single gate every caller checks first. When the
    feature is off or unconfigured, callers degrade gracefully — the report
    omits the commentary section, the endpoint returns 503.
  * Model is claude-opus-4-8 with adaptive thinking (per the Anthropic SDK
    guidance), at medium effort to balance quality against latency/cost.
  * Figures are pre-aggregated by collect_context() so we send a small, bounded
    JSON digest — never raw shift rows — keeping prompts cheap and stable.
"""
import json
import logging
from datetime import date

from sqlalchemy.orm import Session

from ..core.config import settings
from ..models.production import ProductionShift
from ..models.operations import Delivery, MonthlyStock

logger = logging.getLogger("app.ai")

# Conservative caps so a single call can't run away on cost or latency.
_MAX_TOKENS = 2000
_TIMEOUT_S = 90
_CONTEXT_MONTHS = 18

SYSTEM_PROMPT = (
    "You are the operations analyst for the Fibre Mold Plant at Golden "
    "Manufacturers (a recycling department that moulds egg trays / cartons from "
    "waste paper in Fiji). You write for the plant manager and senior management.\n\n"
    "Ground every statement in the figures provided — never invent numbers. When "
    "the data doesn't answer a question, say so plainly. Use the plant's own "
    "terms: trays, shifts (Day/Afternoon/Night), re-pulp/reject rate, downtime, "
    "fuel efficiency (litres of diesel per 1,000 trays), bales (raw paper), and "
    "pallets. Be concise, factual, and specific with numbers; avoid filler and "
    "hype. Figures are in NZ/Fiji style (commas for thousands)."
)


def ai_available() -> bool:
    """True only when the feature is enabled, a key is set, and the SDK imports."""
    if not settings.ai_enabled or not settings.anthropic_api_key.strip():
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        logger.warning("[ai] AI_ENABLED but the 'anthropic' package is not installed")
        return False
    return True


def _client():
    import anthropic
    return anthropic.Anthropic(api_key=settings.anthropic_api_key, timeout=_TIMEOUT_S)


def _complete(messages: list[dict], system: str = SYSTEM_PROMPT,
              max_tokens: int = _MAX_TOKENS) -> str:
    """One Claude call -> the concatenated text of the reply.

    Raises on transport/API errors; callers that must not fail (report builders)
    wrap this and fall back to no commentary.
    """
    client = _client()
    resp = client.messages.create(
        model=settings.ai_model,
        max_tokens=max_tokens,
        thinking={"type": "adaptive"},
        output_config={"effort": "medium"},
        system=system,
        messages=messages,
    )
    if resp.stop_reason == "refusal":
        return "The assistant was unable to answer that request."
    return "".join(b.text for b in resp.content if b.type == "text").strip()


# ---------------------------------------------------------------------------
# Context — a small, bounded digest of the plant's own history
# ---------------------------------------------------------------------------
def collect_context(db: Session, months: int = _CONTEXT_MONTHS) -> dict:
    """Aggregate the last `months` months of production/deliveries/stock into a
    compact JSON-able digest to ground the model. Aggregation is done in Python
    over the (few hundred) soft-delete-filtered rows — dialect-agnostic."""
    shifts = (db.query(ProductionShift)
              .filter(ProductionShift.deleted_at.is_(None))
              .order_by(ProductionShift.work_date).all())
    deliveries = (db.query(Delivery)
                  .filter(Delivery.deleted_at.is_(None)).all())
    stock = (db.query(MonthlyStock)
             .filter(MonthlyStock.deleted_at.is_(None)).all())

    by_month: dict[str, dict] = {}

    def bucket(period: str) -> dict:
        return by_month.setdefault(period, {
            "period": period, "trays": 0.0, "fuel_l": 0.0, "downtime_min": 0.0,
            "sched_hours": 0.0, "repulped": 0.0, "active_days": set(), "shifts": 0,
            "deliveries": 0, "trays_delivered": 0.0,
        })

    for s in shifts:
        b = bucket(f"{s.work_date.year:04d}-{s.work_date.month:02d}")
        b["trays"] += s.qty or 0
        b["fuel_l"] += s.fuel_use or 0
        b["downtime_min"] += s.downtime_min or 0
        b["sched_hours"] += s.sched_hours or 0
        b["repulped"] += s.repulped or 0
        b["shifts"] += 1
        if (s.qty or 0) > 0:
            b["active_days"].add(s.work_date)
    for d in deliveries:
        b = bucket(f"{d.work_date.year:04d}-{d.work_date.month:02d}")
        b["deliveries"] += 1
        b["trays_delivered"] += (d.tray30 or 0) + (d.tray12n or 0) + (d.tray12ff or 0)

    rows = []
    for period in sorted(by_month)[-months:]:
        b = by_month[period]
        trays, sched = b["trays"], b["sched_hours"]
        rows.append({
            "month": period,
            "trays_produced": round(trays),
            "active_days": len(b["active_days"]),
            "avg_trays_per_day": round(trays / len(b["active_days"])) if b["active_days"] else 0,
            "diesel_litres": round(b["fuel_l"]),
            "fuel_eff_l_per_1k_trays": round(b["fuel_l"] / trays * 1000, 1) if trays else None,
            "downtime_hours": round(b["downtime_min"] / 60, 1),
            "downtime_pct_of_scheduled": round(b["downtime_min"] / 60 / sched * 100, 1) if sched else None,
            "repulped_trays": round(b["repulped"]),
            "reject_rate_pct": round(b["repulped"] / trays * 100, 1) if trays else None,
            "deliveries": b["deliveries"],
            "trays_delivered": round(b["trays_delivered"]),
        })

    stock_rows = sorted(
        ({"month": s.period, "diesel_on_hand_l": s.diesel_eom,
          "bales_used": s.bales_used, "bales_purchased": s.bales_purchased,
          "pallets_wrapped": s.pallets_wrapped, "labels_used": s.labels_used}
         for s in stock),
        key=lambda r: r["month"])[-months:]

    return {"monthly_production": rows, "monthly_stock": stock_rows}


# ---------------------------------------------------------------------------
# Report commentary
# ---------------------------------------------------------------------------
def generate_commentary(data: dict) -> str:
    """Write the 'Plant Manager's Commentary' for one month's Month End figures.

    `data` is the dict from report_monthend.collect_monthend(). Returns the
    commentary text, or "" if AI is unavailable or the call fails (so the report
    still builds without it)."""
    if not ai_available():
        return ""
    m = data.get("metrics", {})
    payload = {
        "month": data.get("title"),
        "production": {
            "trays_produced": m.get("total_qty"),
            "active_days": m.get("active_days"),
            "avg_trays_per_day": m.get("avg_per_day"),
            "diesel_litres": m.get("total_fuel"),
            "fuel_eff_l_per_1k_trays": m.get("fuel_eff"),
            "downtime_hours": m.get("total_downtime_hrs"),
            "downtime_pct_of_scheduled": m.get("downtime_pct"),
            "repulped_trays": m.get("total_repulped"),
            "reject_rate_pct": m.get("repulp_rate"),
            "deliveries": m.get("delivery_count"),
        },
        "vs_previous_month_pct_change": data.get("deltas"),
        "previous_month": data.get("prev_label"),
        "stock_and_materials": {
            "diesel_on_hand_litres": data.get("diesel_eom"),
            "bales_used": data.get("bales_used"),
            "bales_purchased": data.get("bales_purchased"),
            "pallets_wrapped": data.get("pallets", {}).get("total"),
        },
    }
    prompt = (
        "Write a 'Plant Manager's Commentary' for the month-end report using ONLY "
        "the figures below.\n\n"
        f"```json\n{json.dumps(payload, indent=1, default=str)}\n```\n\n"
        "Structure it as:\n"
        "1. A two to three sentence headline on the month's production and how it "
        "moved versus the previous month.\n"
        "2. 3-5 short bullet points on the notable drivers — fuel efficiency, "
        "downtime, reject/re-pulp rate, deliveries, and materials/stock — each "
        "citing the figure.\n"
        "3. A short 'Recommended actions' list of 2-3 concrete, plant-relevant "
        "next steps justified by the numbers.\n\n"
        "Keep it under ~250 words. Plain text with simple bullet dashes — no "
        "markdown headers, no preamble like 'Here is'."
    )
    try:
        return _complete([{"role": "user", "content": prompt}])
    except Exception:
        logger.exception("[ai] commentary generation failed; omitting section")
        return ""


# ---------------------------------------------------------------------------
# PowerPoint deck narrative (one structured call for the whole deck)
# ---------------------------------------------------------------------------
def _extract_json(raw: str) -> dict:
    """Parse a JSON object from the model reply, tolerating ```json fences."""
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("```", 2)[1] if s.count("```") >= 2 else s.strip("`")
        if s.lstrip().lower().startswith("json"):
            s = s.lstrip()[4:]
    start, end = s.find("{"), s.rfind("}")
    if start == -1 or end == -1:
        return {}
    return json.loads(s[start:end + 1])


def generate_deck_narrative(payload: dict) -> dict:
    """One Claude call for the whole multi-month deck.

    `payload` is a compact per-month digest built by the PPTX builder. Returns:
      {
        "overall_summary": str,
        "months": {"YYYY-MM": {"production": str, "downtime": str, "fuel": str}},
        "improvement_plan": [{"title": str, "detail": str, "action": str}, ...]
      }
    or {} when AI is unavailable or the call/parse fails — so the deck still
    builds without any AI text.
    """
    if not ai_available():
        return {}
    prompt = (
        "You are writing the narrative for a management PowerPoint deck covering "
        "several months of plant data. Use ONLY the figures in this JSON:\n\n"
        f"```json\n{json.dumps(payload, indent=1, default=str)}\n```\n\n"
        "Return STRICT JSON only — no markdown, no prose, no code fences — with "
        "exactly this shape:\n"
        '{\n'
        '  "overall_summary": "<= 50 words on the key trend across the period",\n'
        '  "months": { "<YYYY-MM>": { "production": "<= 18 words", '
        '"downtime": "<= 18 words", "fuel": "<= 18 words" } },\n'
        '  "improvement_plan": [ { "title": "short issue title", '
        '"detail": "<= 30 words, cite a figure", "action": "<= 20 words, concrete next step" } ]\n'
        "}\n\n"
        "Rules: use the SAME month keys as the input. One concise sentence per "
        "month field, each citing a figure. Provide 3-5 improvement_plan items "
        "grounded in the data — e.g. dominant downtime cause, fuel-efficiency or "
        "machine-speed trend, output swings, reject rate. Never invent numbers."
    )
    try:
        raw = _complete([{"role": "user", "content": prompt}], max_tokens=3500)
        out = _extract_json(raw)
        if not isinstance(out, dict):
            return {}
        out.setdefault("overall_summary", "")
        out.setdefault("months", {})
        out.setdefault("improvement_plan", [])
        return out
    except Exception:
        logger.exception("[ai] deck narrative generation failed; omitting AI text")
        return {}


# ---------------------------------------------------------------------------
# Interactive Q&A
# ---------------------------------------------------------------------------
def answer_question(question: str, db: Session) -> str:
    """Answer a plain-English question grounded in the plant's history digest."""
    context = collect_context(db)
    prompt = (
        "Here is the Fibre Mold Plant's recent monthly data:\n\n"
        f"```json\n{json.dumps(context, indent=1, default=str)}\n```\n\n"
        f"Question: {question.strip()}\n\n"
        "Answer using only this data. Cite the relevant months and figures. If "
        "the data doesn't cover what's asked, say what's missing. Keep it concise."
    )
    return _complete([{"role": "user", "content": prompt}])
