import datetime
import os
import subprocess
import time
from collections import defaultdict
from pathlib import Path

from azure.core.exceptions import (
    ClientAuthenticationError,
    HttpResponseError,
    ResourceNotFoundError,
)
from azure.mgmt.appcontainers import ContainerAppsAPIClient
from azure.mgmt.appcontainers.models import (
    ActiveRevisionsMode,
    AppLogsConfiguration,
    Container,
    ContainerApp,
    ContainerResources,
    EnvironmentVar,
    Ingress,
    LogAnalyticsConfiguration,
    ManagedEnvironment,
    ManagedServiceIdentity,
    RegistryCredentials,
    Revision,
    Scale,
    Secret,
    Template,
    TrafficWeight,
    UserAssignedIdentity,
)
from azure.mgmt.appcontainers.models import (
    Configuration as ContainerAppConfiguration,
)
from azure.mgmt.keyvault.models import SecretCreateOrUpdateParameters, SecretProperties

from ..identity.models import ManagedIdentity
from ..utils import docker
from ..utils.logging import get_logger
from .model import ContainerConfig, RevisionDeploymentResult, SecretKeyVaultConfig

logger = get_logger(__name__)


def _login_to_acr(registry_server: str):
    login_result = subprocess.run(
        [
            "az",
            "acr",
            "login",
            "--name",
            registry_server.split(".")[0],
        ],
        capture_output=True,
        text=True,
    )
    if login_result.returncode != 0:
        raise RuntimeError(f"Failed to login to ACR: {login_result.stderr}")


def build_acr_image(
    dockerfile: str,
    full_image_name: str,
    registry_server: str,
    source_full_image_name: str | None = None,
) -> None:
    logger.info(f"Logging in to ACR '{registry_server}'...")
    _login_to_acr(registry_server)
    logger.info("Logged in successfully.")

    if docker.image_exists(full_image_name):
        logger.info(f"Docker image '{full_image_name}' found locally. Pushing to registry...")
        docker.push_image(full_image_name)
        logger.success(f"Docker image {full_image_name} pushed to registry successfully.")
        return

    if source_full_image_name:
        logger.info(
            f"Docker image '{full_image_name}' not found locally. "
            f"Retagging from existing image '{source_full_image_name}'..."
        )
        docker.pull_retag_and_push_image(
            source_full_image_name,
            full_image_name,
        )
        logger.success(f"Docker image '{full_image_name}' pushed to registry successfully.")
        return

    logger.info(f"Building Docker image '{full_image_name}' from Dockerfile '{dockerfile}'...")
    docker.build_and_push_image(
        dockerfile,
        full_image_name,
    )
    logger.success("Docker image built and pushed to registry successfully.")


def delete_acr_image(registry_server: str, full_image_name: str) -> None:
    """
    Delete an image from Azure Container Registry.

    Args:
        registry_server: ACR server name (e.g., myregistry.azurecr.io)
        image_name: Name of the image repository
        image_tag: Tag of the image to delete
    """
    registry_name = registry_server.split(".")[0]

    logger.info(f"Deleting ACR image '{full_image_name}' from registry '{registry_name}'...")

    delete_result = subprocess.run(
        [
            "az",
            "acr",
            "repository",
            "delete",
            "--name",
            registry_name,
            "--image",
            full_image_name,
            "--yes",
        ],
        capture_output=True,
        text=True,
    )

    if delete_result.returncode != 0:
        # Log warning but don't fail - image might not exist or already deleted
        logger.warning(
            f"Failed to delete ACR image '{full_image_name}': {delete_result.stderr.strip()}"
        )
    else:
        logger.info(f"ACR image '{full_image_name}' deleted successfully")


def bind_aca_managed_certificate(
    custom_domains: list[str],
    container_app_name: str,
    container_app_env_name: str,
    resource_group: str,
):
    result = subprocess.run(
        [
            "bash",
            str(Path(__file__).parent / "bash" / "aca-cert" / "create.sh"),
            "--custom-domains",
            ",".join(custom_domains),
            "--container-app-name",
            container_app_name,
            "--resource-group",
            resource_group,
            "--env-resource-group",
            resource_group,
            "--container-app-env-name",
            container_app_env_name,
        ],
        env=os.environ.copy(),
    )
    if result.returncode != 0:
        logger.error("Failed to bind certificate using aca-cert script.")
        raise RuntimeError("Certificate binding failed.")


def create_container_app_env(
    client: ContainerAppsAPIClient,
    resource_group: str,
    container_app_env_name: str,
    location: str,
    logs_workspace_id: str,
) -> ManagedEnvironment | None:
    logger.info(f"Checking for Container App Environment '{container_app_env_name}'...")
    try:
        client.managed_environments.get(resource_group, container_app_env_name)
        logger.success("Container App Environment already exists.")
    except ResourceNotFoundError:
        logger.info("Container App Environment not found. Creating a new one...")
        env_poller = client.managed_environments.begin_create_or_update(
            resource_group,
            container_app_env_name,
            environment_envelope=ManagedEnvironment(
                location=location,
                app_logs_configuration=AppLogsConfiguration(
                    destination="log-analytics",
                    log_analytics_configuration=LogAnalyticsConfiguration(
                        customer_id=logs_workspace_id
                    ),
                ),
            ),
        )
        env_poller.result()
        logger.success("Container App Environment created successfully.")

    try:
        env = client.managed_environments.get(resource_group, container_app_env_name)
        return env
    except ResourceNotFoundError:
        return None


def build_container_images(
    container_configs: list[ContainerConfig],
    registry_server: str,
    revision_suffix: str,
) -> list[str]:
    image_names = []

    for container_config in container_configs:
        image_tag = revision_suffix
        target_full_image_name = get_aca_docker_image_name(
            registry_server, container_config.image_name, image_tag
        )

        if container_config.existing_image_tag:
            logger.info(
                f"Retagging existing image '{container_config.image_name}:"
                f"{container_config.existing_image_tag}' to '{image_tag}'..."
            )
            source_full_image_name = get_aca_docker_image_name(
                registry_server, container_config.image_name, container_config.existing_image_tag
            )
            docker.pull_retag_and_push_image(source_full_image_name, target_full_image_name)
            logger.success(f"Image retagged successfully to '{image_tag}'")
        elif container_config.dockerfile:
            logger.info(
                f"Building image '{container_config.image_name}' from "
                f"Dockerfile '{container_config.dockerfile}'..."
            )
            build_acr_image(
                dockerfile=container_config.dockerfile,
                full_image_name=target_full_image_name,
                registry_server=registry_server,
            )
            logger.success("Image built successfully")
        image_names.append(target_full_image_name)

    return image_names


def deploy_revision(
    client: ContainerAppsAPIClient,
    subscription_id: str,
    resource_group: str,
    container_app_env: ManagedEnvironment,
    user_identity: ManagedIdentity,
    container_app_name: str,
    registry_server: str,
    registry_user: str,
    registry_pass_env_name: str,
    revision_suffix: str,
    location: str,
    stage: str,
    container_configs: list[ContainerConfig],  # list[ContainerConfig] from yaml_loader
    target_port: int,
    ingress_external: bool,
    ingress_transport: str,
    min_replicas: int,
    max_replicas: int,
    secret_key_vault_config: SecretKeyVaultConfig,
) -> RevisionDeploymentResult:
    """
    Deploy a new revision with multiple containers without updating traffic weights.

    This function creates a new revision with existing traffic preserved and checks
    if the activation succeeds. Returns revision information for use in subsequent
    traffic management operations.

    Args:
        client: ContainerAppsAPIClient instance
        subscription_id: Azure subscription ID
        resource_group: Resource group name
        container_app_env: Managed environment for the container app
        user_identity: User-assigned managed identity
        container_app_name: Name of the container app
        registry_server: Container registry server URL
        registry_user: Registry username
        registry_pass_env_name: Name of the registry password environment variable
        revision_suffix: Revision suffix for naming
        location: Azure location
        stage: Deployment stage label
        container_configs: List of ContainerConfig objects from YAML
        target_port: Target port for ingress
        ingress_external: Whether ingress is external
        ingress_transport: Ingress transport protocol
        min_replicas: Minimum number of replicas
        max_replicas: Maximum number of replicas
        secret_key_vault_config: Key Vault configuration for secrets

    Returns:
        RevisionDeploymentResult with revision name and status information

    Raises:
        RuntimeError: If the deployment fails or image operations fail
    """
    validate_revision_suffix_and_throw(revision_suffix, stage)

    logger.info(f"Deploying new revision for Container App '{container_app_name}'...")
    logger.info(f"Building and deploying {len(container_configs)} container(s)...")

    secret_key_vault_config.secret_names.append(registry_pass_env_name)
    secrets, env_vars_dict = _prepare_secrets_and_env_vars(
        secret_config=secret_key_vault_config,
        subscription_id=subscription_id,
        env_var_names=[
            env_var
            for container_config in container_configs
            for env_var in container_config.env_vars
        ],
        resource_group=resource_group,
    )

    full_image_names = build_container_images(container_configs, registry_server, revision_suffix)
    if len(full_image_names) != len(container_configs):
        raise RuntimeError("Mismatch in number of built images and container configurations.")

    # prepare container definitions
    containers: list[Container] = []
    for target_full_image_name, container_config in zip(
        full_image_names, container_configs, strict=True
    ):
        container_env_vars = [
            env_var for env_var in env_vars_dict if env_var.name in container_config.env_vars
        ]
        containers.append(
            Container(
                image=target_full_image_name,
                name=container_config.name,
                env=container_env_vars,
                resources=ContainerResources(
                    cpu=container_config.cpu, memory=container_config.memory
                ),
                probes=container_config.probes,
            )
        )

    # prepare ingress with existing traffic weights
    existing_app = _get_container_app(client, resource_group, container_app_name)
    existing_traffic_weights = None
    if existing_app and existing_app.configuration and existing_app.configuration.ingress:
        existing_traffic_weights = existing_app.configuration.ingress.traffic
    ingress: Ingress = Ingress(
        external=ingress_external,
        target_port=target_port,
        transport=ingress_transport,
        traffic=existing_traffic_weights,  # Preserve existing traffic
    )

    revision_name = generate_revision_name(container_app_name, revision_suffix, stage)
    logger.info(f"Deploying revision '{revision_name}' with existing traffic preserved")
    poller = client.container_apps.begin_create_or_update(
        resource_group_name=resource_group,
        container_app_name=container_app_name,
        container_app_envelope=ContainerApp(
            location=location,
            environment_id=container_app_env.id,
            configuration=ContainerAppConfiguration(
                ingress=ingress,
                registries=[
                    RegistryCredentials(
                        server=registry_server,
                        username=registry_user,
                        password_secret_ref=_sanitize_secret_name(registry_pass_env_name),
                    )
                ],
                secrets=secrets,
                active_revisions_mode=ActiveRevisionsMode.MULTIPLE,
            ),
            template=Template(
                revision_suffix=revision_suffix,
                containers=containers,
                scale=Scale(min_replicas=min_replicas, max_replicas=max_replicas),
            ),
            identity=ManagedServiceIdentity(
                type="UserAssigned",
                user_assigned_identities={user_identity.resourceId: UserAssignedIdentity()},
            ),
        ),
    )
    logger.info("Waiting for revision deployment to complete...")
    poller.result()

    logger.info(f"Fetching revision '{revision_name}' details...")
    revision = _wait_for_revision_activation(
        client, resource_group, container_app_name, revision_name
    )

    result = RevisionDeploymentResult(
        revision_name=revision.name or revision_name,
        active=revision.active or False,
        health_state=str(revision.health_state) if revision.health_state else "Unknown",
        provisioning_state=str(revision.provisioning_state)
        if revision.provisioning_state
        else "Unknown",
        running_state=str(revision.running_state) if revision.running_state else "Unknown",
        revision_url=revision.fqdn,
    )

    logger.info(
        f"Revision deployed: active={result.active}, health={result.health_state}, "
        f"provisioning={result.provisioning_state}, running={result.running_state}"
    )

    return result


def _wait_for_revision_activation(
    client: ContainerAppsAPIClient,
    resource_group: str,
    container_app_name: str,
    revision_name: str,
    timeout_seconds: int = 300,
    poll_interval_seconds: int = 10,
) -> Revision:
    """
    Polls the revision until it is no longer in the 'Activating' state.

    Args:
        client: The ContainerAppsAPIClient.
        resource_group: The resource group name.
        container_app_name: The container app name.
        revision_name: The revision name.
        timeout_seconds: The maximum time to wait.
        poll_interval_seconds: The interval between polls.

    Returns:
        The final revision object.

    Raises:
        RuntimeError: If the timeout is reached.
    """
    start_time = time.time()
    while time.time() - start_time < timeout_seconds:
        revision = client.container_apps_revisions.get_revision(
            resource_group_name=resource_group,
            container_app_name=container_app_name,
            revision_name=revision_name,
        )
        if revision.running_state != "Activating":
            logger.info(f"Revision '{revision_name}' is now in '{revision.running_state}' state.")
            return revision
        logger.info(
            f"Revision '{revision_name}' is still 'Activating'. Waiting..."
            f" {int(time.time() - start_time)}s elapsed."
        )
        time.sleep(poll_interval_seconds)

    raise RuntimeError(
        f"Timeout reached waiting for revision '{revision_name}' to activate. "
        f"Last state was '{revision.running_state}'."
    )


def get_aca_docker_image_name(registry_server: str, image_name: str, image_tag: str) -> str:
    return f"{registry_server}/{image_name}:{image_tag}"


def _prepare_secrets_and_env_vars(
    secret_config: SecretKeyVaultConfig,
    subscription_id: str,
    env_var_names: list[str],
    resource_group: str,
) -> tuple[list[Secret], list[EnvironmentVar]]:
    env_vars: dict[str, str] = _load_env_vars(env_var_names)

    logger.info(f"Processing secrets for Key Vault '{secret_config.key_vault_name}'...")

    secrets: list[Secret] = []
    envs: list[EnvironmentVar] = []
    for secret_name in list(set(secret_config.secret_names)):
        logger.info(
            f"Setting secret '{secret_name}' in Key Vault '{secret_config.key_vault_name}'..."
        )
        if secret_name not in os.environ:
            raise ValueError(f"Environment variable '{secret_name}' is not set in the environment.")
        secret, env_var = _prepare_secret_and_env(
            secret_name=secret_name,
            secret_value=os.environ[secret_name],
            user_identity_resource_id=secret_config.user_identity.resourceId,
            secret_config=secret_config,
            resource_group=resource_group,
        )
        secrets.append(secret)
        envs.append(env_var)
        if secret_name in env_vars:
            del env_vars[secret_name]  # Remove from plain env vars

    for key, value in env_vars.items():
        envs.append(EnvironmentVar(name=key, value=value))

    return secrets, envs


def _sanitize_secret_name(name: str) -> str:
    return name.replace("_", "-").lower()


def _prepare_secret_and_env(
    secret_name: str,
    secret_value: str,
    user_identity_resource_id: str,
    secret_config: SecretKeyVaultConfig,
    resource_group: str,
) -> tuple[Secret, EnvironmentVar]:
    sanitized_name = _sanitize_secret_name(secret_name)
    secret_result = secret_config.key_vault_client.secrets.create_or_update(
        resource_group_name=resource_group,
        vault_name=secret_config.key_vault_name,
        secret_name=sanitized_name,
        parameters=SecretCreateOrUpdateParameters(properties=SecretProperties(value=secret_value)),
    )
    secret = Secret(
        name=sanitized_name,
        key_vault_url=secret_result.properties.secret_uri,
        identity=secret_config.user_identity.resourceId,
    )
    env_var = EnvironmentVar(name=secret_name, secret_ref=sanitized_name)
    return secret, env_var


def _load_env_vars(env_var_names: list[str]) -> dict[str, str]:
    env_var_dict = {}
    for var_name in env_var_names:
        if var_name in os.environ:
            env_var_dict[var_name] = os.environ[var_name]
        else:
            raise ValueError(f"Environment variable '{var_name}' is not set in the environment.")

    return env_var_dict


def _traffic_weight_str(
    traffic_weight: list[TrafficWeight], selected_revision: list[Revision]
) -> str:
    parts = []
    for t in traffic_weight:
        rev_name = t.revision_name
        found_revision = next((rev for rev in selected_revision if rev.name == rev_name), None)
        is_healthy = _is_revision_healthy(found_revision) if found_revision else False
        parts.append(f"{t.label}:{t.as_dict()}%->{rev_name} (healthy={is_healthy})")
    return " | ".join(parts)


def _get_label_from_rev_name(rev_name: str, container_app_name: str) -> str | None:
    if not rev_name:
        return None
    prefix = f"{container_app_name}--"
    if rev_name.startswith(prefix):
        label_part = rev_name[len(prefix) :]
        label = label_part.split("-")[0]
        return label
    return None


def _get_active_revisions_by_label_group(
    client: ContainerAppsAPIClient,
    resource_group: str,
    container_app_name: str,
    labels: set[str],
) -> dict[str, list[Revision]]:
    revision_results = client.container_apps_revisions.list_revisions(
        resource_group_name=resource_group,
        container_app_name=container_app_name,
    )

    all_revisions = list(revision_results)

    label_group: dict[str, list] = defaultdict(list)
    for rev in all_revisions:
        if not rev.active:
            continue
        if not rev.name:
            continue
        label = _get_label_from_rev_name(rev.name, container_app_name)
        if not label:
            continue
        if label not in labels:
            continue
        label_group[label].append(rev)

    for label in label_group.keys():
        label_group[label] = sorted(label_group[label], key=lambda r: r.name or "")

    return label_group


def _is_revision_healthy(rev: Revision) -> bool:
    return (
        (rev.active or False)
        and rev.health_state == "Healthy"
        and rev.provisioning_state == "Provisioned"
        and rev.running_state not in ("Stopped", "Degraded", "Failed")
    )


def _filter_healthy_revisions(revisions: list[Revision]) -> list[Revision]:
    healthy_revisions = []
    for rev in revisions:
        if rev.name:
            is_healthy = (
                rev.active
                and rev.health_state == "Healthy"
                and rev.provisioning_state == "Provisioned"
                and rev.running_state not in ("Stopped", "Degraded", "Failed")
            )
            if is_healthy:
                healthy_revisions.append(rev)
    return healthy_revisions


def _get_latest_revision_by_label(
    label_revision_groups: dict[str, list[Revision]],
    label: str,
    require_healthy: bool = False,
) -> Revision | None:
    all_revisions_for_label = label_revision_groups.get(label, [])
    if not all_revisions_for_label:
        return None

    for rev in reversed(all_revisions_for_label):
        if _is_revision_healthy(rev):
            return rev

    if require_healthy:
        return None

    logger.warning(f"No healthy revisions found for label '{label}', using latest revision")
    return all_revisions_for_label[-1] if all_revisions_for_label else None


def validate_revision_suffix_and_throw(revision_suffix: str, stage: str) -> bool:
    stage_label, random_string = revision_suffix.split("-")
    if stage_label != stage:
        raise ValueError(
            f"Revision suffix stage label '{stage_label}' does not match "
            f"the provided stage '{stage}'"
        )
    if not random_string.isalnum():
        raise ValueError(f"Revision suffix random string '{random_string}' must be alphanumeric")
    return True


def generate_revision_suffix(stage: str) -> str:
    revision_suffix = stage + "-" + datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
    if validate_revision_suffix_and_throw(revision_suffix, stage):
        return revision_suffix
    raise RuntimeError("Failed to generate valid revision suffix.")


def generate_revision_name(container_app_name: str, revision_suffix: str, stage: str) -> str:
    if validate_revision_suffix_and_throw(revision_suffix, stage):
        return f"{container_app_name}--{revision_suffix}"
    raise RuntimeError("Failed to generate valid revision name.")


def extract_revision_suffix(revision_name: str) -> str | None:
    if "--" in revision_name:
        return revision_name.split("--", 1)[1]
    return None


def _get_container_app(
    client: ContainerAppsAPIClient,
    resource_group: str,
    container_app_name: str,
) -> ContainerApp | None:
    try:
        return client.container_apps.get(
            resource_group_name=resource_group,
            container_app_name=container_app_name,
        )
    except ResourceNotFoundError:
        return None


def __label_revision_group_to_str(label_revision_groups: dict[str, list[Revision]]) -> str:
    parts = []
    for label, revisions in label_revision_groups.items():
        rev_names = [rev.name for rev in revisions if rev.name]
        parts.append(f"{label}:[{', '.join(rev_names)}]")
    return " | ".join(parts)


def update_traffic_weights(
    client: ContainerAppsAPIClient,
    resource_group: str,
    container_app_name: str,
    label_traffic_map: dict[str, int],
    deactivate_old_revisions: bool = True,
    should_delete_acr_images: bool = True,
) -> None:
    """
    Update traffic weights for all labels and optionally deactivate old revisions.

    Args:
        client: Azure Container Apps API client
        resource_group: Resource group name
        container_app_name: Container app name
        label_traffic_map: Dictionary mapping labels to traffic weights
        deactivate_old_revisions: If True, deactivate revisions not receiving traffic
        registry_server: Optional ACR server name for image cleanup during deactivation
        image_name: Optional image name for image cleanup during deactivation

    Raises:
        RuntimeError: If traffic update fails
    """
    if should_delete_acr_images and (not deactivate_old_revisions):
        logger.warning(
            "ACR image deletion is enabled but old revision deactivation is disabled. "
            "No images will be deleted."
        )
    logger.info(f"Updating traffic weights for container app '{container_app_name}'...")
    label_revision_groups = _get_active_revisions_by_label_group(
        client, resource_group, container_app_name, labels=set(label_traffic_map.keys())
    )
    logger.info(f"Label revision groups: {__label_revision_group_to_str(label_revision_groups)}")

    traffic_weights: list[TrafficWeight] = []
    active_revisions: set[str] = set()

    selected_revisions = []
    for label, weight in label_traffic_map.items():
        latest_revision = _get_latest_revision_by_label(
            label_revision_groups, label, require_healthy=False
        )
        if not latest_revision or not latest_revision.name:
            raise RuntimeError(
                f"No revision found for label '{label}'. "
                "Cannot configure traffic for a label with no revisions."
            )
        traffic_weights.append(
            TrafficWeight(
                label=label,
                weight=weight,
                revision_name=latest_revision.name,
                latest_revision=False,
            )
        )
        active_revisions.add(latest_revision.name)
        selected_revisions.append(latest_revision)

    if len(traffic_weights) == 0:
        raise RuntimeError("No valid traffic configuration could be built")

    app = _get_container_app(client, resource_group, container_app_name)
    if not app:
        raise RuntimeError(f"Container app '{container_app_name}' not found")

    if not app.configuration or not app.configuration.ingress:
        raise RuntimeError(f"Container app '{container_app_name}' has no ingress configuration")

    logger.info(
        f"Applying new traffic weights: {_traffic_weight_str(traffic_weights, selected_revisions)}"
    )
    app.configuration.ingress.traffic = traffic_weights

    poller = client.container_apps.begin_update(
        resource_group_name=resource_group,
        container_app_name=container_app_name,
        container_app_envelope=app,
    )
    poller.result()
    logger.success("Traffic weights updated successfully")

    if deactivate_old_revisions:
        deactivate_unused_revisions(
            client,
            resource_group,
            container_app_name,
            active_revisions,
            label_revision_groups,
            should_delete_acr_images,
        )


def _get_revision_container_images(revision: Revision) -> list[str]:
    if revision.template and revision.template.containers and len(revision.template.containers) > 0:
        return [c.image for c in revision.template.containers if c.image]
    return []


def deactivate_unused_revisions(
    client: ContainerAppsAPIClient,
    resource_group: str,
    container_app_name: str,
    active_revisions: set[str],
    label_revision_groups: dict[str, list[Revision]],
    should_delete_acr_images: bool = True,
) -> None:
    """
    Deactivate revisions that are not receiving traffic and optionally delete their ACR images.

    Args:
        client: Azure Container Apps API client
        resource_group: Resource group name
        container_app_name: Container app name
        active_revisions: Set of revision names that should remain active
        label_revision_groups: All revisions grouped by label
    """
    logger.info("Deactivating unused revisions...")

    all_revisions: set[str] = set()
    name_to_revision: dict[str, Revision] = {}
    for revisions in label_revision_groups.values():
        revision_names = {rev.name for rev in revisions if rev.name and rev.active}
        all_revisions.update(revision_names)
        name_to_revision.update({rev.name: rev for rev in revisions if rev.name})

    revisions_to_deactivate = all_revisions.difference(active_revisions)

    if not revisions_to_deactivate:
        logger.info("No revisions to deactivate")
        return

    deactivated_count = 0
    for revision_name in revisions_to_deactivate:
        try:
            logger.info(f"Deactivating revision '{revision_name}'...")
            client.container_apps_revisions.deactivate_revision(
                resource_group_name=resource_group,
                container_app_name=container_app_name,
                revision_name=revision_name,
            )
            deactivated_count += 1
            logger.info(f"Revision '{revision_name}' deactivated")

            revision_suffix = extract_revision_suffix(revision_name)

            if not should_delete_acr_images:
                logger.debug("ACR image deletion is disabled. Skipping image deletion.")
                continue

            if revision_suffix:
                container_images = _get_revision_container_images(name_to_revision[revision_name])
                for image in container_images:
                    registry_server, image_name = image.split("/")
                    logger.info(f"Deleting ACR image '{image}' for revision '{revision_name}'...")
                    delete_acr_image(registry_server, image_name)
            else:
                logger.warning(
                    f"Could not extract revision suffix from '{revision_name}'. "
                    "Skipping ACR image deletion."
                )
        except (ResourceNotFoundError, HttpResponseError, ClientAuthenticationError) as e:
            logger.warning(f"Failed to deactivate revision '{revision_name}': {e}")

    logger.success(f"Deactivated {deactivated_count} unused revision(s)")
