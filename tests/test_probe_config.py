import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from azure_deploy_cli.utils.yaml_loader import extract_probes_from_config, load_container_app_yaml


class TestYamlLoader:
    """Tests for YAML loading functionality."""

    def test_load_container_app_yaml_with_properties_key(self):
        """Test loading YAML with top-level properties key."""
        yaml_content = """
properties:
  template:
    containers:
    - name: my-app
      probes:
      - type: Liveness
        httpGet:
          path: /health
          port: 8080
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            temp_path = Path(f.name)

        try:
            config = load_container_app_yaml(temp_path)
            assert config is not None
            assert config.template is not None
        finally:
            temp_path.unlink()

    def test_load_container_app_yaml_without_properties_key(self):
        """Test loading YAML with properties directly at root."""
        yaml_content = """
template:
  containers:
  - name: my-app
    probes:
    - type: Readiness
      httpGet:
        path: /ready
        port: 8080
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            temp_path = Path(f.name)

        try:
            config = load_container_app_yaml(temp_path)
            assert config is not None
            assert config.template is not None
        finally:
            temp_path.unlink()


class TestExtractProbesFromConfig:
    """Tests for probe extraction functionality."""

    def test_extract_probes_matching_container_name(self):
        """Test extracting probes when container name matches."""
        mock_probe1 = Mock()
        mock_probe1.type = "Liveness"

        mock_probe2 = Mock()
        mock_probe2.type = "Readiness"

        mock_container1 = Mock()
        mock_container1.name = "my-app"
        mock_container1.probes = [mock_probe1, mock_probe2]

        mock_container2 = Mock()
        mock_container2.name = "other-app"
        mock_container2.probes = []

        mock_template = Mock()
        mock_template.containers = [mock_container1, mock_container2]

        mock_config = Mock()
        mock_config.template = mock_template

        probes = extract_probes_from_config(mock_config, "my-app")
        assert probes is not None
        assert len(probes) == 2
        assert probes[0].type == "Liveness"
        assert probes[1].type == "Readiness"

    def test_extract_probes_no_match_raises_error(self):
        """Test extracting probes when container name doesn't match - raises error."""
        mock_probe = Mock()
        mock_probe.type = "Startup"

        mock_container = Mock()
        mock_container.name = "other-app"
        mock_container.probes = [mock_probe]

        mock_template = Mock()
        mock_template.containers = [mock_container]

        mock_config = Mock()
        mock_config.template = mock_template

        with pytest.raises(ValueError, match="Container 'my-app' not found in configuration"):
            extract_probes_from_config(mock_config, "my-app")

    def test_extract_probes_no_template(self):
        """Test extracting probes when config has no template."""
        mock_config = Mock()
        mock_config.template = None

        with pytest.raises(ValueError, match="Container App configuration has no template"):
            extract_probes_from_config(mock_config, "my-app")

    def test_extract_probes_no_containers(self):
        """Test extracting probes when template has no containers."""
        mock_template = Mock()
        mock_template.containers = None

        mock_config = Mock()
        mock_config.template = mock_template

        with pytest.raises(ValueError, match="Container App template has no containers"):
            extract_probes_from_config(mock_config, "my-app")


    def test_extract_probes_empty_containers_list(self):
        """Test extracting probes when containers list is empty."""
        mock_template = Mock()
        mock_template.containers = []

        mock_config = Mock()
        mock_config.template = mock_template

        with pytest.raises(ValueError, match="Container App template has no containers"):
            extract_probes_from_config(mock_config, "my-app")

    def test_extract_probes_container_has_none_probes(self):
        """Test extracting probes when container has None for probes."""
        mock_container = Mock()
        mock_container.name = "my-app"
        mock_container.probes = None

        mock_template = Mock()
        mock_template.containers = [mock_container]

        mock_config = Mock()
        mock_config.template = mock_template

        probes = extract_probes_from_config(mock_config, "my-app")
        assert probes is None

