from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, field_validator


@dataclass
class SPAuthCredentialsWithSecret:
    clientId: str
    clientSecret: str
    subscriptionId: str
    tenantId: str

    def to_dict(self):
        return {
            "clientId": self.clientId,
            "clientSecret": self.clientSecret,
            "subscriptionId": self.subscriptionId,
            "tenantId": self.tenantId,
        }

    def __post_init__(self) -> None:
        if not self.clientId or not self.clientId.strip():
            raise ValueError("clientId cannot be empty")
        if self.clientSecret is None:
            raise ValueError("clientSecret cannot be None")
        if not self.clientSecret or not self.clientSecret.strip():
            raise ValueError("clientSecret cannot be empty")
        if not self.subscriptionId or not self.subscriptionId.strip():
            raise ValueError("subscriptionId cannot be empty")
        if not self.tenantId or not self.tenantId.strip():
            raise ValueError("tenantId cannot be empty")


@dataclass
class SPAuthCredentials:
    clientId: str
    subscriptionId: str
    tenantId: str

    def to_dict(self):
        return {
            "clientId": self.clientId,
            "subscriptionId": self.subscriptionId,
            "tenantId": self.tenantId,
        }

    def __post_init__(self) -> None:
        if not self.clientId or not self.clientId.strip():
            raise ValueError("clientId cannot be empty")
        if not self.subscriptionId or not self.subscriptionId.strip():
            raise ValueError("subscriptionId cannot be empty")
        if not self.tenantId or not self.tenantId.strip():
            raise ValueError("tenantId cannot be empty")


@dataclass
class SPCreateResult:
    """Result of service principal creation."""

    objectId: str
    authCredentials: SPAuthCredentialsWithSecret | SPAuthCredentials

    def __post_init__(self) -> None:
        if not self.objectId or not self.objectId.strip():
            raise ValueError("objectId cannot be empty")


@dataclass
class AzureGroup:
    """Result of security group lookup for role assignment."""

    objectId: str
    displayName: str

    def __post_init__(self) -> None:
        if not self.objectId or not self.objectId.strip():
            raise ValueError("objectId cannot be empty")
        if not self.displayName or not self.displayName.strip():
            raise ValueError("displayName cannot be empty")


@dataclass
class ManagedIdentity:
    """Result of managed identity creation/retrieval."""

    resourceId: str  # Full resource ID
    principalId: str  # Object ID for role assignment

    def __post_init__(self) -> None:
        if not self.resourceId or not self.resourceId.strip():
            raise ValueError("resourceId cannot be empty")
        if not self.principalId or not self.principalId.strip():
            raise ValueError("principalId cannot be empty")


class RoleDefinition(BaseModel):
    """Role definition for assignment to service principals."""

    type: str = "rbac"  # 'cosmos-db' or 'rbac'
    account: str | None = None  # Required for cosmos-db type
    role: str  # Role name (varies by type)
    scope: str  # Resource scope (for rbac) or '/' (for cosmos-db)
    description: str | None = None

    @field_validator("role")
    @classmethod
    def role_not_empty(cls, v: str) -> str:
        """Validate that role is not empty"""
        if not v or not v.strip():
            raise ValueError("Role cannot be empty")
        return v.strip()

    @field_validator("scope")
    @classmethod
    def scope_not_empty(cls, v: str) -> str:
        """Validate that scope is not empty"""
        if not v or not v.strip():
            raise ValueError("Scope cannot be empty")
        return v.strip()

    @field_validator("type")
    @classmethod
    def type_valid(cls, v: str) -> str:
        """Validate that type is one of allowed values"""
        valid_types = {"rbac", "cosmos-db"}
        if v not in valid_types:
            raise ValueError(f"Type must be one of {valid_types}, got '{v}'")
        return v

    def model_post_init(self, __context: Any) -> None:
        """Validate cosmos-db specific requirements after initialization"""
        if self.type == "cosmos-db" and not self.account:
            raise ValueError("Cosmos DB role configuration must include 'account' field")

    class Config:
        """Pydantic config"""

        str_strip_whitespace = True


class RoleConfig(BaseModel):
    """Configuration for role assignments."""

    description: str
    roles: list[RoleDefinition]

    @field_validator("description")
    @classmethod
    def description_not_empty(cls, v: str) -> str:
        """Validate that description is not empty"""
        if not v or not v.strip():
            raise ValueError("Description cannot be empty")
        return v.strip()

    @field_validator("roles")
    @classmethod
    def roles_not_empty(cls, v: list[RoleDefinition]) -> list[RoleDefinition]:
        """Validate that roles list is not empty"""
        if not v:
            raise ValueError("Roles list cannot be empty")
        return v

    class Config:
        """Pydantic config"""

        str_strip_whitespace = True
