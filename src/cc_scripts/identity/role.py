"""Role assignment for service principals (RBAC and Cosmos DB)."""

import json
import subprocess
import uuid
from pathlib import Path
from typing import Any

from azure.mgmt.authorization import AuthorizationManagementClient
from azure.mgmt.authorization.v2022_04_01.models import (
    RoleAssignmentCreateParameters,
)

from ..utils.azure_cli import get_credential, get_subscription_and_tenant, run_command
from ..utils.env import load_env_vars_from_files, substitute_env_vars
from ..utils.logging import get_logger
from .models import RoleConfig, RoleDefinition

logger = get_logger(__name__)


def load_role_config(roles_config_path: Path) -> RoleConfig:
    try:
        with open(roles_config_path) as f:
            role_config_data = json.load(f)
        return RoleConfig(**role_config_data)
    except FileNotFoundError:
        logger.error(f"Roles config file not found: {roles_config_path}")
        raise
    except Exception as e:
        logger.error(f"Failed to load roles config: {str(e)}")
        raise


def assign_role_by_files(
    object_id: str,
    roles_config: Path,
    env_vars_files: list[Path],
    subscription_id: str | None = None,
    object_type: str = "ServicePrincipal",
) -> None:
    role_config = load_role_config(roles_config)

    try:
        env_vars = load_env_vars_from_files(env_vars_files)
    except Exception as e:
        logger.error(f"Failed to load environment variables: {str(e)}")
        raise

    if subscription_id is None:
        try:
            subscription_id, _ = get_subscription_and_tenant()
        except Exception as e:
            logger.error(f"Failed to get subscription info: {str(e)}")
            raise

    if not subscription_id:
        raise ValueError("Subscription ID is required for role assignment")

    env_vars["SUBSCRIPTION_ID"] = subscription_id

    try:
        assign_roles(object_id, subscription_id, role_config, env_vars, object_type=object_type)
    except Exception as e:
        logger.error(f"Failed to assign roles: {str(e)}")
        raise

    logger.success("Service principal created and roles assigned successfully")


def assign_roles(
    object_id: str,
    subscription_id: str,
    role_config: RoleConfig,
    env_vars: dict[str, str] | None = None,
    object_type: str = "ServicePrincipal",
) -> None:
    """
    Assign roles to a service principal based on role configuration.

    Args:
        object_id: Object ID of the service principal
        subscription_id: Azure subscription ID
        role_config: RoleConfig object containing description and roles list
        env_vars: Dictionary of environment variables to substitute in scopes

    Raises:
        ValueError: If any role configuration is invalid
    """
    if env_vars is None:
        env_vars = {}

    try:
        logger.info(f"Processing role config: {role_config.description}")
        logger.info(f"Validating {len(role_config.roles)} role definitions")

        for i, role_def in enumerate(role_config.roles):
            logger.critical(f"Processing role {i + 1}/{len(role_config.roles)}: {role_def.role}")

            if role_def.type == "cosmos-db":
                assign_cosmos_db_role(
                    object_id,
                    role_def,
                    env_vars,
                )
            elif role_def.type == "rbac":
                assign_rbac_role(
                    object_id,
                    subscription_id,
                    role_def,
                    env_vars,
                    object_type=object_type,
                )
            else:
                logger.warning(f"Unknown role type: {role_def.type}")

        logger.success("Role assignments completed")

    except Exception as e:
        logger.error(f"Failed to assign roles: {str(e)}")
        raise


def get_cosmos_accounts() -> list[dict[str, Any]]:
    list_cmd: list[str] = [
        "az",
        "cosmosdb",
        "list",
        "--output",
        "json",
    ]

    accounts: list[dict[str, Any]] = run_command(list_cmd)
    return accounts


def extract_resource_group(account_name: str, accounts: list[dict[str, Any]]) -> str | None:
    for account in accounts:
        if account.get("name") == account_name:
            return account.get("resourceGroup")
    return None


def get_cosmos_role_def(
    role_name: str, account_name: str, resource_group: str
) -> dict[str, Any] | None:
    command = [
        "az",
        "cosmosdb",
        "sql",
        "role",
        "definition",
        "list",
        "--account-name",
        account_name,
        "--resource-group",
        resource_group,
        "--output",
        "json",
    ]
    role_defs: list[dict[str, Any]] = run_command(command)
    for role_def in role_defs:
        if role_def.get("roleName") == role_name:
            return role_def
    return None


def exists_cosmos_role_assignment(
    role_def: dict[str, Any], account_name: str, resource_group: str
) -> bool:
    command = [
        "az",
        "cosmosdb",
        "sql",
        "role",
        "assignment",
        "list",
        "--account-name",
        account_name,
        "--resource-group",
        resource_group,
        "--output",
        "json",
    ]
    assignments: list[dict[str, Any]] = run_command(command)
    for assignment in assignments:
        if assignment.get("roleDefinitionId") == role_def.get("id"):
            return True
    return False


def assign_cosmos_db_role(
    object_id: str,
    role_def: RoleDefinition,
    env_vars: dict[str, str],
) -> None:
    """
    Assign a Cosmos DB role to a service principal via Azure CLI.

    Args:
        cosmos_client: Cosmos DB management client
        object_id: Object ID of the service principal
        role_def: Validated role definition with type='cosmos-db'
        env_vars: Environment variables for substitution

    Raises:
        KeyError: If required environment variables are missing
        subprocess.CalledProcessError: If role assignment fails
    """
    try:
        account_name = substitute_env_vars(role_def.account or "", env_vars)
        scope = role_def.scope
        role_name = role_def.role

        logger.info(f"Assigning Cosmos DB role '{role_name}' to SP on account '{account_name}'")

        accounts = get_cosmos_accounts()
        resource_group = extract_resource_group(account_name, accounts)

        if not resource_group:
            logger.error(f"Cosmos DB account '{account_name}' not found")
            raise ValueError(f"Cosmos DB account '{account_name}' not found")

        logger.info(f"Found account in resource group '{resource_group}'")

        role_definition = get_cosmos_role_def(role_name, account_name, resource_group)
        if not role_definition:
            logger.error(f"Role definition '{role_name}' not found in account '{account_name}'")
            raise ValueError(f"Role definition '{role_name}' not found in account '{account_name}'")

        if exists_cosmos_role_assignment(role_definition, account_name, resource_group):
            logger.success(
                f"Cosmos DB role '{role_name}' is already assigned on account '{account_name}'"
            )
            return

        assign_cmd: list[str] = [
            "az",
            "cosmosdb",
            "sql",
            "role",
            "assignment",
            "create",
            "--account-name",
            account_name,
            "--resource-group",
            resource_group,
            "--role-definition-name",
            role_name,
            "--principal-id",
            object_id,
            "--scope",
            scope,
            "--output",
            "json",
        ]

        run_command(assign_cmd)
        logger.success(f"Cosmos DB role '{role_name}' assigned successfully")

    except KeyError as e:
        logger.error(f"Environment variable substitution failed for Cosmos DB role: {str(e)}")
        raise
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to assign Cosmos DB role: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error assigning Cosmos DB role: {str(e)}")
        raise


def assign_rbac_role(
    object_id: str,
    subscription_id: str,
    role_def: RoleDefinition,
    env_vars: dict[str, str],
    object_type: str = "ServicePrincipal",
) -> None:
    """
    Assign an RBAC role to a service principal.

    Args:
        object_id: Object ID of the service principal
        subscription_id: Azure subscription ID
        role_def: Validated role definition
        env_vars: Environment variables for substitution

    Raises:
        Exception: If role assignment fails
    """
    try:
        scope = substitute_env_vars(role_def.scope, env_vars)
        role_name = role_def.role

        logger.info(f"Looking up role definition for '{role_name}' at scope '{scope}'")

        credential = get_credential(cache=True)
        auth_client = AuthorizationManagementClient(credential, subscription_id)

        role_defs = auth_client.role_definitions.list(
            scope=scope,
            filter=f"roleName eq '{role_name}'",
        )
        role_def_list = list(role_defs)

        if not role_def_list:
            logger.error(f"Role '{role_name}' not found at scope '{scope}'")
            return

        role_id = role_def_list[0].id
        logger.critical(f"Assigning role '{role_name}' to SP")

        existing_assignments = auth_client.role_assignments.list_for_scope(
            scope=scope,
            filter=f"principalId eq '{object_id}'",
        )
        existing_role_assignments = [
            a for a in existing_assignments if a.role_definition_id == role_id
        ]
        if existing_role_assignments:
            logger.success(f"Role '{role_name}' is already assigned at scope '{scope}'")
            return

        auth_client.role_assignments.create(
            scope=scope,
            role_assignment_name=str(uuid.uuid4()),
            parameters=RoleAssignmentCreateParameters(
                role_definition_id=role_id,
                principal_id=object_id,
                principal_type=object_type,
            ),
        )

        logger.success(f"Role '{role_name}' assigned successfully")

    except Exception as e:
        logger.error(f"Failed to assign RBAC role: {str(e)}")
        raise
