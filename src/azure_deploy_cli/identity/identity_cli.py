import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from ..utils.azure_cli import run_command
from ..utils.env import add_var_to_env_file, load_env_vars_from_files
from ..utils.logging import get_logger
from .group import get_group
from .managed_identity import create_or_get_user_identity
from .models import SPAuthCredentialsWithSecret
from .role import assign_role_by_files
from .service_principal import (
    create_sp,
    delete_service_principal_by_name,
    reset_sp_credentials,
)

logger = get_logger(__name__)


def _load_credentials(env_file: Path | None, cred_key: str) -> Any:
    """
    Load AZ_CREDENTIALS from env file or environment variable.

    Args:
        env_file: Optional path to env file

    Returns:
        Dictionary with credentials (clientId, clientSecret, subscriptionId,
        tenantId)

    Raises:
        FileNotFoundError: If env file not found
        ValueError: If credentials not found or invalid
        json.JSONDecodeError: If AZ_CREDENTIALS JSON is invalid
    """
    credentials_json: str = ""

    if env_file:
        env_vars = load_env_vars_from_files([env_file])
        c = env_vars.get(cred_key, "")
        if c:
            credentials_json = c

    if not credentials_json:
        credentials_json = os.environ.get(cred_key, "")

    if not credentials_json:
        raise ValueError(
            f"Cannot find {cred_key} from --env-file or {cred_key} environment variable"
        )

    creds_dict = json.loads(credentials_json)
    return creds_dict


def _save_credentials(
    credentials: SPAuthCredentialsWithSecret, env_file: Path | None, cred_key: str
) -> None:
    logger.critical(f"Saving credentials to env file: {env_file}")

    if not env_file:
        logger.warning("No --env-file provided; credentials will not be saved to file")

    if env_file:
        if isinstance(credentials, SPAuthCredentialsWithSecret):
            try:
                logger.info(f"Updating credentials in '{env_file}'")
                credentials_json = json.dumps(credentials.to_dict(), separators=(",", ":"))
                add_var_to_env_file({cred_key: credentials_json}, env_file)
                logger.success(f"Credentials saved to '{env_file}'")
            except Exception as e:
                raise Exception(f"Failed to save credentials: {str(e)}") from None
        else:
            logger.warning(
                f"Credentials do not contain secret; cannot save to "
                f"{env_file}. Only credentials with secrets can be "
                f"persisted."
            )
    else:
        logger.warning("No --env-file provided; credentials will not be saved to file")


def cli_create_and_assign(args: Any) -> None:
    try:
        sp_result = create_sp(args.sp_name, skip_assignment=True)

        if args.reset_secrets and not isinstance(
            sp_result.authCredentials, SPAuthCredentialsWithSecret
        ):
            try:
                credentials = reset_sp_credentials(args.sp_name)
                sp_result.authCredentials = credentials
            except Exception as e:
                raise Exception(f"Failed to reset secrets: {str(e)}") from None

            _save_credentials(
                sp_result.authCredentials,
                args.env_file,
                args.cred_key,
            )

        if args.print:
            logger.critical(
                f"Created credentials: {json.dumps(sp_result.authCredentials.to_dict(), indent=2)}",
            )

        assign_role_by_files(
            sp_result.objectId,
            args.roles_config,
            args.env_vars_files,
        )
        logger.success("Service principal created and roles assigned successfully")
    except Exception as e:
        logger.error(str(e))
        sys.exit(1)


def cli_reset_credentials(args: Any) -> None:
    try:
        credentials = reset_sp_credentials(args.sp_name)

        _save_credentials(credentials, args.env_file, args.cred_key)

        if args.print:
            logger.info(
                f"Created credentials: {json.dumps(credentials.to_dict(), indent=2)}",
            )

        logger.success("Credentials reset successfully")
    except Exception as e:
        logger.error(str(e))
        sys.exit(1)


def cli_login(args: Any) -> None:
    try:
        credentials_dict = _load_credentials(args.env_file, args.cred_key)
        credentials = SPAuthCredentialsWithSecret(**credentials_dict)

        logger.info(f"Logging in with service principal {credentials.clientId}")

        login_cmd: list[str] = [
            "az",
            "login",
            "--service-principal",
            "-u",
            credentials.clientId,
            "-p",
            credentials.clientSecret,
            "--tenant",
            credentials.tenantId,
        ]

        run_command(login_cmd)
        logger.success(f"Successfully logged in with service principal {credentials.clientId}")
    except Exception as e:
        logger.error(str(e))
        sys.exit(1)


def cli_delete_service_principal(args: Any) -> None:
    try:
        delete_service_principal_by_name(args.sp_name)
    except Exception as e:
        logger.error(str(e))
        sys.exit(1)


def cli_assign_roles_to_group(args: Any) -> None:
    try:
        group_result = get_group(args.group_name)

        if group_result is None:
            raise Exception(f"Security group '{args.group_name}' not found")

        logger.success(
            f"Found security group '{args.group_name}' with object ID: {group_result.objectId}"
        )

        assign_role_by_files(
            group_result.objectId,
            args.roles_config,
            args.env_vars_files,
            object_type="Group",
        )

        logger.success("Roles assigned to security group successfully")
    except Exception as e:
        logger.error(str(e))
        sys.exit(1)


def cli_create_and_assign_managed_identity(args: Any) -> None:
    try:
        logger.info(f"Setting up managed identity '{args.identity_name}'...")
        identity_result = create_or_get_user_identity(
            args.identity_name,
            args.resource_group,
            args.location,
        )
        logger.success(f"Managed identity ready: {identity_result.resourceId}")

        if args.roles_config:
            assign_role_by_files(
                identity_result.principalId,
                args.roles_config,
                args.env_vars_files,
            )
            logger.success("Roles assigned to managed identity successfully")
        else:
            logger.info("No role config provided; skipping role assignment")

        logger.success(
            f"Managed identity '{args.identity_name}' created and ready for use. "
            f"Resource ID: {identity_result.resourceId}"
        )
    except Exception as e:
        logger.error(str(e))
        sys.exit(1)


def add_commands(subparsers: argparse._SubParsersAction) -> None:
    azid_parser = subparsers.add_parser(
        "azid",
        help="Azure identity management (service principals, credentials, roles)",
        description="Manage Azure service principals, credentials, and role assignments",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create a new service principal and assign roles
  cc azid create-sp-and-assign-roles \\
    --sp-name my-sp \\
    --roles-config roles-config.json \\
    --env-vars-files .env.local \\
    --env-file .env.credentials \\
    --print

  # Reset credentials for an existing service principal
  cc azid reset-sp-credentials \\
    --sp-name my-sp \\
    --env-file .env.credentials \\
    --print

  # Assign roles to a security group
  cc azid assign-roles-to-group \\
    --group-name "My Security Team" \\
    --roles-config roles-config.json \\
    --env-vars-files .env.local

  # Create user-assigned managed identity and assign roles
  cc azid create-and-assign-managed-identity \\
    --identity-name my-app-identity \\
    --resource-group my-rg \\
    --location eastus \\
    --roles-config roles-config.json \\
    --env-vars-files .env.local

  # Login using stored credentials
  cc azid login --env-file .env.credentials
        """,
    )

    azid_subparsers = azid_parser.add_subparsers(
        dest="azid_command", help="Identity command to execute"
    )
    azid_subparsers.required = True

    create_parser = azid_subparsers.add_parser(
        "create-sp-and-assign-roles",
        help="Create a service principal and assign roles",
        description=(
            "Create a new service principal in Azure and assign it roles "
            "based on a configuration file."
        ),
    )
    create_parser.add_argument(
        "--sp-name",
        required=True,
        help="Name of the service principal to create",
    )
    create_parser.add_argument(
        "--roles-config",
        required=True,
        type=Path,
        help="Path to roles-config.json file containing role definitions",
    )
    create_parser.add_argument(
        "--env-vars-files",
        required=True,
        type=Path,
        nargs="+",
        help="Paths to .env files with environment variables (can specify multiple files)",
    )
    create_parser.add_argument(
        "-f",
        "--env-file",
        type=Path,
        help="Path to environment file to save credentials (optional)",
    )
    create_parser.add_argument(
        "-k",
        "--cred-key",
        type=str,
        default="AZ_CREDENTIALS",
        help="Credential key used to save credentials (optional)",
    )
    create_parser.add_argument(
        "--print",
        action="store_true",
        help="Print credentials to stdout in JSON format",
    )
    create_parser.add_argument(
        "--reset-secrets",
        action="store_true",
        help="Reset secrets after creation if SP already exists (has no secret)",
    )
    create_parser.set_defaults(func=cli_create_and_assign)

    reset_parser = azid_subparsers.add_parser(
        "reset-sp-credentials",
        help="Reset service principal credentials",
        description="Reset (rotate) credentials for an existing service principal.",
    )
    reset_parser.add_argument(
        "--sp-name",
        required=True,
        help="Display name of the service principal",
    )
    reset_parser.add_argument(
        "-f",
        "--env-file",
        type=Path,
        help="Path to environment file to save credentials (optional)",
    )
    reset_parser.add_argument(
        "-k",
        "--cred-key",
        type=str,
        default="AZ_CREDENTIALS",
        help="Credential key used to save credentials (optional)",
    )
    reset_parser.add_argument(
        "--print",
        action="store_true",
        help="Print credentials to stdout in JSON format",
    )
    reset_parser.set_defaults(func=cli_reset_credentials)

    login_parser = azid_subparsers.add_parser(
        "login",
        help="Login using service principal credentials",
        description="Authenticate with Azure using stored service principal credentials.",
    )
    login_parser.add_argument(
        "-f",
        "--env-file",
        type=Path,
        help=(
            "Path to environment file containing AZ_CREDENTIALS "
            "(optional, checks env vars if not provided)"
        ),
    )
    login_parser.add_argument(
        "-k",
        "--cred-key",
        type=str,
        default="AZ_CREDENTIALS",
        help="Credential key used to load credentials (optional)",
    )
    login_parser.set_defaults(func=cli_login)

    delete_parser = azid_subparsers.add_parser(
        "delete-sp",
        help="Delete a service principal by name",
        description="Delete a service principal from Azure by its display name.",
    )
    delete_parser.add_argument(
        "--sp-name",
        required=True,
        help="Display name of the service principal to delete",
    )
    delete_parser.set_defaults(func=cli_delete_service_principal)

    group_parser = azid_subparsers.add_parser(
        "assign-roles-to-group",
        help="Assign roles to a security group",
        description=(
            "Assign roles to an Azure AD security group based on a configuration file. "
            "This is similar to create-sp-and-assign-roles but for security groups "
            "instead of service principals."
        ),
    )
    group_parser.add_argument(
        "--group-name",
        required=True,
        help="Display name of the Azure AD security group",
    )
    group_parser.add_argument(
        "--roles-config",
        required=True,
        type=Path,
        help="Path to roles-config.json file containing role definitions",
    )
    group_parser.add_argument(
        "--env-vars-files",
        required=True,
        type=Path,
        nargs="+",
        help="Paths to .env files with environment variables (can specify multiple files)",
    )
    group_parser.set_defaults(func=cli_assign_roles_to_group)

    mi_parser = azid_subparsers.add_parser(
        "create-and-assign-managed-identity",
        help="Create a user-assigned managed identity and assign roles",
        description=(
            "Create a new user-assigned managed identity in Azure and optionally "
            "assign it roles based on a configuration file."
        ),
    )
    mi_parser.add_argument(
        "--identity-name",
        required=True,
        help="Name of the user-assigned managed identity to create or retrieve",
    )
    mi_parser.add_argument(
        "--resource-group",
        required=True,
        help="Azure resource group name where the identity will be created",
    )
    mi_parser.add_argument(
        "--location",
        required=True,
        help="Azure region location for the identity (e.g., eastus, westus2)",
    )
    mi_parser.add_argument(
        "--roles-config",
        required=False,
        type=Path,
        help="Path to roles-config.json file containing role definitions (optional)",
    )
    mi_parser.add_argument(
        "--env-vars-files",
        required=False,
        type=Path,
        nargs="+",
        help="Paths to .env files with environment variables (can specify multiple files)",
    )
    mi_parser.set_defaults(func=cli_create_and_assign_managed_identity)
