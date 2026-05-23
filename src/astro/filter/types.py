"""Filter type aliases."""

from __future__ import annotations

from collections.abc import Callable

import polars as pl

FilterFn = Callable[[pl.DataFrame], pl.DataFrame]
