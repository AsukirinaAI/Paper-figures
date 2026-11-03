# 论文翻译时的图表处理 Prompt（可直接复制）

在完整翻译我提供的论文 PDF 时，**请先访问并阅读以下 GitHub 通用图表处理规范，并严格依照其中的流程执行，不要自行简化或替换方案**：

https://github.com/AsukirinaAI/Paper-figures/blob/main/docs/PAPER_ASSET_WORKFLOW.md

所有图表素材统一归档到 `Papers/<Paper-Name>/`，Manifest 的 `output_dir` 必须填写该完整相对路径；不要在仓库根目录创建论文文件夹，不保留旧图片 URL 兼容。

按规范核对本篇论文（包括附录）的全部 Figure 与 Table：优先复用仓库已有且版本匹配的高清 PNG；若缺失，则按规范精确裁剪、归档、上传 GitHub，确认真实链接可访问后再引用。在译文对应位置嵌入已验证的 GitHub Raw PNG 图片地址，完整翻译图注与表注，并用 Obsidian `[[#^块ID]]` 形式实现正文中的图表自引用。

**最终只交付一个完整的 Obsidian Markdown `.md` 文件**，所有图表引用已在文件内部处理妥当；不要另外交付图片、PDF、ZIP 或其他附件。若无法读取规范或完成上传/验证，请如实说明，绝不可编造图片链接。其他翻译内容和格式要求按我提供的主翻译要求执行。