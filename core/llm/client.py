"""
LLM 客户端

支持多种 LLM 提供商：Anthropic Claude、OpenAI、通义千问等
"""

import asyncio
import base64
import io
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar

from PIL import Image

logger = logging.getLogger("llm")


class LLMProvider(str, Enum):
    """LLM 提供商"""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    QWEN = "qwen"
    GEMINI = "gemini"
    LOCAL = "local"


@dataclass
class LLMConfig:
    """LLM 配置"""

    provider: LLMProvider = LLMProvider.ANTHROPIC
    model: str = "claude-3-5-sonnet-20241022"
    api_key: str | None = None
    base_url: str | None = None
    max_tokens: int = 1024
    temperature: float = 0.7
    timeout: float = 30.0
    max_retries: int = 2
    budget_per_session: int = 50
    enable_logging: bool = False

    # 默认模型映射
    DEFAULT_MODELS: ClassVar[dict[LLMProvider, str]] = {
        LLMProvider.ANTHROPIC: "claude-3-5-sonnet-20241022",
        LLMProvider.OPENAI: "gpt-4o",
        LLMProvider.QWEN: "qwen-vl-max",
        LLMProvider.GEMINI: "gemini-2.5-pro",
        LLMProvider.LOCAL: "local-vlm",
    }


class BaseLLMClient(ABC):
    """LLM 客户端基类"""

    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    @abstractmethod
    async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        """
        发送聊天请求

        Args:
            messages: 消息列表

        Returns:
            响应文本
        """
        pass

    @abstractmethod
    async def chat_with_image(
        self, prompt: str, image: Image.Image, system_prompt: str | None = None, **kwargs: Any
    ) -> str:
        """
        发送带图片的聊天请求

        Args:
            prompt: 用户提示
            image: 图片
            system_prompt: 系统提示

        Returns:
            响应文本
        """
        pass

    def _image_to_base64(self, image: Image.Image, format: str = "PNG") -> str:
        """将图片转换为 base64"""
        buffer = io.BytesIO()
        image.save(buffer, format=format)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")


class AnthropicClient(BaseLLMClient):
    """Anthropic Claude 客户端"""

    def __init__(self, config: LLMConfig) -> None:
        super().__init__(config)
        try:
            import anthropic

            self.client: anthropic.AsyncAnthropic = anthropic.AsyncAnthropic(api_key=config.api_key)
        except ImportError:
            raise ImportError("请安装 anthropic: pip install anthropic")

    async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        """发送聊天请求"""
        response = await self.client.messages.create(
            model=self.config.model,
            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
            temperature=kwargs.get("temperature", self.config.temperature),
            messages=messages,
        )
        # response.content[0] 是 TextBlock，.text 是 str
        text = response.content[0].text
        return text if text is not None else ""

    async def chat_with_image(
        self, prompt: str, image: Image.Image, system_prompt: str | None = None, **kwargs: Any
    ) -> str:
        """发送带图片的请求"""
        # 转换图片
        image_base64 = self._image_to_base64(image)
        image_media_type = "image/png"

        messages: list[dict[str, Any]] = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": image_media_type,
                            "data": image_base64,
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt,
                    },
                ],
            }
        ]

        params: dict[str, Any] = {
            "model": self.config.model,
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "messages": messages,
        }

        if system_prompt:
            params["system"] = system_prompt

        response = await self.client.messages.create(**params)
        text = response.content[0].text
        return text if text is not None else ""


# OpenAI content 类型 - 使用更宽松的类型
OpenAIContentPart = str | dict[str, Any] | list[dict[str, Any]]


class OpenAIClient(BaseLLMClient):
    """OpenAI 客户端"""

    def __init__(self, config: LLMConfig) -> None:
        super().__init__(config)
        try:
            from openai import AsyncOpenAI

            self.client: AsyncOpenAI = AsyncOpenAI(api_key=config.api_key, base_url=config.base_url)
        except ImportError:
            raise ImportError("请安装 openai: pip install openai")

    async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        """发送聊天请求"""
        response = await self.client.chat.completions.create(
            model=self.config.model,
            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
            temperature=kwargs.get("temperature", self.config.temperature),
            messages=messages,
        )
        content = response.choices[0].message.content
        return content if content is not None else ""

    async def chat_with_image(
        self, prompt: str, image: Image.Image, system_prompt: str | None = None, **kwargs: Any
    ) -> str:
        """发送带图片的请求"""
        # 转换图片
        image_base64 = self._image_to_base64(image)
        image_url = f"data:image/png;base64,{image_base64}"

        messages: list[dict[str, OpenAIContentPart]] = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append(
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_url}},
                    {"type": "text", "text": prompt},
                ],
            }
        )

        response = await self.client.chat.completions.create(
            model=self.config.model,
            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
            messages=messages,  # type: ignore[arg-type]
        )
        content = response.choices[0].message.content
        return content if content is not None else ""


# Qwen content 类型
QwenContentPart = str | dict[str, Any] | list[dict[str, Any]]


class QwenClient(BaseLLMClient):
    """通义千问客户端"""

    def __init__(self, config: LLMConfig) -> None:
        super().__init__(config)
        try:
            import dashscope
            from dashscope import MultiModalConversation

            self.client: type[MultiModalConversation] = MultiModalConversation
            dashscope.api_key = config.api_key
        except ImportError:
            raise ImportError("请安装 dashscope: pip install dashscope")

    async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        """发送聊天请求"""
        response = self.client.call(
            model=self.config.model,
            messages=messages,
        )
        content = response.output.choices[0].message.content
        return str(content) if content is not None else ""

    async def chat_with_image(
        self, prompt: str, image: Image.Image, system_prompt: str | None = None, **kwargs: Any
    ) -> str:
        """发送带图片的请求"""
        # 转换图片
        image_base64 = self._image_to_base64(image)
        image_url = f"data:image/png;base64,{image_base64}"

        messages: list[dict[str, QwenContentPart]] = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": [{"image": image_url}, {"text": prompt}]})

        response = self.client.call(
            model=self.config.model,
            messages=messages,  # type: ignore[arg-type]
        )
        content = response.output.choices[0].message.content
        return str(content) if content is not None else ""


class GeminiClient(BaseLLMClient):
    """Google Gemini 客户端"""

    def __init__(self, config: LLMConfig) -> None:
        super().__init__(config)
        try:
            from google import genai

            self._genai = genai
            self.client: Any = genai.Client(api_key=config.api_key)
        except ImportError:
            raise ImportError("请安装 google-genai: pip install google-genai")

    async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        """发送聊天请求"""
        contents = [m.get("content", "") for m in messages if m.get("role") == "user"]
        response = self.client.models.generate_content(
            model=self.config.model,
            contents=contents,
        )
        return response.text or ""

    async def chat_with_image(
        self, prompt: str, image: Image.Image, system_prompt: str | None = None, **kwargs: Any
    ) -> str:
        """发送带图片的请求"""
        config = self._genai.types.GenerateContentConfig(
            max_output_tokens=kwargs.get("max_tokens", self.config.max_tokens),
            temperature=kwargs.get("temperature", self.config.temperature),
            system_instruction=system_prompt,
        )
        response = self.client.models.generate_content(
            model=self.config.model,
            contents=[image, prompt],
            config=config,
        )
        return response.text or ""


class LLMClient:
    """
    统一的 LLM 客户端

    封装多种 LLM 提供商，提供统一的接口
    """

    def __init__(self, config: LLMConfig | None = None) -> None:
        if config is None:
            config = self._load_config_from_env()

        self.config = config
        self._client: BaseLLMClient = self._create_client()
        self._call_count = 0

    def _load_config_from_env(self) -> LLMConfig:
        """从环境变量加载配置"""
        import os

        provider_str = os.getenv("LLM_PROVIDER", "anthropic")
        provider = LLMProvider(provider_str)

        # 获取默认模型，确保不为 None
        default_model = LLMConfig.DEFAULT_MODELS.get(provider, "")
        model = os.getenv("LLM_MODEL", default_model) or default_model

        return LLMConfig(
            provider=provider,
            model=model,
            api_key=(
                os.getenv("LLM_API_KEY")
                or os.getenv("ANTHROPIC_API_KEY")
                or os.getenv("OPENAI_API_KEY")
                or os.getenv("GEMINI_API_KEY")
            ),
            base_url=os.getenv("LLM_BASE_URL"),
        )

    def _create_client(self) -> BaseLLMClient:
        """创建底层客户端"""
        clients: dict[LLMProvider, type[BaseLLMClient]] = {
            LLMProvider.ANTHROPIC: AnthropicClient,
            LLMProvider.OPENAI: OpenAIClient,
            LLMProvider.QWEN: QwenClient,
            LLMProvider.GEMINI: GeminiClient,
        }

        client_class = clients.get(self.config.provider)
        if client_class is None:
            raise ValueError(f"不支持的 LLM 提供商: {self.config.provider}")

        return client_class(self.config)

    async def _guarded_call(self, fn: Any, *args: Any, **kwargs: Any) -> str:
        if self._call_count >= self.config.budget_per_session:
            raise RuntimeError("LLM 调用预算耗尽")
        last_err: Exception | None = None
        for _ in range(self.config.max_retries + 1):
            try:
                result: str = await asyncio.wait_for(
                    fn(*args, **kwargs), timeout=self.config.timeout
                )
                self._call_count += 1
                if self.config.enable_logging:
                    logger.debug("llm response=%.80s", result[:80])
                return result
            except asyncio.TimeoutError:
                raise
            except Exception as exc:
                last_err = exc
        raise last_err  # type: ignore[misc]

    async def analyze_game_state(
        self,
        screenshot: Image.Image,
        context: str | None = None,
        game_knowledge: str | None = None,
        **kwargs: Any,
    ) -> str:
        """
        分析游戏画面

        Args:
            screenshot: 游戏截图
            context: 上下文信息
            game_knowledge: 游戏知识

        Returns:
            分析结果
        """
        from core.llm.prompts import GamePrompts

        prompt = GamePrompts.ANALYZE_GAME_STATE
        if context:
            prompt += f"\n\n当前上下文：{context}"

        if game_knowledge:
            prompt += f"\n\n游戏知识：{game_knowledge}"

        return await self._guarded_call(
            self._client.chat_with_image,
            prompt=prompt,
            image=screenshot,
            system_prompt=GamePrompts.SYSTEM_PROMPT,
            **kwargs,
        )

    async def decide_action(
        self,
        screenshot: Image.Image,
        game_state: dict[str, Any],
        priority: str = "balanced",
        **kwargs: Any,
    ) -> str:
        """
        决策下一步操作

        Args:
            screenshot: 游戏截图
            game_state: 游戏状态
            priority: 优先级 (save_gold/level_up/chase_three/protect_hp/balanced)

        Returns:
            决策结果（JSON 格式）
        """
        from core.llm.prompts import GamePrompts

        prompt = GamePrompts.build_decision_prompt(game_state=game_state, priority=priority)

        return await self._guarded_call(
            self._client.chat_with_image,
            prompt=prompt,
            image=screenshot,
            system_prompt=GamePrompts.SYSTEM_PROMPT,
            **kwargs,
        )

    async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        """发送聊天请求"""
        return await self._guarded_call(self._client.chat, messages, **kwargs)

    async def chat_with_image(
        self, prompt: str, image: Image.Image, system_prompt: str | None = None, **kwargs: Any
    ) -> str:
        """发送带图片的聊天请求"""
        return await self._guarded_call(
            self._client.chat_with_image, prompt, image, system_prompt, **kwargs
        )


def create_llm_client(
    provider: str = "anthropic", model: str | None = None, api_key: str | None = None, **kwargs: Any
) -> LLMClient:
    """
    创建 LLM 客户端的便捷函数

    Args:
        provider: 提供商名称
        model: 模型名称
        api_key: API Key
        **kwargs: 其他配置

    Returns:
        LLMClient 实例
    """
    provider_enum = LLMProvider(provider)
    # 获取默认模型，确保不为 None
    default_model = LLMConfig.DEFAULT_MODELS.get(provider_enum, "")
    final_model = model or default_model or ""

    config = LLMConfig(
        provider=provider_enum,
        model=final_model,
        api_key=api_key,
        **kwargs,
    )
    return LLMClient(config)
