from dataclasses import dataclass

from azure.mgmt.keyvault import KeyVaultManagementClient

from ..identity.models import ManagedIdentity


@dataclass
class SecretKeyVaultConfig:
    key_vault_client: KeyVaultManagementClient
    key_vault_name: str
    secret_names: list[str]
    user_identity: ManagedIdentity


@dataclass
class RevisionDeploymentResult:
    """Result of a revision deployment operation."""

    revision_name: str
    active: bool
    health_state: str
    provisioning_state: str
    running_state: str
    revision_url: str | None

    @property
    def is_healthy(self) -> bool:
        """Check if the revision is healthy and active."""
        return (
            self.active
            and self.health_state == "Healthy"
            and self.provisioning_state == "Provisioned"
            and self.running_state not in ("Stopped", "Degraded", "Failed")
        )
