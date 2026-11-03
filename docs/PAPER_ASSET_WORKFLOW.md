# 论文图表的高清提取、归档与引用规范（通用）

> **唯一规范入口。** 适用于所有可取得原始 PDF 的研究论文，不限于 Doc-to-LoRA。**所有论文资产统一存放在仓库 `Papers/<Paper-Name>/`，禁止在根目录直接新建论文目录，旧图片地址不再兼容。** 论文翻译 Agent 应先读取本文件，然后依据当前论文的 PDF 和仓库资产目录执行。未完成核查或上传时不可杜撰有效链接。

## 1. 目标与交付约束

1. **完整性**：逐页识别正文和附录的全部编号 **Figure / Table**；对双栏、跨栏、子图 (a)/(b)、跨页表格及表格注释格外注意。
2. **精确裁剪**：保留整张图或表的主体、刻度/图例、表头/尾行、脚注和必要注释；去除论文页眉页脚、无关正文和可单独翻译的 Figure/Table Caption。不得裁断笔画、字符或图表元素。
3. **只输出高清 PNG**：从**原始 PDF 页面直接重新渲染裁剪区域**，默认 `scale = 4 × √4.5 ≈ 8.4853`，即 `72 × scale ≈ 611 DPI`，相对 288 DPI 旧版**总像素数约 4.5 倍**（宽、高各约 2.121 倍）。可按原始图质量调整，但不得通过二次放大低清截图充数。底色默认白色；不添加水印、不修改实验数值。
4. **分类存储**：每篇论文独立目录 `Papers/<Paper-Name>/`，包含 `figures/Figure_01.png` 和 `tables/Table_01.png`（编号从原文，英文/附录编号原样保留），图片名字稳定。
5. **溯源**：记录论文题名、版本、PDF 源地址、页数、每一项原 PDF 物理页码（从 1 开始）、裁剪坐标 `x0,y0,x1,y1`（PDF point）、倍率、数量与 Raw 链接。更新论文版本必须重新核对坐标。
6. **可直接引用**：图表先确保已提交 GitHub `main` 并验证文件存在，再在译文中引用 Raw PNG 地址。翻译任务最终只交付一份已嵌入引用的 `.md` 文件，不附图片文件夹、压缩包或裁剪 PDF。

## 2. 标准处理流程

### 2.1 确认论文身份与版本

- 确定 DOI/arXiv ID、版本（v1/v2 之间分页可能改变）、论文总页数及来源可靠性。
- 优先使用用户提供的原始 PDF；公网上有**完全相同的版本**时，GitHub Actions 可从公开 HTTPS 地址重新下载。私人或非公开 PDF 不可上传到公开仓库，除非用户明确授权；本工作流仅适用于公开源。
- 检查 `Papers/` 下是否已有该论文目录和 Manifest。如有完整图表并且版本匹配，**优先复用**，避免重复提取；否则新增或重建。

### 2.2 盘点图表数量与位置

- 逐页阅读 PDF 的正文、附录，寻找 `Figure N` / `Table N` 的**标题/Caption**，不能把正文中的 “see Figure N” 当作新图。
- 检查标题与主体是否位于不同的页面/栏，并分清多面板图与独立图；多面板图默认合成一张 Figure，不逐面板拆分。
- 在清单里记录编号、标题所在页、主体所在页；核对连续编号、数量、重复编号和漏项。遇到跨页或非标准编号时，Manifest 可明确记录额外信息，必要时采取多个图片和清楚的引用方案。

### 2.3 可视化定位与人工复核坐标

- **先低 DPI 渲染预览整页并检查图表布局**，再为每项确定精确的 `fitz.Rect(x0,y0,x1,y1)`。
- 坐标系：PDF point，左上角原点（在 PyMuPDF 坐标系中）；`page` 从 1 开始，程序调用 `doc[page - 1]`。
- 默认图注放在译文中单独翻译，裁剪区不含 caption；表格主体需包含所有表头、行、列及脚注中承载信息的内容。不能只按“离 Table N 最近的矩形”粗裁。
- 根据图片预览检查空白边距、页眉干扰、图例边界和右侧最后一列，尤其注意双栏内嵌小表格与附录图片。

### 2.4 建立论文 Manifest

在 `manifests/<paper-slug>.json` 保存以下字段；实际示例见 [`doc-to-lora-2026.json`](../manifests/doc-to-lora-2026.json)。

```json
{
  "slug": "example-2026",
  "title": "Paper Title",
  "citation": "Author et al. (2026), ...",
  "source_version": "arXiv v1 (... pages)",
  "source_urls": ["https://example.org/paper.pdf"],
  "expected_pages": 12,
  "repository": "AsukirinaAI/Paper-figures",
  "output_dir": "Papers/Example-Paper",
  "render_scale": 8.48528137423857,
  "figures": [{"id": 1, "page": 2, "rect": [55, 102, 540, 341]}],
  "tables": [{"id": 1, "page": 3, "rect": [59, 155, 500, 294]}]
}
```

**`output_dir` 必须为 `Papers/<Paper-Name>`，且仅允许一层英文字母、数字、连字符或下划线命名的论文目录。提取脚本会强制校验。**

**上述矩形仅是格式示例，绝不可直接用于其他论文。** 每份论文必须逐项定位并视觉验证。若 caption 页与主体页不同，可使用 `caption_page`。从不根据“论文通常有多少图”猜测应有条目数。

### 2.5 PNG 高分辨率导出

使用库：`PyMuPDF / fitz`。核心调用：

```python
import math
import fitz

scale = 4.0 * math.sqrt(4.5)
doc = fitz.open("paper.pdf")
page = doc[page_number - 1]
clip = fitz.Rect(x0, y0, x1, y1)
pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=clip, alpha=False)
pix.set_dpi(round(72 * scale), round(72 * scale))
pix.save("Figure_01.png")
```

这是**直接对原始 PDF 矢量/文字内容进行高分辨率光栅化**，不是对小截图插值扩张。如果原始论文的素材本身是低清位图，则增加 DPI 不会创造丢失的细节。**不导出裁剪版 PDF**。

通用脚本执行：

```bash
python -m pip install pymupdf
python scripts/extract_paper_assets.py --manifest manifests/<paper-slug>.json --pdf /path/to/original.pdf
# 若 Manifest 记录的 PDF 为公开 HTTPS 地址，也可省略 --pdf，脚本自动下载
python scripts/extract_paper_assets.py --manifest manifests/<paper-slug>.json
# 批量重新生成全部公开论文素材
python scripts/extract_paper_assets.py --all
```

脚本会检查 PDF 页数、caption 覆盖与位置、裁剪矩形越界、重复 ID，自动生成 `Papers/<Paper-Name>/README.md` 索引及新路径的 Raw PNG 引用。Manifest 用于复现，新增论文时无需修改通用提取算法。

### 2.6 检查与 GitHub 提交

- **质量验收**：逐张查看大图和总览图，确保完整、清晰、图中实验数字与原文一致；没有图注混入或其他正文；无需追求无意义的超高 DPI，避免超大文件。
- **完整性验收**：Figure/Table 数量与逐页盘点一致，所有文件命名和序号正确，`README.md` 和 Manifest 对应一致。
- 使用 GitHub 写权限提交 `Papers/<Paper-Name>/figures/`、`Papers/<Paper-Name>/tables/`、论文的 `README.md` 及根目录的 Manifest；不要上传源论文 PDF、裁剪 PDF、临时截图或调试文件。
- 公开论文可通过 [通用 GitHub Actions](../.github/workflows/build-paper-assets.yml) 在 GitHub Runner 上重新获取 PDF、生成 PNG 并自动提交，从而绕过聊天连接不能直接上传二进制文件的限制。
- **确认 Actions success 后仍需查询仓库目录**，核查图片文件实际存在、至少抽样检查 Raw URL 返回正常内容；未验证前不要宣称“已上传”或输出虚构的可用引用。

## 3. 目录、引用与 Obsidian 规则

```text
Papers/
└── <Paper-Name>/
    ├── README.md
    ├── figures/Figure_01.png
    └── tables/Table_01.png
```

基础 URL：

```text
https://raw.githubusercontent.com/AsukirinaAI/Paper-figures/main/Papers/<Paper-Name>/figures/Figure_01.png
https://raw.githubusercontent.com/AsukirinaAI/Paper-figures/main/Papers/<Paper-Name>/tables/Table_01.png
```

在 Obsidian Markdown 译文中，图表嵌入使用 Markdown 图片语法（**不是**普通 GitHub `blob/` 页面地址）：

```markdown
![图 1：中文说明](https://raw.githubusercontent.com/AsukirinaAI/Paper-figures/main/Papers/Example-Paper/figures/Figure_01.png)

图 1：完整的中文图注。 ^fig1

![表 1：中文说明](https://raw.githubusercontent.com/AsukirinaAI/Paper-figures/main/Papers/Example-Paper/tables/Table_01.png)

表 1：完整的中文表注。 ^tab1

正文引用：如图 1 所示（[[#^fig1]]），或参考表 1（[[#^tab1]]）。
```

- 将图片放在原文出现的恰当位置；图表说明与标题翻译成中文，严格保持序号和数据。
- 原图内英文图例/表头**保持原文像素**；必要时在译文追加译注，不擅自重绘或改动原始数据。
- 译文使用 Obsidian 的 `[[#^块ID]]` 来链接该 Markdown 内对应图表标题/说明块；ID 须唯一。
- 表格默认使用高分辨率 PNG 保持复杂版式；是否额外转为 Markdown 原生表格由翻译任务另外明确，**不得代替**保存图表 PNG。
- 不使用 Base64 Data URI、Obsidian 本地附件文件夹或额外 zip，除非用户另有明确要求。

## 4. 翻译任务的输出合同

1. 先打开并遵守本规范，并检查已有资源是否完整；缺失时依据工作流提取上传并验证后引用。
2. 译完原文要求翻译的所有正文与附录，保持图表顺序、编号、完整中文 Caption 和引用。与图表无关的翻译要求以用户主 Prompt 为准。
3. **只交付一个最终 `.md` 文件**，里面已嵌入经验证的 Raw PNG 地址、Obsidian 块锚点与交叉引用。仓库中允许保存素材 PNG，但不要把它们作为翻译交付附件。
4. 如果 PDF 或 GitHub 不可访问、无仓库写权限、上传失败或版权/保密限制导致无法上传，要明确报告问题，**不可伪造成功、不可使用未上传的假链接**。

## 5. 论文版本变更与维护

- 不提供旧根目录图片路径兼容；翻译引用要使用 `/main/Papers/<Paper-Name>/...`，旧路径由使用者自行更新。
- 论文 PDF 版本发生变化时重新盘点所有图表、更新 Manifest 坐标和索引，运行质量检查。
- 不保留低分辨率重复版本或裁剪 PDF；统一使用高质量 PNG。
- 引用文件名以原文的编号为核心，避免论文内容更新后指向错误图表；如果编号有变化，应同步更新翻译引用。
- 每次提交检验 workflow 成功、图表数量完整和 Raw 链接实际可用。