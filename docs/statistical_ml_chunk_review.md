# Statistical ML course chunks 人工核对表

> 本文用于逐条核对 `data/statistical_ml_chunks.json` 中 17 条 chunk 与课件原文
> （`lec8.pdf`，数据文件中登记为 `ai_lec8_statistical_learning.pdf`，47 页）的一致性。
> **所有 chunk 的 `review_status` 目前均为 `codex_draft`，本表只生成待核对项，不擅自将其标记为 `human_verified`。**
> 课件原文由本地 PDF 用 pypdf 提取（`lec8.pdf` 的 SHA-256 与 manifest 中登记的
> `76c2ef3baa4877088bb12745707afd7ad08a68be5fa848deae8625622db7e543` 一致）。

一致性标记约定：
- **一致**：chunk 正文与课件对应页的核心表述相符；
- **部分一致**：核心表述相符，但 chunk 含有超出课件字面的补充/推断措辞；
- **待确认**：chunk 表述无法从课件对应页直接找到出处，需人工核对。

| chunk_id | topic_ids | source_file | 页码 | chunk 正文摘要 | 课件原文对应内容摘要 | 是否一致 | 待人工确认项 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `statistical_ml_supervised_learning` | `statistical_ml__supervised_learning` | ai_lec8_statistical_learning.pdf | 3 | 监督学习：所有训练样本均有对应标注，模型从带标注样本中学习输入到输出的映射。 | 第 3 页「监督学习(Supervised Learning) 监督学习：所有训练样本均有对应的标注」 | 部分一致 | 「模型从带标注样本中学习输入到输出的映射」为对定义的引申，非第 3 页字面；确认是否可接受 |
| `statistical_ml_unsupervised_learning` | `statistical_ml__unsupervised_learning` | ai_lec8_statistical_learning.pdf | 40 | 无监督学习：所有训练样本均没有标注，模型需自行发现数据的内在结构。 | 第 40 页「无监督学习：所有训练样本均没有标注」 | 部分一致 | 「模型需自行发现数据的内在结构」为引申，非第 40 页字面；确认出处 |
| `statistical_ml_knn_lazy_learning` | `statistical_ml__knn_lazy_learning` | ai_lec8_statistical_learning.pdf | 5 | k 近邻是懒惰学习的代表：训练阶段不显式建模，预测时找到最近的 k 个样本投票（分类）或平均（回归）。 | 第 5 页「k 近邻学习器…找到最近的 k 个样本，投票 或者 平均；关键问题：k 值选取；距离计算」 | 待确认 | 第 5 页未出现「懒惰学习 / lazy learning」「训练阶段不显式建模」字样，仅描述「投票或平均」；需确认「懒惰学习」这一表述的课件出处 |
| `statistical_ml_knn_k_value_selection` | `statistical_ml__knn_k_value_selection` | ai_lec8_statistical_learning.pdf | 6–7 | k 值选取影响模型复杂度：k 过小模型复杂易过拟合，k 过大（直至 k=N）模型过于简单。 | 第 7 页「较小的 k…泛化误差会增大…模型变得更复杂，容易发生过拟合；k=N…模型过于简单」 | 一致 | 无 |
| `statistical_ml_knn_distance_metric` | `statistical_ml__knn_distance_metric` | ai_lec8_statistical_learning.pdf | 8 | 距离度量用闵可夫斯基距离，p=2 为欧氏距离，p=1 为曼哈顿距离。 | 第 8 页「闵可夫斯基距离：p=2 欧氏距离，p=1 曼哈顿距离」 | 一致 | 无 |
| `statistical_ml_linear_regression_univariate` | `statistical_ml__linear_regression_univariate` | ai_lec8_statistical_learning.pdf | 15–19 | 一元线性回归 f(x)=wx+b 拟合连续目标，最小二乘法最小化均方误差；闭式解 b=ȳ−w·x̄。 | 第 16 页「最小二乘法…均方误差」；第 18 页「b=1/n Σ(yᵢ−w xᵢ)=ȳ−w x̄」 | 一致 | 无 |
| `statistical_ml_linear_regression_multivariate` | `statistical_ml__linear_regression_multivariate` | ai_lec8_statistical_learning.pdf | 20–24 | 多元线性回归 f(x)=wᵀx+b 用多个特征线性组合预测，矩阵闭式解为 (XᵀX)⁻¹XᵀY。 | 第 20 页「通过属性的线性组合进行预测…向量形式 f(x)=wᵀx+b」；第 23 页「W=(XᵀX)⁻¹XᵀY」 | 一致 | 无 |
| `statistical_ml_linear_regression_regularization` | `statistical_ml__linear_regression_regularization` | ai_lec8_statistical_learning.pdf | 27–28 | 正则化限制参数大小以提升泛化：岭回归用 L2 范数，LASSO 用 L1 范数。 | 第 27 页「限制假设空间复杂度：提升泛化能力…限制参数 w」；第 28 页「岭回归…‖w‖₂；LASSO…‖w‖₁」 | 一致 | 无 |
| `statistical_ml_linear_regression_srm` | `statistical_ml__linear_regression_srm` | ai_lec8_statistical_learning.pdf | 29 | 结构风险最小化最小化 arg min L(w,b)+λ‖w‖_p，权衡经验风险与结构风险。 | 第 29 页「结构风险最小化 arg min L(w,b)+‖w‖_p；经验风险 结构风险」 | 一致 | 无 |
| `statistical_ml_logistic_regression_glm` | `statistical_ml__logistic_regression_glm` | ai_lec8_statistical_learning.pdf | 31–34 | 广义线性模型用联系函数扩展线性模型；对数几率回归是其用于二分类的特例，是分类学习算法。 | 第 31 页「广义线性模型…」；第 34 页「注意：它是分类学习算法！」 | 一致 | 无 |
| `statistical_ml_logistic_regression_sigmoid` | `statistical_ml__logistic_regression_sigmoid` | ai_lec8_statistical_learning.pdf | 32–33 | 单位阶跃函数性质不好，用单调可微的 sigmoid 函数 y=1/(1+e^(−z)) 作为替代函数。 | 第 32 页「单位阶跃函数…性质不好，需找替代函数…单调可微…sigmoid 函数 y=1/(1+e^−z)」 | 一致 | 无 |
| `statistical_ml_logistic_regression_mle` | `statistical_ml__logistic_regression_mle` | ai_lec8_statistical_learning.pdf | 35–36 | 对数几率回归用极大似然估计求解，等价于最小化交叉熵损失。 | 第 36 页「极大似然估计…等价于最小化…交叉熵损失」 | 一致 | 无 |
| `statistical_ml_logistic_regression_gradient_descent` | `statistical_ml__logistic_regression_gradient_descent` | ai_lec8_statistical_learning.pdf | 37 | 梯度下降沿负梯度方向迭代更新参数 w=w−η∇f(w)，学习率 η 控制步长。 | 第 37 页「参数更新 w=w−η∇f(w)；η 称为步长或学习率」 | 一致 | 无 |
| `statistical_ml_clustering_evaluation` | `statistical_ml__clustering_evaluation` | ai_lec8_statistical_learning.pdf | 42 | 聚类好坏没有绝对标准，基本原则是簇内相似度高且簇间相似度低。 | 第 42 页「聚类的"好坏"不存在绝对标准…簇内相似度高，且簇间相似度低」 | 一致 | 无 |
| `statistical_ml_kmeans_algorithm` | `statistical_ml__kmeans_algorithm` | ai_lec8_statistical_learning.pdf | 44–45 | K 均值以簇内样本均值表示簇：选 k 个中心、划分样本、更新均值，直到中心不再变化。 | 第 44 页「每个簇以该簇中所有样本点的均值表示；Step1 选中心、Step2 划分、Step3 更新均值、Step4 未变则停止」 | 一致 | 无 |
| `statistical_ml_kmeans_limitations` | `statistical_ml__kmeans_limitations` | ai_lec8_statistical_learning.pdf | 46 | K 均值需预设簇数、对初始化敏感、迭代开销大，且假设各维度重要性相同。 | 第 46 页「需要事先确定聚类数目…对初始化敏感…时间开销非常大…假设每个维度重要性一样」 | 一致 | 无 |
| `statistical_ml_clustering_applications` | `statistical_ml__clustering_applications` | ai_lec8_statistical_learning.pdf | 47 | 聚类可单独发现数据结构，也可作为分类等任务的前驱，例如文本聚类与色彩压缩。 | 第 47 页「文本分类：将 200 多万篇论文聚类到 29000 个类别…色彩压缩」 | 部分一致 | ①课件字面为「文本分类」而非「文本聚类」（其描述本身是把论文"聚类"到类别，可接受，但需确认）；②「也可作为分类等任务的前驱」为一般性推断，第 47 页未直接表述 |

## 核对结论

- 17 条 chunk 中，**12 条一致**、**3 条部分一致**（`supervised_learning`、`unsupervised_learning`、`clustering_applications`）、**2 条待确认**（`knn_lazy_learning` 的「懒惰学习」措辞、`clustering_applications` 的「文本聚类/前驱」措辞）。
- 所有 chunk 的页码与 `source_file`（`ai_lec8_statistical_learning.pdf`）均已与本地 `lec8.pdf` 逐页比对，页号范围正确。
- 在课程 owner 确认上述「部分一致 / 待确认」项并核对完成后，才可将对应 chunk 从 `codex_draft` 提升为 `human_verified`。
