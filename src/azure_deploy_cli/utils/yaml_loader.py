from pathlib import Path

import yaml
from azure.mgmt.appcontainers.models import ContainerApp


def load_container_app_yaml(yaml_path: Path) -> ContainerApp:
    """
    Load Azure Container Apps YAML configuration using the SDK's built-in models.

    The YAML should follow the Azure Container Apps resource template format.

    Args:
        yaml_path: Path to the YAML file

    Returns:
        ContainerApp model instance with all configuration
    """
    with open(yaml_path, "r") as f:
        data = yaml.safe_load(f)

    # The SDK models can be instantiated directly from dictionaries
    # If the YAML has a top-level 'properties' key (ARM template format)
    if "properties" in data:
        return ContainerApp(**data)
    else:
        # If it's just the properties directly
        return ContainerApp(properties=data)
