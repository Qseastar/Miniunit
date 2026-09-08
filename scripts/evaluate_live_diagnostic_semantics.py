#!/usr/bin/env python
"""Run a deliberately small, operator-invoked DeepSeek semantic evaluation.

This script is never used by pytest.  It reads only the environment variable
names consumed by ``DeepSeekAdapter.from_env`` and writes its report outside
the repository by default.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from introai_tutor.deepseek_adapter import (  # noqa: E402
    DeepSeekAdapter,
    DeepSeekConfigurationError,
)
from introai_tutor.diagnostic_benchmark import load_diagnostic_scoring_benchmark  # noqa: E402
from introai_tutor.diagnostic_semantics import DiagnosticSemanticAdjudicator  # noqa: E402
from introai_tutor.live_semantic_evaluation import (  # noqa: E402
    LiveSemanticEvaluationError,
    evaluate_live_semantics,
    write_live_semantic_report,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate only the bounded diagnostic semantic adjudicator."
    )
    parser.add_argument(
        "--case-id",
        action="append",
        dest="case_ids",
        help="Evaluate one explicit benchmark case; repeat the option for more cases.",
    )
    parser.add_argument("--limit", type=int, help="Limit selected cases after filtering.")
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="Explicit repeats per selected case (default: 1).",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("/tmp/introai_diagnostic_live_semantic_report.json"),
        help="Local JSON report path (default: /tmp/introai_diagnostic_live_semantic_report.json).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        benchmark = load_diagnostic_scoring_benchmark(
            ROOT / "data" / "diagnostic_scoring_benchmark.json"
        )
        with (ROOT / "data" / "diagnostic_questions.json").open(encoding="utf-8") as handle:
            questions_data = json.load(handle)
        adapter = DeepSeekAdapter.from_env()
        # This evaluation is budget-bounded: one complete_json attempt per
        # assessment, with no transport or response retries hidden inside it.
        adapter.max_retries = 0
        report = evaluate_live_semantics(
            questions_data=questions_data,
            benchmark_data=benchmark,
            semantic_adjudicator=DiagnosticSemanticAdjudicator(adapter=adapter),
            case_ids=args.case_ids,
            limit=args.limit,
            repeat=args.repeat,
        )
        destination = write_live_semantic_report(report, args.report)
    except DeepSeekConfigurationError:
        print("DeepSeek configuration is unavailable; no evaluation request was sent.", file=sys.stderr)
        return 2
    except (LiveSemanticEvaluationError, ValueError, OSError, json.JSONDecodeError) as error:
        # Deliberately do not include adapter internals, request headers, or prompts.
        print(f"Live semantic evaluation setup failed: {type(error).__name__}.", file=sys.stderr)
        return 2

    summary = report["summary"]
    print(
        "Live semantic evaluation complete: "
        f"cases={summary['case_count']}, calls={summary['actual_model_call_count']}, "
        f"semantic_judgment_exact={summary['semantic_judgment_exact_match']}, "
        f"authoritative_outcome={summary['authoritative_outcome_accuracy']}, "
        f"containment={summary['containment_success']}, "
        f"harmful_false_positives={summary['harmful_semantic_false_positive_count']}, "
        f"contained_false_positives={summary['contained_false_positive_count']}, "
        f"report={destination}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
