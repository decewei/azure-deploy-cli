from pathlib import Path
from typing import Any

import yaml
from azure.mgmt.appcontainers.models import ContainerApp

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
