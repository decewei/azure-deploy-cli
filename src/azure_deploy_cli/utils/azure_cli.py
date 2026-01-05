import json
import os
import subprocess
from typing import Any

from .logging import get_logger

logger = get_logger(__name__)

# Singleton credential instance
_credential = None


def run_command(command: list[str]) -> Any:
    """
    Run an Azure CLI command and return the JSON output.

    Args:
        command: List of command arguments starting with 'az'

    Returns:
        Parsed JSON output from the command

    Raises:
        subprocess.CalledProcessError: If command fails
    """
    try:
        # Set environment to suppress Azure authentication logs
        env = os.environ.copy()
        env["AZURE_CORE_ONLY_SHOW_ERRORS"] = "True"

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            env=env,
        )
        if result.stdout.strip() == "":
            return {}
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {' '.join(command)}")
        logger.error(f"Error: {e.stderr}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON output: {e}")
        return {}


def get_subscription_and_tenant() -> tuple[str, str]:
    """
    Get subscription ID and tenant ID from Azure CLI.

    Returns:
        Tuple of (subscription_id, tenant_id)

    Raises:
        ValueError: If subscription or tenant ID cannot be retrieved
    """
    account_info = run_command(["az", "account", "show", "--output", "json"])
    subscription_id: str = account_info.get("id", "")
    tenant_id: str = account_info.get("tenantId", "")

    if not subscription_id or not tenant_id:
        raise ValueError("Failed to retrieve subscription or tenant information")

    return subscription_id, tenant_id


def get_credential(cache: bool = True):
    """
    Get or create Azure CLI credential.

    Args:
        cache: If True, returns cached credential singleton. If False,
        creates new credential each time.

    Returns:
        AzureCliCredential instance

    Note:
        Using cached credentials (cache=True) is recommended for most use cases to avoid
        repeated authentication overhead. Set cache=False only if you need isolated credentials
        for testing or specific scenarios.
    """
    from azure.identity import AzureCliCredential

    global _credential

    if cache:
        if _credential is None:
            _credential = AzureCliCredential()
        return _credential
    else:
        return AzureCliCredential()
