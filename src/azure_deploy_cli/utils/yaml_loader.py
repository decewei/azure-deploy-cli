from pathlib import Path
from typing import Any

import yaml
from azure.mgmt.appcontainers.models import ContainerAppProbe
from pydantic import BaseModel, Field, field_validator, model_validator


class ContainerConfig(BaseModel):
    """Configuration for a single container from YAML."""

    name: str
    image_name: str = Field(..., description="Just the image name, no registry or tag")
    cpu: float
    memory: str
    env_vars: list[str] = Field(default_factory=list, description="List of environment variable names to load")
    probes: list[ContainerAppProbe] | None = Field(default=None, description="List of probe configurations")
    existing_image_tag: str | None = Field(default=None, description="Optional tag to retag from")
    dockerfile: str | None = Field(default=None, description="Optional dockerfile path")
    
    @field_validator('probes', mode='before')
    @classmethod
    def parse_probes(cls, v: list[dict[str, Any]] | None) -> list[ContainerAppProbe] | None:
        """Parse probe dictionaries to ContainerAppProbe objects."""
        if v is None:
            return None
        return [ContainerAppProbe(**probe_data) for probe_data in v]
    
    class Config:
        arbitrary_types_allowed = True


class AppConfig(BaseModel):
    """Root configuration model for the YAML file."""
    
    containers: list[ContainerConfig] = Field(..., min_length=1, description="List of container configurations")


def load_app_config_yaml(yaml_path: Path) -> list[ContainerConfig]:
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
        # Use Pydantic to validate and parse the configuration
        app_config = AppConfig(**data)
        return app_config.containers
    except Exception as e:
        raise ValueError(f"Invalid YAML configuration: {e}") from e

