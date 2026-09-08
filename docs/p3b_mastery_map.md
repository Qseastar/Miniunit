# P3b Search Algorithms Mastery Map v1

## 目标与数据边界

知识掌握图谱是现有 learner state 的展示与导航层，不是新的证据、推荐或课程知识系统。概念名称、说明、模块与直接先修关系均来自 `data/knowledge_points.json`。`data/search_algorithms_mastery_map_layout.json` 只保存固定的 `concept_id`、显示层和同层顺序；它不重复标题、说明、掌握度、诊断覆盖或先修语义。

布局经过完整性、唯一性、先修端点和 DAG 检查。分层方便学生阅读，且每条已登记的先修关系都从较早层指向较后层；图谱不把纯视觉排布额外宣称为新的教学先修关系。

## 展示状态与可访问性

掌握度原始值和 P5B 更新公式不变。图谱仅使用以下 display-only 区间：

- mastery mapping 中缺失：`尚未追踪`；
- `0.00 <= score < 0.60`：`建议复习`；
- `0.60 <= score < 0.80`：`初步掌握`；
- `0.80 <= score <= 1.00`：`掌握较稳`。

这些阈值不参与 evidence gate、正式评分或 recommendation。非法、非有限或范围外的显示值会安全降级为“状态暂不可用”，不会被悄悄归一化。

卡片使用集中定义的灰色到绿色 CSS token，但每个节点始终同时显示中文名称、状态文字、已追踪时的数值与诊断覆盖文字。节点通过明确的“查看此知识点”按钮选择，避免依赖颜色或脆弱的整卡 JavaScript 点击。

## Reviewed diagnostic coverage

覆盖从生产 `data/diagnostic_templates.json` 动态计算。只有 `review_status="human_verified"`、`purpose="mastery_verification"`，且 `concept_ids` 第一个元素为该节点的模板，才计为“可审核诊断”。supporting concept、候选题和 blocked capability 不计入覆盖。

当前 blocked UCS frontier-update slot 不是 production template，因此不会增加 UCS 的覆盖数量或生成入口；UCS 节点只显示实际的 production `verify_ucs_min_g_choice_v1`。图谱不会把“有一题可审核”表述为“该概念已被完整覆盖”。

## 节点详情与入口

详情显示权威中英文名称、系统估计掌握度、直接先修、production 覆盖、概念说明和可从当前 learner state 可靠推导的审核活动摘要。现有恢复后的 learner state 不携带逐概念更新时间或可展示的 assistance 分类统计，因此界面明确显示“暂无记录”，不伪造时间或独立/提示/答案后次数。

“围绕此知识点提问”只根据可信中文标题预填问题并一次性切回课程问答，绝不自动提交、调用 API、更新 mastery 或写入 persistence。“开始审核诊断（N题）”复用已有 reviewed-template handoff 和 session 创建，只在用户主动点击后创建正式验证会话；没有 primary coverage 的节点不显示该操作。

验证完成后，“查看知识掌握图谱”会在已有状态更新中按稳定 concept ID 选择一个节点，并一次性定位图谱。它不会恢复诊断、额外写入 learner state 或重复 integration。

点击任一节点的“查看此知识点”后，界面会保存新的 transient action revision，并在 rerun 后一次性定位固定 `mastery_map_detail` anchor。该定位使用现有白名单 scroll request、`scrollIntoView` 和 reduced-motion 降级，不依赖页面底部、固定像素、用户文本或随机 DOM class。同一节点的下一次明确点击会生成新的 revision，因此可以再次定位。详情区的“返回知识图谱”保留当前选中节点，并一次性回到固定 `mastery_map_overview` anchor。

验证完成后到图谱的既有行为仍优先展示更新后的节点/图谱概览；不会自动跳过节点而直接定位到底部详情。自动测试验证 anchor、request、revision 和一次性消费顺序，真实物理滚动距离仍由人工浏览器复测。

## 持久化与非目标

图谱读取既有 SQLite-backed learner state，故同一匿名本地 profile 的刷新与服务重启会恢复同样的掌握显示。选中节点是 transient UI state：新 profile 和清空学习记录会移除它，持久化 schema 不变。

本轮不包含动态图数据库、课程关系编辑、算法动画、外部 CDN、远程组件、额外 production templates、临时可评分题或跨设备同步。

## 自动与人工验收

单元测试覆盖布局完整性、先修 DAG、稳定排序、display 阈值和非法值、primary coverage、candidate/supporting/unknown fail-closed、详情安全摘要和预填问题。AppTest 覆盖第三个标签、节点选择、QA 预填、diagnostic 入口及完成后的图谱定位。

人工验收：新 profile 应全部显示“尚未追踪”；选择“迭代加深深度优先搜索”可查看权威详情并进入 QA 或其正式验证题；完成验证后返回图谱应立即反映新 mastery；刷新、重启、创建新 profile 与清空记录应分别恢复、隔离或清空图谱状态。

复测 discoverability：选择 IDDFS 后应直接定位“知识点详情”；从详情返回图谱后应仍保留 IDDFS 选中状态；随后选择 A* 或再次选择 IDDFS 都应再次定位新详情，且不改变 learner state。
