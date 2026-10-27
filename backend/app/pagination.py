"""Bounds for every list endpoint.

A list with no bound returns the whole table one day. ``limit`` defaults to 50 and may not exceed
100; ``offset`` may not be negative; FastAPI answers 422 to anything else before the handler runs.
The numbers are the spec's (§ Decisions, List bounds). Declare a parameter as

    limit: LimitQuery = DEFAULT_LIMIT, offset: OffsetQuery = 0
"""

from typing import Annotated

from fastapi import Query

DEFAULT_LIMIT = 50
MAX_LIMIT = 100

LimitQuery = Annotated[int, Query(ge=1, le=MAX_LIMIT)]
OffsetQuery = Annotated[int, Query(ge=0)]
