"""
Gemini provider 单测（mock，不依赖真实 key）
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from core.llm.client import LLMConfig, LLMProvider


@pytest.fixture
def gemini_config() -> LLMConfig:
    return LLMConfig(
        provider=LLMProvider.GEMINI,
        model="gemini-2.5-pro",
        api_key="fake-key",
    )


def _make_gemini_client(config: LLMConfig, mock_genai: MagicMock):
    """构造 GeminiClient，用 mock 替代 google.genai。"""
    mock_google = MagicMock()
    mock_google.genai = mock_genai
    with patch.dict(
        "sys.modules",
        {"google": mock_google, "google.genai": mock_genai},
    ):
        from core.llm.client import GeminiClient

        return GeminiClient(config)


def test_gemini_client_init(gemini_config: LLMConfig) -> None:
    mock_genai = MagicMock()
    _make_gemini_client(gemini_config, mock_genai)
    mock_genai.Client.assert_called_once_with(api_key="fake-key")


async def test_gemini_chat(gemini_config: LLMConfig) -> None:
    mock_genai = MagicMock()
    mock_genai.Client.return_value.models.generate_content.return_value = MagicMock(
        text="test response"
    )
    client = _make_gemini_client(gemini_config, mock_genai)

    result = await client.chat([{"role": "user", "content": "hello"}])
    assert result == "test response"


async def test_gemini_chat_with_image(gemini_config: LLMConfig) -> None:
    mock_genai = MagicMock()
    mock_genai.Client.return_value.models.generate_content.return_value = MagicMock(
        text="image analysis"
    )
    client = _make_gemini_client(gemini_config, mock_genai)

    result = await client.chat_with_image("describe", Image.new("RGB", (100, 100)))
    assert result == "image analysis"
