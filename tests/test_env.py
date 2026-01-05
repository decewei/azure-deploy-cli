import tempfile
from pathlib import Path

import pytest

from azure_deploy_cli.utils.env import (
    add_var_to_env_file,
    load_env_vars_from_files,
    substitute_env_vars,
)


class TestSubstituteEnvVars:
    def test_simple_substitution(self):
        env_vars = {"VAR1": "value1", "VAR2": "value2"}
        result = substitute_env_vars("Hello ${VAR1} and ${VAR2}", env_vars)
        assert result == "Hello value1 and value2"

    def test_no_substitution(self):
        env_vars = {"VAR1": "value1"}
        result = substitute_env_vars("Hello world", env_vars)
        assert result == "Hello world"

    def test_azure_scope_substitution(self):
        env_vars = {
            "SUBSCRIPTION_ID": "12345678-1234-1234-1234-123456789012",
            "RESOURCE_GROUP": "my-rg",
            "OPENAI_RESOURCE_NAME": "my-openai",
        }
        scope = (
            "/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/"
            "${RESOURCE_GROUP}/providers/Microsoft.CognitiveServices/accounts/"
            "${OPENAI_RESOURCE_NAME}"
        )
        result = substitute_env_vars(scope, env_vars)
        expected = (
            "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/"
            "my-rg/providers/Microsoft.CognitiveServices/accounts/"
            "my-openai"
        )
        assert result == expected

    def test_missing_variable_raises_error(self):
        env_vars = {"VAR1": "value1"}
        with pytest.raises(KeyError):
            substitute_env_vars("Hello ${VAR1} and ${MISSING}", env_vars)


class TestLoadEnvVarsFromFiles:
    def test_load_single_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("KEY1=value1\n")
            f.write("KEY2=value2\n")
            f.flush()
            result = load_env_vars_from_files([Path(f.name)])
            assert result == {"KEY1": "value1", "KEY2": "value2"}

    def test_load_multiple_files(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f1:
            f1.write("KEY1=value1\n")
            f1.write("KEY2=value2\n")
            f1.flush()

            with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f2:
                f2.write("KEY2=override\n")
                f2.write("KEY3=value3\n")
                f2.flush()

                result = load_env_vars_from_files([Path(f1.name), Path(f2.name)])
                assert result == {"KEY1": "value1", "KEY2": "override", "KEY3": "value3"}

    def test_empty_list(self):
        result = load_env_vars_from_files([])
        assert result == {}

    def test_none_input(self):
        result = load_env_vars_from_files(None)
        assert result == {}


class TestAddVarToEnvFile:
    def test_add_to_new_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            add_var_to_env_file({"KEY": "value"}, env_path)
            content = env_path.read_text()
            assert "KEY=value" in content

    def test_add_to_existing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            env_path.write_text("EXISTING=value\n")
            add_var_to_env_file({"NEW_KEY": "new_value"}, env_path)
            content = env_path.read_text()
            assert "EXISTING=value" in content
            assert "NEW_KEY=new_value" in content

    def test_update_existing_variable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            env_path.write_text("KEY=old_value\n")
            add_var_to_env_file({"KEY": "new_value"}, env_path)
            content = env_path.read_text()
            assert "KEY=new_value" in content
            assert "old_value" not in content

    def test_add_multiple_variables(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            add_var_to_env_file({"KEY1": "value1", "KEY2": "value2"}, env_path)
            content = env_path.read_text()
            assert "KEY1=value1" in content
            assert "KEY2=value2" in content
