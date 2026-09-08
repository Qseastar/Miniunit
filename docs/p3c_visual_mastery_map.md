# P3c Visual Mastery Map and Student-Facing Concept Polish

## 双视图与数据边界

知识掌握图谱保留两种互补视图：默认的“分层浏览”让首次进入的学生先看到可读、可操作的学习路径；“关系图”帮助学生理解课程整体先修结构。两者都只读取现有 `data/knowledge_points.json` 中的 concept 与 prerequisite，以及 `data/search_algorithms_mastery_map_layout.json` 中固定 layer/order。关系箭头始终表示“直接先修 → 后续知识”，不把 recommendation 或视觉排序伪装成先修关系。

全局关系图使用 Streamlit 原生 `st.graphviz_chart` 的确定性 raw DOT。节点、边、rank 和状态均由纯 Python view model 构建；没有外部组件、CDN、JavaScript、图片 URL 或可点击图形 hack。Graphviz 渲染不可用时，页面显示说明并保留完整的分层浏览与详情操作。

## 状态、覆盖与聚焦关系

图中节点保留文字状态，避免只依赖颜色：尚未追踪、建议复习、初步掌握、掌握较稳或状态暂不可用。显式 `0.0` 仍是“建议复习”，与 mastery mapping 中缺失的“尚未追踪”不同。当前推荐与当前查看分别有文字和边框标记，可以同时出现。

“可审核诊断”仅指 human-verified production template 的 primary concept 覆盖；supporting concept、candidate 与 blocked capability 均不计入。顶部仅显示知识点、已有审核证据与状态数量，不显示伪造的课程完成率或考试成绩。

选中节点时，页面用稳定的三栏面板展示其直接先修、当前节点和直接后续节点。局部关系来自同一 prerequisite DAG；无关关系不会被推测。分层浏览提供全部、当前推荐、已追踪、可审核诊断和建议复习筛选，筛选只影响展示。

## 中文学生端文案与详情

`data/search_algorithms_concept_copy_zh.json` 为全部 26 个 registry concept 提供独立的中文简要说明。其 schema、完整性、长度、占位文本和实现标识均由离线校验；该文件不改变 registry 中的 concept ID、先修关系或课程语义。若材料不足，文案只保守转述现有 registry description。

详情依次显示中英文名称、状态、当前掌握度、中文说明、直接先修、直接后续、reviewed coverage 与现有学习证据摘要。掌握度明确是审核诊断证据形成的估计，不是考试成绩；课程问答和浏览不会直接提高它。无覆盖时显示“当前暂无人工审核诊断题”。QA 预填、reviewed diagnostic 入口、completion → map 以及 overview/detail 的一次性滚动继续复用 P3b 行为。每次明确选择节点都会生成新的瞬态 action revision/event ID；该 ID 会进入滚动组件的安全载荷，使同一固定详情锚点在后续选择（包括再次选择同一节点）时重新执行一次滚动。该请求既不持久化，也不会在刷新、重启或切换 profile 后恢复。

## 可访问性、小屏与人工验收

关系图有简短文字说明；无法使用关系图时可切换分层浏览。卡片在窄窗口中由 Streamlit 列布局自然退化，标题启用换行，关系图在图表容器中渲染而不以固定像素滚动页面。状态同时提供文字、颜色、推荐与选中标签。P3b 的 fixed-anchor、一回消费、`prefers-reduced-motion` 和不抢焦点行为保持不变。

人工复测：

1. 新 profile 打开图谱，确认默认分层浏览显示学生友好阶段名称、紧凑卡片和“尚未追踪”状态。
2. 切换关系图，确认显示 26 个中文节点、先修箭头和推荐/当前查看边框；再切回分层浏览检查五种筛选与空结果提示。
3. 选择 IDDFS，确认中文说明、DFS/BFS 直接先修和真实后续关系；QA 只预填，审核诊断仍走 reviewed flow。
4. 完成一个验证题后回到图谱，确认节点状态和顶部计数同步；刷新与服务重启后既有持久化状态仍恢复。
5. 缩窄窗口或在 Graphviz 不可用环境中确认可切换到分层浏览完成全部操作。

## 当前限制

关系图是只读总览，不支持通过图形节点直接点击选题；稳定的分层按钮承担交互。自动测试验证 DOT、view model、anchor 和 fallback 条件，真实 SVG 视觉与物理布局仍需浏览器人工验收。
