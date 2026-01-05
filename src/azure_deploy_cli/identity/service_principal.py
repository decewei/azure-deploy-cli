"""Service principal lifecycle management."""

import json
import subprocess
from typing import Any

from ..utils.azure_cli import get_subscription_and_tenant, run_command
from ..utils.logging import get_logger
from .models import SPAuthCredentials, SPAuthCredentialsWithSecret, SPCreateResult

logger = get_logger(__name__)


def list_cmd(sp_name: str) -> list[str]:
    """Build command to list service principals by name."""
    return [
        "az",
        "ad",
        "sp",
        "list",
        "--filter",
        f"displayName eq '{sp_name}'",
        "--output",
        "json",
    ]


def exists_sp(sp_name: str) -> str | None:
    """
    Check if service principal exists by name.

    Args:
        sp_name: Display name of the service principal

    Returns:
        Object ID if found, None otherwise

    Raises:
        ValueError: If multiple service principals with same name found
    """
    result: list[dict[str, Any]] = run_command(list_cmd(sp_name))

    if not result or len(result) == 0:
        return None

    if len(result) > 1:
        raise ValueError(
            f"Multiple service principals found with name '{sp_name}'. "
            "Please use a more specific name."
        )

    sp_object_id: str = result[0]["id"]
    return sp_object_id


def get_sp(sp_name: str, subscription_id: str, tenant_id: str) -> SPCreateResult | None:
    """
    Get existing service principal by name.

    Args:
        sp_name: Display name of the service principal
        subscription_id: Azure subscription ID
        tenant_id: Azure tenant ID

    Returns:
        SPCreateResult if found, None otherwise
    """
    list_cmd_args: list[str] = list_cmd(sp_name)

    try:
        existing_sps: list[dict[str, Any]] = run_command(list_cmd_args)
        if existing_sps:
            logger.warning(f"Service principal '{sp_name}' already exists")
            sp = existing_sps[0]
            object_id: str = sp.get("id", "")
            app_id: str = sp.get("appId", "")

            if not object_id or not app_id:
                raise ValueError("Failed to load existing service principal details")

            # Note: existing SP won't have clientSecret - caller must reset
            # credentials
            return SPCreateResult(
                objectId=object_id,
                authCredentials=SPAuthCredentials(
                    clientId=app_id,
                    subscriptionId=subscription_id,
                    tenantId=tenant_id,
                ),
            )
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return None
    return None


def create_sp(
    sp_name: str,
    skip_assignment: bool = True,
) -> SPCreateResult:
    """
    Create a service principal if it doesn't already exist.

    Args:
        sp_name: Name of the service principal to create
        skip_assignment: Whether to skip role assignment during creation

    Returns:
        SPCreateResult containing object ID and credentials

    Raises:
        subprocess.CalledProcessError: If creation fails
        ValueError: If service principal creation is unsuccessful
    """
    try:
        subscription_id, tenant_id = get_subscription_and_tenant()

        logger.info(f"Checking if service principal '{sp_name}' exists")
        result = get_sp(sp_name, subscription_id, tenant_id)
        if result is not None:
            logger.warning(f"Service principal '{sp_name}' already exists")
            return result

        logger.info(f"Creating service principal '{sp_name}'")
        create_cmd: list[str] = [
            "az",
            "ad",
            "sp",
            "create-for-rbac",
            "--name",
            sp_name,
            "--output",
            "json",
        ]

        if skip_assignment:
            create_cmd.insert(4, "--skip-assignment")

        sp_output: dict[str, Any] = run_command(create_cmd)
        get_sp_output = get_sp(sp_name, subscription_id, tenant_id)
        if not get_sp_output:
            raise ValueError("Failed to create service principal")
        logger.info(f"{sp_output} {get_sp_output}")

        object_id = get_sp_output.objectId
        app_id = sp_output.get("appId", "")
        client_secret = sp_output.get("password", "")

        logger.success(f"Service principal '{sp_name}' created successfully")

        return SPCreateResult(
            objectId=object_id,
            authCredentials=SPAuthCredentialsWithSecret(
                clientId=app_id,
                clientSecret=client_secret,
                subscriptionId=subscription_id,
                tenantId=tenant_id,
            ),
        )

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to create service principal: {str(e)}")
        raise


def reset_sp_credentials(
    sp_name: str,
    credential_name: str = "Grant Scraper",
    years: int = 2,
) -> SPAuthCredentialsWithSecret:
    """
    Reset service principal credentials.

    Args:
        sp_name: The display name of the service principal
        credential_name: Display name for the credential
        years: Number of years for the credential validity

    Returns:
        AuthCredentialsWithSecret with clientId, clientSecret,
        subscriptionId, tenantId

    Raises:
        subprocess.CalledProcessError: If reset fails
        ValueError: If service principal not found
    """
    try:
        subscription_id, tenant_id = get_subscription_and_tenant()

        logger.critical(f"Looking up service principal '{sp_name}'")

        # Get the app ID for the service principal by name
        sp_result = get_sp(sp_name, subscription_id, tenant_id)
        if not sp_result:
            raise ValueError(f"Service principal '{sp_name}' not found")

        client_id = sp_result.authCredentials.clientId
        logger.info(f"Found service principal with app ID: {client_id}")

        logger.critical(f"Resetting credentials for service principal '{sp_name}'")

        reset_cmd: list[str] = [
            "az",
            "ad",
            "sp",
            "credential",
            "reset",
            "--id",
            client_id,
            "--display-name",
            credential_name,
            "--years",
            str(years),
            "--output",
            "json",
        ]

        result: dict[str, Any] = run_command(reset_cmd)

        logger.success(f"Credentials reset for service principal '{sp_name}'")

        return SPAuthCredentialsWithSecret(
            clientId=client_id,
            clientSecret=result.get("password", ""),
            subscriptionId=subscription_id,
            tenantId=tenant_id,
        )

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to reset service principal credentials: {str(e)}")
        raise


def delete_service_principal_by_name(sp_name: str) -> None:
    """
    Delete a service principal by display name.

    Args:
        sp_name: The display name of the service principal to delete

    Raises:
        subprocess.CalledProcessError: If the delete operation fails
        ValueError: If the service principal is not found
    """
    try:
        logger.info(f"Looking up service principal '{sp_name}'")
        sp_object_id = exists_sp(sp_name)
        if not sp_object_id:
            logger.success(f"Service principal '{sp_name}' does not exist; nothing to delete")
            return
        logger.info(f"Found service principal with object ID: {sp_object_id}")

        delete_cmd: list[str] = [
            "az",
            "ad",
            "sp",
            "delete",
            "--id",
            sp_object_id,
            "--output",
            "json",
        ]

        run_command(delete_cmd)
        logger.success(f"Service principal '{sp_name}' deleted successfully")

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to delete service principal: {str(e)}")
        raise
