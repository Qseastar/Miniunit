# Statistical ML course chunks — 人工核对清单（已确认）

> 从 `docs/statistical_ml_chunk_review.md` 提取的「待人工确认」条目。以下 4 条已由课程
> owner 确认处理完成（状态：**已确认**），chunk 正文/页码已按处理结果同步更新到
> `data/statistical_ml_chunks.json`。chunk 的 `review_status` 仍为 `codex_draft`（本次
> 未提升为 `human_verified`）。

### 1. `statistical_ml_supervised_learning` — ✅ 已确认（保持）

- **topic_ids**：`statistical_ml__supervised_learning`
- **课件页码**：第 3 页
- **chunk 正文摘要**：监督学习：所有训练样本均有对应的标注，模型从带标注样本中学习输入到输出的映射。
- **课件原文摘要**：「监督学习(Supervised Learning) 监督学习：所有训练样本均有对应的标注」
- **处理结果**：保持内容不变（「模型从带标注样本中学习输入到输出的映射」为可接受的引申）。

### 2. `statistical_ml_unsupervised_learning` — ✅ 已确认（保持）

- **topic_ids**：`statistical_ml__unsupervised_learning`
- **课件页码**：第 40 页
- **chunk 正文摘要**：无监督学习：所有训练样本均没有标注，模型需自行发现数据的内在结构。
- **课件原文摘要**：「无监督学习 无监督学习：所有训练样本均没有标注」
- **处理结果**：保持内容不变（「模型需自行发现数据的内在结构」为可接受的引申）。

### 3. `statistical_ml_knn_lazy_learning` — ✅ 已确认（页码更正）

- **topic_ids**：`statistical_ml__knn_lazy_learning`
- **课件页码**：第 4–5 页（原第 5 页 → 更正为 4–5）
- **chunk 正文摘要**：k 近邻是懒惰学习的代表：训练阶段不显式建模，预测时找到最近的 k 个样本投票（分类）或平均（回归）。
- **课件原文摘要**：第 4 页「…近朱者赤，近墨者黑 懒惰学习(lazy learning)的代表」；第 5 页「k 近邻学习器…找到最近的 k 个样本，投票 或者 平均」
- **处理结果**：「懒惰学习」出处确认为第 4 页；页码由第 5 页改为第 4–5 页，正文措辞保持不变。

### 4. `statistical_ml_clustering_applications` — ✅ 已确认（正文修改）

- **topic_ids**：`statistical_ml__clustering_applications`
- **课件页码**：第 47 页
- **chunk 正文摘要**：聚类可单独发现数据结构，例如文本分类与色彩压缩。
- **课件原文摘要**：「K-Means 的应用：文本分类（将 200 多万篇论文聚类到 29000 个类别）…色彩压缩」
- **处理结果**：「文本聚类」改为「文本分类」（与课件原文一致）；删除「也可作为分类等任务的前驱」这一一般性引申。
