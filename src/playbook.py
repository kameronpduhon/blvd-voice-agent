import json
import logging
import os

logger = logging.getLogger("agent")


def load_playbook() -> dict:
    """Load compiled playbook from disk."""
    path = os.environ.get(
        "COMPILED_PLAYBOOK_PATH", "playbooks/cajun-hvac.compiled.json"
    )
    logger.info(f"Loading playbook from {path}")
    with open(path) as f:
        return json.load(f)
