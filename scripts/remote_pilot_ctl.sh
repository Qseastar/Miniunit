#!/usr/bin/env bash
# Single operator entrypoint for the owner-managed P4d remote Pilot.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
export PYTHONPATH="src${PYTHONPATH:+:$PYTHONPATH}"
exec python tools/remote_pilot_control.py "$@"
