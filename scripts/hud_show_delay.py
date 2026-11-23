"""Centralized hold-to-show delay for the compact ShortcutHUD.

The delay is persisted in milliseconds (``show_delay_ms``) because that is the
unit Qt timers use, while the Settings dialog presents it in seconds.  The
Win-only hold keeps a safety floor: arming the Win discovery proxy too early
would intercept more native Win shortcuts than necessary, so a configured
delay below ``WIN_ONLY_MIN_SHOW_DELAY_MS`` is raised to that floor instead of
being rejected.
"""

from __future__ import annotations

import math

# Persisted settings key: how long a modifier must stay held before the
# passive Quick HUD appears.
SHOW_DELAY_SETTING = "show_delay_ms"
DEFAULT_SHOW_DELAY_MS = 150
MIN_SHOW_DELAY_MS = 0
MAX_SHOW_DELAY_MS = 5000

# The Win discovery proxy may swallow and replay the physical Win key once its
# hold threshold is reached.  Keep at least this long so native Win shortcuts
# are not disturbed by an aggressively short user setting.
WIN_ONLY_MIN_SHOW_DELAY_MS = 300


def normalize_show_delay_ms(
    value: object,
    default: int = DEFAULT_SHOW_DELAY_MS,
) -> int:
    """Return a usable integer millisecond delay.

    Invalid inputs degrade to ``default`` instead of raising, so a corrupted
    settings file can never stop the HUD from appearing.
    """

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    numeric = float(value)
    if not math.isfinite(numeric):
        return default
    return max(MIN_SHOW_DELAY_MS, min(MAX_SHOW_DELAY_MS, int(round(numeric))))


def resolve_show_delay_ms(
    value: object,
    default: int = DEFAULT_SHOW_DELAY_MS,
    *,
    win_only: bool = False,
) -> int:
    """Normalize a configured delay, applying the Win-only safety floor."""

    delay_ms = normalize_show_delay_ms(value, default)
    if win_only:
        return max(delay_ms, WIN_ONLY_MIN_SHOW_DELAY_MS)
    return delay_ms
