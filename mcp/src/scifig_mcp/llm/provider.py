"""国内大模型 provider 抽象（OpenAI 兼容接口）。

支持：通义千问 Qwen、智谱 GLM、DeepSeek、OpenAI 兼容任何端点。
通过环境变量配置：
  SCIFIG_LLM_BASE  : API base url，如 https://dashscope.aliyuncs.com/compatible-mode/v1
  SCIFIG_LLM_KEY   : API key
  SCIFIG_LLM_MODEL : 模型名，如 qwen-max / glm-4 / deepseek-chat
  SCIFIG_LLM_PROVIDER : 快捷选择 qwen | glm | deepseek | openai（可选，覆盖上面三者的默认值）
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    def load_dotenv(*args, **kwargs):  # type: ignore
        return False

# 自动加载 .env：优先项目根，其次 mcp/ 目录（环境变量优先，.env 兜底）
_p = Path(__file__).resolve()
for _cand in (_p.parents[3], _p.parents[3].parent):  # mcp/ -> project root
    load_dotenv(_cand / ".env")

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore


@dataclass
class LLM:
    client: object
    model: str

    def chat(self, system: str, user: str, temperature: float = 0.2) -> str:
        # 部分国内服务商网关（VLLM）非流式会强制注入 stream_options 导致 400，
        # 统一用流式兼容。
        stream = os.environ.get("SCIFIG_LLM_STREAM", "1") != "0"
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            stream=stream,
        )
        if not stream:
            return resp.choices[0].message.content or ""
        parts = []
        for chunk in resp:
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                parts.append(chunk.choices[0].delta.content)
        return "".join(parts)


@dataclass(frozen=True)
class ModelConfig:
    """一个文本或多模态模型端点的运行配置。"""

    base: str
    key: str
    model: str
    provider: str = ""


_DEFAULTS = {
    "qwen": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-max"),
    "glm": ("https://open.bigmodel.cn/api/paas/v4", "glm-4"),
    "deepseek": ("https://api.deepseek.com/v1", "deepseek-chat"),
    "openai": ("https://api.openai.com/v1", "gpt-4o"),
}


def get_model_config(kind: str = "text") -> ModelConfig:
    """读取文本或多模态模型配置。

    多模态模型优先读取 ``SCIFIG_VISION_*``，缺省时复用统一的
    ``SCIFIG_LLM_*`` 配置。这样论文图表解析、视觉质检和文本拆解可以
    使用同一个 OpenAI 兼容网关，也允许视觉模型单独切换。
    """
    if kind not in {"text", "multimodal"}:
        raise ValueError(f"不支持的模型类型: {kind}")

    if kind == "multimodal":
        provider = (os.environ.get("SCIFIG_VISION_PROVIDER")
                    or os.environ.get("SCIFIG_LLM_PROVIDER", "")).lower()
        base = (os.environ.get("SCIFIG_VISION_BASE")
                or os.environ.get("SCIFIG_LLM_BASE"))
        key = (os.environ.get("SCIFIG_VISION_KEY")
               or os.environ.get("SCIFIG_LLM_KEY"))
        model = (os.environ.get("SCIFIG_VISION_MODEL")
                 or os.environ.get("SCIFIG_LLM_VISION_MODEL")
                 or os.environ.get("SCIFIG_LLM_MODEL"))
    else:
        provider = os.environ.get("SCIFIG_LLM_PROVIDER", "").lower()
        base = os.environ.get("SCIFIG_LLM_BASE")
        key = os.environ.get("SCIFIG_LLM_KEY")
        model = os.environ.get("SCIFIG_LLM_MODEL")

    if provider and not (base and model):
        dbase, dmodel = _DEFAULTS.get(provider, (base, model))
        base = base or dbase
        # 文本模型的默认名不能安全地当作视觉模型使用；多模态模型
        # 必须显式指定，除非用户已经通过 SCIFIG_LLM_MODEL 复用它。
        if kind == "text":
            model = model or dmodel

    if not base or not key or not model:
        prefix = "SCIFIG_VISION_* 或 SCIFIG_LLM_*" if kind == "multimodal" else "SCIFIG_LLM_*"
        raise RuntimeError(
            f"缺少{('多模态' if kind == 'multimodal' else '文本')}模型配置。"
            f"请设置 {prefix}（base/key/model）。"
        )

    return ModelConfig(base=base, key=key, model=model, provider=provider)


def get_llm() -> LLM:
    if OpenAI is None:
        raise RuntimeError("需要安装 openai 库: pip install openai")

    cfg = get_model_config("text")
    client = OpenAI(base_url=cfg.base, api_key=cfg.key)
    return LLM(client=client, model=cfg.model)
