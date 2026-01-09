from unittest.mock import Mock, patch

import pytest

from azure_deploy_cli.aca.deploy_aca import (
    deploy_revision,
    get_aca_docker_image_name,
)
from azure_deploy_cli.utils.docker import pull_image, pull_retag_and_push_image, tag_image


class TestRetagImage:
    """Tests for image retagging functionality."""

    @patch("azure_deploy_cli.utils.docker.subprocess.Popen")
    def test_pull_image_success(self, mock_popen):
        """Test successful image pull."""
        mock_process = Mock()
        mock_process.stdout.readline = Mock(side_effect=[""])  # EOF immediately
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        pull_image("registry.io/myapp:tag1")
        mock_popen.assert_called_once_with(
            ["docker", "pull", "registry.io/myapp:tag1"],
            stdout=-1,
            stderr=-2,
            text=True,
        )

    @patch("azure_deploy_cli.utils.docker.subprocess.Popen")
    def test_pull_image_failure(self, mock_popen):
        """Test image pull failure."""
        mock_process = Mock()
        mock_process.stdout.readline = Mock(side_effect=[""])  # EOF immediately
        mock_process.wait.return_value = 1
        mock_popen.return_value = mock_process

        with pytest.raises(RuntimeError, match="Docker pull failed"):
            pull_image("registry.io/myapp:nonexistent")

    @patch("azure_deploy_cli.utils.docker.subprocess.Popen")
    def test_tag_image_success(self, mock_popen):
        """Test successful image tagging."""
        mock_process = Mock()
        mock_process.stdout.readline = Mock(side_effect=[""])  # EOF immediately
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        tag_image("registry.io/myapp:old", "registry.io/myapp:new")
        mock_popen.assert_called_once_with(
            ["docker", "tag", "registry.io/myapp:old", "registry.io/myapp:new"],
            stdout=-1,
            stderr=-2,
            text=True,
        )

    @patch("azure_deploy_cli.utils.docker.subprocess.Popen")
    def test_tag_image_failure(self, mock_popen):
        """Test image tagging failure."""
        mock_process = Mock()
        mock_process.stdout.readline = Mock(side_effect=[""])  # EOF immediately
        mock_process.wait.return_value = 1
        mock_popen.return_value = mock_process

        with pytest.raises(RuntimeError, match="Docker tag failed"):
            tag_image("registry.io/myapp:old", "registry.io/myapp:new")

    @patch("azure_deploy_cli.utils.docker.push_image")
    @patch("azure_deploy_cli.utils.docker.tag_image")
    @patch("azure_deploy_cli.utils.docker.pull_image")
    @patch("azure_deploy_cli.utils.docker.image_exists")
    def test_retag_and_push_image_success(self, mock_exists, mock_pull, mock_tag, mock_push):
        """Test successful image retagging and push."""
        mock_exists.return_value = False
        pull_retag_and_push_image(
            "registry.azurecr.io/myapp:old-tag",
            "registry.azurecr.io/myapp:new-tag",
        )

        mock_pull.assert_called_once_with("registry.azurecr.io/myapp:old-tag")
        mock_tag.assert_called_once_with(
            "registry.azurecr.io/myapp:old-tag", "registry.azurecr.io/myapp:new-tag"
        )
        mock_push.assert_called_once_with("registry.azurecr.io/myapp:new-tag")

    @patch("azure_deploy_cli.utils.docker.push_image")
    @patch("azure_deploy_cli.utils.docker.tag_image")
    @patch("azure_deploy_cli.utils.docker.pull_image")
    @patch("azure_deploy_cli.utils.docker.image_exists")
    def test_retag_and_push_image_pull_failure(self, mock_exists, mock_pull, mock_tag, mock_push):
        """Test retagging failure when image doesn't exist."""
        mock_exists.return_value = False
        mock_pull.side_effect = RuntimeError("Docker pull failed: Image not found")

        with pytest.raises(RuntimeError, match="Docker pull failed"):
            pull_retag_and_push_image(
                "registry.azurecr.io/myapp:nonexistent",
                "registry.azurecr.io/myapp:new-tag",
            )

        mock_pull.assert_called_once()
        mock_tag.assert_not_called()
        mock_push.assert_not_called()


class TestDeployRevisionWithRetag:
    """Tests for deploy_revision with existing_image_tag parameter."""

    @patch("azure_deploy_cli.aca.deploy_aca._wait_for_revision_activation")
    @patch("azure_deploy_cli.aca.deploy_aca._get_container_app")
    @patch("azure_deploy_cli.aca.deploy_aca.build_container_images")
    @patch("azure_deploy_cli.aca.deploy_aca._prepare_secrets_and_env_vars")
    def test_deploy_revision_with_existing_image_tag(
        self, mock_prepare_secrets, mockbuild_container_images, mock_get_app, mock_wait
    ):
        """Test deploy_revision successfully handles container with existing_image_tag."""
        # Setup mocks
        mock_client = Mock()
        mock_env = Mock(id="env-id")
        mock_user_identity = Mock(resourceId="identity-id")
        mock_secret_config = Mock(secret_names=[], user_identity=mock_user_identity)

        mock_prepare_secrets.return_value = ([], [])
        mock_get_app.return_value = None
        mock_container = Mock()
        mockbuild_container_images.return_value = [mock_container]

        mock_revision = Mock()
        mock_revision.name = "myapp--prod-20231215120000"
        mock_revision.active = True
        mock_revision.health_state = "Healthy"
        mock_revision.provisioning_state = "Provisioned"
        mock_revision.running_state = "Running"
        mock_revision.fqdn = "myapp.azurecontainerapps.io"
        mock_wait.return_value = mock_revision

        # Mock the poller
        mock_poller = Mock()
        mock_poller.result.return_value = None
        mock_client.container_apps.begin_create_or_update.return_value = mock_poller

        # Create container config with existing_image_tag
        container_config = Mock()
        container_config.name = "myapp"
        container_config.image_name = "myapp"
        container_config.env_vars = []
        container_config.existing_image_tag = "prod-20231214120000"

        # Call deploy_revision with container_configs
        result = deploy_revision(
            client=mock_client,
            subscription_id="sub-id",
            resource_group="rg",
            container_app_env=mock_env,
            user_identity=mock_user_identity,
            container_app_name="myapp",
            registry_server="registry.azurecr.io",
            registry_user="user",
            registry_pass_env_name="PASS",
            revision_suffix="prod-20231215120000",
            location="eastus",
            stage="prod",
            container_configs=[container_config],
            target_port=8080,
            ingress_external=True,
            ingress_transport="auto",
            min_replicas=1,
            max_replicas=3,
            secret_key_vault_config=mock_secret_config,
        )

        # Verify build_images was called with container_configs
        mockbuild_container_images.assert_called_once()
        args = mockbuild_container_images.call_args[0]
        assert args[0] == [container_config]
        assert args[1] == "registry.azurecr.io"
        assert args[2] == "prod-20231215120000"

        # Verify deployment succeeded
        assert result.revision_name == "myapp--prod-20231215120000"
        assert result.active is True

    @patch("azure_deploy_cli.aca.deploy_aca._get_container_app")
    @patch("azure_deploy_cli.aca.deploy_aca.build_container_images")
    @patch("azure_deploy_cli.aca.deploy_aca._prepare_secrets_and_env_vars")
    def test_deploy_revision_with_nonexistent_image_tag(
        self, mock_prepare_secrets, mockbuild_container_images, mock_get_app
    ):
        """Test deploy_revision fails when image building/retagging fails."""
        # Setup mocks
        mock_client = Mock()
        mock_env = Mock(id="env-id")
        mock_user_identity = Mock(resourceId="identity-id")
        mock_secret_config = Mock(secret_names=[], user_identity=mock_user_identity)

        mock_prepare_secrets.return_value = ([], [])
        mock_get_app.return_value = None
        mockbuild_container_images.side_effect = RuntimeError("Docker pull failed")

        # Create container config with existing_image_tag
        container_config = Mock()
        container_config.name = "myapp"
        container_config.image_name = "myapp"
        container_config.env_vars = []
        container_config.existing_image_tag = "nonexistent-tag"

        # Call deploy_revision - should fail during image building
        with pytest.raises(RuntimeError, match="Docker pull failed"):
            deploy_revision(
                client=mock_client,
                subscription_id="sub-id",
                resource_group="rg",
                container_app_env=mock_env,
                user_identity=mock_user_identity,
                container_app_name="myapp",
                registry_server="registry.azurecr.io",
                registry_user="user",
                registry_pass_env_name="PASS",
                revision_suffix="prod-20231215120000",
                location="eastus",
                stage="prod",
                container_configs=[container_config],
                target_port=8080,
                ingress_external=True,
                ingress_transport="auto",
                min_replicas=1,
                max_replicas=3,
                secret_key_vault_config=mock_secret_config,
            )

    @patch("azure_deploy_cli.aca.deploy_aca._wait_for_revision_activation")
    @patch("azure_deploy_cli.aca.deploy_aca._get_container_app")
    @patch("azure_deploy_cli.aca.deploy_aca.build_container_images")
    @patch("azure_deploy_cli.aca.deploy_aca._prepare_secrets_and_env_vars")
    def test_deploy_revision_without_existing_image_tag(
        self, mock_prepare_secrets, mockbuild_container_images, mock_get_app, mock_wait
    ):
        """Test deploy_revision works normally when existing_image_tag is not provided."""
        # Setup mocks
        mock_client = Mock()
        mock_env = Mock(id="env-id")
        mock_user_identity = Mock(resourceId="identity-id")
        mock_secret_config = Mock(secret_names=[], user_identity=mock_user_identity)

        mock_prepare_secrets.return_value = ([], [])
        mock_get_app.return_value = None
        mock_container = Mock()
        mockbuild_container_images.return_value = [mock_container]

        mock_revision = Mock()
        mock_revision.name = "myapp--prod-20231215120000"
        mock_revision.active = True
        mock_revision.health_state = "Healthy"
        mock_revision.provisioning_state = "Provisioned"
        mock_revision.running_state = "Running"
        mock_revision.fqdn = "myapp.azurecontainerapps.io"
        mock_wait.return_value = mock_revision

        # Mock the poller
        mock_poller = Mock()
        mock_poller.result.return_value = None
        mock_client.container_apps.begin_create_or_update.return_value = mock_poller

        # Create container config without existing_image_tag
        container_config = Mock()
        container_config.name = "myapp"
        container_config.image_name = "myapp"
        container_config.env_vars = []
        container_config.existing_image_tag = None
        container_config.dockerfile = "Dockerfile"

        # Call deploy_revision without existing_image_tag
        result = deploy_revision(
            client=mock_client,
            subscription_id="sub-id",
            resource_group="rg",
            container_app_env=mock_env,
            user_identity=mock_user_identity,
            container_app_name="myapp",
            registry_server="registry.azurecr.io",
            registry_user="user",
            registry_pass_env_name="PASS",
            revision_suffix="prod-20231215120000",
            location="eastus",
            stage="prod",
            container_configs=[container_config],
            target_port=8080,
            ingress_external=True,
            ingress_transport="auto",
            min_replicas=1,
            max_replicas=3,
            secret_key_vault_config=mock_secret_config,
        )

        # Verify build_images was called
        mockbuild_container_images.assert_called_once()

        # Verify deployment succeeded
        assert result.revision_name == "myapp--prod-20231215120000"
        assert result.active is True


class TestGetAcaDockerImageName:
    """Tests for get_aca_docker_image_name function."""

    def test_get_aca_docker_image_name(self):
        """Test constructing full image name."""
        result = get_aca_docker_image_name("registry.azurecr.io", "myapp", "prod-20231215120000")
        assert result == "registry.azurecr.io/myapp:prod-20231215120000"
