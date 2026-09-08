#!/usr/bin/env bash
# Offline verification quality gate. Run from any directory.
set -euo pipefail

mode="${1:-quick}"
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
export PYTHONPATH="src${PYTHONPATH:+:$PYTHONPATH}"

stage() { printf '\n== %s ==\n' "$1"; }

stage "compile smoke"
python -m py_compile tools/verification_benchmark.py tools/course_material_manifest.py tools/verify_local_course_materials.py tools/verification_quality_gate.py tools/release_preflight.py tools/generate_template_review_packet.py tools/generate_verification_reports.py
stage "offline quality gate"
python tools/verification_quality_gate.py --strict --json-report /tmp/introai_verification_quality.json --markdown-report /tmp/introai_verification_quality.md
stage "acceptance and release hardening"
python -m pytest tests/test_template_acceptance.py tests/test_p2f_candidate_templates.py tests/test_p2g_quality_gate.py tests/test_release_preflight.py -q
stage "smoke"
python -m pytest -m smoke -q

case "$mode" in
  quick) ;;
  strict|ci)
    stage "full suite"
    python -m pytest -q
    stage "collection inventory"
    python -m pytest --collect-only -q
    ;;
  *)
    echo "usage: bash scripts/quality_gate.sh [quick|strict|ci]" >&2
    exit 2
    ;;
esac
stage "diff check"
git diff --check
