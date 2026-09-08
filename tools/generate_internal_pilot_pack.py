#!/usr/bin/env python3
"""Generate a privacy-minimal, offline six-person pilot session pack."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from introai_tutor.pilot_feedback import FEEDBACK_SCHEMA_VERSION  # noqa: E402
from introai_tutor.pilot_focus_roles import (  # noqa: E402
    PILOT_EXECUTION_RELEASE,
    load_focus_roles,
    ordered_focus_roles,
)
from introai_tutor.pilot_tasks import load_pilot_tasks, ordered_tasks  # noqa: E402
from introai_tutor.knowledge import load_knowledge_points  # noqa: E402
from tools.verification_benchmark import build_manifest  # noqa: E402


OUTPUT_FILES = (
    "pilot_release_manifest.json",
    "tester_focus_assignments.csv",
    "tester_instructions.md",
    "facilitator_checklist.md",
    "issue_triage_template.csv",
    "debrief_notes_template.md",
    "feedback_inbox_README.md",
    "remote_tester_message_template.md",
    "remote_facilitator_launch_checklist.md",
)


class PilotPackError(ValueError):
    """Raised when a session pack cannot be generated safely."""


def generate_pack(
    *,
    root: str | Path = ROOT,
    output_dir: str | Path,
    generated_at_utc: str | None = None,
    overwrite: bool = False,
) -> list[Path]:
    root = Path(root).resolve()
    destination = Path(output_dir)
    if destination.exists() and not destination.is_dir():
        raise PilotPackError("输出路径不是目录。")
    if destination.exists() and any(destination.iterdir()) and not overwrite:
        raise PilotPackError("输出目录已有文件；如需覆盖请显式使用 --overwrite。")

    tasks_data = load_pilot_tasks(root / "data" / "pilot_search_algorithms_tasks.json")
    roles_data = load_focus_roles(
        root / "data" / "internal_pilot_focus_roles.json", tasks_data=tasks_data
    )
    tasks = ordered_tasks(tasks_data)
    roles = ordered_focus_roles(roles_data, tasks_data=tasks_data)
    manifest = build_manifest(root=root)
    knowledge = load_knowledge_points(root / "data" / "knowledge_points.json")
    timestamp = generated_at_utc or _utc_now()
    _validate_timestamp(timestamp)
    pack = {
        "pilot_release_manifest.json": _manifest(
            root=root,
            generated_at_utc=timestamp,
            production_count=len(manifest["production"]),
            concept_count=len(knowledge["knowledge_points"]),
            pilot_task_count=len(tasks),
            focus_role_count=len(roles),
        ),
        "tester_focus_assignments.csv": _assignments(roles),
        "tester_instructions.md": _tester_instructions(),
        "facilitator_checklist.md": _facilitator_checklist(),
        "issue_triage_template.csv": _triage_template(),
        "debrief_notes_template.md": _debrief_template(),
        "feedback_inbox_README.md": _inbox_readme(),
        "remote_tester_message_template.md": _remote_tester_message(),
        "remote_facilitator_launch_checklist.md": _remote_facilitator_checklist(),
    }
    destination.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for name in OUTPUT_FILES:
        path = destination / name
        content = pack[name]
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8", newline="")
        paths.append(path)
    return paths


def _manifest(*, root: Path, generated_at_utc: str, production_count: int, concept_count: int, pilot_task_count: int, focus_role_count: int) -> str:
    payload = {
        "schema_version": 1,
        "pilot_release": PILOT_EXECUTION_RELEASE,
        "generated_at_utc": generated_at_utc,
        "git_commit_short_sha": _git_sha(root),
        "production_template_count": production_count,
        "concept_count": concept_count,
        "pilot_task_count": pilot_task_count,
        "focus_role_count": focus_role_count,
        "expected_feedback_schema_version": FEEDBACK_SCHEMA_VERSION,
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _assignments(roles: list[dict[str, Any]]) -> str:
    fields = ["role_id", "title_zh", "focus", "required_core_task_ids", "observation_prompts", "expected_duration_minutes"]
    rows: list[dict[str, Any]] = []
    for role in roles:
        rows.append(
            {
                "role_id": role["role_id"],
                "title_zh": role["title_zh"],
                "focus": role["focus"],
                "required_core_task_ids": "；".join(role["required_core_task_ids"]),
                "observation_prompts": "；".join(role["observation_prompts"]),
                "expected_duration_minutes": role["expected_duration_minutes"],
            }
        )
    from io import StringIO

    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def _triage_template() -> str:
    fields = [
        "issue_id", "severity", "tester_focus_role", "anonymous_tester_code",
        "affected_area", "reproduction_steps", "expected_behavior", "actual_behavior",
        "reproducibility", "screenshot_available", "blocks_pilot", "owner", "status",
        "resolution_note",
    ]
    from io import StringIO

    output = StringIO()
    csv.writer(output, lineterminator="\n").writerow(fields)
    return output.getvalue()


def _tester_instructions() -> str:
    return """# 六人组内内测操作说明

## 规则

每位测试者都要完成 P4a 的六项核心任务，再额外关注分工表中的重点方向。
角色只用于分工；页面生成的 `G-XXXXXX` 只是匿名反馈文件编号，两者不是同一概念。
不要填写姓名、联系方式、完整课程问题或答案，也不要填写 API Key、`.env` 或本地数据库内容。

## 操作顺序

1. 按页面顺序完成六项任务，记录可复现的困惑或错误。
2. 在内测反馈页填写八项 1–5 量表和可选开放反馈。
3. 生成并下载反馈 JSON；仅通过负责人指定的组内渠道发送。
4. 遇到 P0/P1 问题时先保留复现步骤，不继续尝试破坏性操作。

反馈文件只由测试者主动下载，不会自动上传或写入学习档案。
"""


def _facilitator_checklist() -> str:
    return """# 负责人执行清单

- [ ] 运行离线 preflight，确认关键项没有 FAIL。
- [ ] 为六名测试者分配 role_a–role_f；所有人完成六项核心任务。
- [ ] 使用独立的本地学习档案或临时 SQLite 路径启动 Pilot mode。
- [ ] 收回下载的反馈 JSON，放入 `pilot_feedback_inbox/`。
- [ ] 使用现有汇总工具生成 JSON、CSV、Markdown，不把输出放回收件箱。
- [ ] 按 P0/P1/P2/P3 分级并去重问题。
- [ ] 在 8 月 10 日组会上确认阻塞项、频率和下一步负责人。

端口占用时不要自动结束未知进程；由负责人确认占用者后再决定。
"""


def _debrief_template() -> str:
    return """# 8 月 10 日组会内测总结

日期：
参与人数：
有效反馈数：

## 关键结论

- 最有帮助的流程：
- 最常见的困惑：
- 是否发现 P0/P1：

## 问题决策

P0 立即停止内测；P1 在组会前修复；P2 按频率和影响排序；P3 进入 backlog。

## 下一步

- 必须修复：
- 可以优化：
- 暂不处理：
"""


def _inbox_readme() -> str:
    return """# 反馈收件箱说明

请只把测试者主动下载的 JSON 放入此目录，再运行：

```bash
PYTHONPATH=src python tools/summarize_pilot_feedback.py \
  pilot_feedback_inbox --output-dir pilot_feedback_summary
```

真实反馈和汇总产物已由 `.gitignore` 排除，不应提交 Git。汇总会报告有效样本、拒绝文件、重复文件、量表分布和开放反馈；不要把开放反馈发送给 LLM。
"""


def _remote_tester_message() -> str:
    return """# IntroAI Tutor 远程内测邀请模板

测试地址：<PILOT_HTTPS_URL>

访问码：<PILOT_ACCESS_CODE>

你的重点角色：<FOCUS_ROLE>

反馈回传渠道：<FEEDBACK_RETURN_CHANNEL>

截止时间：<DEADLINE>

## 请按以下方式参与

1. 只使用负责人私发的 HTTPS 地址，并在页面输入单独收到的访问码。
2. 不转发 URL、访问码或自己的 learner URL；不要多人共用同一个浏览器会话。
3. 完成全部六项核心任务，并额外关注你的重点角色。
4. 内测结束时生成并下载匿名 feedback JSON，通过指定组内渠道回传。
5. 不在反馈中填写姓名、学号、API Key、私人信息、完整问题或完整回答。
6. 页面短暂断开时先等待，再刷新；远程地址在内测结束后会失效。
"""


def _remote_facilitator_checklist() -> str:
    return """# P4d 远程内测负责人启动清单

- [ ] 同步并确认最新 main，检查工作区。
- [ ] 通过安全环境配置设置访问码；不要把访问码放入 URL 或命令参数。
- [ ] 运行远程预检。
- [ ] 启动 remote launcher。
- [ ] 从 cloudflared 终端输出复制 HTTPS URL。
- [ ] 通过不同私密渠道分别发送 URL 与访问码。
- [ ] 记录六名测试者的 focus role 分工。
- [ ] 保持启动终端运行。
- [ ] 出现 P0/P1 时停止测试。
- [ ] 收集六份下载的 feedback JSON。
- [ ] 运行离线反馈汇总。
- [ ] 使用 Ctrl+C 关闭隧道，并确认本轮 Streamlit 子进程退出。
- [ ] 不提交反馈、URL、日志、SQLite 或运行目录。
- [ ] 内测结束后轮换或删除旧访问码。
"""


def _git_sha(root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = result.stdout.strip()
    return value or None


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _validate_timestamp(value: str) -> None:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise PilotPackError("generated_at_utc 必须是 UTC 时间戳。")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise PilotPackError("generated_at_utc 必须是 UTC 时间戳。") from None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成离线六人内测 Session Pack。")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output-dir", type=Path, default=Path("pilot_session_pack"))
    parser.add_argument("--generated-at-utc")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    try:
        paths = generate_pack(
            root=args.root,
            output_dir=args.output_dir,
            generated_at_utc=args.generated_at_utc,
            overwrite=args.overwrite,
        )
    except (OSError, ValueError) as error:
        print(f"生成失败：{error}", file=sys.stderr)
        return 2
    for path in paths:
        print(path.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
