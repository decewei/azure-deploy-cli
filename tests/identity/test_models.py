import pytest

from azure_deploy_cli.identity.models import (
    AzureGroup,
    ManagedIdentity,
    RoleConfig,
    RoleDefinition,
    SPAuthCredentials,
    SPAuthCredentialsWithSecret,
    SPCreateResult,
)


class TestSPAuthCredentialsWithSecret:
    def test_valid_credentials(self):
        creds = SPAuthCredentialsWithSecret(
            clientId="test-client-id",
            clientSecret="test-secret",
            subscriptionId="test-subscription-id",
            tenantId="test-tenant-id",
        )
        assert creds.clientId == "test-client-id"
        assert creds.clientSecret == "test-secret"
        assert creds.subscriptionId == "test-subscription-id"
        assert creds.tenantId == "test-tenant-id"

    def test_to_dict(self):
        creds = SPAuthCredentialsWithSecret(
            clientId="client",
            clientSecret="secret",
            subscriptionId="sub",
            tenantId="tenant",
        )
        result = creds.to_dict()
        assert result == {
            "clientId": "client",
            "clientSecret": "secret",
            "subscriptionId": "sub",
            "tenantId": "tenant",
        }

    def test_empty_client_id_raises_error(self):
        with pytest.raises(ValueError, match="clientId cannot be empty"):
            SPAuthCredentialsWithSecret(
                clientId="",
                clientSecret="secret",
                subscriptionId="sub",
                tenantId="tenant",
            )

    def test_empty_client_secret_raises_error(self):
        with pytest.raises(ValueError, match="clientSecret cannot be empty"):
            SPAuthCredentialsWithSecret(
                clientId="client",
                clientSecret="",
                subscriptionId="sub",
                tenantId="tenant",
            )

    def test_whitespace_only_client_id_raises_error(self):
        with pytest.raises(ValueError, match="clientId cannot be empty"):
            SPAuthCredentialsWithSecret(
                clientId="   ",
                clientSecret="secret",
                subscriptionId="sub",
                tenantId="tenant",
            )


class TestSPAuthCredentials:
    def test_valid_credentials(self):
        creds = SPAuthCredentials(
            clientId="test-client-id",
            subscriptionId="test-subscription-id",
            tenantId="test-tenant-id",
        )
        assert creds.clientId == "test-client-id"
        assert creds.subscriptionId == "test-subscription-id"
        assert creds.tenantId == "test-tenant-id"

    def test_to_dict(self):
        creds = SPAuthCredentials(
            clientId="client",
            subscriptionId="sub",
            tenantId="tenant",
        )
        result = creds.to_dict()
        assert result == {
            "clientId": "client",
            "subscriptionId": "sub",
            "tenantId": "tenant",
        }

    def test_empty_subscription_id_raises_error(self):
        with pytest.raises(ValueError, match="subscriptionId cannot be empty"):
            SPAuthCredentials(
                clientId="client",
                subscriptionId="",
                tenantId="tenant",
            )


class TestSPCreateResult:
    def test_valid_result_with_secret(self):
        creds = SPAuthCredentialsWithSecret(
            clientId="client",
            clientSecret="secret",
            subscriptionId="sub",
            tenantId="tenant",
        )
        result = SPCreateResult(objectId="object-id", authCredentials=creds)
        assert result.objectId == "object-id"
        assert result.authCredentials == creds

    def test_valid_result_without_secret(self):
        creds = SPAuthCredentials(
            clientId="client",
            subscriptionId="sub",
            tenantId="tenant",
        )
        result = SPCreateResult(objectId="object-id", authCredentials=creds)
        assert result.objectId == "object-id"
        assert result.authCredentials == creds

    def test_empty_object_id_raises_error(self):
        creds = SPAuthCredentials(
            clientId="client",
            subscriptionId="sub",
            tenantId="tenant",
        )
        with pytest.raises(ValueError, match="objectId cannot be empty"):
            SPCreateResult(objectId="", authCredentials=creds)


class TestAzureGroup:
    def test_valid_group(self):
        group = AzureGroup(objectId="group-id", displayName="Test Group")
        assert group.objectId == "group-id"
        assert group.displayName == "Test Group"

    def test_empty_object_id_raises_error(self):
        with pytest.raises(ValueError, match="objectId cannot be empty"):
            AzureGroup(objectId="", displayName="Test Group")

    def test_empty_display_name_raises_error(self):
        with pytest.raises(ValueError, match="displayName cannot be empty"):
            AzureGroup(objectId="group-id", displayName="")


class TestManagedIdentity:
    def test_valid_identity(self):
        identity = ManagedIdentity(
            resourceId="/subscriptions/sub/resourceGroups/rg/providers/..."
            "/Microsoft.ManagedIdentity/userAssignedIdentities/my-identity",
            principalId="principal-id",
        )
        assert identity.principalId == "principal-id"
        assert "my-identity" in identity.resourceId

    def test_empty_resource_id_raises_error(self):
        with pytest.raises(ValueError, match="resourceId cannot be empty"):
            ManagedIdentity(resourceId="", principalId="principal-id")

    def test_empty_principal_id_raises_error(self):
        with pytest.raises(ValueError, match="principalId cannot be empty"):
            ManagedIdentity(resourceId="/resource/id", principalId="")


class TestRoleDefinition:
    def test_valid_rbac_role(self):
        role = RoleDefinition(
            type="rbac",
            role="Contributor",
            scope="/subscriptions/sub-id",
        )
        assert role.type == "rbac"
        assert role.role == "Contributor"
        assert role.scope == "/subscriptions/sub-id"

    def test_valid_cosmos_db_role(self):
        role = RoleDefinition(
            type="cosmos-db",
            account="my-cosmos-account",
            role="Cosmos DB Built-in Data Contributor",
            scope="/",
        )
        assert role.type == "cosmos-db"
        assert role.account == "my-cosmos-account"
        assert role.role == "Cosmos DB Built-in Data Contributor"

    def test_invalid_type_raises_error(self):
        with pytest.raises(ValueError, match="Type must be one of"):
            RoleDefinition(
                type="invalid",
                role="Contributor",
                scope="/subscriptions/sub-id",
            )

    def test_empty_role_raises_error(self):
        with pytest.raises(ValueError, match="Role cannot be empty"):
            RoleDefinition(
                type="rbac",
                role="",
                scope="/subscriptions/sub-id",
            )

    def test_empty_scope_raises_error(self):
        with pytest.raises(ValueError, match="Scope cannot be empty"):
            RoleDefinition(
                type="rbac",
                role="Contributor",
                scope="",
            )

    def test_cosmos_db_without_account_raises_error(self):
        with pytest.raises(ValueError, match="must include 'account' field"):
            RoleDefinition(
                type="cosmos-db",
                role="Cosmos DB Built-in Data Contributor",
                scope="/",
            )


class TestRoleConfig:
    def test_valid_config(self):
        config = RoleConfig(
            description="Test role config",
            roles=[
                RoleDefinition(type="rbac", role="Contributor", scope="/subscriptions/sub-id"),
            ],
        )
        assert config.description == "Test role config"
        assert len(config.roles) == 1

    def test_empty_description_raises_error(self):
        with pytest.raises(ValueError, match="Description cannot be empty"):
            RoleConfig(
                description="",
                roles=[
                    RoleDefinition(type="rbac", role="Contributor", scope="/subscriptions/sub-id"),
                ],
            )

    def test_empty_roles_raises_error(self):
        with pytest.raises(ValueError, match="Roles list cannot be empty"):
            RoleConfig(
                description="Test config",
                roles=[],
            )
