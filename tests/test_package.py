import cc_scripts


class TestPackageExports:
    def test_version_is_defined(self):
        assert hasattr(cc_scripts, "__version__")
        # Version is now dynamic from setuptools-scm, so just check it's a string
        assert isinstance(cc_scripts.__version__, str)
        assert len(cc_scripts.__version__) > 0

    def test_model_exports(self):
        assert hasattr(cc_scripts, "SPAuthCredentials")
        assert hasattr(cc_scripts, "SPAuthCredentialsWithSecret")
        assert hasattr(cc_scripts, "SPCreateResult")
        assert hasattr(cc_scripts, "RoleConfig")
        assert hasattr(cc_scripts, "RoleDefinition")
        assert hasattr(cc_scripts, "ManagedIdentity")
        assert hasattr(cc_scripts, "AzureGroup")

    def test_function_exports(self):
        assert hasattr(cc_scripts, "create_sp")
        assert hasattr(cc_scripts, "reset_sp_credentials")
        assert hasattr(cc_scripts, "create_or_get_user_identity")
        assert hasattr(cc_scripts, "delete_user_identity")
        assert hasattr(cc_scripts, "get_identity_principal_id")
        assert hasattr(cc_scripts, "assign_roles")

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
            assert export in cc_scripts.__all__, f"{export} not in __all__"
