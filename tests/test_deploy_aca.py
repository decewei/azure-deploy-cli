from unittest.mock import Mock

from azure_deploy_cli.aca.deploy_aca import (
    _get_active_revisions_by_label_group,
    _get_container_app,
    _get_latest_revision_by_label,
    deactivate_unused_revisions,
    generate_revision_name,
)


class TestGetRevisionName:
    """Tests for _get_revision_name function."""

    def test_basic_revision_name(self):
        """Test basic revision name generation."""
        result = generate_revision_name("myapp", "prod-20231215120000", "prod")
        assert result == "myapp--prod-20231215120000"

    def test_with_special_characters(self):
        """Test revision name with special characters."""
        result = generate_revision_name("my-app-123", "staging-20231215120000", "staging")
        assert result == "my-app-123--staging-20231215120000"


def create_mock_revision(name):
    mock_rev = Mock()
    mock_rev.name = name
    mock_rev.active = True
    mock_rev.health_state = "Healthy"
    mock_rev.provisioning_state = "Provisioned"
    mock_rev.running_state = "Running"

    # Mock the nested structure for template and containers
    mock_template = Mock()
    mock_container = Mock()
    mock_container.image = f"example.com/image-for-{name}"
    mock_template.containers = [mock_container]
    mock_rev.template = mock_template

    return mock_rev


def create_mock_revisions(names: list[str]):
    return [create_mock_revision(name) for name in names]


class TestGetLatestRevisionByLabel:
    """Tests for _get_latest_revision_by_label function."""

    def test_returns_latest_revision(self):
        """Test that the latest (last in sorted list) revision is returned."""
        label_revision_groups = {
            "prod": create_mock_revisions(["app--prod-20231214120000", "app--prod-20231215120000"]),
            "staging": create_mock_revision(["app--staging-20231215120000"]),
        }
        result = _get_latest_revision_by_label(label_revision_groups, "prod")
        assert result is not None
        assert result.name == "app--prod-20231215120000"

    def test_returns_single_revision(self):
        """Test with only one revision for a label."""
        label_revision_groups = {"staging": create_mock_revisions(["app--staging-20231215120000"])}
        result = _get_latest_revision_by_label(label_revision_groups, "staging")
        assert result is not None
        assert result.name == "app--staging-20231215120000"

    def test_returns_none_when_label_not_found(self):
        """Test that None is returned when label doesn't exist."""
        label_revision_groups = {"prod": create_mock_revisions(["app--prod-20231215120000"])}
        result = _get_latest_revision_by_label(label_revision_groups, "staging")
        assert result is None

    def test_returns_none_when_empty_revisions_list(self):
        """Test that None is returned when revisions list is empty."""
        label_revision_groups: dict[str, list] = {"prod": []}
        result = _get_latest_revision_by_label(label_revision_groups, "prod")
        assert result is None


def get_revision_names(revisions: list) -> list[str]:
    return [rev.name for rev in revisions]


class TestGetRevisionsByLabelGroup:
    """Tests for _get_revisions_by_label_group function."""

    def test_groups_revisions_by_label(self):
        """Test that revisions are correctly grouped by label."""
        mock_client = Mock()

        def create_mock_revision(name):
            mock_rev = Mock()
            mock_rev.name = name
            mock_rev.active = True
            mock_rev.health_state = "Healthy"
            mock_rev.provisioning_state = "Provisioned"
            mock_rev.running_state = "Running"
            return mock_rev

        mock_revisions = [
            create_mock_revision("app--prod-20231215120000"),
            create_mock_revision("app--prod-20231214120000"),
            create_mock_revision("app--staging-20231215120000"),
        ]
        mock_client.container_apps_revisions.list_revisions.return_value = mock_revisions

        result = _get_active_revisions_by_label_group(
            mock_client, "rg", "app", labels={"prod", "staging"}
        )

        assert "prod" in result
        assert "staging" in result
        assert len(result["prod"]) == 2
        assert len(result["staging"]) == 1
        assert get_revision_names(result["prod"]) == [
            "app--prod-20231214120000",
            "app--prod-20231215120000",
        ]
        assert get_revision_names(result["staging"]) == ["app--staging-20231215120000"]

    def test_excludes_non_matching_labels(self):
        """Test that revisions with non-matching labels are excluded."""
        mock_client = Mock()

        def create_mock_revision(name):
            mock_rev = Mock()
            mock_rev.name = name
            mock_rev.active = True
            mock_rev.health_state = "Healthy"
            mock_rev.provisioning_state = "Provisioned"
            mock_rev.running_state = "Running"
            return mock_rev

        mock_revisions = [
            create_mock_revision("app--prod-20231215120000"),
            create_mock_revision("app--dev-20231215120000"),
        ]
        mock_client.container_apps_revisions.list_revisions.return_value = mock_revisions

        result = _get_active_revisions_by_label_group(mock_client, "rg", "app", labels={"prod"})

        assert "prod" in result
        assert "dev" not in result
        assert len(result["prod"]) == 1


class TestGetContainerApp:
    """Tests for _get_container_app function."""

    def test_returns_app_when_exists(self):
        """Test that app is returned when it exists."""
        mock_client = Mock()
        mock_app = Mock()
        mock_client.container_apps.get.return_value = mock_app

        result = _get_container_app(mock_client, "rg", "app")

        assert result == mock_app

    def test_returns_none_when_app_not_found(self):
        """Test that None is returned when the app doesn't exist."""
        from azure.core.exceptions import ResourceNotFoundError

        mock_client = Mock()
        mock_client.container_apps.get.side_effect = ResourceNotFoundError("Not found")

        result = _get_container_app(mock_client, "rg", "app")

        assert result is None


class TestDeactivateUnusedRevisions:
    """Tests for deactivate_unused_revisions function."""

    def test_deactivates_unused_revisions(self):
        """Test that revisions not receiving traffic are deactivated."""
        mock_client = Mock()
        active_revisions = {"app--prod-20231215120000"}
        label_revision_groups = {
            "prod": create_mock_revisions(["app--prod-20231214120000", "app--prod-20231215120000"]),
        }

        deactivate_unused_revisions(
            mock_client, "rg", "app", active_revisions, label_revision_groups
        )

        mock_client.container_apps_revisions.deactivate_revision.assert_called_once_with(
            resource_group_name="rg",
            container_app_name="app",
            revision_name="app--prod-20231214120000",
        )

    def test_no_deactivation_when_all_active(self):
        """Test that no revisions are deactivated when all receive traffic."""
        mock_client = Mock()
        active_revisions = {"app--prod-20231215120000", "app--prod-20231214120000"}
        label_revision_groups = {
            "prod": create_mock_revisions(["app--prod-20231214120000", "app--prod-20231215120000"]),
        }

        deactivate_unused_revisions(
            mock_client, "rg", "app", active_revisions, label_revision_groups
        )

        mock_client.container_apps_revisions.deactivate_revision.assert_not_called()

    def test_continues_on_deactivation_error(self):
        """Test that deactivation continues even if one revision fails."""
        from azure.core.exceptions import HttpResponseError

        mock_client = Mock()
        mock_client.container_apps_revisions.deactivate_revision.side_effect = [
            HttpResponseError("Deactivation failed"),
            None,
        ]
        active_revisions = {"app--prod-20231216120000"}
        label_revision_groups = {
            "prod": create_mock_revisions(
                [
                    "app--prod-20231214120000",
                    "app--prod-20231215120000",
                    "app--prod-20231216120000",
                ]
            ),
        }

        # Should not raise an exception
        deactivate_unused_revisions(
            mock_client, "rg", "app", active_revisions, label_revision_groups
        )

        # Both deactivations should have been attempted
        assert mock_client.container_apps_revisions.deactivate_revision.call_count == 2
