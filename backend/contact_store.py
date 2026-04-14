"""Store contact support messages in the contact_messages table."""

from __future__ import annotations

import logging

from backend.db import execute

logger = logging.getLogger(__name__)


def save_contact_message(
    name: str,
    email: str,
    message: str,
    user_id: int | None = None,
) -> None:
    """Insert a contact support message. Never raises — failures are logged to stderr."""
    try:
        execute(
            """
            INSERT INTO contact_messages (name, email, message, user_id)
            VALUES (%s, %s, %s, %s)
            """,
            (name, email, message, user_id),
        )
    except Exception as e:
        logger.warning("contact_store: failed to save message from %s: %s", email, e)
