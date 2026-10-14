---
name: scifig
description: 将学术论文(上传PDF+需求)拆解为可编辑科研图(机制图/流程图/架构图/示意图),输出 SVG+EMF,可直接插入 PPT/Word 编辑。覆盖全论文类型。
---

# SciFig：论文拆解 → 可编辑科研图

把一篇学术论文 + 一个作图需求，变成**可编辑矢量科研图**（SVG + EMF），全程四阶段。

## 核心原则

1. **先拆解，确认无问题，再出图**。绝不跳过确认直接画。
2. **按论文类型分类**选图示，不套死模板。
3. 交付 **可编辑矢量**（SVG + EMF），EMF 进 PPT/Word 直接可编辑，不是位图。

## 工作流（四阶段）

### 阶段0 输入
用户提供：
- 论文 PDF 路径（或已解析文本）
- 作图需求描述（"画机制图/流程图/架构图/示意图…"，或"把第X方法画成图"）

### 阶段1 解析（调用 MCP 工具 `parse_paper`）
- PDF → 结构化文本（标题/摘要/方法/图表/参考文献/公式）
- 输出 markdown + 图位置定位
- 若已直接给文本，可跳过

### 阶段2 拆解（核心，调用 `decompose` + LLM）
用"分类决策树"拆解，产出结构：
1. **论文类型分类**：见 `references/paper-types.md`（方法/机制/评测/综述/理论/工程/数据）
2. **识别可作图信息**：流程 / 机制 / 架构 / 对比 / 结构 / 数据等
3. **推荐图清单**：对应 `references/figure-types.md` 中的图示类型
4. 输出 `figure_spec`（JSON）

> ⚠️ **对话内确认闸门**：把拆解结果展示给用户，用户确认或修改后才进入阶段3。
> 展示格式参考《references/prompt-templates.md》中的"确认展示模板"。

### 阶段3 出图（调用 `render_svg` / `render_emf`）
- 把确认后的 `figure_spec` → 渲染成 SVG + EMF
- 遵循 `references/design-theory.md` 的配色/排版/层次规范

### 阶段4 交付
- 输出：SVG、EMF、预览 PNG、图注建议
- 说明如何在 PPT/Word 中"插入→转换为形状"使其可编辑

## 交互要求

- 每阶段结束用简洁文本小结当前结果，不啰嗦。
- 阶段2 的确认是**硬闸门**，必须等用户明确同意后才出图。
- 用户若有修改意见（加/删/改某个元素），回到阶段2 或 3 对应调整。

## 参考文件

- `references/paper-types.md` — 论文类型分类决策树
- `references/figure-types.md` — 科研图示类型与适用场景
- `references/design-theory.md` — 配色/排版/层次设计规范
- `references/prompt-templates.md` — 拆解与出图的提示词模板
