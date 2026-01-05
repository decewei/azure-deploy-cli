"""Managed identity (user-assigned identity) lifecycle management."""

from azure.mgmt.msi import ManagedServiceIdentityClient

from ..utils.azure_cli import get_credential, get_subscription_and_tenant
from ..utils.logging import get_logger
from .models import ManagedIdentity

logger = get_logger(__name__)


def get_user_identity(
    identity_name: str, resource_group: str, subscription_id: str
) -> ManagedIdentity | None:
    """Get existing managed identity by name."""
    try:
        credential = get_credential(cache=True)
        msi_client = ManagedServiceIdentityClient(credential, subscription_id)

        logger.info(f"Looking up managed identity '{identity_name}'")
        identities = msi_client.user_assigned_identities.list_by_resource_group(resource_group)

        for identity in identities:
            if identity.name == identity_name:
                logger.info(f"Found managed identity '{identity_name}'")
                principal_id = identity.principal_id
                if not principal_id:
                    raise ValueError("Principal ID is missing from identity")

                return ManagedIdentity(
                    resourceId=identity.id,
                    principalId=principal_id,
                )

        return None

    except Exception as e:
        logger.error(f"Failed to retrieve managed identity: {str(e)}")
        raise


def create_or_get_user_identity(
    identity_name: str,
    resource_group: str,
    location: str,
) -> ManagedIdentity:
    """
    Create a managed identity if it doesn't already exist.

    Args:
        identity_name: Name of the managed identity to create
        resource_group: Azure resource group name
        location: Azure region location

    Returns:
        ManagedIdentity containing resourceId and principalId

    Raises:
        Exception: If creation fails
    """
    try:
        subscription_id, _ = get_subscription_and_tenant()

        logger.info(f"Checking if managed identity '{identity_name}' exists")
        result = get_user_identity(identity_name, resource_group, subscription_id)
        if result is not None:
            logger.warning(f"Managed identity '{identity_name}' already exists")
            return result

        logger.critical(f"Creating managed identity '{identity_name}'")

        credential = get_credential(cache=True)
        msi_client = ManagedServiceIdentityClient(credential, subscription_id)

        identity_params = {
            "location": location,
        }

        identity = msi_client.user_assigned_identities.create_or_update(
            resource_group, identity_name, identity_params
        )

        principal_id = identity.principal_id
        if not principal_id:
            raise ValueError("Principal ID is missing from created identity")

        logger.success(f"Managed identity '{identity_name}' created successfully")

        return ManagedIdentity(
            resourceId=identity.id,
            principalId=principal_id,
        )

    except Exception as e:
        logger.error(f"Failed to create managed identity: {str(e)}")
        raise


def get_identity_principal_id(identity_id: str) -> str:
    """
    Get the principal ID (object ID) of a managed identity.

    Args:
        identity_id: Resource ID of the managed identity

    Returns:
        Principal ID (object ID) of the identity

    Raises:
        Exception: If identity not found or principal ID cannot be retrieved
    """
    try:
        if not identity_id or not identity_id.strip():
            raise ValueError("Identity ID cannot be empty")

        logger.info(f"Retrieving principal ID for identity: {identity_id}")

        subscription_id, _ = get_subscription_and_tenant()
        credential = get_credential(cache=True)
        msi_client = ManagedServiceIdentityClient(credential, subscription_id)

        # Parse resource ID to extract resource group and name
        # Format: /subscriptions/{sub}/resourceGroups/{rg}/providers/
        # Microsoft.ManagedIdentity/userAssignedIdentities/{name}
        parts = identity_id.split("/")
        if len(parts) < 9:
            raise ValueError(f"Invalid identity resource ID format: {identity_id}")

        resource_group = parts[4]
        identity_name = parts[8]

        identity = msi_client.user_assigned_identities.get(resource_group, identity_name)

        principal_id = identity.principal_id
        if not principal_id:
            raise ValueError(f"Principal ID is empty for identity: {identity_id}")

        logger.success(f"Retrieved principal ID: {principal_id}")
        return str(principal_id)

    except Exception as e:
        logger.error(f"Failed to retrieve principal ID for identity: {str(e)}")
        raise


def delete_user_identity(identity_name: str, resource_group: str) -> None:
    """
    Delete a managed identity by name.

    Args:
        identity_name: Name of the managed identity to delete
        resource_group: Azure resource group name

    Raises:
        Exception: If deletion fails
    """
    try:
        subscription_id, _ = get_subscription_and_tenant()

        logger.info(f"Looking up managed identity '{identity_name}'")
        identity = get_user_identity(identity_name, resource_group, subscription_id)

        if not identity:
            logger.success(f"Managed identity '{identity_name}' does not exist; nothing to delete")
            return

        logger.info(f"Found managed identity with resource ID: {identity.resourceId}")

        credential = get_credential(cache=True)
        msi_client = ManagedServiceIdentityClient(credential, subscription_id)

        msi_client.user_assigned_identities.delete(resource_group, identity_name)
        logger.success(f"Managed identity '{identity_name}' deleted successfully")

    except Exception as e:
        logger.error(f"Failed to delete managed identity: {str(e)}")
        raise
