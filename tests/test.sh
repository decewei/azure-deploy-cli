#!/bin/bash

script_dir=$(dirname "$0")

# allow skipping login
skip_login=false
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -s|--skip-login) skip_login=true ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

if [ "$skip_login" = false ]; then
    az login
fi

echo -e "\n--- Testing create-sp-and-assign-roles ---\n"
python3 -m cc_scripts.cli azid create-sp-and-assign-roles \
    --sp-name "test-sp" \
    --roles-config $script_dir/roles-config.json \
    --env-vars-files $script_dir/.env.role-public \
    --env-file $script_dir/.env.file \
    --print

echo -e "\n--- Testing azid login ---\n"
python3 -m cc_scripts.cli azid login --env-file ./$script_dir/.env.file

echo -e "\n--- Testing create-sp-and-assign-roles with secret reset ---\n"
az login
python3 -m cc_scripts.cli azid create-sp-and-assign-roles \
    --sp-name "test-sp" \
    --roles-config $script_dir/roles-config.json \
    --env-vars-files $script_dir/.env.role-public \
    --env-file $script_dir/.env.file \
    --reset-secrets \
    --print

echo -e "\n--- Testing reset-sp-credentials ---\n"
python3 -m cc_scripts.cli azid reset-sp-credentials \
    --sp-name "test-sp" \
    --env-file $script_dir/.env.file

echo -e "\n--- Testing delete-sp ---\n"
python3 -m cc_scripts.cli azid delete-sp \
    --sp-name "test-sp"

echo -e "\n========== GROUP LIFECYCLE TESTS ==========\n"

TEST_GROUP_NAME="test-group-$(date +%s)"
GROUP_ID=$(az ad group create --display-name "$TEST_GROUP_NAME" --mail-nickname "$TEST_GROUP_NAME" --query "id" -o tsv)
if [ -z "$GROUP_ID" ]; then
    echo "Failed to create test group"
    exit 1
fi
echo "Created group with ID: $GROUP_ID"

# Test: Assign roles to group
echo -e "\n--- Assigning roles to test group ---\n"
python3 -m cc_scripts.cli azid assign-roles-to-group \
    --group-name "$TEST_GROUP_NAME" \
    --roles-config $script_dir/roles-config.json \
    --env-vars-files $script_dir/.env.role-public

az ad group delete --group "$TEST_GROUP_NAME" --output none

echo "Successfully deleted test group"

echo -e "\n========== MANAGED IDENTITY LIFECYCLE TESTS ==========\n"

# Get subscription and location for tests
SUBSCRIPTION_ID=$(az account show --query "id" -o tsv)
LOCATION="eastus"

TEST_IDENTITY_NAME="test-identity-$(date +%s)"
echo -e "\n--- Creating and assigning roles to test managed identity: $TEST_IDENTITY_NAME ---\n"
TEST_RG="test-rg-$(date +%s)"

# Only create resource group if it doesn't exist
if ! az group show -n "$TEST_RG" &>/dev/null; then
    echo "Creating test resource group: $TEST_RG"
    az group create -n "$TEST_RG" -l "$LOCATION" --output none
fi

python3 -m cc_scripts.cli azid create-and-assign-managed-identity \
    --identity-name "$TEST_IDENTITY_NAME" \
    --resource-group "$TEST_RG" \
    --location "$LOCATION" \
    --roles-config $script_dir/roles-config.json \
    --env-vars-files $script_dir/.env.role-public

# Test: Verify identity and roles were created
echo -e "\n--- Verifying managed identity and role assignment ---\n"
IDENTITY_ID=$(az identity show \
    -n "$TEST_IDENTITY_NAME" \
    -g "$TEST_RG" \
    --query "id" -o tsv)

if [ -z "$IDENTITY_ID" ]; then
    echo "Failed to find created managed identity"
    exit 1
fi

echo "Found managed identity: $IDENTITY_ID"

PRINCIPAL_ID=$(az identity show \
    --ids "$IDENTITY_ID" \
    --query "principalId" -o tsv)

echo "Principal ID: $PRINCIPAL_ID"

az identity delete --ids "$IDENTITY_ID" --output none
echo "Successfully deleted test managed identity"

# Clean up test resource group if we created it
echo -e "Cleaning up test resource group: $TEST_RG"
az group delete -n "$TEST_RG" --yes

echo -e "\n========== ALL TESTS COMPLETED SUCCESSFULLY ==========\n"
