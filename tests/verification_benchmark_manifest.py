"""Test-facing access to P2g's single derived verification manifest.

Question content remains in production data plus the pre-existing acceptance
contracts; this module deliberately contains no copied template definitions.
"""

from tools.verification_benchmark import BLOCKED_SLOTS, build_manifest

__all__ = ["BLOCKED_SLOTS", "build_manifest"]
