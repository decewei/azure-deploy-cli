from azure.mgmt.keyvault import KeyVaultManagementClient

from ..utils.azure_cli import get_credential


def get_key_vault_client(
    subscription_id: str, resource_group: str, key_vault_name: str
) -> KeyVaultManagementClient:
    credential = get_credential()
    kv_client = KeyVaultManagementClient(credential, subscription_id)
    return kv_client
