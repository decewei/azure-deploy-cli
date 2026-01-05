import azure_deploy_cli


class TestPackageExports:
    def test_version_is_defined(self):
        assert hasattr(azure_deploy_cli, "__version__")
        # Version is now dynamic from setuptools-scm, so just check it's a string
        assert isinstance(azure_deploy_cli.__version__, str)
        assert len(azure_deploy_cli.__version__) > 0

    def test_model_exports(self):
        assert hasattr(azure_deploy_cli, "SPAuthCredentials")
        assert hasattr(azure_deploy_cli, "SPAuthCredentialsWithSecret")
        assert hasattr(azure_deploy_cli, "SPCreateResult")
        assert hasattr(azure_deploy_cli, "RoleConfig")
        assert hasattr(azure_deploy_cli, "RoleDefinition")
        assert hasattr(azure_deploy_cli, "ManagedIdentity")
        assert hasattr(azure_deploy_cli, "AzureGroup")

    def test_function_exports(self):
        assert hasattr(azure_deploy_cli, "create_sp")
        assert hasattr(azure_deploy_cli, "reset_sp_credentials")
        assert hasattr(azure_deploy_cli, "create_or_get_user_identity")
        assert hasattr(azure_deploy_cli, "delete_user_identity")
        assert hasattr(azure_deploy_cli, "get_identity_principal_id")
        assert hasattr(azure_deploy_cli, "assign_roles")

    def test_all_exports_match_all_list(self):
        expected_exports = [
            "SPAuthCredentials",
            "SPAuthCredentialsWithSecret",
            "SPCreateResult",
            "RoleConfig",
            "RoleDefinition",
            "ManagedIdentity",
            "AzureGroup",
            "create_sp",
            "reset_sp_credentials",
            "create_or_get_user_identity",
            "delete_user_identity",
            "get_identity_principal_id",
            "assign_roles",
        ]
        for export in expected_exports:
            assert export in azure_deploy_cli.__all__, f"{export} not in __all__"
