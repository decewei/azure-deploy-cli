from azure_deploy_cli.identity import (
    AzureGroup,
    ManagedIdentity,
    RoleConfig,
    RoleDefinition,
    SPAuthCredentials,
    SPAuthCredentialsWithSecret,
    SPCreateResult,
    assign_roles,
    create_or_get_user_identity,
    create_sp,
    delete_user_identity,
    get_identity_principal_id,
    reset_sp_credentials,
)

# Get version using standard importlib.metadata (preferred method)
try:
    from importlib.metadata import PackageNotFoundError, version

    __version__ = version("azure-deploy-cli")
except PackageNotFoundError:
    # Fallback to setuptools-scm generated file
    try:
        from azure_deploy_cli._version import __version__
    except ImportError:
        # Final fallback for development installations without git
        __version__ = "0.0.0.dev0"

__all__ = [
    "SPAuthCredentials",
    "SPAuthCredentialsWithSecret",
    "SPCreateResult",
    "RoleConfig",
    "RoleDefinition",
    "ManagedIdentity",
    "AzureGroup",
    "create_sp",
    "reset_sp_credentials",
    "create_or_get_user_identity",
    "delete_user_identity",
    "get_identity_principal_id",
    "assign_roles",
]
