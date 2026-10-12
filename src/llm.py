from __future__ import annotations

"""LLM client dùng chung — OpenAI hoặc Gemini (qua endpoint tương thích OpenAI).

Provider được chọn trong config.py theo key có trong .env. Với Gemini free tier,
mọi lời gọi đi qua 1 rate limiter chung (LLM_RPM) để không bị 429.
"""

import os, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import LLM_MODEL, LLM_RPM

_CLIENT = None
_LIMITER = None
last_wait_s = 0.0  # thời gian lời gọi chat() gần nhất phải chờ rate limiter


def get_rate_limiter():
    """Rate limiter chung cho cả pipeline lẫn RAGAS. None nếu không giới hạn (LLM_RPM=0)."""
    global _LIMITER
    if LLM_RPM <= 0:
        return None
    if _LIMITER is None:
        from langchain_core.rate_limiters import InMemoryRateLimiter
        _LIMITER = InMemoryRateLimiter(requests_per_second=LLM_RPM / 60,
                                       check_every_n_seconds=0.1, max_bucket_size=1)
    return _LIMITER


def make_client(**kwargs):
    """OpenAI client mà mọi HTTP request (kể cả retry) đều chờ rate limiter chung.

    Free tier trả 429 kèm "retry in ~55s", dài hơn backoff tối đa của SDK, nên phải chặn
    trước khi gửi thay vì trông vào retry. LLM_RPM=0 → client thường.
    """
    from openai import OpenAI
    kwargs.setdefault("max_retries", 8)
    limiter = get_rate_limiter()
    if limiter is None:
        return OpenAI(**kwargs)
    import httpx

    class ThrottledTransport(httpx.HTTPTransport):
        def handle_request(self, request):
            limiter.acquire(blocking=True)
            return super().handle_request(request)

    return OpenAI(http_client=httpx.Client(transport=ThrottledTransport()), **kwargs)


def chat(system: str, user: str, max_tokens: int | None = None, json_mode: bool = False) -> str:
    """1 lần gọi chat completion (temperature=0), trả về content đã strip."""
    global _CLIENT, last_wait_s
    if _CLIENT is None:
        from openai import OpenAI
        _CLIENT = OpenAI(max_retries=8)  # đọc OPENAI_API_KEY / OPENAI_BASE_URL do config.py set

    limiter = get_rate_limiter()
    t0 = time.perf_counter()
    if limiter is not None:
        limiter.acquire(blocking=True)
    last_wait_s = time.perf_counter() - t0

    kwargs = {}
    if max_tokens:
        kwargs["max_tokens"] = max_tokens
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    resp = _CLIENT.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0,
        **kwargs,
    )
    return (resp.choices[0].message.content or "").strip()
