"""Track completed mock LLM costs in Redis per UTC day."""

from datetime import datetime, timezone

from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

# USD per 1,000 tokens for the model simulated in this lab.
PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006
RETENTION_SECONDS = 2 * 24 * 60 * 60


def daily_cost_key() -> str:
    day = datetime.now(timezone.utc).date().isoformat()
    return f"agent:{settings.environment}:cost:{day}"


def check_budget() -> None:
    total_cost = float(r.get(daily_cost_key()) or 0)
    if total_cost >= settings.daily_budget_usd:
        raise HTTPException(status_code=402, detail="Daily budget exhausted")


def record_cost(input_tokens: int, output_tokens: int) -> float:
    cost = (input_tokens * PRICE_INPUT_PER_1K + output_tokens * PRICE_OUTPUT_PER_1K) / 1000
    key = daily_cost_key()
    with r.pipeline() as pipeline:
        pipeline.incrbyfloat(key, cost)
        pipeline.expire(key, RETENTION_SECONDS)
        pipeline.execute()
    return cost
