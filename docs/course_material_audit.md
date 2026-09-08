# Search Algorithms Course Material Audit

## Material provenance and page policy

All source PDFs are pre-extracted project subsets prepared by the project owner
and regenerated with qpdf to preserve their text layer.

The eight PDFs under `local_materials/course_core/` and
`local_materials/prerequisite_support/` are the formal sources for this MVP.
Every current physical page is allowed material. `data/course_chunks.json`
therefore uses the current PDF's 1-based page numbers, not page numbers from a
larger original deck. `original_sources/` and `_edge_print_backup/` are not
used for chunk provenance or page validation.

## Extraction inventory

`pdfinfo` and `pdftotext -layout` were run for every formal source. The text
counts below exclude whitespace, so they indicate recoverable extracted text
rather than PDF file size.

| File | Source role | Pages | Non-whitespace extracted characters | Main readable sections |
|---|---|---:|---:|---|
| `ai_lec2_uninformed_search.pdf` | `course_core` | 66 | 3,663 | Search formulation; tree/graph search; frontier; BFS; DFS; IDDFS; UCS |
| `ai_lec3_informed_search.pdf` | `course_core` | 65 | 3,470 | Heuristics; greedy search; A*; admissibility; consistency; heuristic design |
| `ai_lec4_local_search_and_llm_search.pdf` | `course_core` | 32 | 3,476 | LLM search/test-time scaling; local search; hill climbing; simulated annealing; evolutionary search |
| `ai_lec5_adversarial_search.pdf` | `course_core` | 38 | 3,267 | Game model; minimax; alpha-beta pruning; search order; evaluation functions |
| `ai_lec6_mcts_and_search_summary.pdf` | `course_core` | 44 | 3,978 | Monte Carlo estimation; exploration/exploitation; UCB; MCTS; AlphaGo; search summary |
| `ds_stack_queue_priority_queue.pdf` | `prerequisite_support` | 15 | 2,181 | Stack, recursion call stack, FIFO queue, priority queue |
| `ds_tree_traversal_heap.pdf` | `prerequisite_support` | 13 | 1,615 | Tree terminology, level-order traversal, heap/priority queue |
| `ds_graph_traversal_shortest_path.pdf` | `prerequisite_support` | 26 | 4,674 | Graph basics, visited, DFS/BFS traversal, Dijkstra shortest paths |

All eight formal sources produced recoverable text. No OCR was used.

## Chunking decisions

The chunk file contains concise, source-faithful summaries rather than copied
slide text. Course-core chunks cover the whole Search Algorithms unit, while
the three data-structure PDFs remain `prerequisite_support` only. Their chunks
explicitly say which AI-search concept they help explain and do not replace AI
course definitions. In particular, the Dijkstra support chunk says it is useful
for comparing cumulative-cost selection with UCS, not that the two algorithms
are identical.

The older extraction-failure placeholder IDs were removed:

- `lec4_image_only_material`
- `lec5_image_only_material`
- `lec6_image_only_material`
- `support_stack_for_dfs`
- `support_queue_for_bfs`
- `support_tree_for_search_tree`
- `support_graph_for_search`

They were replaced with page-specific factual chunks from the regenerated
sources. `codex_draft` means that the extracted text sufficiently supports the
summary, not that it has received final instructor approval.

## Intentionally skipped or de-emphasized pages

Chunks are organized by concept rather than a fixed page cadence. The following
pages add no independent retrieval concept, or are duplicate/interactive
material:

| File | Pages | Reason |
|---|---|---|
| Lec2 | 1–5, 19, 30, 36, 50–52, 59, 65–66 | introductory examples, agendas, video placeholders, section dividers, or closing material already represented elsewhere |
| Lec3 | 1, 3, 6, 15, 42–47, 51, 58 | recall/agenda slides or video placeholders |
| Lec4 | 1–2, 31 | recall/title slides or an illustration-only transition slide; page 32 is represented as part of the unit's existing coverage rather than duplicated |
| Lec5 | 1–3, 7–8, 32–34 | title/duplicate outlines or quiz slides; repeated pruning diagrams are summarized only where they introduce a rule |
| Lec6 | 1–5, 21–31, 36 | repeated preceding-lecture material, MCTS trace diagrams, or illustration-only material; conceptual MCTS stages are retained from page 20 |
| Support PDFs | none wholesale | all pages are used only when they provide a direct implementation or terminology bridge to an AI-search concept |

## Project-owner visual verification

The project owner visually checked Lec6 pages 19, 32, and 33 against the
rendered PDF:

- Page 19 confirms the UCB structure
  `Q_k + C * sqrt(ln T / T_k)`. The summary now describes the second term as
  an exploration bonus or uncertainty-sensitive exploration term, not as a
  generic statistical "bias." The page supports the interpretation
  "empirical mean plus exploration bonus," so
  `lec6_upper_confidence_bound` is `human_verified`.
- Page 32 confirms one MCTS iteration through selection, expansion and
  simulation, and backpropagation. The displayed path statistics change after
  the simulation. The summary does not impose a fixed meaning on every
  numerator, denominator, or player perspective, and
  `lec6_mcts_selection_simulation_backpropagation` is `human_verified`.
- Page 33 opens normally and contains an alternating-player game tree with
  animation- or annotation-like numeric overlays. It supports only the general
  fact that node statistics are updated after simulations. The exact
  numerator/denominator meaning, player perspective, and interpretation of
  overwritten values still require instructor context or the original slide
  animation.

The former two-page chunk `lec6_mcts_adversarial_variant` was replaced by
page-specific chunks so that page 32's verified iteration and page 33's
remaining ambiguity have different review states.

## Remaining visual-review item

One chunk remains `needs_human_review`:

| Chunk ID | File and pages | Review reason |
|---|---|---|
| `lec6_adversarial_mcts_statistics` | `ai_lec6_mcts_and_search_summary.pdf`, p. 33 | The page is readable, but its numeric overlays do not establish the exact statistic definition or player perspective. |

The chunk explicitly avoids Minimax-style value negation, a mandatory
`1-value` transformation, a fixed win-rate flip, or any other update rule not
stated on the page.

## Knowledge-graph verification

Existing concept IDs were retained. New IDs were added only for concepts
explicitly named in the regenerated core lectures: hill climbing, simulated
annealing, evolutionary search, minimax, alpha-beta pruning, game-state
evaluation, Monte Carlo search, exploration/exploitation, and UCB. The
existing local-search, LLM-search, adversarial-search, and MCTS IDs were
rechecked against their now-readable sources. Data-structure terms such as
stack, queue, heap, graph, visited, and Dijkstra remain support tags rather
than being promoted into the mastery graph.

No diagnostic questions were added. The BFS → equal-step-cost condition → UCS
diagnostic case remains the only deep diagnostic reference case.

## Project-owner final spot-check checklist

- Obtain instructor context or the original slide animation for Lec6 page 33
  before assigning fixed meanings to its fractions or player perspectives.
- Review Chinese/English terms for frontier, explored/visited state, path cost,
  and the MAX/MIN game-tree roles.
- Confirm the instructional framing of the LLM-search examples and cited game
  applications before presenting them as current-course extensions.
- Confirm that prerequisite-support chunks remain auxiliary and that no UI or
  answer generator presents Dijkstra as identical to UCS.
- Sample page boundaries for each lecture after any future PDF replacement;
  `validate_course_chunks(..., verify_local_sources=True)` checks the current
  formal-source page limits without being confused by backups or originals.
