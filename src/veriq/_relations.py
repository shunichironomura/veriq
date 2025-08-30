from __future__ import annotations

import logging

from scoped_context import NoContextError

from ._models import Requirement

logger = logging.getLogger(__name__)


def depends(requirement: Requirement) -> None:
    try:
        parent = Requirement.current()
    except NoContextError:
        logger.exception("No active requirement found.")
        raise

    parent.depends_on.append(requirement)
