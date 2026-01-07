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


@dataclass
class IngressConfig:
    """Ingress configuration at app level."""

    external: bool
    target_port: int
    transport: str = "auto"


@dataclass
class AppConfig:
    """Full application configuration from YAML."""

    containers: list[ContainerConfig]
    ingress: IngressConfig | None = None
    min_replicas: int = 1
    max_replicas: int = 10


def load_app_config_yaml(yaml_path: Path) -> AppConfig:
    """
    Load container app configuration from YAML file.

    The YAML should have the following structure:
    ```yaml
    ingress:
      external: true
      target_port: 8080
      transport: auto  # optional, defaults to auto
    scale:
      min_replicas: 1  # optional, defaults to 1
      max_replicas: 10  # optional, defaults to 10
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
        AppConfig instance with parsed configuration

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

        # Parse probes if present
        probes = None
        if "probes" in container_data and container_data["probes"]:
            from azure.mgmt.appcontainers.models import (
                ContainerAppProbe,
                ContainerAppProbeHttpGet,
                ContainerAppProbeHttpGetHttpHeadersItem,
                ContainerAppProbeTcpSocket,
            )

            probes = []
            for probe_data in container_data["probes"]:
                probe_dict = dict(probe_data)
                
                # Convert httpGet to proper object if present
                if "httpGet" in probe_dict and probe_dict["httpGet"]:
                    http_get_data = probe_dict["httpGet"]
                    headers = None
                    if "httpHeaders" in http_get_data:
                        headers = [
                            ContainerAppProbeHttpGetHttpHeadersItem(**h)
                            for h in http_get_data["httpHeaders"]
                        ]
                        http_get_data = dict(http_get_data)
                        http_get_data["http_headers"] = headers
                        del http_get_data["httpHeaders"]
                    
                    probe_dict["http_get"] = ContainerAppProbeHttpGet(**http_get_data)
                    del probe_dict["httpGet"]
                
                # Convert tcpSocket to proper object if present
                if "tcpSocket" in probe_dict and probe_dict["tcpSocket"]:
                    tcp_data = probe_dict["tcpSocket"]
                    probe_dict["tcp_socket"] = ContainerAppProbeTcpSocket(**tcp_data)
                    del probe_dict["tcpSocket"]
                
                # Convert camelCase to snake_case for other fields
                if "initialDelaySeconds" in probe_dict:
                    probe_dict["initial_delay_seconds"] = probe_dict["initialDelaySeconds"]
                    del probe_dict["initialDelaySeconds"]
                if "periodSeconds" in probe_dict:
                    probe_dict["period_seconds"] = probe_dict["periodSeconds"]
                    del probe_dict["periodSeconds"]
                if "timeoutSeconds" in probe_dict:
                    probe_dict["timeout_seconds"] = probe_dict["timeoutSeconds"]
                    del probe_dict["timeoutSeconds"]
                if "failureThreshold" in probe_dict:
                    probe_dict["failure_threshold"] = probe_dict["failureThreshold"]
                    del probe_dict["failureThreshold"]
                if "successThreshold" in probe_dict:
                    probe_dict["success_threshold"] = probe_dict["successThreshold"]
                    del probe_dict["successThreshold"]
                
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

    # Parse ingress
    ingress = None
    if "ingress" in data and data["ingress"]:
        ingress_data = data["ingress"]
        if "target_port" not in ingress_data:
            raise ValueError("Ingress must have 'target_port'")
        
        ingress = IngressConfig(
            external=ingress_data.get("external", True),
            target_port=int(ingress_data["target_port"]),
            transport=ingress_data.get("transport", "auto"),
        )

    # Parse scale settings
    scale_data = data.get("scale", {})
    min_replicas = int(scale_data.get("min_replicas", 1))
    max_replicas = int(scale_data.get("max_replicas", 10))

    return AppConfig(
        containers=containers,
        ingress=ingress,
        min_replicas=min_replicas,
        max_replicas=max_replicas,
    )
