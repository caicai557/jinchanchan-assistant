"""
手动连通性测试 - 需要真实 GEMINI_API_KEY

用法:
    GEMINI_API_KEY=xxx python tests/manual_gemini_smoke.py
"""

import asyncio
import os

from PIL import Image

from core.llm.client import GeminiClient, LLMConfig, LLMProvider


async def main() -> None:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("请设置 GEMINI_API_KEY 环境变量")
        return

    config = LLMConfig(
        provider=LLMProvider.GEMINI,
        model=os.getenv("GEMINI_MODEL", "gemini-2.5-pro"),
        api_key=api_key,
    )
    client = GeminiClient(config)

    # 纯文本
    text = await client.chat([{"role": "user", "content": "说 hello"}])
    print(f"chat: {text}")

    # 带图片
    img = Image.new("RGB", (200, 200), color=(255, 0, 0))
    text = await client.chat_with_image("这张图片是什么颜色？", img)
    print(f"vision: {text}")


if __name__ == "__main__":
    asyncio.run(main())
