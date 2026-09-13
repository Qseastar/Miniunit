# Statistical ML 模块 — 自由问答（QA）实测记录

> 本文记录 `statistical_ml` 模块自由问答链路的实测过程与结论。**不包含任何 API 密钥。**
> 密钥仅通过当前 shell 会话的环境变量 `DEEPSEEK_API_KEY` 注入，未写入任何文件，
> 未出现在日志、SQLite、`.env` 或任何被 Git 追踪的文件中。

## 测试环境

- 仓库：`C:\Users\92847\statistical_ml_workspace`（独立仓库 `Qseastar/Miniunit`）
- 应用：Streamlit，`127.0.0.1:8501`，后台运行，健康检查返回 HTTP 200
- 适配器：`DeepSeekAdapter.from_env()`（`DEEPSEEK_MODEL` 未显式设置，使用默认 `deepseek-v4-flash`）
- QA 服务：`build_question_answer_service(root, adapter, module_id="statistical_ml")`

## 启动命令（本会话）

```bash
DEEPSEEK_API_KEY="<会话内注入>" PYTHONPATH=src python -m streamlit run app.py \
  --server.headless true --server.address 127.0.0.1 --server.port 8501
```

应用在首次问答时通过 `DeepSeekAdapter.from_env()` 从环境变量读取密钥，无需在启动时
显式校验；密钥不会出现在应用日志中。

## 测试问题

> 什么是监督学习和无监督学习的区别？

## 实测结果

| 检查项 | 结果 |
| --- | --- |
| QA 是否返回回答 | 是，`status="answered"` |
| 回答是否围绕 lec8 内容 | 是（正确区分「训练样本是否带标注」这一核心区别） |
| 引用的 chunk | `statistical_ml_supervised_learning`、`statistical_ml_unsupervised_learning`（另有 `statistical_ml_knn_lazy_learning` 进入检索候选） |
| citation 的 source_file | 全部为 `ai_lec8_statistical_learning.pdf` |
| citation 页码 | 第 3 页（监督学习）、第 40 页（无监督学习）、第 5 页（kNN）——页码合理 |
| 是否引用 Search 模块课件 | 否（无 `search` 相关 source_file） |

回答正文（节选）：

> 监督学习与无监督学习的核心区别在于训练样本是否带有标注。监督学习的训练样本均有
> 对应的标注，模型从带标注样本中学习输入到输出的映射。无监督学习的训练样本均没有
> 标注，模型需要自行发现数据的内在结构。

## 结论

- QA 链路对 `statistical_ml` 模块正常工作，回答基于本模块的 `ai_lec8_statistical_learning.pdf` chunk；
- citation 来源与页码均正确指向 lec8，未发生跨模块引用（未引用 Search 课件）。
- 密钥仅在会话内通过环境变量使用，未写入任何文件；测试后未清理任何残留密钥文件（本就不存在）。
