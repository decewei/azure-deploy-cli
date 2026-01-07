from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from azure.mgmt.appcontainers.models import ContainerAppProbe


@dataclass
class ContainerConfig:
    """Configuration for a single container from YAML."""

    name: str
    image_name: str  # Just the image name, no registry or tag
    cpu: float
    memory: str
    env_vars: list[str]  # List of environment variable names to load
    probes: list[ContainerAppProbe] | None = None
    existing_image_tag: str | None = None  # Optional tag to retag from
    dockerfile: str | None = None  # Optional dockerfile path


def load_app_config_yaml(yaml_path: Path) -> list[ContainerConfig]:
    """
    Load container configurations from YAML file.

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
        probes:  # optional
          - type: Liveness
            httpGet:
              path: /health
              port: 8080
    ```

    Args:
        yaml_path: Path to the YAML configuration file

    Returns:
        List of ContainerConfig instances

    Raises:
        ValueError: If YAML structure is invalid
    """
    with open(yaml_path) as f:
        data: dict[str, Any] = yaml.safe_load(f)

    if not data:
        raise ValueError("YAML file is empty")

    # Parse containers
    if "containers" not in data or not data["containers"]:
        raise ValueError("YAML must contain 'containers' list")

    containers = []
    for container_data in data["containers"]:
        if "name" not in container_data:
            raise ValueError("Each container must have a 'name'")
        if "image_name" not in container_data:
            raise ValueError(f"Container '{container_data['name']}' must have 'image_name'")
        if "cpu" not in container_data:
            raise ValueError(f"Container '{container_data['name']}' must have 'cpu'")
        if "memory" not in container_data:
            raise ValueError(f"Container '{container_data['name']}' must have 'memory'")

        # Parse probes if present - convert camelCase to snake_case for SDK
        probes = None
        if "probes" in container_data and container_data["probes"]:
            from azure.mgmt.appcontainers.models import ContainerAppProbe
            
            probes = []
            for probe_data in container_data["probes"]:
                # Convert camelCase keys to snake_case
                probe_dict = {}
                for key, value in probe_data.items():
                    # Map camelCase to snake_case
                    key_map = {
                        "httpGet": "http_get",
                        "tcpSocket": "tcp_socket",
                        "initialDelaySeconds": "initial_delay_seconds",
                        "periodSeconds": "period_seconds",
                        "timeoutSeconds": "timeout_seconds",
                        "failureThreshold": "failure_threshold",
                        "successThreshold": "success_threshold",
                    }
                    probe_dict[key_map.get(key, key)] = value
                
                probes.append(ContainerAppProbe(**probe_dict))

        containers.append(
            ContainerConfig(
                name=container_data["name"],
                image_name=container_data["image_name"],
                cpu=float(container_data["cpu"]),
                memory=str(container_data["memory"]),
                env_vars=container_data.get("env_vars", []),
                probes=probes,
                existing_image_tag=container_data.get("existing_image_tag"),
                dockerfile=container_data.get("dockerfile"),
            )
        )

    return containers

