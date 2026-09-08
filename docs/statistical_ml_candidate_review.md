# 统计机器学习候选诊断题人工审核清单

> 来源：`data/candidate_templates/statistical_ml_p1_candidates.json`（18 道，`candidate_status=pending_human_review`）
> 用途：供课程负责人逐题审核。
>
> **全部 18 题已通过人工审核并 promotion 到 production（`data/statistical_ml_templates.json`）。**

## 1. verify_supervised_vs_unsupervised_definition_v1
- **concept_id**: `statistical_ml__unsupervised_learning`
- **题型**: single_choice（single_choice_v1）
- **题干**: 给定一批训练样本，如果其中每个样本都没有对应的标注（标签），这属于哪一类学习任务？
- **正确答案**: `unsupervised`（无监督学习）
- **干扰项**: `supervised`（监督学习）、`reinforcement`（强化学习）、`semi_supervised`（半监督学习）
- **explanation 要点**: 监督学习要求所有训练样本都有对应的标注；无监督学习的训练样本均没有标注（例如聚类任务）。题干明确说明样本均无标注，因此属于无监督学习。
- **依据页码**: p.3; p.40
- **审核结论**: approve

## 2. verify_knn_k_value_effect_v1
- **concept_id**: `statistical_ml__knn_k_value_selection`
- **题型**: single_choice（single_choice_v1）
- **题干**: 在 k 近邻算法中，若 k 值取得过小（例如 k=1），通常会导致？
- **正确答案**: `overfitting`（模型变得复杂，容易过拟合）
- **干扰项**: `underfitting`（模型过于简单，欠拟合）、`no_effect`（对模型没有影响）、`always_better`（一定提高泛化性能）
- **explanation 要点**: k 减小意味着模型变得更复杂，训练误差减小但泛化误差增大，容易过拟合；k 增大（直至 k=N）则模型过于简单。
- **依据页码**: p.7
- **审核结论**: approve

## 3. verify_knn_manhattan_distance_v1
- **concept_id**: `statistical_ml__knn_distance_metric`
- **题型**: numeric_answer（numeric_answer_v1）
- **题干**: 二维空间中，两点 x=(1,1) 与 x'=(4,5) 的曼哈顿距离（闵可夫斯基距离 p=1）等于多少？
- **正确答案**: `7`（容差 ±0.01）
- **干扰项**: 无（数值填空，scorer 拒绝非数值/错误数值）
- **explanation 要点**: 曼哈顿距离（p=1）为 Σ|xi − xi'| = |4−1| + |5−1| = 3 + 4 = 7。注意欧氏距离（p=2）是 5，不要混淆。
- **依据页码**: p.8
- **审核结论**: approve

## 4. verify_linear_regression_least_squares_objective_v1
- **concept_id**: `statistical_ml__linear_regression_univariate`
- **题型**: single_choice（single_choice_v1）
- **题干**: 一元线性回归 f(x)=wx+b 中，最小二乘法（least square method）的优化目标是？
- **正确答案**: `min_mse`（最小化预测值与真实值之差的平方和（均方误差））
- **干扰项**: `min_abs`（最小化预测值与真实值之差的绝对值之和）、`max_likelihood`（最大化样本的似然）、`min_param`（最小化参数 w 和 b 的绝对值）
- **explanation 要点**: 最小二乘法最小化均方误差，即 Σ(yi − f(xi))²，对应『差的平方和』，而不是绝对值之和（那是 L1 损失）。
- **依据页码**: p.15-16
- **审核结论**: approve

## 5. verify_linear_regression_closed_form_intercept_v1
- **concept_id**: `statistical_ml__linear_regression_univariate`
- **题型**: numeric_answer（numeric_answer_v1）
- **题干**: 一元线性回归 f(x)=wx+b 中，若训练样本 x 的均值 x̄=5、y 的均值 ȳ=3，且已求得 w=2，则闭式解给出的截距 b 等于多少？（提示：b = ȳ − w·x̄）
- **正确答案**: `-7`（容差 ±0.01）
- **干扰项**: 无（数值填空，scorer 拒绝非数值/错误数值）
- **explanation 要点**: 一元回归闭式解 b = ȳ − w x̄，代入得 b = 3 − 2×5 = −7。
- **依据页码**: p.17
- **审核结论**: approve

## 6. verify_logistic_regression_is_classifier_v1
- **concept_id**: `statistical_ml__logistic_regression_glm`
- **题型**: single_choice（single_choice_v1）
- **题干**: 关于对数几率回归（logistic regression），下列哪项说法正确？
- **正确答案**: `is_classifier`（它是一种分类学习算法）
- **干扰项**: `is_regression`（它是一种回归算法，用于预测连续值）、`is_clustering`（它是一种无监督聚类算法）、`no_sigmoid`（它不使用 sigmoid 函数）
- **explanation 要点**: 对数几率回归在回归模型中引入 sigmoid 函数，输出概率并用于二分类，因此是分类学习算法；『回归』只是历史命名。
- **依据页码**: p.33
- **审核结论**: approve

## 7. verify_logistic_regression_sigmoid_range_v1
- **concept_id**: `statistical_ml__logistic_regression_sigmoid`
- **题型**: single_choice（single_choice_v1）
- **题干**: 对数几率回归中，sigmoid 函数 y = 1/(1+e^(−z)) 的输出取值范围是？
- **正确答案**: `open_01`（(0, 1)）
- **干扰项**: `closed_01`（[0, 1]）、`all_real`（(−∞, +∞)）、`binary`（{−1, +1}）
- **explanation 要点**: sigmoid 函数 y = 1/(1+e^(−z)) 的输出范围是开区间 (0,1)，不会取到端点 0 或 1。
- **依据页码**: p.32
- **审核结论**: approve

## 8. verify_kmeans_steps_order_v1
- **concept_id**: `statistical_ml__kmeans_algorithm`
- **题型**: ordering（ordering_v1）
- **题干**: 请将 K 均值（K-Means）聚类的执行步骤按正确顺序排列。
- **正确顺序**: `init`(随机选取 k 个样本点作为簇中心) → `assign`(将其他样本点根据其与簇中心的距离，划分给最近的簇) → `update`(更新各簇的均值向量，将其作为新的簇中心) → `check`(若所有簇中心未发生改变则停止，否则回到划分步骤)
- **干扰项**: 顺序错乱（scorer 要求精确完整顺序）
- **explanation 要点**: 正确顺序为：①随机选 k 个簇中心 → ②按距离把样本划分给最近的簇 → ③更新各簇均值作为新中心 → ④判断是否停止，未停止则回到②。
- **依据页码**: p.44
- **审核结论**: approve

## 9. verify_kmeans_limitations_v1
- **concept_id**: `statistical_ml__kmeans_limitations`
- **题型**: single_choice（single_choice_v1）
- **题干**: 下列哪项不是 K 均值（K-Means）聚类的不足？
- **正确答案**: `auto_k`（能够自动确定最优的聚类数目）
- **干扰项**: `preset_k`（需要事先确定聚类数目）、`sensitive_init`（初始化簇中心对聚类结果影响较大）、`high_cost`（迭代执行的时间开销较大）
- **explanation 要点**: K-Means 恰恰无法自动确定簇数目（需要事先指定 k），所以『能自动确定最优聚类数目』不是它的特性，而是其不足的反面。
- **依据页码**: p.46
- **审核结论**: approve

## 10. verify_statistical_ml_supervised_learning_sc_v1
- **concept_id**: `statistical_ml__supervised_learning`
- **题型**: single_choice（single_choice_v1）
- **题干**: 关于监督学习，下列哪项说法正确？
- **正确答案**: `labeled`（所有训练样本均有对应的标注）
- **干扰项**: `unlabeled`（所有训练样本均没有标注）、`partial`（只有部分训练样本有标注）、`no_data`（不需要任何训练样本）
- **explanation 要点**: 监督学习要求所有训练样本均有对应的标注，模型从带标注样本中学习输入到输出的映射。
- **依据页码**: p.3
- **审核结论**: approve

## 11. verify_statistical_ml_knn_lazy_learning_sc_v1
- **concept_id**: `statistical_ml__knn_lazy_learning`
- **题型**: single_choice（single_choice_v1）
- **题干**: k近邻算法被称为懒惰学习（lazy learning）的原因是？
- **正确答案**: `defer_modeling`（训练阶段不显式建模，预测时才基于邻近样本计算）
- **干扰项**: `eager_model`（训练阶段就构建出完整的决策模型）、`no_train`（完全不需要训练数据）、`slow_predict`（预测速度比训练更快）
- **explanation 要点**: k近邻是懒惰学习的代表：训练阶段不显式建模，把计算推迟到预测时，基于邻近样本投票或平均。
- **依据页码**: p.5
- **审核结论**: approve

## 12. verify_statistical_ml_linear_regression_multivariate_sc_v1
- **concept_id**: `statistical_ml__linear_regression_multivariate`
- **题型**: single_choice（single_choice_v1）
- **题干**: 多元线性回归与一元线性回归的主要区别在于？
- **正确答案**: `multi_features`（使用多个特征的线性组合进行预测）
- **干扰项**: `single_feature`（只使用一个特征进行预测）、`non_linear`（不再使用线性函数）、`for_classify`（用于分类而不是回归）
- **explanation 要点**: 多元线性回归用多个特征的线性组合 f(x)=w₁x₁+…+wₙxₙ+b 预测，矩阵形式闭式解为 (XᵀX)⁻¹XᵀY。
- **依据页码**: p.20-24
- **审核结论**: approve

## 13. verify_statistical_ml_linear_regression_regularization_sc_v1
- **concept_id**: `statistical_ml__linear_regression_regularization`
- **题型**: single_choice（single_choice_v1）
- **题干**: 岭回归（Ridge Regression）在损失函数中加入的正则化项使用哪种范数？
- **正确答案**: `l2_norm`（L2 范数（‖w‖²））
- **干扰项**: `l1_norm`（L1 范数（‖w‖₁））、`l0_norm`（L0 范数）、`no_norm`（不加入任何范数惩罚）
- **explanation 要点**: 岭回归使用 L2 范数 ‖w‖² 作为正则化项，而 LASSO 使用 L1 范数 ‖w‖₁。
- **依据页码**: p.27-28
- **审核结论**: approve

## 14. verify_statistical_ml_linear_regression_srm_sc_v1
- **concept_id**: `statistical_ml__linear_regression_srm`
- **题型**: single_choice（single_choice_v1）
- **题干**: 结构风险最小化（SRM）的优化目标由哪两部分组成？
- **正确答案**: `empirical_structural`（经验风险与结构风险（参数范数惩罚））
- **干扰项**: `only_empirical`（只有经验风险）、`only_structural`（只有结构风险）、`bias_variance`（偏差与方差）
- **explanation 要点**: 结构风险最小化最小化 arg min L(w,b)+λ‖w‖_p，第一项 L(w,b) 是经验风险，第二项 λ‖w‖_p 是结构风险。
- **依据页码**: p.29
- **审核结论**: approve

## 15. verify_statistical_ml_logistic_regression_mle_sc_v1
- **concept_id**: `statistical_ml__logistic_regression_mle`
- **题型**: single_choice（single_choice_v1）
- **题干**: 对数几率回归用极大似然估计求解，等价于最小化哪种损失函数？
- **正确答案**: `cross_entropy`（交叉熵损失）
- **干扰项**: `mse`（均方误差损失）、`mae`（平均绝对误差损失）、`hinge`（合页损失）
- **explanation 要点**: 对数几率回归的极大似然估计等价于最小化交叉熵损失 −Σ[y ln f + (1−y) ln(1−f)]。
- **依据页码**: p.35-36
- **审核结论**: approve

## 16. verify_statistical_ml_logistic_regression_gradient_descent_sc_v1
- **concept_id**: `statistical_ml__logistic_regression_gradient_descent`
- **题型**: single_choice（single_choice_v1）
- **题干**: 梯度下降中，学习率（步长）η 的作用是？
- **正确答案**: `step_size`（控制每次参数更新的幅度）
- **干扰项**: `layer_count`（控制模型的层数）、`sample_size`（控制训练样本的数量）、`feature_count`（控制特征的数量）
- **explanation 要点**: 梯度下降按 w = w − η∇f(w) 更新参数，学习率 η 控制每步更新的幅度，不能太大也不能太小。
- **依据页码**: p.37
- **审核结论**: approve

## 17. verify_statistical_ml_clustering_evaluation_sc_v1
- **concept_id**: `statistical_ml__clustering_evaluation`
- **题型**: single_choice（single_choice_v1）
- **题干**: 评价聚类结果『好坏』的基本原则是？
- **正确答案**: `high_intra_low_inter`（簇内相似度高，簇间相似度低）
- **干扰项**: `low_intra_high_inter`（簇内相似度低，簇间相似度高）、`equal_size`（所有簇的大小相同）、`more_clusters`（簇的数量越多越好）
- **explanation 要点**: 聚类的『好坏』没有绝对标准，基本原则是簇内相似度高且簇间相似度低。
- **依据页码**: p.42
- **审核结论**: approve

## 18. verify_statistical_ml_clustering_applications_sc_v1
- **concept_id**: `statistical_ml__clustering_applications`
- **题型**: single_choice（single_choice_v1）
- **题干**: 下列哪项是 lec8 课件中提到的聚类应用？
- **正确答案**: `text_clustering`（将大量论文文本聚类到不同类别）
- **干扰项**: `sorting`（对数组进行排序）、`encryption`（对数据进行加密）、`compilation`（编译程序代码）
- **explanation 要点**: 课件提到文本分类（将 200 多万篇论文聚类到 29000 个类别）和色彩压缩，都是聚类的典型应用。
- **依据页码**: p.47
- **审核结论**: approve
