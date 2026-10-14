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

## 使用（standalone 测试）

```python
from scifig_mcp.tools.render import build_svg, render_to_svg

spec = {
    "title": "图1 系统框架",
    "direction": "LR",
    "groups": [{"name": "输入层", "color": "blues"}],
    "nodes": [
        {"id": "n1", "label": "预处理", "group": "输入层"},
        {"id": "n2", "label": "模型", "group": ""},
        {"id": "n3", "label": "输出", "group": ""},
    ],
    "edges": [
        {"from": "n1", "to": "n2", "label": "特征"},
        {"from": "n2", "to": "n3", "label": "结果"},
    ],
    "caption": "示例图注",
}
render_to_svg(spec, "demo.svg")
```

## 在 opencode 中接入

在 opencode 配置中添加 MCP server：

```jsonc
{
  "mcp": {
    "scifig": {
      "type": "local",
      "command": ["python", "-m", "scifig_mcp.server"],
      "env": {
        "SCIFIG_LLM_PROVIDER": "qwen",
        "SCIFIG_LLM_KEY": "sk-xxxx",
        "SCIFIG_OUT_DIR": "./loot"
      }
    }
  }
}
```

配合 `skill/` 目录使用，按四阶段工作流执行。
