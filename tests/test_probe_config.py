import tempfile
from pathlib import Path

import pytest

from azure_deploy_cli.utils.yaml_loader import load_app_config_yaml


class TestYamlLoader:
    """Tests for YAML loading functionality."""

    def test_load_app_config_basic(self):
        """Test loading basic app configuration."""
        yaml_content = """
ingress:
  external: true
  target_port: 8080

containers:
  - name: my-app
    image_name: my-image
    cpu: 0.5
    memory: "1.0Gi"
    env_vars:
      - ENV_VAR1
    dockerfile: ./Dockerfile
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            temp_path = Path(f.name)

        try:
            config = load_app_config_yaml(temp_path)
            assert config is not None
            assert len(config.containers) == 1
            assert config.containers[0].name == "my-app"
            assert config.containers[0].image_name == "my-image"
            assert config.containers[0].cpu == 0.5
            assert config.containers[0].memory == "1.0Gi"
            assert config.containers[0].env_vars == ["ENV_VAR1"]
            assert config.containers[0].dockerfile == "./Dockerfile"
            assert config.ingress is not None
            assert config.ingress.target_port == 8080
        finally:
            temp_path.unlink()

    def test_load_app_config_with_probes(self):
        """Test loading configuration with health probes."""
        yaml_content = """
ingress:
  external: true
  target_port: 8080

containers:
  - name: my-app
    image_name: my-image
    cpu: 0.5
    memory: "1.0Gi"
    env_vars: []
    dockerfile: ./Dockerfile
    probes:
      - type: Liveness
        httpGet:
          path: /health
          port: 8080
        initialDelaySeconds: 10
        periodSeconds: 30
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            temp_path = Path(f.name)

        try:
            config = load_app_config_yaml(temp_path)
            assert config is not None
            assert len(config.containers) == 1
            assert config.containers[0].probes is not None
            assert len(config.containers[0].probes) == 1
            assert config.containers[0].probes[0].type == "Liveness"
        finally:
            temp_path.unlink()

    def test_load_app_config_multiple_containers(self):
        """Test loading configuration with multiple containers."""
        yaml_content = """
ingress:
  external: true
  target_port: 8080

scale:
  min_replicas: 2
  max_replicas: 20

containers:
  - name: main-app
    image_name: main-image
    cpu: 1.0
    memory: "2.0Gi"
    env_vars:
      - VAR1
      - VAR2
    dockerfile: ./Dockerfile

  - name: sidecar
    image_name: sidecar-image
    cpu: 0.25
    memory: "0.5Gi"
    env_vars:
      - SIDECAR_VAR
    existing_image_tag: v1.0.0
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            temp_path = Path(f.name)

        try:
            config = load_app_config_yaml(temp_path)
            assert config is not None
            assert len(config.containers) == 2
            assert config.containers[0].name == "main-app"
            assert config.containers[1].name == "sidecar"
            assert config.containers[1].existing_image_tag == "v1.0.0"
            assert config.min_replicas == 2
            assert config.max_replicas == 20
        finally:
            temp_path.unlink()

    def test_load_app_config_missing_required_field(self):
        """Test that missing required fields raise ValueError."""
        yaml_content = """
containers:
  - name: my-app
    cpu: 0.5
    memory: "1.0Gi"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            temp_path = Path(f.name)

        try:
            with pytest.raises(ValueError, match="must have 'image_name'"):
                load_app_config_yaml(temp_path)
        finally:
            temp_path.unlink()

    def test_load_app_config_no_containers(self):
        """Test that configuration without containers raises ValueError."""
        yaml_content = """
ingress:
  target_port: 8080
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            temp_path = Path(f.name)

        try:
            with pytest.raises(ValueError, match="must contain 'containers' list"):
                load_app_config_yaml(temp_path)
        finally:
            temp_path.unlink()

    def test_load_app_config_defaults(self):
        """Test that default values are applied correctly."""
        yaml_content = """
containers:
  - name: my-app
    image_name: my-image
    cpu: 0.5
    memory: "1.0Gi"
    dockerfile: ./Dockerfile
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            temp_path = Path(f.name)

        try:
            config = load_app_config_yaml(temp_path)
            assert config is not None
            # Check defaults
            assert config.min_replicas == 1
            assert config.max_replicas == 10
            assert config.ingress is None
            assert config.containers[0].env_vars == []
        finally:
            temp_path.unlink()
