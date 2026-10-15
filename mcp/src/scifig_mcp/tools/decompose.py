"""论文拆解：用 LLM 把论文文本 + 需求 → 可作图信息 + Diagram IR(图结构)。

这是整个工作流的核心阶段（阶段2）。产出结构供：
- 对话内确认闸门展示（DIAGRAM IR：节点/边/分组/泳道/方向 + locks）
- 渲染阶段(render_svg/render_pptx/render_emf)消费
"""

from __future__ import annotations

import json
import re
from typing import List, Tuple

from scifig_mcp.llm.provider import LLM

_SYSTEM = """你是学术论文分析与科研绘图专家。请把论文拆解为"可作图信息"，
严格按给定 JSON schema 输出，不要额外文字。忠实原文，不臆造。"""

_MAX_CHARS = 60000

_FOCUS_KEYWORDS = (
    "method", "approach", "model", "framework", "system",
    "architecture", "algorithm", "materials", "procedure",
    "方法", "模型", "框架", "系统", "建模", "算法", "实验", "方案",
)


def _focus_text(paper_text: str, limit: int = _MAX_CHARS) -> str:
    """超长论文截断：保留摘要 + 方法/实验等核心章节（确定性，非简单头部截断）。

    - 按 markdown 标题切分章节
    - 开头（摘要）恒保留，占 1/4 预算
    - 其余章节按标题关键词得分降序挑选，同分按原文顺序
    - 无标题的纯文本回退为 头+尾 截断
    """
    text = paper_text.strip()
    if len(text) <= limit:
        return text

    parts = re.split(r"(?m)^(#{1,6}\s+.+)$", text)
    # 解析出的 markdown 通常以 "# 论文标题" 开头：把标题+其正文（摘要）
    # 恒归为 intro，不参与章节评分，避免摘要被当成普通章节截掉
    if not parts[0].strip() and len(parts) >= 3:
        intro = (parts[1] + "\n" + parts[2]).strip()
        rest_start = 3
    else:
        intro = parts[0].strip()
        rest_start = 1
    sections: List[Tuple[str, str]] = []
    for i in range(rest_start, len(parts) - 1, 2):
        sections.append((parts[i].strip(), parts[i + 1].strip()))

    if not sections:
        half = (limit - 24) // 2
        return (text[:half] + "\n\n...[中间截断]...\n\n" + text[-half:])[:limit]

    intro_budget = min(len(intro), limit // 4)
    kept = intro[:intro_budget]
    budget = limit - len(kept) - 40

    def score(heading: str) -> int:
        h = heading.lower()
        return sum(2 for kw in _FOCUS_KEYWORDS if kw in h)

    ranked = sorted(range(len(sections)), key=lambda i: (-score(sections[i][0]), i))
    picked: List[Tuple[int, str]] = []
    for i in ranked:
        if budget <= 200:
            break
        heading, body = sections[i]
        seg = heading + "\n" + body
        take = seg[: min(len(seg), budget)]
        picked.append((i, take))
        budget -= len(take)

    picked.sort(key=lambda t: t[0])
    out = [kept, "...[文本截断：仅保留摘要与核心章节，其余省略]..."]
    out.extend(seg for _, seg in picked)
    return "\n\n".join(out)[:limit]


def _user_prompt(paper_text: str, requirement: str) -> str:
    req = requirement.strip() or "（用户未指定，请由论文内容自动推荐合适的图）"
    return f"""【论文文本】
{_focus_text(paper_text)}

【用户作图需求】
{req}

请输出严格 JSON，schema 如下（Diagram IR）：
{{
  "paper_type": {{"type": "method", "confidence": 0.9, "evidence": "摘要出现'我们提出…'"}},
  "parts": [
    {{"id": "p1", "kind": "flow|mechanism|architecture|comparison|structure|data",
      "desc": "内容描述", "source": "原文位置(图1/方法4.2等)", "confidence": 0.9}}
  ],
  "recommended_figures": ["method_overview", "architecture"],
  "figure_irs": [
    {{
      "title": "图1 ...",
      "direction": "LR|TB",
      "groups": [{{"id": "g1", "label": "输入层"}}],
      "lanes": [{{"id": "l1", "label": "阶段A"}}],
      "nodes": [
        {{"id": "n1", "label": "...", "group": "g1", "lane": "l1",
          "shape": "round|box|diamond|cylinder|ellipse|parallelogram|cloud",
          "icon": "关键词(细胞/membrane/DNA/protein/virus 等，生物机制图填充)"}}
      ],
      "edges": [{{"id": "e1", "source": "n1", "target": "n2", "label": "...", "style": "solid|dashed"}}],
      "locks": {{"nodes": [], "edges": [], "groups": []}},
      "caption": "图注建议"
    }}
  ],
  "notes": "拆解说明，供用户确认阅读"
}}
规则：
- 每个图的节点建议 5-10 个、箭头 6-12 个（单栏 ≤5-7 节点/6-10 箭头）
- 每个节点必须有 label；边必须引用存在的节点 id
- 同一功能的节点归入同一 group；用 lanes 表示并行分支或并行阶段
- 单个节点要么属于 lane、要么属于 group，不要对同一划分两者都填（冗余双容器会导致布局断裂）
- 只输出 JSON。"""


def decompose_paper(llm: LLM, paper_text: str, requirement: str = "") -> dict:
    raw = llm.chat(_SYSTEM, _user_prompt(paper_text, requirement))
    return extract_json(raw)


def extract_json(text: str) -> dict:
    """从模型输出提取 JSON 对象（容忍 ```json 包裹、前后缀文本、markdown）。"""
    # 优先直接 JSON 解析
    body = text.strip()
    try:
        return json.loads(body)
    except (json.JSONDecodeError, TypeError):
        pass

    # 移除 ``` 代码围栏标记（可能单行或多行包裹）
    body = body.replace("```", " ")

    start = body.find("{")
    end = body.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"无法从 LLM 输出提取 JSON: {text[:200]}")
    return json.loads(body[start : end + 1])
