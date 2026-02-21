"""LLMClient 预算/重试/超时/日志 guard 测试"""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.llm.client import LLMClient, LLMConfig, LLMProvider


def _make_client(
    budget: int = 50, max_retries: int = 2, timeout: float = 30.0, enable_logging: bool = False
) -> tuple[LLMClient, AsyncMock]:
    """构造 LLMClient，mock 掉底层 provider。"""
    config = LLMConfig(
        provider=LLMProvider.GEMINI,
        model="fake",
        api_key="fake-key",
        budget_per_session=budget,
        max_retries=max_retries,
        timeout=timeout,
        enable_logging=enable_logging,
    )
    mock_genai = MagicMock()
    mock_google = MagicMock()
    mock_google.genai = mock_genai
    with patch.dict("sys.modules", {"google": mock_google, "google.genai": mock_genai}):
        client = LLMClient(config)
    mock_chat = AsyncMock(return_value="ok")
    client._client.chat = mock_chat  # type: ignore[assignment]
    return client, mock_chat


async def test_budget_exceeded() -> None:
    client, mock_chat = _make_client(budget=2)
    await client.chat([{"role": "user", "content": "a"}])
    await client.chat([{"role": "user", "content": "b"}])
    with pytest.raises(RuntimeError, match="预算耗尽"):
        await client.chat([{"role": "user", "content": "c"}])


async def test_retry_on_error() -> None:
    client, mock_chat = _make_client(max_retries=2)
    mock_chat.side_effect = [ValueError("boom"), ValueError("boom"), "recovered"]
    result = await client.chat([{"role": "user", "content": "x"}])
    assert result == "recovered"
    assert mock_chat.call_count == 3


async def test_timeout() -> None:
    client, mock_chat = _make_client(timeout=0.05)

    async def slow(*a: object, **kw: object) -> str:
        await asyncio.sleep(10)
        return "late"

    mock_chat.side_effect = slow
    with pytest.raises(asyncio.TimeoutError):
        await client.chat([{"role": "user", "content": "x"}])


async def test_logging_disabled_by_default(caplog: pytest.LogCaptureFixture) -> None:
    client, _ = _make_client(enable_logging=False)
    with caplog.at_level(logging.DEBUG, logger="llm"):
        await client.chat([{"role": "user", "content": "x"}])
    assert not caplog.records
