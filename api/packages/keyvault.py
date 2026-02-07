import os
from decouple import config
from django.conf import settings
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential
from azure.identity import ClientSecretCredential

tenant_id = config("AZURE_TENANT_ID")
client_id = config("AZURE_CLIENT_ID")
client_secret = config("AZURE_CLIENT_SECRET")

# credential = DefaultAzureCredential()
credential = ClientSecretCredential(tenant_id, client_id, client_secret)
keyVaultName = config("AZURE_KEY_VAULT_NAME", default="")
KVUri = f"https://{keyVaultName}.vault.azure.net"
client = SecretClient(vault_url=KVUri, credential=credential)

def get_secret(secretName):
    """Fetch secret from Azure Key Vault"""
    try:
        # secrets = client.list_properties_of_secrets()
        # all_secret = [secret.name for secret in secrets]
        # print(all_secret)
        retrieved_secret = client.get_secret(secretName)
        return retrieved_secret.value
    except Exception as e:
        print(f"Error fetching secret {secretName}: {e}")
        return ""

def set_secret(secretName, secretValue):
    """Set secret to Azure Key Vault"""
    try:
        client.set_secret(secretName, secretValue)
        return True
    except Exception as e:
        print(f"Error fetching secret {secretName}: {e}")
        return None

def delete_secret(secretName):
    """Delete secret to Azure Key Vault"""
    try:
        client.begin_delete_secret(secretName)
        return True
    except Exception as e:
        print(f"Error fetching secret {secretName}: {e}")
        return None          

