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


_DEFAULTS = {
    "qwen": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-max"),
    "glm": ("https://open.bigmodel.cn/api/paas/v4", "glm-4"),
    "deepseek": ("https://api.deepseek.com/v1", "deepseek-chat"),
    "openai": ("https://api.openai.com/v1", "gpt-4o"),
}


def get_llm() -> LLM:
    if OpenAI is None:
        raise RuntimeError("需要安装 openai 库: pip install openai")

    provider = os.environ.get("SCIFIG_LLM_PROVIDER", "").lower()
    base = os.environ.get("SCIFIG_LLM_BASE")
    key = os.environ.get("SCIFIG_LLM_KEY")
    model = os.environ.get("SCIFIG_LLM_MODEL")

    if provider and not (base and model):
        dbase, dmodel = _DEFAULTS.get(provider, (base, model))
        base = base or dbase
        model = model or dmodel

    if not base or not key or not model:
        raise RuntimeError(
            "缺少 LLM 配置。请设置 SCIFIG_LLM_BASE / SCIFIG_LLM_KEY / SCIFIG_LLM_MODEL "
            "或 SCIFIG_LLM_PROVIDER=qwen|glm|deepseek|openai (+SCIFIG_LLM_KEY)"
        )

    client = OpenAI(base_url=base, api_key=key)
    return LLM(client=client, model=model)
