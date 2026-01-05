import azure_deploy_cli.identity.identity_cli
from azure_deploy_cli.identity.managed_identity import (
    create_or_get_user_identity,
    delete_user_identity,
    get_identity_principal_id,
)
from azure_deploy_cli.identity.models import (
    AzureGroup,
    ManagedIdentity,
    RoleConfig,
    RoleDefinition,
    SPAuthCredentials,
    SPAuthCredentialsWithSecret,
    SPCreateResult,
)
from azure_deploy_cli.identity.role import assign_roles
from azure_deploy_cli.identity.service_principal import create_sp, reset_sp_credentials

__version__ = "0.1.0"

__all__ = [
    "SPAuthCredentials",
    "SPAuthCredentialsWithSecret",
    "RoleConfig",
    "RoleDefinition",
    "SPCreateResult",
    "ManagedIdentity",
    "AzureGroup",
    "assign_roles",
    "create_sp",
    "create_or_get_user_identity",
    "delete_user_identity",
    "get_identity_principal_id",
    "identity_cli",
    "reset_sp_credentials",
]
