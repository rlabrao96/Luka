"""Autonomous Template Agent — discovers, generates, validates, promotes, and retires templates."""

import hashlib
import json
import logging
import random
from datetime import datetime, timedelta

import google.genai as genai
from sqlalchemy import select, func, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from modules.email.models import EmailTemplate, ParsedEmailLog, BankRegistry
from modules.email.template_executor import execute_template
from modules.email.llm_parser import parse_with_llm

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


async def discover_candidate_banks(*, db: AsyncSession) -> list[tuple[str, int, int]]:
    """Find banks with enough LLM-parsed emails but no active template."""
    min_total = settings.template_agent_min_emails
    min_recent = settings.template_agent_recency_min
    recency_days = settings.template_agent_recency_days
    cutoff = datetime.utcnow() - timedelta(days=recency_days)

    active_stmt = select(BankRegistry.bank_domain).where(
        BankRegistry.active_template_id.isnot(None)
    )
    active_result = await db.execute(active_stmt)
    active_domains = {row[0] for row in active_result.all()}

    stmt = (
        select(
            ParsedEmailLog.bank_domain,
            func.count().label("total_count"),
            func.count().filter(ParsedEmailLog.created_at >= cutoff).label("recent_count"),
        )
        .where(ParsedEmailLog.parser_used == "llm")
        .where(ParsedEmailLog.raw_email_html.isnot(None))
        .group_by(ParsedEmailLog.bank_domain)
    )
    result = await db.execute(stmt)
    rows = result.all()

    candidates = []
    for domain, total, recent in rows:
        if domain in active_domains:
            continue
        if total >= min_total and recent >= min_recent:
            candidates.append((domain, total, recent))
    return candidates


async def generate_template_json(samples: list[dict], *, bank_domain: str) -> dict | None:
    """Use LLM to generate a declarative extraction template from samples."""
    prompt = f"""You are a bank email template generator for {bank_domain}.

Given these sample bank notification emails and their correct field extractions,
generate a declarative JSON extraction template.

The template must use this exact schema:
{{
  "bank_domain": "{bank_domain}",
  "version": 1,
  "currency": "CLP",
  "selectors": {{
    "amount": {{
      "css": "CSS selector or null",
      "regex": "regex pattern with capture group or null",
      "transform": "one of: clp_integer, cop_integer, usd_cents, mxn_cents, brl_centavos, pen_centimos"
    }},
    "merchant": {{
      "css": "CSS selector or null",
      "regex": "regex pattern or null",
      "transform": "strip"
    }},
    "date": {{
      "css": "CSS selector or null",
      "regex": "regex pattern or null",
      "transform": "one of: parse_date_ddmmyyyy_hhmm, parse_date_ddmmyyyy, parse_date_mmddyy, parse_date_iso, now"
    }},
    "transaction_type": {{
      "keywords_expense": ["list", "of", "keywords"],
      "keywords_transfer": ["list"],
      "keywords_income": ["list"]
    }}
  }}
}}

Return ONLY the JSON template, no explanation.

SAMPLES:
"""
    for i, s in enumerate(samples[:10]):
        prompt += f"\n--- Sample {i+1} ---\nHTML:\n{s['html'][:2000]}\n\nCorrect extraction:\n{json.dumps(s['extraction'])}\n"

    try:
        response = await _get_client().aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=genai.types.GenerateContentConfig(temperature=0.1, max_output_tokens=2048),
        )
        text = response.text.strip()
        if text.startswith("```"):
            lines = text.split("\n")[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        return json.loads(text)
    except Exception as e:
        logger.error("Template generation failed for %s: %s", bank_domain, e)
        return None


def validate_template(template_results: list[dict], llm_results: list[dict]) -> tuple[bool, float]:
    """Validate template vs LLM ground truth. 100% amount match, 95% merchant match required."""
    if not template_results or len(template_results) != len(llm_results):
        return False, 0.0

    amount_matches = 0
    merchant_matches = 0
    total = len(template_results)

    for t_row, g_row in zip(template_results, llm_results):
        if t_row.get("amount") == g_row.get("amount"):
            amount_matches += 1
        t_merchant = (t_row.get("merchant") or "").strip().upper()
        g_merchant = (g_row.get("merchant") or "").strip().upper()
        if t_merchant == g_merchant or (t_merchant and g_merchant and t_merchant in g_merchant):
            merchant_matches += 1

    if amount_matches < total:
        return False, amount_matches / total

    merchant_accuracy = merchant_matches / total
    overall = (amount_matches + merchant_matches) / (total * 2)
    return merchant_accuracy >= 0.95, overall


def should_retire_template(shadow_results: list[dict]) -> bool:
    """ANY amount mismatch in shadow validation triggers retirement."""
    for r in shadow_results:
        if not r.get("amount_match", True):
            return True
    return False


async def promote_template(template_id, bank_domain: str, *, db: AsyncSession) -> None:
    await db.execute(
        update(EmailTemplate)
        .where(EmailTemplate.id == template_id)
        .values(status="active", promoted_at=datetime.utcnow())
    )
    await db.execute(
        update(BankRegistry)
        .where(BankRegistry.bank_domain == bank_domain)
        .values(active_template_id=template_id)
    )
    await db.commit()
    logger.info("Promoted template %s for %s", template_id, bank_domain)


async def retire_template(template_id, bank_domain: str, reason: str, *, db: AsyncSession) -> None:
    await db.execute(
        update(EmailTemplate)
        .where(EmailTemplate.id == template_id)
        .values(status="retired", retired_at=datetime.utcnow(), retired_reason=reason)
    )
    await db.execute(
        update(BankRegistry)
        .where(BankRegistry.bank_domain == bank_domain)
        .values(active_template_id=None)
    )
    await db.commit()
    logger.warning("Retired template %s for %s: %s", template_id, bank_domain, reason)


async def run_shadow_validation(*, db: AsyncSession) -> None:
    """Shadow validate active templates: compare template vs LLM on a sample."""
    rate = settings.llm_shadow_validation_rate

    stmt = select(BankRegistry).where(BankRegistry.active_template_id.isnot(None))
    result = await db.execute(stmt)
    banks = result.scalars().all()

    for bank in banks:
        cutoff = datetime.utcnow() - timedelta(days=1)
        log_stmt = select(ParsedEmailLog).where(
            and_(
                ParsedEmailLog.bank_domain == bank.bank_domain,
                ParsedEmailLog.parser_used == "template",
                ParsedEmailLog.created_at >= cutoff,
                ParsedEmailLog.shadow_match.is_(None),
            )
        )
        log_result = await db.execute(log_stmt)
        logs = log_result.scalars().all()

        sample = [entry for entry in logs if random.random() < rate]
        if not sample:
            continue

        shadow_results = []
        for log_entry in sample:
            if not log_entry.raw_email_html:
                continue
            llm_parsed, _, _ = await parse_with_llm(
                log_entry.raw_email_html,
                bank_metadata={"country": bank.country, "bank_name": bank.bank_name},
            )
            if not llm_parsed:
                continue

            template_data = log_entry.template_extraction or {}
            amount_match = template_data.get("amount") == llm_parsed.amount
            shadow_results.append({"shadow_match": True, "amount_match": amount_match})
            log_entry.shadow_match = amount_match
            log_entry.llm_extraction = {
                "merchant": llm_parsed.raw_merchant,
                "amount": llm_parsed.amount,
                "currency": llm_parsed.currency,
            }

        if shadow_results and should_retire_template(shadow_results):
            await retire_template(
                bank.active_template_id,
                bank.bank_domain,
                f"Shadow validation drift: amount mismatch in {len(shadow_results)} samples",
                db=db,
            )

    await db.commit()


async def run_template_agent(ctx: dict) -> None:
    """Main entry point — runs daily as ARQ cron job."""
    from core.database import get_db_session

    async with get_db_session() as db:
        await run_shadow_validation(db=db)

        candidates = await discover_candidate_banks(db=db)
        logger.info("Template agent found %d candidate banks", len(candidates))

        for bank_domain, total_count, recent_count in candidates:
            stmt = (
                select(ParsedEmailLog)
                .where(
                    and_(
                        ParsedEmailLog.bank_domain == bank_domain,
                        ParsedEmailLog.parser_used == "llm",
                        ParsedEmailLog.raw_email_html.isnot(None),
                        ParsedEmailLog.llm_extraction.isnot(None),
                    )
                )
                .order_by(ParsedEmailLog.created_at.desc())
                .limit(20)
            )
            result = await db.execute(stmt)
            logs = result.scalars().all()

            if len(logs) < 10:
                continue

            samples = [
                {"html": log.raw_email_html, "extraction": log.llm_extraction} for log in logs
            ]

            template_json = await generate_template_json(samples, bank_domain=bank_domain)
            if not template_json:
                continue

            template_results = []
            llm_results = []
            for s in samples:
                t_result = execute_template(s["html"], template_json, full_text="")
                if t_result:
                    template_results.append(
                        {"amount": t_result.amount, "merchant": t_result.raw_merchant}
                    )
                    llm_results.append(
                        {
                            "amount": s["extraction"]["amount"],
                            "merchant": s["extraction"]["merchant"],
                        }
                    )

            if len(template_results) < len(samples) * 0.8:
                logger.info("Template for %s failed: too many extraction failures", bank_domain)
                continue

            passed, accuracy = validate_template(template_results, llm_results)
            if not passed:
                logger.info(
                    "Template for %s failed validation (accuracy: %.2f)", bank_domain, accuracy
                )
                continue

            template_hash = hashlib.sha256(
                json.dumps(template_json, sort_keys=True).encode()
            ).hexdigest()
            new_template = EmailTemplate(
                bank_domain=bank_domain,
                country=logs[0].country or "",
                template_code=template_json,
                template_hash=template_hash,
                status="candidate",
                validated_count=len(template_results),
                accuracy=accuracy,
            )
            db.add(new_template)
            await db.flush()
            await promote_template(new_template.id, bank_domain, db=db)

        logger.info("Template agent run complete")
