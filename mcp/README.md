# SciFig MCP Server

论文解析 → 拆解 → 可编辑科研图（SVG + EMF）的 MCP 工具集。

## 工具

| 工具 | 说明 |
|------|------|
| `parse_paper` | PDF → 结构化 markdown（复用 MinerU / pdfplumber） |
| `decompose` | 论文文本 + 需求 → Diagram IR JSON（LLM 拆解，含 locks） |
| `validate_ir_tool` | 校验 Diagram IR 合法可渲染 |
| `audit_ir_tool` | 确定性质量审计（passed 闸门） |
| `render_svg` | Diagram IR → SVG 文件 |
| `render_pptx` | Diagram IR → 原生可编辑 PPTX（python-pptx 形状/连接线） |
| `render_emf` | Diagram IR → EMF 文件（预览） |
| `export_spec` | IR → 带 LOCKED 标记文本（锁定重生成） |

## 安装

```bash
pip install -e .
```

可选依赖：
- 解析：`pip install pdfplumber`（轻量）或 `pip install mineru`（高精度）
- PPTX 可编辑输出：`pip install python-pptx`
- EMF 预览：`pip install cairosvg pillow`

## 配置（国内模型，OpenAI 兼容）

```bash
set SCIFIG_LLM_PROVIDER=qwen     # qwen | glm | deepseek | openai
set SCIFIG_LLM_KEY=sk-xxxx
```

或自定义端点：
```bash
set SCIFIG_LLM_BASE=...
set SCIFIG_LLM_KEY=...
set SCIFIG_LLM_MODEL=...
```

## 配置（国内模型，OpenAI 兼容）

推荐用 `.env`（已自动加载，且被 gitignore，不会上传）：

```bash
# 复制 .env.example 为 .env 并填写
copy .env.example .env
```

配置项：
```
SCIFIG_LLM_PROVIDER=deepseek   # qwen | glm | deepseek | openai
SCIFIG_LLM_BASE=https://newapi.ai.gduf.top/v1
SCIFIG_LLM_KEY=sk-xxxx
SCIFIG_LLM_MODEL=deepseek-v4-flash
SCIFIG_LLM_STREAM=1            # 流式（部分 VLLM 网关必要）
```

或直接用环境变量注入（MCP 通过 env 传入，优先于 .env）。

## 使用（standalone 测试）

```python
from scifig_mcp.tools.render import render_to_pptx, render_to_svg
from scifig_mcp.tools.audit import audit_ir
from scifig_mcp.diagram_ir import validate_ir

ir = {
    "title": "图1 系统框架",
    "direction": "LR",
    "groups": [{"id": "g1", "label": "输入层"}, {"id": "g2", "label": "处理层"}],
    "lanes": [{"id": "l1", "label": "阶段A"}, {"id": "l2", "label": "阶段B"}],
    "nodes": [
        {"id": "n1", "label": "预处理", "group": "g1", "lane": "l1", "shape": "round"},
        {"id": "n2", "label": "模型", "group": "g2", "lane": "l2", "shape": "box"},
        {"id": "n3", "label": "输出", "group": "g2", "lane": "l2", "shape": "cylinder"},
    ],
    "edges": [
        {"id": "e1", "source": "n1", "target": "n2", "label": "特征", "style": "solid"},
        {"id": "e2", "source": "n2", "target": "n3", "label": "结果", "style": "solid"},
    ],
    "locks": {"nodes": [], "edges": [], "groups": []},
}

assert not validate_ir(ir)
print(audit_ir(ir))            # passed 闸门
render_to_pptx(ir, "demo.pptx")  # 原生可编辑 PPTX
render_to_svg(ir, "demo.svg")
```

## 在 opencode 中接入

在 opencode 配置中添加 MCP server（通过 env 传 key，或依赖自动加载的 .env）：

```jsonc
{
  "mcp": {
    "scifig": {
      "type": "local",
      "command": ["python", "-m", "scifig_mcp.server"],
      "env": {
        "SCIFIG_LLM_PROVIDER": "deepseek",
        "SCIFIG_LLM_BASE": "https://newapi.ai.gduf.top/v1",
        "SCIFIG_LLM_KEY": "sk-xxxx",
        "SCIFIG_LLM_MODEL": "deepseek-v4-flash",
        "SCIFIG_OUT_DIR": "./loot"
      }
    }
  }
}
```

> 需先把 `mcp/` 加入 Python 路径（`cd mcp && pip install -e .`），或用绝对模块路径。

配合 `skill/` 目录使用，按四阶段工作流执行（解析 → 拆解确认 → 审计 → 出图）。
