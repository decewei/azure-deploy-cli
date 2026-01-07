from pathlib import Path
from typing import Any

import yaml
from azure.mgmt.appcontainers.models import ContainerApp, ContainerAppProbe

# Placeholder value for location field (required by SDK but not used for probe extraction)
LOCATION_PLACEHOLDER = "placeholder"


def load_container_app_yaml(yaml_path: Path) -> ContainerApp:
    """
    Load Azure Container Apps YAML configuration using the SDK's built-in models.

    The YAML should follow the Azure Container Apps resource template format.

    Args:
        yaml_path: Path to the YAML file

    Returns:
        ContainerApp model instance with all configuration
    """
    with open(yaml_path) as f:
        data: dict[str, Any] = yaml.safe_load(f)

    # The SDK models can be instantiated directly from dictionaries
    # If the YAML has a top-level 'properties' key (ARM template format)
    if "properties" in data:
        # Extract properties and merge with top-level keys like location, tags, etc.
        properties = data["properties"]
        # Location is required, but we'll use a placeholder since we only care about template/config
        return ContainerApp(location=data.get("location", LOCATION_PLACEHOLDER), **properties)
    else:
        # If it's just the properties directly
        return ContainerApp(location=LOCATION_PLACEHOLDER, **data)


def extract_probes_from_config(
    config: ContainerApp, container_name: str
) -> list[ContainerAppProbe] | None:
    """
    Extract probes for a specific container from Container App config.

    Args:
        config: ContainerApp configuration loaded from YAML
        container_name: Name of the container to extract probes for

    Returns:
        List of probes if found

    Raises:
        ValueError: If container name doesn't match any container in config
    """
    if not config.template:
        raise ValueError("Container App configuration has no template")

    template = config.template
    if not template.containers:
        raise ValueError("Container App template has no containers")

    # Find the matching container
    for container in template.containers:
        if container.name == container_name:
            return container.probes

    # If no match, raise error
    raise ValueError(
        f"Container '{container_name}' not found in configuration. "
        f"Available containers: {[c.name for c in template.containers]}"
    )
