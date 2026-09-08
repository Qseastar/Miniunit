# 课程引用页预览

## Purpose

课程自由问答仍先显示受校验的课件文件名和物理页码。用户主动点击“查看引用课件”后，系统才在对应 citation 的紧邻下方渲染课件原页，形成“回答 → citation → 课件原页”的可核查闭环。

这不是完整 PDF 阅读器，也不会自动打开、下载或公开原始课件。

## Trust model

预览只接受已经由 grounded-answer 服务产生的 citation。`source_role`、`source_file` 和页码必须再次通过课程材料白名单及 manifest 校验；学生输入不能直接成为文件路径。

## Runtime asset contract

课程 PDF 保持本地、未跟踪，不进入 Git。运行时通过目录环境变量提供材料根目录：

```bash
export INTROAI_COURSE_MATERIALS_DIR=/path/to/course/materials
```

目录内使用既有布局：`course_core/` 和 `prerequisite_support/`。程序根据 manifest 批准的文件名和 source role 解析文件，不依赖负责人机器的绝对路径或当前工作目录。

## Security model

- source 必须先通过 `ALLOWED_SOURCE_FILES` 和 `data/course_material_manifest.json`；
- 只接受 PDF basename，拒绝任意文件名、绝对路径、URI 和 traversal；
- `resolve()` 后再次检查路径仍在配置的材料根目录内，symlink escape 直接拒绝；
- 页码是 1-based PDF physical page，并受 manifest `page_count` 限制；
- 服务端使用 Poppler 按需只渲染当前一页，不使用 `shell=True`；
- 不创建独立文件服务器、公开 PDF URL 或全文下载接口；
- 现有 P4c 访问门和 Streamlit 生命周期保持不变。

## Local setup

配置材料目录后重新启动 Streamlit：

```bash
export INTROAI_COURSE_MATERIALS_DIR=/path/to/course/materials
PYTHONPATH=src python -m streamlit run app.py
```

未配置或材料不可用时，课程问答和 citation 文本仍正常，预览只显示安全的“当前无法预览这条课件引用”提示。

## Remote Pilot

Remote Pilot 主机必须拥有同一份经授权的本地材料目录，并在受管进程环境中设置 `INTROAI_COURSE_MATERIALS_DIR`。Quick Tunnel 只转发已授权的 Streamlit 页面，不直接暴露 PDF 文件，也不会生成 PDF URL。`doctor` 会把预览可用性作为非阻塞的 optional readiness 项报告。

## Limitations

- 多页 citation 默认显示 `page_start`，并只允许在该 citation 已校验的 `page_start` 至 `page_end` 范围内以前后页按钮逐页查看；每次操作只渲染当前页，不会预渲染整段范围；
- 同一时间只展开一个 citation 预览。打开操作会以一次性、固定锚点平滑定位到该 citation 下方的预览区域；这不会持久化，也不会在普通 rerun 后重复触发；
- 不提供完整 PDF 阅读、下载、上传或跨课程材料包；
- 预览属于短暂页面状态，不写入 learner state、SQLite、evidence、mastery 或 recommendation；
- Poppler、材料目录或具体 PDF 不可用时，QA 主流程仍可使用，但预览不可用。
