# IntroAI Tutor — Search Algorithms Summer 2026

**P5c — Repository Reproducibility & Engineering Integrity Audit**

## Release scope

这是当前 Search Algorithms v1 的可冻结暑期技术快照。它把课程材料、受校验引用、
人工审核的确定性验证题、匿名本地学习记录和掌握图谱组合成一个可复现的研究运行时。
本页是 release snapshot，不替代历史设计文档，也不以任何下游展示活动定义项目路线。

## Product capabilities

- 课程自由问答：问题理解、轻量本地检索和受课件约束的回答；
- 回答展示已校验的课件来源，并可在配置本地 PDF 时按页预览；
- 26 个 concept registry 中，21/26 个 concept 具有 direct primary formal coverage，共 28 个 human-reviewed production diagnostic templates；
- 受控验证题完成后才写入 learner-state evidence；
- SQLite 匿名 learner profile、重复正式证据保护和 Search Algorithms mastery map；
- 可选的六人内部 Pilot 访问门及 Cloudflare Quick Tunnel 运维工具。

## Architecture boundaries

Python 负责 schema、白名单、确定性 scorer、evidence gate、mastery、recommendation、
learner state 和安全降级。DeepSeek 只用于可选的自由问答理解/生成；没有 API key 时，
确定性诊断、验证题和图谱仍可运行。LLM 不直接写 mastery、创建 concept ID 或选择证据。

## Course grounding

课程 chunk、source manifest、source role 和 1-based physical page refs 是回答与验证题的
边界。课程 PDF 留在本地，不进入 Git。`INTROAI_COURSE_MATERIALS_DIR` 是可选运行时根目录；
未配置、文件缺失或 `pdftoppm` 不可用时，citation 文本仍可用，页预览只安全显示不可用提示。

## Reviewed diagnostic coverage

当前实际清单（由 `tools/verification_benchmark.py` 重新生成）：

- production：28；
- active candidates：0；
- blocked slots：1（`verify_ucs_frontier_update_v1`）；
- concept registry：26；
- direct primary formal coverage：21/26；
- SQLite schema：3。

28 个模板是窄能力的 evidence opportunities，不是 28 个能力的完整掌握证明，也不是学习
效果研究。P5b 的 8 个 owner-approved 模板已在 production 可见，candidate staging 为空。

## Learner-state semantics

只有完成 reviewed verification 且通过 evidence gate 的结果才能形成正式 observation。
开放式 QA、形成性反馈、查看图谱和 citation preview 不修改 mastery。提示、scaffold、reveal
和 practice-only repeat 的 assistance provenance 会保留在受控流程中；重复 exposure 不会
制造重复的 formal evidence。

## Citation verification boundary

预览是服务端单页渲染，不是 PDF 文件服务器或公开 PDF URL。source file、source role、路径
containment、symlink 和 physical page bounds 每次都校验；预览临时文件不写入 learner state。

## Internal pilot

P4e/P4d 的六人 formative internal usability pilot 用于观察反馈清晰度、导航自然度、学习
记录信任和图谱帮助性；它不是 efficacy study，也不证明学习效果。Remote Pilot 默认关闭，
只是可选的短期内测工具，不是核心研究运行时依赖。

## Post-pilot improvements

已合并的收尾包括 QA/diagnostic handoff、mastery map 导航、citation page preview、重复
证据边界和 P5b reviewed coverage expansion。本 release 不把这些历史阶段倒写成初始原型能力。

## Quality assurance

发布前运行：

```bash
PYTHONPATH=src python tools/release_preflight.py --strict
bash scripts/quality_gate.sh strict
PYTHONPATH=src python -m pytest -q
```

preflight 和 quality gate 都是 offline、network-disabled、fail-closed 检查；没有 provider
请求，也不会读取 `.env` 文件。

## Runtime requirements

- Python 3.11+；
- `python -m pip install -r requirements.txt`（当前运行依赖只有 Streamlit）；
- 本地测试另需 `python -m pip install pytest`；CI 会在测试前显式安装它；
- `PYTHONPATH=src` 启动方式；
- `DEEPSEEK_API_KEY` 仅在需要自由问答时配置；
- Poppler `pdftoppm` 仅是可选 citation-preview 系统依赖；
- `cloudflared` 仅是可选 Remote Pilot 依赖；
- 默认 learner DB：`~/.introai_tutor/learner_state.sqlite3`，可用 `INTROAI_STATE_DB` 指定。

## Reproducibility readiness

研究成员可复制 `.env.example` 为 `.env`，只导出实际需要的值；应用不会自动执行该文件。
运行 `tools/release_preflight.py` 可以在不联网、不写 learner DB 的情况下检查 registry、
启动组合根、SQLite schema、可选材料和 Remote Pilot 边界。常规应用优先使用 localhost；
Remote Pilot 是独立的可选内测工具，不是核心运行时依赖。

## Known limitations

- 没有账号系统或云同步；learner profile 是本机匿名 UUID；
- provider、课程材料和 Quick Tunnel 都可能暂时不可用；
- 21/26 是 formal primary evidence coverage，不是 21 个 concept 已掌握；
- remaining uncovered concepts 和 UCS frontier-update blocked slot 仍需未来人工课程审核；
- 内部 Pilot 样本小，不能推出 learning effectiveness。

## Explicitly deferred work

本 release 不新增 concept、diagnostic template、scorer、mastery/recommendation 规则、LLM
provider、retrieval/agent/vector database、PDF reader、UI 页面或复杂 release system。未覆盖
concept、UCS lower-cost frontier update evidence、账号/云同步和更长期的 remote hosting 均列入
后续 backlog。

## Reproduction commands

```bash
cp .env.example .env
# 按需编辑并在当前 shell export 配置（不要把真实 secret 提交到 Git）
PYTHONPATH=src python tools/release_preflight.py --strict
PYTHONPATH=src python -m streamlit run app.py
```
