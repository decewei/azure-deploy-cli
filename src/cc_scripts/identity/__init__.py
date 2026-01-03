import cc_scripts.identity.identity_cli
from cc_scripts.identity.managed_identity import (
    create_or_get_user_identity,
    delete_user_identity,
    get_identity_principal_id,
)
from cc_scripts.identity.models import (
    AzureGroup,
    ManagedIdentity,
    RoleConfig,
    RoleDefinition,
    SPAuthCredentials,
    SPAuthCredentialsWithSecret,
    SPCreateResult,
)
from cc_scripts.identity.role import assign_roles
from cc_scripts.identity.service_principal import create_sp, reset_sp_credentials

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
