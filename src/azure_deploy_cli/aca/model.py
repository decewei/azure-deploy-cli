from dataclasses import dataclass
from typing import Any

from azure.mgmt.appcontainers.models import ContainerAppProbe
from azure.mgmt.keyvault import KeyVaultManagementClient
from pydantic import BaseModel, Field, field_validator

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


class ContainerConfig(BaseModel):
    """Configuration for a single container from YAML."""

    name: str
    image_name: str = Field(..., description="Just the image name, no registry or tag")
    cpu: float
    memory: str
    env_vars: list[str] = Field(
        default_factory=list, description="List of environment variable names to load"
    )
    probes: list[ContainerAppProbe] | None = Field(
        default=None, description="List of probe configurations"
    )
    existing_image_tag: str | None = Field(default=None, description="Optional tag to retag from")
    dockerfile: str | None = Field(default=None, description="Optional dockerfile path")

    def post_init(self):
        if not (self.dockerfile or self.existing_image_tag):
            raise ValueError(
                f"Container '{self.name}' must have either 'dockerfile' "
                f"or 'existing_image_tag' specified"
            )

    @field_validator("probes", mode="before")
    @classmethod
    def parse_probes(cls, v: list[dict[str, Any]] | None) -> list[ContainerAppProbe] | None:
        """Parse probe dictionaries to ContainerAppProbe objects."""
        if v is None:
            return None
        return [ContainerAppProbe(**probe_data) for probe_data in v]

    class Config:
        """Pydantic configuration for ContainerConfig."""

        arbitrary_types_allowed = True


class ContainerAppConfig(BaseModel):
    containers: list[ContainerConfig] = Field(
        ..., min_length=1, description="List of container configurations"
    )
