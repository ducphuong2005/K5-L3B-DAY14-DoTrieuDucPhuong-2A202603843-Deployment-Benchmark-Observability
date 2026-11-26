"""Production AI Agent for the Day 14 lab."""

import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from time import perf_counter

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from redis.exceptions import RedisError

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, record_cost
from app.rate_limiter import check_rate_limit
from app.redis_client import r, redis_healthy
from utils.mock_llm import ask as llm_ask


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
                "level": record.levelname,
                "event": record.getMessage(),
                **getattr(record, "fields", {}),
            },
            ensure_ascii=False,
        )


handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logger = logging.getLogger(__name__)
logger.handlers = [handler]
logger.propagate = False
logger.setLevel(logging.INFO)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info(
        "startup",
        extra={"fields": {"environment": settings.environment, "port": settings.port}},
    )
    try:
        yield
    finally:
        # Uvicorn drains requests before entering the lifespan shutdown phase.
        r.close()
        logger.info("shutdown")


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


@app.middleware("http")
async def log_request(request: Request, call_next):
    started = perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        logger.info(
            "request",
            extra={
                "fields": {
                    "method": request.method,
                    "route": getattr(request.scope.get("route"), "path", "unmatched"),
                    "status": status,
                    "ms": round((perf_counter() - started) * 1000, 1),
                }
            },
        )


@app.get("/health")
def health():
    return {"status": "ok", "environment": settings.environment}


@app.get("/ready")
def ready():
    if not redis_healthy():
        raise HTTPException(status_code=503, detail="Redis unavailable")
    return {"status": "ready"}


@app.exception_handler(RedisError)
async def handle_redis_error(_request: Request, _error: RedisError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": "Redis unavailable"})


@app.post("/ask")
def ask(body: AskRequest, api_key: str = Depends(verify_api_key)):
    check_rate_limit(api_key)
    check_budget()
    answer = llm_ask(body.question)
    # The mock has no tokenizer. Estimate its input and output tokens from words.
    input_tokens = max(1, 2 * len(body.question.split()))
    output_tokens = max(1, 2 * len(answer.split()))
    record_cost(input_tokens, output_tokens)
    return {"question": body.question, "answer": answer}
