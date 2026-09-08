# 统计机器学习候选诊断题人工审核清单

> 来源：`data/candidate_templates/statistical_ml_p1_candidates.json`（9 道，`candidate_status=pending_human_review`）
> 用途：供课程负责人逐题审核，在每题后填写 `approve` / `revise` / `reject`。

## 1. verify_supervised_vs_unsupervised_definition_v1
- **concept_id**: `statistical_ml__supervised_vs_unsupervised`
- **题型**: single_choice（single_choice_v1）
- **题干**: 给定一批训练样本，如果其中每个样本都没有对应的标注（标签），这属于哪一类学习任务？
- **正确答案**: `unsupervised`（无监督学习）
- **干扰项**: `supervised`（监督学习）、`reinforcement`（强化学习）、`semi_supervised`（半监督学习）
- **explanation 要点**: 监督学习要求所有训练样本都有对应的标注；无监督学习的训练样本均没有标注（例如聚类任务）。题干明确说明样本均无标注，因此属于无监督学习。
- **依据页码**: p.3; p.40
- **审核结论**: （待填 approve / revise / reject）

## 2. verify_knn_k_value_effect_v1
- **concept_id**: `statistical_ml__k_nearest_neighbors`
- **题型**: single_choice（single_choice_v1）
- **题干**: 在 k 近邻算法中，若 k 值取得过小（例如 k=1），通常会导致？
- **正确答案**: `overfitting`（模型变得复杂，容易过拟合）
- **干扰项**: `underfitting`（模型过于简单，欠拟合）、`no_effect`（对模型没有影响）、`always_better`（一定提高泛化性能）
- **explanation 要点**: k 减小意味着模型变得更复杂，训练误差减小但泛化误差增大，容易过拟合；k 增大（直至 k=N）则模型过于简单。
- **依据页码**: p.7
- **审核结论**: （待填 approve / revise / reject）

## 3. verify_knn_manhattan_distance_v1
- **concept_id**: `statistical_ml__k_nearest_neighbors`
- **题型**: numeric_answer（numeric_answer_v1）
- **题干**: 二维空间中，两点 x=(1,1) 与 x'=(4,5) 的曼哈顿距离（闵可夫斯基距离 p=1）等于多少？
- **正确答案**: `7`（容差 ±0.01）
- **干扰项**: 无（数值填空，scorer 拒绝非数值/错误数值）
- **explanation 要点**: 曼哈顿距离（p=1）为 Σ|xi − xi'| = |4−1| + |5−1| = 3 + 4 = 7。注意欧氏距离（p=2）是 5，不要混淆。
- **依据页码**: p.8
- **审核结论**: （待填 approve / revise / reject）

## 4. verify_linear_regression_least_squares_objective_v1
- **concept_id**: `statistical_ml__linear_regression_least_squares`
- **题型**: single_choice（single_choice_v1）
- **题干**: 一元线性回归 f(x)=wx+b 中，最小二乘法（least square method）的优化目标是？
- **正确答案**: `min_mse`（最小化预测值与真实值之差的平方和（均方误差））
- **干扰项**: `min_abs`（最小化预测值与真实值之差的绝对值之和）、`max_likelihood`（最大化样本的似然）、`min_param`（最小化参数 w 和 b 的绝对值）
- **explanation 要点**: 最小二乘法最小化均方误差，即 Σ(yi − f(xi))²，对应『差的平方和』，而不是绝对值之和（那是 L1 损失）。
- **依据页码**: p.15-16
- **审核结论**: （待填 approve / revise / reject）

## 5. verify_linear_regression_closed_form_intercept_v1
- **concept_id**: `statistical_ml__linear_regression_least_squares`
- **题型**: numeric_answer（numeric_answer_v1）
- **题干**: 一元线性回归 f(x)=wx+b 中，若训练样本 x 的均值 x̄=5、y 的均值 ȳ=3，且已求得 w=2，则闭式解给出的截距 b 等于多少？（提示：b = ȳ − w·x̄）
- **正确答案**: `-7`（容差 ±0.01）
- **干扰项**: 无（数值填空，scorer 拒绝非数值/错误数值）
- **explanation 要点**: 一元回归闭式解 b = ȳ − w x̄，代入得 b = 3 − 2×5 = −7。
- **依据页码**: p.17
- **审核结论**: （待填 approve / revise / reject）

## 6. verify_logistic_regression_is_classifier_v1
- **concept_id**: `statistical_ml__logistic_regression`
- **题型**: single_choice（single_choice_v1）
- **题干**: 关于对数几率回归（logistic regression），下列哪项说法正确？
- **正确答案**: `is_classifier`（它是一种分类学习算法）
- **干扰项**: `is_regression`（它是一种回归算法，用于预测连续值）、`is_clustering`（它是一种无监督聚类算法）、`no_sigmoid`（它不使用 sigmoid 函数）
- **explanation 要点**: 对数几率回归在回归模型中引入 sigmoid 函数，输出概率并用于二分类，因此是分类学习算法；『回归』只是历史命名。
- **依据页码**: p.33
- **审核结论**: （待填 approve / revise / reject）

## 7. verify_logistic_regression_sigmoid_range_v1
- **concept_id**: `statistical_ml__logistic_regression`
- **题型**: single_choice（single_choice_v1）
- **题干**: 对数几率回归中，sigmoid 函数 y = 1/(1+e^(−z)) 的输出取值范围是？
- **正确答案**: `open_01`（(0, 1)）
- **干扰项**: `closed_01`（[0, 1]）、`all_real`（(−∞, +∞)）、`binary`（{−1, +1}）
- **explanation 要点**: sigmoid 函数 y = 1/(1+e^(−z)) 的输出范围是开区间 (0,1)，不会取到端点 0 或 1。
- **依据页码**: p.32
- **审核结论**: （待填 approve / revise / reject）

## 8. verify_kmeans_steps_order_v1
- **concept_id**: `statistical_ml__k_means_clustering`
- **题型**: ordering（ordering_v1）
- **题干**: 请将 K 均值（K-Means）聚类的执行步骤按正确顺序排列。
- **正确顺序**: `init`(随机选取 k 个样本点作为簇中心) → `assign`(将其他样本点根据其与簇中心的距离，划分给最近的簇) → `update`(更新各簇的均值向量，将其作为新的簇中心) → `check`(若所有簇中心未发生改变则停止，否则回到划分步骤)
- **干扰项**: 顺序错乱（scorer 要求精确完整顺序）
- **explanation 要点**: 正确顺序为：①随机选 k 个簇中心 → ②按距离把样本划分给最近的簇 → ③更新各簇均值作为新中心 → ④判断是否停止，未停止则回到②。
- **依据页码**: p.44
- **审核结论**: （待填 approve / revise / reject）

## 9. verify_kmeans_limitations_v1
- **concept_id**: `statistical_ml__k_means_clustering`
- **题型**: single_choice（single_choice_v1）
- **题干**: 下列哪项不是 K 均值（K-Means）聚类的不足？
- **正确答案**: `auto_k`（能够自动确定最优的聚类数目）
- **干扰项**: `preset_k`（需要事先确定聚类数目）、`sensitive_init`（初始化簇中心对聚类结果影响较大）、`high_cost`（迭代执行的时间开销较大）
- **explanation 要点**: K-Means 恰恰无法自动确定簇数目（需要事先指定 k），所以『能自动确定最优聚类数目』不是它的特性，而是其不足的反面。
- **依据页码**: p.46
- **审核结论**: （待填 approve / revise / reject）
