import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from azure.mgmt.appcontainers import ContainerAppsAPIClient

from ..identity.managed_identity import create_or_get_user_identity
from ..identity.role import assign_role_by_files
from ..utils.azure_cli import get_credential, get_subscription_and_tenant
from ..utils.key_vault import get_key_vault_client
from ..utils.logging import get_logger
from .deploy_aca import (
    SecretKeyVaultConfig,
    bind_aca_managed_certificate,
    create_container_app_env,
    deploy_revision,
    generate_revision_suffix,
    update_traffic_weights,
    validate_revision_suffix_and_throw,
)
from .yaml_loader import ContainerAppConfig, load_app_config_yaml

logger = get_logger(__name__)

REGISTRY_PASS_SECRET_ENV_NAME = "ACA_REGISTRY_PASS"
REGISTRY_USER_SECRET_ENV_NAME = "ACA_REGISTRY_USER"

# Traffic weight configuration constants
MIN_TRAFFIC_WEIGHT = 0
MAX_TRAFFIC_WEIGHT = 100


def _label_weight_pair(pair_str: str) -> tuple[str, int]:
    if "=" not in pair_str:
        raise argparse.ArgumentTypeError(
            f"Invalid format: '{pair_str}'. Expected format: label=weight"
        )

    label, weight_str = pair_str.split("=", 1)
    label = label.strip()
    weight_str = weight_str.strip()

    if not label:
        raise argparse.ArgumentTypeError("Label name cannot be empty")

    try:
        weight = int(weight_str)
    except ValueError as e:
        raise argparse.ArgumentTypeError(
            f"Invalid weight '{weight_str}' for label '{label}'. Weight must be an integer"
        ) from e

    if weight < MIN_TRAFFIC_WEIGHT or weight > MAX_TRAFFIC_WEIGHT:
        raise argparse.ArgumentTypeError(
            f"Invalid weight {weight} for label '{label}'. "
            f"Weight must be between {MIN_TRAFFIC_WEIGHT} and {MAX_TRAFFIC_WEIGHT}"
        )

    return (label, weight)


def _convert_label_traffic_args(label_traffic_list: list[tuple[str, int]]) -> dict[str, int]:
    """
    Convert list of (label, weight) tuples to dictionary.

    Args:
        label_traffic_list: List of (label, weight) tuples from argparse

    Returns:
        Dictionary mapping labels to traffic weights
    """
    return dict(label_traffic_list)


def _validate_cli_deploy(args: Any):
    if args.revision_suffix:
        validate_revision_suffix_and_throw(args.revision_suffix, args.stage)
    if not os.getenv(REGISTRY_PASS_SECRET_ENV_NAME):
        raise ValueError(f"Environment variable {REGISTRY_PASS_SECRET_ENV_NAME} is not set")

    if args.role_config and args.role_env_vars_files:
        pass
    elif args.role_config:
        raise ValueError("Role config provided without env vars files")
    elif args.role_env_vars_files:
        raise ValueError("Role env vars files provided without role config")


def cli_deploy(args: Any) -> None:
    """
    Deploy Azure Container App revision from YAML configuration without updating traffic.

    This command orchestrates:
    1. Load container configuration from YAML
    2. Create/get user-assigned managed identity (if specified)
    3. Assign roles to the identity (if role config provided)
    4. Build/push container images for all containers
    5. Deploy new revision with 0% traffic
    6. Verify revision activation and health
    7. Output the revision name for use in traffic management

    Args:
        args: Parsed command line arguments
    """
    _validate_cli_deploy(args)
    registry_user = os.getenv(REGISTRY_USER_SECRET_ENV_NAME)
    if not registry_user:
        raise ValueError(f"Environment variable {REGISTRY_USER_SECRET_ENV_NAME} is not set")

    try:
        logger.critical("Starting ACA revision deployment process...")
        subscription_id, _ = get_subscription_and_tenant()
        credential = get_credential(cache=True)
        container_apps_api_client = ContainerAppsAPIClient(credential, subscription_id)
        key_vault_client = get_key_vault_client(
            subscription_id=subscription_id,
            resource_group=args.resource_group,
            key_vault_name=args.keyvault_name,
        )

        revision_suffix = (
            args.revision_suffix
            if args.revision_suffix
            else generate_revision_suffix(stage=args.stage)
        )

        logger.critical(f"Loading container configuration from '{args.container_config}'...")
        app_config: ContainerAppConfig = load_app_config_yaml(args.container_config)
        logger.critical(f"Loaded configuration with {len(app_config.containers)} container(s)")

        logger.critical("Setting up managed identity and roles...")
        user_identity = create_or_get_user_identity(
            args.user_assigned_identity_name, args.resource_group, subscription_id
        )
        if args.role_config and args.role_env_vars_files:
            assign_role_by_files(
                user_identity.principalId,
                args.role_config,
                args.role_env_vars_files,
            )

        logger.critical("Creating or getting Container App Environment...")
        env = create_container_app_env(
            container_apps_api_client,
            resource_group=args.resource_group,
            container_app_env_name=args.container_app_env,
            location=args.location,
            logs_workspace_id=args.logs_workspace_id,
        )
        if not env:
            raise ValueError("Cannot create container app env")

        logger.critical("Deploying new revision...")
        result = deploy_revision(
            client=container_apps_api_client,
            subscription_id=subscription_id,
            resource_group=args.resource_group,
            container_app_env=env,
            user_identity=user_identity,
            container_app_name=args.container_app,
            registry_server=args.registry_server,
            registry_user=registry_user,
            registry_pass_env_name=REGISTRY_PASS_SECRET_ENV_NAME,
            revision_suffix=revision_suffix,
            location=args.location,
            stage=args.stage,
            container_configs=app_config.containers,
            target_port=args.target_port,
            ingress_external=args.ingress_external,
            ingress_transport=args.ingress_transport,
            min_replicas=args.min_replicas,
            max_replicas=args.max_replicas,
            secret_key_vault_config=SecretKeyVaultConfig(
                key_vault_client=key_vault_client,
                key_vault_name=args.keyvault_name,
                secret_names=args.env_var_secrets or [],
                user_identity=user_identity,
            ),
        )

        if args.custom_domains:
            logger.critical("Binding SSL certificate to Container App...")
            bind_aca_managed_certificate(
                custom_domains=args.custom_domains,
                container_app_name=args.container_app,
                container_app_env_name=args.container_app_env,
                resource_group=args.resource_group,
            )

        logger.success("========== Deployment Complete ==========")
        logger.success(
            f"Deployed revision: {result.revision_name} "
            f"(active={result.active}, healthy={result.is_healthy})"
        )
        logger.stdout(
            f"""
                {
                json.dumps(
                    {
                        "revisionName": result.revision_name,
                        "revisionUrl": result.revision_url,
                    }
                )
            }
            """
        )
        if not result.is_healthy:
            logger.error(
                f"Revision '{result.revision_name}' is not healthy: "
                f"active={result.active}, health={result.health_state}, "
                f"provisioning={result.provisioning_state}, running={result.running_state}"
            )
            sys.exit(1)
    except Exception:
        logger.error("Failed to deploy revision", exc_info=True)
        sys.exit(1)


def cli_update_traffic(args: Any) -> None:
    """
    Update traffic weights for Azure Container App labels.

    This command:
    1. Updates traffic distribution across labels based on configuration
    2. Optionally deactivates revisions not receiving traffic
    3. Optionally deletes unused ACR images to prevent accumulation

    Args:
        args: Parsed command line arguments
    """
    label_traffic_map = _convert_label_traffic_args(args.label_stage_traffic)

    try:
        logger.critical("Starting traffic weight update process...")
        subscription_id, _ = get_subscription_and_tenant()
        credential = get_credential(cache=True)
        container_apps_api_client = ContainerAppsAPIClient(credential, subscription_id)

        logger.critical("Updating traffic weights...")
        update_traffic_weights(
            client=container_apps_api_client,
            resource_group=args.resource_group,
            container_app_name=args.container_app,
            label_traffic_map=label_traffic_map,
            deactivate_old_revisions=not args.no_deactivate,
            should_delete_acr_images=args.delete_acr_images,
        )

        logger.success("========== Traffic Update Complete ==========")
    except Exception:
        logger.error("Failed to update traffic weights", exc_info=True)
        sys.exit(1)


def add_commands(subparsers: argparse._SubParsersAction) -> None:
    """
    Register ACA namespace commands under the 'aca' subparser.

    Args:
        subparsers: The subparsers action from the main parser
    """
    aca_parser = subparsers.add_parser(
        "azaca",
        help="Azure Container Apps management",
        description="Manage Azure Container Apps deployments and configurations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=True,
    )

    aca_subparsers = aca_parser.add_subparsers(dest="aca_command", help="ACA commands")

    deploy_parser = aca_subparsers.add_parser(
        "deploy",
        help="Deploy ACA with optional identity and role setup",
        description=(
            "Set up managed identity and optionally assign roles before ACA deployment. "
            "All unrecognized arguments are passed to the bash deployment script."
            f"Required env vars: {REGISTRY_USER_SECRET_ENV_NAME} "
            f"and {REGISTRY_PASS_SECRET_ENV_NAME}."
        ),
        add_help=True,
    )

    deploy_parser.add_argument(
        "--resource-group",
        required=True,
        type=str,
        help="Azure resource group name",
    )
    deploy_parser.add_argument(
        "--location",
        required=True,
        type=str,
        help="Azure region location (e.g., eastus, westus2)",
    )
    deploy_parser.add_argument(
        "--container-app-env",
        required=True,
        type=str,
        help="Name of the container app environment.",
    )
    deploy_parser.add_argument(
        "--logs-workspace-id",
        required=True,
        type=str,
        help="Log Analytics workspace ID for the container app environment.",
    )
    deploy_parser.add_argument(
        "--user-assigned-identity-name",
        required=True,
        type=str,
        help="Name of the user-assigned managed identity.",
    )
    deploy_parser.add_argument(
        "--container-app",
        required=True,
        type=str,
        help="Name of the container app.",
    )
    deploy_parser.add_argument(
        "--revision-suffix",
        required=False,
        type=str,
        help="Suffix to append to the revision name for identification.",
    )
    deploy_parser.add_argument(
        "--registry-server",
        required=True,
        type=str,
        help="Container registry server.",
    )
    deploy_parser.add_argument(
        "--keyvault-name",
        required=True,
        type=str,
        help="Name of the Key Vault for storing secrets.",
    )

    deploy_parser.add_argument(
        "--stage",
        required=True,
        type=str,
        help="Deployment stage label (e.g., staging, prod) used for revision naming.",
    )

    deploy_parser.add_argument(
        "--target-port",
        required=True,
        type=int,
        help="Target port for the container app ingress.",
    )

    deploy_parser.add_argument(
        "--ingress-external",
        required=False,
        type=bool,
        default=True,
        help="Whether ingress is external (default: True).",
    )

    deploy_parser.add_argument(
        "--ingress-transport",
        required=False,
        type=str,
        default="auto",
        choices=["auto", "http", "http2", "tcp"],
        help="Ingress transport protocol (default: auto).",
    )

    deploy_parser.add_argument(
        "--min-replicas",
        required=True,
        type=int,
        help="Minimum number of replicas for the container app.",
    )

    deploy_parser.add_argument(
        "--max-replicas",
        required=True,
        type=int,
        help="Maximum number of replicas for the container app.",
    )

    deploy_parser.add_argument(
        "--env-var-secrets",
        required=False,
        type=str,
        nargs="+",
        help="Space-separated names of environment variables to be stored as secrets in Key Vault.",
    )

    deploy_parser.add_argument(
        "--role-config",
        required=False,
        type=Path,
        help=(
            "Path to role configuration JSON file for role assignment. "
            "Must be provided together with --role-env-vars-files."
        ),
    )

    deploy_parser.add_argument(
        "--role-env-vars-files",
        required=False,
        type=Path,
        nargs="+",
        help=(
            "Environment files for variable substitution in role config scopes. "
            "Must be provided together with --role-config."
        ),
    )

    deploy_parser.add_argument(
        "--custom-domains",
        required=False,
        type=str,
        nargs="+",
        help="Space-separated list of custom domains to "
        + "bind SSL certificates to the container app.",
    )

    deploy_parser.add_argument(
        "--container-config",
        required=True,
        type=Path,
        help="Path to YAML file containing container configurations "
        "(includes image names, cpu, memory, env_vars, probes, ingress, and scale settings)",
    )

    deploy_parser.set_defaults(func=cli_deploy)

    # Add update-traffic command
    update_traffic_parser = aca_subparsers.add_parser(
        "update-traffic",
        help="Update traffic weights and deactivate old revisions",
        description=(
            "Update traffic distribution across stage labels and optionally "
            "deactivate revisions not receiving traffic and clean up ACR images."
        ),
        add_help=True,
    )

    update_traffic_parser.add_argument(
        "--resource-group",
        required=True,
        type=str,
        help="Azure resource group name",
    )

    update_traffic_parser.add_argument(
        "--container-app",
        required=True,
        type=str,
        help="Name of the container app.",
    )

    update_traffic_parser.add_argument(
        "--label-stage-traffic",
        type=_label_weight_pair,
        nargs="+",
        required=True,
        metavar="LABEL=WEIGHT",
        help=(
            "Traffic weight configuration for stage labels (e.g., prod=100 staging=0). "
            "Specify one or more label=weight pairs."
        ),
    )

    update_traffic_parser.add_argument(
        "--no-deactivate",
        action="store_true",
        help="Skip deactivation of revisions not receiving traffic.",
    )

    update_traffic_parser.add_argument(
        "--delete-acr-images",
        action="store_true",
        help="Disable deletion of unused ACR images when deactivating revisions.",
    )

    update_traffic_parser.set_defaults(func=cli_update_traffic)
