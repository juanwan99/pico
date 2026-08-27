"""Image generation adapter.

Owner 2026-08-27: SiliconFlow for images is REJECTED. Do not call it.
Product path = Zhipu glm-image when owner writes 「接 glm-image」.
Until then: fail-closed, never invent pixels, never ask ops for SILICONFLOW.
"""

from __future__ import annotations

import logging
import os

from pico_orchestrator.gateway import ToolError

logger = logging.getLogger(__name__)

_MAX_PROMPT = 2000

# Keep name stable for tests / face copy that import NO_KEY_MESSAGE.
NO_KEY_MESSAGE = "出图尚未接通。待业主书面接通智谱 glm-image，不能编造图片。"
REJECTED_PROVIDER_MESSAGE = (
    "出图提供商硅基流动已否决，不再调用。待接通智谱 glm-image，不能编造图片。"
)
TIMEOUT_MESSAGE = "出图超时（45 秒）。请稍后重试，不能编造图片。"
REJECT_MESSAGE = "出图服务拒绝了这次请求。请稍后重试或换一句描述，不能编造图片。"
INVALID_MESSAGE = "出图结果不是可打开的 png/jpg，未保存，不能编造图片。"


def siliconflow_api_key() -> str:
    """Legacy env peek only — presence must reject, not enable."""
    return (os.environ.get("SILICONFLOW_API_KEY") or "").strip()


def image_model() -> str:
    return ""


async def generate_image_bytes(prompt: str) -> tuple[bytes, str]:
    """Return (image_bytes, png|jpg). Never invent pixels. SiliconFlow path dead."""
    text = (prompt or "").strip()
    if not text:
        raise ToolError("tool.invalid_arguments", "请写要画的内容。")
    if len(text) > _MAX_PROMPT:
        raise ToolError("tool.invalid_arguments", f"出图描述不能超过 {_MAX_PROMPT} 字。")
    if siliconflow_api_key():
        logger.warning("generate_image refused: SiliconFlow key present but provider rejected")
        raise ToolError("image.provider_rejected", REJECTED_PROVIDER_MESSAGE)
    raise ToolError("image.unconfigured", NO_KEY_MESSAGE)
