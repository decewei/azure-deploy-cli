from pathlib import Path
from typing import Any

import yaml

from .model import ContainerAppConfig


def load_app_config_yaml(yaml_path: Path) -> ContainerAppConfig:
    """
    Load container configurations from YAML file using Pydantic for validation.

    The YAML should have the following structure:
    ```yaml
    containers:
      - name: my-app
        image_name: my-image  # Just the image name
        cpu: 0.5
        memory: "1.0Gi"
        env_vars:  # List of env var names to load from environment
          - ENV_VAR1
          - ENV_VAR2
        dockerfile: ./Dockerfile  # optional
        existing_image_tag: v1.0  # optional
        probes:  # optional - use snake_case keys
          - type: Liveness
            http_get:
              path: /health
              port: 8080
            initial_delay_seconds: 10
            period_seconds: 30
    ```

    Args:
        yaml_path: Path to the YAML configuration file

    Returns:
        List of ContainerConfig instances

    Raises:
        ValueError: If YAML structure is invalid or validation fails
    """
    with open(yaml_path) as f:
        data: dict[str, Any] = yaml.safe_load(f)

    if not data:
        raise ValueError("YAML file is empty")

    try:
        app_config = ContainerAppConfig(**data)
        return app_config
    except Exception as e:
        raise ValueError(f"Invalid YAML configuration: {e}") from e
