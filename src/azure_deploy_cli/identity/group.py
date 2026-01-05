"""Azure AD Security Group lifecycle and role management."""

import json
import subprocess
from typing import Any

from ..utils.azure_cli import run_command
from ..utils.logging import get_logger
from .models import AzureGroup

logger = get_logger(__name__)


def list_cmd(group_name: str) -> list[str]:
    """Build command to list security groups by name."""
    return [
        "az",
        "ad",
        "group",
        "list",
        "--display-name",
        group_name,
        "--output",
        "json",
    ]


def exists_group(group_name: str) -> str | None:
    """
    Check if security group exists by name.

    Args:
        group_name: Display name of the security group

    Returns:
        Object ID if found, None otherwise

    Raises:
        ValueError: If multiple groups with same name found
    """
    result: list[dict[str, Any]] = run_command(list_cmd(group_name))

    if not result or len(result) == 0:
        return None

    if len(result) > 1:
        raise ValueError(
            f"Multiple security groups found with name '{group_name}'. "
            "Please use a more specific name."
        )

    group_object_id: str = result[0]["id"]
    return group_object_id


def get_group(group_name: str) -> AzureGroup | None:
    """
    Get existing security group by name.

    Args:
        group_name: Display name of the security group

    Returns:
        GroupAssignResult if found, None otherwise
    """
    list_cmd_args: list[str] = list_cmd(group_name)

    try:
        existing_groups: list[dict[str, Any]] = run_command(list_cmd_args)
        if existing_groups:
            logger.info(f"Found security group '{group_name}'")
            group = existing_groups[0]
            object_id: str = group.get("id", "")

            if not object_id:
                raise ValueError("Failed to load existing group details")

            return AzureGroup(
                objectId=object_id,
                displayName=group_name,
            )
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return None
    return None
