"""视觉质检：Diagram IR / 本地图像 → 本地 VL 模型（Ollama）严格质检问题清单。

默认问题是"发表质量五项"（方向/连线/截断/标签/差距），可带论文背景 context
——等效于"切到视觉模型读图"，详见 SKILL.md 阶段4。
"""

from __future__ import annotations

import base64
import os
from typing import Any, Dict, List

from scifig_mcp.tools.render import build_svg

VISION_BASE = os.environ.get("SCIFIG_VISION_BASE", "http://localhost:11434/v1")
VISION_MODEL = os.environ.get("SCIFIG_VISION_MODEL", "qwen2.5vl:7b")
VISION_TIMEOUT = int(os.environ.get("SCIFIG_VISION_TIMEOUT", "300"))

DEFAULT_QA_PROMPT = (
    "请严格质检这张科研图并逐条回答（只列问题，不泛泛夸奖）: "
    "1)数据流方向是什么，起点/终点节点是什么 "
    "2)连线箭头是否正确连接，有无断线或交叉混乱 "
    "3)有无节点重叠、文字被截断或超出框外 "
    "4)标题和分组/泳道标签是否完整可读 "
    "5)距离论文插图发表质量还差什么，指出最该改的1-2处"
)


def _chat(messages: List[Dict], model: str = None, base: str = None,
          timeout: int = None) -> Dict[str, Any]:
    """OpenAI-compatible 单次多模态请求（默认打本地 Ollama）。"""
    from openai import OpenAI

    client = OpenAI(base_url=base or VISION_BASE, api_key="ollama",
                    timeout=timeout or VISION_TIMEOUT)
    resp = client.chat.completions.create(
        model=model or VISION_MODEL, messages=messages, temperature=0.1
    )
    usage = {}
    if resp.usage is not None:
        usage = {
            "prompt_tokens": getattr(resp.usage, "prompt_tokens", None),
            "completion_tokens": getattr(resp.usage, "completion_tokens", None),
        }
    return {"answer": resp.choices[0].message.content or "", "usage": usage}


def _svg_to_png_bytes(svg: str, width: int = 1800) -> bytes:
    import cairosvg

    return cairosvg.svg2png(bytestring=svg.encode("utf-8"), output_width=width)


def _image_blocks(b64: str, question: str) -> List[Dict]:
    return [
        {"type": "text", "text": question},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64," + b64}},
    ]


def _build_messages(png_bytes: bytes, question: str, context: str = "") -> List[Dict]:
    messages: List[Dict] = []
    if context and context.strip():
        messages.append({"role": "user", "content": context.strip()})
    messages.append({
        "role": "user",
        "content": _image_blocks(base64.b64encode(png_bytes).decode(), question),
    })
    return messages


def figure_qa(ir: Dict, question: str = "", context: str = "",
              scheme: str = "okabe-ito", out_dir: str = None,
              out_name: str = "figure") -> Dict[str, Any]:
    """IR → SVG → PNG（落盘）→ VL 严格质检 → 问题清单。"""
    svg = build_svg(ir, scheme)
    png = _svg_to_png_bytes(svg)

    png_path = None
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        png_path = os.path.join(out_dir, f"{out_name}_qa.png")
        with open(png_path, "wb") as f:
            f.write(png)

    q = (question or "").strip() or DEFAULT_QA_PROMPT
    try:
        result = _chat(_build_messages(png, q, context))
    except Exception as e:
        raise RuntimeError(
            f"本地视觉模型不可用（{VISION_BASE} / {VISION_MODEL}）: {e}. "
            "请确认 ollama 正在运行且模型已拉取（ollama serve / ollama pull）。"
        )
    return {"ok": True, "png_path": png_path, **result}


def vision_describe(image_path: str, question: str = "请详细描述这张图的内容",
                    context: str = "") -> Dict[str, Any]:
    """让本地视觉模型直接读一张本地图并回答问题（深检任意图）。"""
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"图片不存在: {image_path}")
    with open(image_path, "rb") as f:
        png = f.read()
    try:
        result = _chat(_build_messages(png, question, context))
    except Exception as e:
        raise RuntimeError(
            f"本地视觉模型不可用（{VISION_BASE} / {VISION_MODEL}）: {e}. "
            "请确认 ollama 正在运行且模型已拉取。"
        )
    return {"ok": True, "image_path": image_path, **result}
