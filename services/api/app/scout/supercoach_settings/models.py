"""Strict-ish Pydantic model for SuperCoach /settings response.

The settings response has ~100 deeply-nested fields. We don't depend on
individual leaves; we just want to know the four top-level groups are
there. `extra="forbid"` at the top guards against new sibling sections;
inner fields are opaque dicts.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class SuperCoachSettings(BaseModel):
    """Top-level envelope of the SC /settings response."""

    model_config = ConfigDict(extra="forbid")

    competition: dict[str, Any]
    content: dict[str, Any]
    game: dict[str, Any]
    system: dict[str, Any]
