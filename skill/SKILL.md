---
name: scifig
description: 将学术论文(上传PDF/DOCX/DOC+需求)拆解为可编辑科研图(机制图/流程图/架构图/示意图),输出原生可编辑 PPTX+SVG，并提供 PNG/PDF/EMF 预览。
---

# SciFig：论文拆解 → 可编辑科研图

把一篇学术论文 + 一个作图需求，变成**可编辑矢量科研图**（SVG/PPTX），全程经过解析、规划、确认、审计和质检。

## 核心原则

1. **先拆解，确认无问题，再出图**。绝不跳过确认直接画。
2. **按论文类型分类**选图示，不套死模板。
3. 交付 **原生可编辑 PPTX**（一等产物，PPT 内直接编辑形状/连线）+ **SVG/EMF 矢量**。

## 工作流（四阶段）

### 阶段0 输入
用户提供：
- 论文 PDF / DOCX / DOC 路径（或已解析文本）
- 作图需求描述（"画机制图/流程图/架构图/示意图…"，或"把第X方法画成图"）

### 阶段1-2 解析与规划（优先调用 MCP 工具 `prepare_figure`）
- 默认 `planner_mode=codex`：MCP 返回正文、图表/公式视觉证据和来源，Codex 自己生成 Diagram IR，不需要额外文本模型 Key
- 需要 MCP 自动规划时显式传 `planner_mode=mcp`，此时才调用注册表里的 LLM 规划插件
- 需要单独调试时再分别调用 `parse_document`、`decompose`
- PDF / DOCX / DOC → 结构化文本（标题/摘要/方法/图表/参考文献/公式）
- DOCX 优先读取段落、标题、表格和嵌入图片；安装 LibreOffice 后再补充页面级视觉解析
- 同步提取含图表标题的页面截图，交给**已配置的多模态模型**识别图、表、公式和视觉关系，结果追加到解析 markdown
- 多模态模型通过 `SCIFIG_VISION_BASE/KEY/MODEL` 配置；未单独配置时复用 `SCIFIG_LLM_BASE/KEY/MODEL`
- 输出 markdown + 图位置定位
- 若已直接给文本，可跳过
- 若用户把 PDF 作为**附件**发来（模型可能无法直接读 PDF），先定位其文件路径再调 `parse_paper`，不要把 PDF 内容硬喂给 LLM

### 阶段2 拆解（核心，调用 `decompose` + LLM；或由 `prepare_figure` 编排）
用"分类决策树"拆解，产出结构：
1. **论文类型分类**：见 `references/paper-types.md`（方法/机制/评测/综述/理论/工程/数据）
2. **识别可作图信息**：流程 / 机制 / 架构 / 对比 / 结构 / 数据等
3. **推荐图清单**：对应 `references/figure-types.md` 中的图示类型
4. 输出 **Diagram IR**（JSON）：`{title, direction, groups, lanes, nodes, edges, layout, locks}`；`layout.canvas_ratio` 默认使用科研图常见的 `"4:3"`，汇报场景可指定 `"16:9"`

> ⚠️ **对话内确认闸门**：调用 `export_spec` 把 IR 转成带 `[LOCKED]` 标记的可读文本，
> 展示给用户确认/修改（可加/删/改节点、连线、分组，或用 locks 锁定要保留的元素），
> 确认无问题后才进入阶段3。硬闸门，必须等用户明确同意。

### 阶段3 审计（调用 `audit_ir_tool`）
- 对确认后的 Diagram IR 做**确定性质量审计**（信息密度/越界/孤立节点/空标签/空分组）
- 必须 `passed == True`（无 hard 失败）才允许出图；有 hard 失败先修复 IR

### 阶段4 出图（优先调用 `render_confirmed_figure`）
- 把确认+审计通过的 Diagram IR → 渲染成 **PPTX + SVG + PNG/PDF/EMF**
- 低级调试时再分别调用 `render_pptx` / `render_svg` / `render_emf`
- PPTX 是原生可编辑 OOXML 形状/连接线，PPT 内直接编辑，无需"转换为形状"
- 遵循 `references/design-theory.md` 配色/排版/层次规范
- **视觉自检（必做，调用 `figure_qa`）**：使用已配置的 OpenAI 兼容多模态模型对渲染出的图自动质检——
  方向/连线/截断/标签/发表质量五项，带 `context`（论文背景）提高判断准确性；
  有问题先修 IR 或渲染，复检通过再交付。
- **深检（可选）**：调用 `vision_describe` 让同一个多模态模型读取论文原图或本地 PNG，避免切换到单独的本地视觉服务。

### 阶段5 交付
- 输出：PPTX、SVG、PNG/PDF 预览、质检结果、图注建议和证据来源
- 说明如何在 PPT/Word 中编辑各元素

## 交互要求

- 每阶段结束用简洁文本小结当前结果，不啰嗦。
- 阶段2 的确认是**硬闸门**，必须等用户明确同意后才出图。
- 用户若有修改意见（加/删/改某个元素），回到阶段2 或 3 对应调整。
- 参考 `references/figure-types.md` 的五个失败模式做交付前自查。

## 参考文件

- `references/paper-types.md` — 论文类型分类决策树
- `references/figure-types.md` — 科研图示类型、容量规范、五个失败模式
- `references/design-theory.md` — 配色/排版/层次设计规范
- `references/prompt-templates.md` — 拆解与出图的提示词模板
