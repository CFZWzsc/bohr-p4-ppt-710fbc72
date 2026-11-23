---
name: slide-template-adapter
description: Use when source pages must be mapped onto a declared PPT master/layout/placeholder template with text fitting, figure scaling, numbering and batch consistency checks.
---

# 学术 PPT 模板与格式适配

## 用途与适用条件

把已有页面内容（或论文分节材料）映射到声明的母版/版式/占位符结构：为每页选择版式、把标题/正文/图表/页脚写入正确占位符，按字号阶梯估算文本溢出并给出可读的最小字号，按容器等比缩放图表并检查纵横比与分辨率，统一图号与正文引用，并对整册做标题位置、页脚、页码、字号层级的一致性审计；同时给出确定性的导出检查计划与版本记录。

适用条件：`/input/case.json`（或 `--case`）含模板结构（`template`/`masters`/`layouts`/`placeholders`）与源页面（`slides`/`pages`/`deck`），或含可分页的 `sections`/`paper_sections`/`outline`。典型键：`template`、`slide_size`、`fonts`、`theme_colors`、`footer`、`slides`、`figures`、`tables`、`export`。

不适用：不生成新的科学结论，不做论文精读，不做 PPT 软件本身开发；不伪造已安装字体、已渲染 pptx/PDF/PNG 或官方模板继承关系。缺少模板时明确标记为通用版式假设，不声称真实套用了母版。

## 输入

- `/input/case.json`：主输入；`template` 可以是对象，也可以是同目录下指向 JSON 模板文件的相对路径。
- `/input/task.md`：存在时补充页数上限、目标模板、导出格式与字体要求。
- 声明引用的相对路径文件会被实际读取；改为绝对路径或不存在时登记到 `errors`/`uncertainty`。
- 仅用 Python 标准库；不联网、不写 `/input`、不读取未声明路径。

## 处理流程

1. **读入与哈希**：加载 case.json、task.md 与声明的模板 JSON，记录来源与 SHA-256。
2. **模板解析**：读取 `masters`/`layouts`/`placeholders`，归一版式 id/名称与占位符类型（title/subtitle/body/picture/table/chart/footer/slide_number/date/notes）、英寸几何与字号；缺失几何时用保守默认值并标 `geometry_assumed`。
3. **页面归一**：读取 `slides`/`pages`/`deck.slides`，抽取标题、要点、备注、图表、源定位；无页面时从 `sections`/`outline` 生成骨架页并标 `generated`，不补造论文事实。
4. **版式匹配**：按页面角色（cover/section/content/picture/closing）与显式 `layout_hint` 给版式打分，选择最高分版式并记录理由；无匹配时回退到通用版式并登记。
5. **占位符填充**：标题、副标题、正文、页码、页脚写入对应槽位；图片/表格写入 picture/table 槽位；槽位不足时记录 `placeholder_fallback` 与替代建议，不新增未声明槽位。
6. **字号与溢出**：按模板字号或内置阶梯（title 32 / section 28 / subtitle 22 / body 20 / caption 14 / footnote 12）估算每段文本的行数与所需高度；溢出时优先降一档字号，低于最小可读字号（标题 24、正文 14）则标 `text_overflow_unresolvable` 并给出可容纳字数估计。
7. **图表适配**：按容器 `contain`（默认）等比缩放，`cover` 计算裁切比例，`stretch` 标 `aspect_distortion_risk`；位图按渲染尺寸估算有效 PPI，低于 150 标 `low_resolution_figure`，矢量图跳过；尺寸缺失时不编造缩放结果。
8. **编号一致性**：比较图表声明标签与页面文字中的 `图/表/Figure/Table N` 引用，标 `figure_reference_without_asset`、`figure_asset_unreferenced`、`duplicate_figure_label`、`page_figure_number_mismatch`；无标签图表标 `figure_label_missing`。
9. **批量一致性**：对内容页比较标题占位符位置、正文左边距与字号，检查页脚/页码缺失，标 `title_position_inconsistent`、`body_margin_inconsistent`、`body_font_size_inconsistent`、`footer_missing_on_page`、`page_number_missing`。
10. **字体与颜色**：读取主题字体与主题色；若提供可用字体清单则核对缺失并给出回退链；若文本色与背景色为 hex 则计算对比度，低于 4.5 标 `low_contrast_text`。
11. **导出与版本**：登记 pptx/PDF/PNG 检查项（`performed=false`）；记录页面计划内容哈希、批量操作与回退方式。
12. **契约落盘**：保留 `case_id` 与全部 `output_contract` 字段；未支持字段写 `null` 并记入 `contract_notes`。

## 评分维度对应

- **实际效果**：每页是否进入正确版式、占位符是否按类型填充、图表是否等比且编号可对。
- **结果正确性/完整性**：标题、正文、图表、页脚、页码、备注与源定位齐备；数字不因适配被改写。
- **结果可核验性**：页级版式理由、槽位映射、溢出计算、图表适配与批量检查均可逐条复核。
- **创新增益**：版式打分、字号阶梯拟合、图表等比/裁切与编号交叉校验、整册一致性审计。
- **可靠体验**：模板缺失、槽位不足、字体未知、图表尺寸缺失、溢出不可解时诚实标记，不静默压字或拉伸图片。

## 输出契约

`/app/output/result.json` 顶层保留 `case_id`、`output_contract` 全部字段、`status`、`result`、`evidence`、`uncertainty`、`errors`、`stats`、`skill`、`challenge_id`、`contract_notes`。未支持字段写 `null` 并记录原因。

主要交付段：`result.slides`（页级版式/槽位/溢出/图表/源定位）、`result.template_summary`、`result.font_plan`、`result.figure_adaptation`、`result.consistency`、`result.checks`、`result.export_plan`、`result.version_record`、`result.source_register`。

## 异常处理

| 情况 | 处理 | 输出表现 |
|---|---|---|
| case.json 缺失/非法 | 结构化失败 | 退出码 `2`，`status=failed` |
| 无模板结构 | 用通用版式假设并明确标注 | `template_summary.declared=false`，`status=partial`，`template_not_declared` |
| 无源页面也无分节材料 | 不编造页面 | `status=insufficient_input` |
| 从分节生成骨架页 | 只取已有句子 | `generated=true`，`status=partial` |
| 版式缺图片/表格槽位 | 回退到正文区域并记录 | `placeholder_fallback` |
| 文本溢出且降档到最小仍溢出 | 不压到不可读 | `text_overflow_unresolvable`，给可容纳字数 |
| 图表显式要求拉伸 | 保留声明但不静默接受 | `aspect_distortion_risk` 并建议 `contain` |
| 图表尺寸/标签缺失 | 不编造缩放或编号 | `figure_dimensions_unknown` / `figure_label_missing` |
| 引用图号不存在 | 保留引用并标悬空 | `figure_reference_without_asset` |
| 字体可用性未知 | 只给回退链不声称已安装 | `font_availability_unknown` |
| 渲染工具缺失 | 仍须生成 pptx；无法渲染时在 deliverable 明确标注 | `deliverable.rendered=false`、`pptx_not_generated` |

## 限制

版式匹配与文本拟合是基于字符宽度与行高的确定性估算，不是真实渲染器测量；英寸几何、PPI 与对比度结论只在输入提供相应数值时成立。脚本不生成 pptx 二进制、不嵌入字体、不执行 PDF 导出；最终 pptx、字体与 PDF/PNG 预览由调用 Agent 按「最终交付物（强制）」完成。通用版式回退不代表真实母版继承。

## 最小调用示例（示例，非官方案例结果）

```bash
python scripts/run_skill.py --case /input/case.json --out /app/output/result.json
```

示例输入（示意）：一个含 2 个版式（Title and Content、Title Only）和 2 页源内容的最小 case。示例输出（示意）：`status="success"`，`slides[0].layout_id` 命中标题版式，正文槽位 `overflow=false`，`export_plan[0].performed=false`。仅为示例，不代表官方固定案例结果。


## 最终交付物（强制）

脚本只产出 `result.json` 中的页级结构与证据映射；调用 Agent 必须继续完成最终交付：

1. 用 `python-pptx`（或等价可编辑格式）按 `result` 的页序、版式与占位符生成 `slides.pptx`；文字、备注、图表编号均可编辑，不把文字压成图片。
2. 用 `office-renderer`/LibreOffice 将 `slides.pptx` 渲染为 `preview.pdf` 与逐页 `preview_p01.png...`，并实际查看预览，确认无溢出、缺字、错页、空白页。
3. 把产物路径、页数、渲染命令与检查结果写入 `result.json` 的 `deliverable`（`pptx_path`、`preview_paths`、`rendered`、`checks`），并记录源文件哈希。
4. 工具确实缺失时，在 `result.json` 与 `limitations` 明确写 `pptx_not_generated` 及原因，不得声称已生成或已渲染。

## 交付保证与评分对齐

调用顺序（固定）：

1. 先运行包内脚本（若存在）：`python scripts/run_skill.py`（默认读 `/input/case.json`，写 `/app/output/result.json`）；路径不同时用 `--case` / `--out` 指定。
2. 再完成脚本无法自动完成的实质工作（译文、论述、图表、修订、结论等），把结果写回 `result.json` 对应字段。
3. 最后自检：`case_id` 与输入一致；`output_contract` 每个字段都存在；`status` 为 `completed`（仅在确实缺输入时为 `partial`）；无 `pending` 占位；数字、引用、来源可逐条回溯。

运行保证：

- 输入缺失、JSON 损坏、字段异常、输出目录不存在时，仍须写出结构化 `result.json` 并正常结束，不得崩溃或非零退出。
- 不联网、不伪造数据、不声称平台评分或官方案例结果。
- 交付物必须是可直接编辑与复核的成品，而不是流程说明。

评分对齐（本题五个维度）：

- 实际效果（40）：完整产出任务要求的最终成品，覆盖全部输入条目，可直接进入修改流程。
- 使用增益（25）：体现相对基础 Agent 的可验证改进（结构化、术语/数字/引用核对、可编辑性）。
- 创新增益（15）：保留方法学增量（分块、对齐、二次校验、版本比对等），并用结果证明其价值。
- 可靠体验（10）：异常输入有明确降级与说明，不同长度/文体/重复运行下稳定产出。
- 生态贡献（10）：用途、调用、输入输出、限制、示例、维护信息齐全，资源可被他人复用。

## 最终交付强制要求

1. **调用 Agent 必须交付成品，不是流程说明**：脚本产出只是索引、核对或规格骨架；调用 Agent 必须在同一 `result.json` 中补齐本题要求的最终产物（正文/译文/审稿意见/综述/分析结论/图表源文件与导出件/幻灯片页内容与讲稿/实验方案等）。交付字段为空、只有标题骨架，或含 `pending`、`TODO` 之类占位，一律视为未完成。
2. **必须覆盖全部输入条目**：输入中的每个章节、问题、文献、图、页面、指标都要有对应条目，不得只处理示例或首条；确实缺失的条目写入 `uncertainty` / `limitations` 并说明原因，不得静默跳过。
3. **必须自检后再交付**：`case_id` 与输入一致；`output_contract` 每个字段都存在；状态值取本题契约规定的枚举；数字、单位、引用、来源可逐条回溯；结果内部无自相矛盾。
4. **参数等价**：`python scripts/run_skill.py --case <输入> --out <输出>` 与 `--output <输出>` 等价；默认 `/input/case.json` → `/app/output/result.json`。
5. **平台用 3 个固定案例分别运行**：逻辑要由输入驱动，不针对某一份示例硬编码；字段命名差异走别名匹配与显式降级，并在 `uncertainty` 记录假设。
