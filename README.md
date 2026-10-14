# SciFig — 学术论文 → 可编辑科研图

把**一篇学术论文（PDF + 作图需求）**自动拆解，并生成**可编辑矢量科研图**（机制图/流程图/架构图/示意图），输出 **SVG / PPTX / EMF**。PPTX 由 python-pptx 生成**原生可编辑 OOXML 形状与连接线**，在 PowerPoint 里本就是可编辑对象（无需"转换为形状"）；SVG/EMF 亦可插入 Word/PPT 二次编辑。

覆盖全论文类型，`skill + MCP server` 双形态交付，面向国内大模型生态（Qwen / GLM / DeepSeek）。

## 核心思想

**先拆解、确认无问题、再出图。可编辑对象，而非位图。**

四条设计原则：
1. **按论文类型分类**选图示（方法/机制/评测/综述/理论/工程/数据 × 11 种图）
2. **拆解确认闸门**：LLM 拆解出 **Diagram IR**（节点/边/分组/泳道/方向 + locks），你在对话内确认或修改后才出图
3. **可编辑对象交付**：PPTX 原生可编辑形状/连接线 + SVG + EMF
4. **多端接入国内模型**：OpenAI 兼容接口，一次配置通吃 Qwen / GLM / DeepSeek

## 工作流

```
论文PDF + 需求
   │ ① 解析(可复用 MinerU) ─→ 结构化 markdown
   ▼
拆解(LLM 分类决策树) ─→ Diagram IR JSON（节点/边/组/泳道 + locks）
   │  [对话内确认闸门：展示带 LOCKED 的 IR，确认/修改后继续]
   ▼
审计(确定性质量闸门) ─→ passed = (hard==0)（越界/密度/孤立节点等）
   ▼
渲染(可编辑对象) ─→ PPTX + SVG + EMF（PPT/Word 原生可编辑）
   ▼
交付：改定稿图 + 预览 + 图注建议
```

## 目录结构

```
skill/                 # opencode skill（主工作流指令 + 参考资料）
  SKILL.md               # 四阶段工作流指令
  references/            # paper-types / figure-types / design-theory / prompt-templates
mcp/                   # MCP server（Python, FastMCP）
  src/scifig_mcp/
    server.py             # MCP 入口：parse_paper/decompose/validate/audit/render_svg/pptx/emf
    diagram_ir.py         # Diagram IR schema + 校验 + 锁定重生成序列化
    palette.py            # 8-role 语义配色 + 5 套预设（Okabe-Ito/Nature/IEEE/Vivid/Pastel）
    llm/provider.py       # 国内模型抽象（Qwen/GLM/DeepSeek, OpenAI 兼容）
    tools/parse.py        # 论文解析（MinerU / pdfplumber）
    tools/decompose.py    # LLM 拆解 → Diagram IR
    tools/render.py       # SVG / PPTX(OOML) / EMF 渲染
    tools/audit.py        # 确定性质量审计
examples/              # 示例
loot/                  # 输出目录（SVG/PPTX/EMF/解析结果）
```

## 快速开始

### 1. 安装 MCP server

```bash
cd mcp
pip install -e .
# 解析：pip install pdfplumber  →或→  pip install mineru（高精度）
# PPTX 可编辑输出：pip install python-pptx
# EMF 预览：pip install cairosvg pillow
```

### 2. 配置国内模型（任选一）

```bash
# 方式A：指定 provider（Qwen 为例）
set SCIFIG_LLM_PROVIDER=qwen
set SCIFIG_LLM_KEY=sk-xxxx
# 方式B：自定义端点
set SCIFIG_LLM_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
set SCIFIG_LLM_KEY=sk-xxxx
set SCIFIG_LLM_MODEL=qwen-max
```

### 3. 在 opencode 使用

skill 位于 `skill/`，MCP server 在 `mcp/`。详见 `mcp/README.md`。

## MCP 工具

| 工具 | 说明 |
|------|------|
| `parse_paper` | PDF → 结构化 markdown |
| `decompose` | 论文 + 需求 → Diagram IR JSON（LLM 拆解） |
| `validate_ir_tool` | 校验 IR 合法可渲染 |
| `audit_ir_tool` | 确定性质量审计（passed 闸门） |
| `render_svg` | IR → SVG |
| `render_pptx` | IR → 原生可编辑 PPTX |
| `render_emf` | IR → EMF（预览） |
| `export_spec` | IR → 带 LOCKED 标记文本（锁定重生成） |

## 路线图

- [x] 工作流 + skill 骨架 + MCP server
- [x] Diagram IR schema + 校验 + locks 锁定重生成
- [x] PPTX 原生可编辑渲染器（python-pptx 形状/连接线）
- [x] 8-role 语义配色 + 5 套预设
- [x] 确定性质量审计
- [ ] MinerU 高精度解析接入
- [ ] 机制图图标素材库集成（research-figure-library / Bioicons / Servier）
- [ ] draw.io 实时画布 MCP（二期）

## License

MIT

