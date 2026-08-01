"""Which sectors this study engine knows, and where their vocabulary lives.

The engine was written for one sector and the sector was written into the engine.
`verification/rules.py` held credit-reporting term lists as module constants and
`detect_mechanism` named credit-reporting mechanisms in an if-ladder; `findings/engine.py`
held their definitions. None of that is engine logic -- the matching, the qualification
rule and the finding assembly are all sector-neutral -- but a second sector could not be
added without editing them.

This registry is the same seam the review board profiles took: the engine keeps the
logic, the pack supplies the words. `get()` refuses an unknown sector rather than
defaulting, because a run that asked for property management and silently received credit
reporting would classify with the wrong vocabulary and report nothing unusual.
"""

from __future__ import annotations

from sectors.models import MechanismRule, SectorPack, TermGroup
from sectors.credit_reporting import CREDIT_REPORTING

SECTORS: dict[str, SectorPack] = {CREDIT_REPORTING.sector_id: CREDIT_REPORTING}

DEFAULT_SECTOR_ID = CREDIT_REPORTING.sector_id


def get(sector_id: str | None = None) -> SectorPack:
    """Resolve a registered sector pack, defaulting to credit reporting."""

    resolved = sector_id or DEFAULT_SECTOR_ID
    try:
        return SECTORS[resolved]
    except KeyError:
        raise LookupError(
            f"No sector pack registered as {resolved!r}. Registered: {', '.join(sorted(SECTORS))}"
        ) from None


__all__ = ["SECTORS", "DEFAULT_SECTOR_ID", "MechanismRule", "SectorPack", "TermGroup", "get"]
