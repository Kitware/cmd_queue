"""Private rendering helpers shared by queue classes."""
from __future__ import annotations

from typing import Optional

import ubelt as ub


def coerce_style(
    style: str = 'auto',
    with_rich: Optional[bool] = None,
    colors: bool | int = True,
) -> str:
    """Normalize legacy style arguments without changing public behavior."""

    if with_rich is not None:
        ub.schedule_deprecation(
            'cmd_queue',
            'with_rich',
            'arg',
            migration='use style="rich" instead',
        )
        if with_rich:
            style = 'rich'
    if style == 'auto':
        style = 'colors' if colors else 'plain'
    return style
