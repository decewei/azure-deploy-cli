from unittest.mock import Mock, patch

import pytest

from cc_scripts.aca.deploy_aca import (
    deploy_revision,
    get_aca_docker_image_name,
)
from cc_scripts.utils.docker import pull_image, pull_retag_and_push_image, tag_image


class TestRetagImage:
    """Tests for image retagging functionality."""

    @patch("cc_scripts.utils.docker.subprocess.run")
    def test_pull_image_success(self, mock_run):
        """Test successful image pull."""
        mock_run.return_value = Mock(returncode=0)
        pull_image("registry.io/myapp:tag1")
        mock_run.assert_called_once_with(
            ["docker", "pull", "registry.io/myapp:tag1"],
            capture_output=True,
            text=True,
        )

    @patch("cc_scripts.utils.docker.subprocess.run")
    def test_pull_image_failure(self, mock_run):
        """Test image pull failure."""
        mock_run.return_value = Mock(returncode=1, stderr="Image not found")
        with pytest.raises(RuntimeError, match="Docker pull failed"):
            pull_image("registry.io/myapp:nonexistent")

    @patch("cc_scripts.utils.docker.subprocess.run")
    def test_tag_image_success(self, mock_run):
        """Test successful image tagging."""
        mock_run.return_value = Mock(returncode=0)
        tag_image("registry.io/myapp:old", "registry.io/myapp:new")
        mock_run.assert_called_once_with(
            ["docker", "tag", "registry.io/myapp:old", "registry.io/myapp:new"],
            capture_output=True,
            text=True,
        )

    @patch("cc_scripts.utils.docker.subprocess.run")
    def test_tag_image_failure(self, mock_run):
        """Test image tagging failure."""
        mock_run.return_value = Mock(returncode=1, stderr="Tag failed")
        with pytest.raises(RuntimeError, match="Docker tag failed"):
            tag_image("registry.io/myapp:old", "registry.io/myapp:new")

    @patch("cc_scripts.utils.docker.push_image")
    @patch("cc_scripts.utils.docker.tag_image")
    @patch("cc_scripts.utils.docker.pull_image")
    @patch("cc_scripts.utils.docker.image_exists")
    def test_retag_and_push_image_success(
        self, mock_exists, mock_pull, mock_tag, mock_push
    ):
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

    @patch("cc_scripts.utils.docker.push_image")
    @patch("cc_scripts.utils.docker.tag_image")
    @patch("cc_scripts.utils.docker.pull_image")
    @patch("cc_scripts.utils.docker.image_exists")
    def test_retag_and_push_image_pull_failure(
        self, mock_exists, mock_pull, mock_tag, mock_push
    ):
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

    @patch("cc_scripts.aca.deploy_aca._wait_for_revision_activation")
    @patch("cc_scripts.aca.deploy_aca._get_container_app")
    @patch("cc_scripts.utils.docker.pull_retag_and_push_image")
    @patch("cc_scripts.aca.deploy_aca._prepare_secrets_and_env_vars")
    def test_deploy_revision_with_existing_image_tag(
        self, mock_prepare_secrets, mock_retag, mock_get_app, mock_wait
    ):
        """Test deploy_revision successfully retags an existing image."""
        # Setup mocks
        mock_client = Mock()
        mock_env = Mock(id="env-id")
        mock_user_identity = Mock(resourceId="identity-id")
        mock_secret_config = Mock(secret_names=[], user_identity=mock_user_identity)

        mock_prepare_secrets.return_value = ([], [])
        mock_get_app.return_value = None
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

        # Call deploy_revision with existing_image_tag
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
            image_name="myapp",
            image_tag="prod-20231215120000",
            location="eastus",
            stage="prod",
            target_port=8080,
            cpu=1.0,
            memory="2.0",
            min_replicas=1,
            max_replicas=3,
            secret_key_vault_config=mock_secret_config,
            env_var_names=[],
            revision_suffix="prod-20231215120000",
            existing_image_tag="prod-20231214120000",
        )

        # Verify retag was called with correct parameters
        mock_retag.assert_called_once_with(
            "registry.azurecr.io/myapp:prod-20231214120000",
            "registry.azurecr.io/myapp:prod-20231215120000",
        )

        # Verify deployment succeeded
        assert result.revision_name == "myapp--prod-20231215120000"
        assert result.active is True

    @patch("cc_scripts.aca.deploy_aca._get_container_app")
    @patch("cc_scripts.utils.docker.pull_retag_and_push_image")
    @patch("cc_scripts.aca.deploy_aca._prepare_secrets_and_env_vars")
    def test_deploy_revision_with_nonexistent_image_tag(
        self, mock_prepare_secrets, mock_retag, mock_get_app
    ):
        """Test deploy_revision fails when existing image doesn't exist."""
        # Setup mocks
        mock_client = Mock()
        mock_env = Mock(id="env-id")
        mock_user_identity = Mock(resourceId="identity-id")
        mock_secret_config = Mock(secret_names=[], user_identity=mock_user_identity)

        mock_prepare_secrets.return_value = ([], [])
        mock_get_app.return_value = None
        mock_retag.side_effect = RuntimeError("Docker pull failed")

        # Call deploy_revision with nonexistent existing_image_tag
        with pytest.raises(RuntimeError, match="does not exist or retagging failed"):
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
                image_name="myapp",
                image_tag="prod-20231215120000",
                location="eastus",
                stage="prod",
                target_port=8080,
                cpu=1.0,
                memory="2.0",
                min_replicas=1,
                max_replicas=3,
                secret_key_vault_config=mock_secret_config,
                env_var_names=[],
                revision_suffix="prod-20231215120000",
                existing_image_tag="nonexistent-tag",
            )

    @patch("cc_scripts.aca.deploy_aca._wait_for_revision_activation")
    @patch("cc_scripts.aca.deploy_aca._get_container_app")
    @patch("cc_scripts.utils.docker.pull_retag_and_push_image")
    @patch("cc_scripts.aca.deploy_aca._prepare_secrets_and_env_vars")
    def test_deploy_revision_without_existing_image_tag(
        self, mock_prepare_secrets, mock_retag, mock_get_app, mock_wait
    ):
        """Test deploy_revision works normally when existing_image_tag is not provided."""
        # Setup mocks
        mock_client = Mock()
        mock_env = Mock(id="env-id")
        mock_user_identity = Mock(resourceId="identity-id")
        mock_secret_config = Mock(secret_names=[], user_identity=mock_user_identity)

        mock_prepare_secrets.return_value = ([], [])
        mock_get_app.return_value = None
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
            image_name="myapp",
            image_tag="prod-20231215120000",
            location="eastus",
            stage="prod",
            target_port=8080,
            cpu=1.0,
            memory="2.0",
            min_replicas=1,
            max_replicas=3,
            secret_key_vault_config=mock_secret_config,
            env_var_names=[],
            revision_suffix="prod-20231215120000",
        )

        # Verify retag was NOT called
        mock_retag.assert_not_called()

        # Verify deployment succeeded
        assert result.revision_name == "myapp--prod-20231215120000"
        assert result.active is True


class TestGetAcaDockerImageName:
    """Tests for get_aca_docker_image_name function."""

    def test_get_aca_docker_image_name(self):
        """Test constructing full image name."""
        result = get_aca_docker_image_name("registry.azurecr.io", "myapp", "prod-20231215120000")
        assert result == "registry.azurecr.io/myapp:prod-20231215120000"
