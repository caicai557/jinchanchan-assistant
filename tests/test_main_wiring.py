"""main.py wiring 集成测试（fake adapter，不触网）"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.llm.client import LLMProvider
from main import JinchanchanAssistant, create_llm_client, load_config
from tests.test_smoke_e2e import FakePlatformAdapter


def test_wiring_dry_run_no_execute() -> None:
    """dry_run 模式下 executor.execute 不被调用。"""
    adapter = FakePlatformAdapter()
    assistant = JinchanchanAssistant(platform_adapter=adapter, llm_client=None, dry_run=True)
    assert assistant.dry_run is True
    assert assistant.decision_engine.llm_client is None


def test_create_llm_client_none() -> None:
    assert create_llm_client("none") is None


def test_create_llm_client_gemini_wiring() -> None:
    mock_genai = MagicMock()
    mock_google = MagicMock()
    mock_google.genai = mock_genai
    with patch.dict("sys.modules", {"google": mock_google, "google.genai": mock_genai}):
        client = create_llm_client(
            provider="gemini",
            model="gemini-2.5-pro",
            timeout=10.0,
            max_retries=1,
            budget=5,
            enable_logging=True,
        )
    assert client is not None
    assert client.config.provider == LLMProvider.GEMINI
    assert client.config.timeout == 10.0
    assert client.config.max_retries == 1
    assert client.config.budget_per_session == 5
    assert client.config.enable_logging is True


def test_wiring_with_llm_sets_engine() -> None:
    mock_genai = MagicMock()
    mock_google = MagicMock()
    mock_google.genai = mock_genai
    with patch.dict("sys.modules", {"google": mock_google, "google.genai": mock_genai}):
        client = create_llm_client("gemini", budget=3)
    adapter = FakePlatformAdapter()
    assistant = JinchanchanAssistant(
        platform_adapter=adapter,
        llm_client=client,
        dry_run=False,
    )
    assert assistant.decision_engine.llm_client is client


def test_load_config_missing_file() -> None:
    assert load_config("/nonexistent/path.yaml") == {}
