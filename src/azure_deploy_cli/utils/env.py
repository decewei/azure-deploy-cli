"""Environment variable and credential file handling utilities."""

from pathlib import Path
from string import Template

from dotenv import dotenv_values

from .logging import get_logger

logger = get_logger(__name__)


def substitute_env_vars(value: str, env_vars: dict[str, str]) -> str:
    """
    Substitute environment variables in a string using Template format.

    All ${VAR_NAME} placeholders in the value must have corresponding entries in
    env_vars, otherwise a KeyError is raised.

    Args:
        value: String with ${VAR_NAME} placeholders
        env_vars: Dictionary of variable values

    Returns:
        Fully substituted string with all variables replaced

    Raises:
        KeyError: If any ${VAR_NAME} placeholders in value are not found in
                  env_vars

    Example:
        >>> env_vars = {
        ...     "SUBSCRIPTION_ID": "12345678-1234-1234-1234-123456789012",
        ...     "RESOURCE_GROUP": "my-rg",
        ...     "OPENAI_RESOURCE_NAME": "my-openai",
        ... }
        >>> scope = "/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/\
        ${RESOURCE_GROUP}/providers/Microsoft.CognitiveServices/accounts/\
        ${OPENAI_RESOURCE_NAME}"
        >>> substitute_env_vars(scope, env_vars)
        '/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/\
        my-rg/providers/Microsoft.CognitiveServices/accounts/my-openai'
    """
    template = Template(value)
    result = template.substitute(env_vars)
    return result


def load_env_vars_from_files(
    env_file_paths: list[Path] | None,
) -> dict[str, str]:
    """
    Load environment variables from multiple .env files using python-dotenv.

    Files are loaded in order and merged, with later files overriding earlier
    ones.

    Args:
        env_file_paths: List of paths to .env files with KEY=VALUE format

    Returns:
        Merged dictionary of environment variables

    Raises:
        FileNotFoundError: If any file doesn't exist
        Exception: If file parsing fails
    """
    if not env_file_paths:
        return {}

    merged_vars: dict[str, str | None] = {}

    for env_file_path in env_file_paths:
        env_vars = dotenv_values(env_file_path)
        merged_vars.update(env_vars)
        logger.info(f"Loaded {len(env_vars)} variables from {env_file_path}")

    logger.info(f"Total merged: {len(merged_vars)} unique environment variables")
    merged_vars_cleaned: dict[str, str] = {k: v for k, v in merged_vars.items() if v is not None}
    return merged_vars_cleaned


def add_var_to_env_file(
    env_var_map: dict[str, str],
    env_file_path: Path,
) -> None:
    """
    Add or update in an environment file.

    Args:
        env_var_map: Dictionary of environment variable key-value pairs
        env_file_path: Path to the environment file
    """
    env_file_path.parent.mkdir(parents=True, exist_ok=True)
    existing_content = ""
    if env_file_path.exists():
        with open(env_file_path) as f:
            existing_content = f.read()
    lines = [
        line
        for line in existing_content.split("\n")
        if not any(line.startswith(f"{env_var_key}=") for env_var_key in env_var_map.keys())
    ]
    with open(env_file_path, "w") as f:
        f.write("\n".join(lines).rstrip())
        for env_var_key, env_var_value in env_var_map.items():
            env_var_line = f"{env_var_key}={env_var_value}\n"
            f.write("\n" + env_var_line)
