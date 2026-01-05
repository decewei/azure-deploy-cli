#!/bin/bash

###############################################################################
# Azure Container App Certificate Binding Script
# Cr. to: https://gist.github.com/LynnAU/131426847d2793c76e36548f9937f966#file-create-sh
#
# This script binds managed certificates to Azure Container App domains.
# It validates DNS ASUID records, creates managed certificates if needed,
# and binds them to custom domains.
###############################################################################

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --custom-domains)
      CUSTOM_DOMAINS="$2"
      shift 2
      ;;
    --container-app-name)
      CONTAINER_APP_NAME="$2"
      shift 2
      ;;
    --resource-group)
      RESOURCE_GROUP="$2"
      shift 2
      ;;
    --env-resource-group)
      ENV_RESOURCE_GROUP="$2"
      shift 2
      ;;
    --container-app-env-name)
      CONTAINER_APP_ENV_NAME="$2"
      shift 2
      ;;
    --help)
      cat <<EOF
Usage: $0 [OPTIONS]

Bind managed certificates to Azure Container App custom domains.

OPTIONS:
  --custom-domains DOMAINS            Comma-separated list of custom domains (required)
  --container-app-name NAME           Container App name (required)
  --resource-group GROUP              Resource group name (required)
  --env-resource-group ENV_GROUP      Environment resource group name (required)
  --container-app-env-name ENV_NAME   Container App Environment name (required)
  --help                              Display this help message

EXAMPLES:
  $0 \\
    --custom-domains "example.com,www.example.com" \\
    --container-app-name my-app \\
    --resource-group my-rg \\
    --env-resource-group my-env-rg \\
    --container-app-env-name my-env

EOF
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# Validate required arguments
if [[ -z "$CUSTOM_DOMAINS" ]] || [[ -z "$CONTAINER_APP_NAME" ]] || \
   [[ -z "$RESOURCE_GROUP" ]] || [[ -z "$ENV_RESOURCE_GROUP" ]] || \
   [[ -z "$CONTAINER_APP_ENV_NAME" ]]; then
  echo "Error: Missing required arguments"
  echo "Usage: $0 --custom-domains DOMAINS --container-app-name NAME --resource-group GROUP --env-resource-group ENV_GROUP --container-app-env-name ENV_NAME"
  echo "Use --help for more information"
  exit 1
fi

# functions below taken from: https://stackoverflow.com/a/25515370
yell() { echo "$0: $*" >&2; }
die() {
  yell "$*"
  exit 111
}

bind() {
  CUSTOM_DOMAIN=$1
  echo "binding domain: $CUSTOM_DOMAIN"
  # az --verison
  # use dig to verify the asuid txt record exists on the DNS host
  # azure requires this to exist prior to adding the domain
  # azure's dns can also be slow, so best to check propagation
  tries=0
  until [ "$tries" -ge 12 ]; do
    [[ ! -z $(dig @8.8.8.8 txt asuid.$CUSTOM_DOMAIN +short) ]] && break
    tries=$((tries + 1))
    sleep 10
  done
  if [ "$tries" -ge 12 ]; then
    die "'asuid.${CUSTOM_DOMAIN}' txt record does not exist"
  fi

  echo "took $tries trie(s) for the dns record to exist publically"

  # check if the hostname already exists on the container app
  # if not, add it since it's required to provision a managed cert
  # TODO: DOMAINS! this doesn't work for an array of custom domains
  DOES_CUSTOM_DOMAIN_EXIST=$(
    az containerapp hostname list \
      -n $CONTAINER_APP_NAME \
      -g $RESOURCE_GROUP \
      --query "[?name=='$CUSTOM_DOMAIN'].name" \
      --output tsv
  )
  if [ -z "${DOES_CUSTOM_DOMAIN_EXIST}" ]; then
    echo "adding custom hostname to container app first since it does not exist yet"
    az containerapp hostname add \
      -n $CONTAINER_APP_NAME \
      -g $RESOURCE_GROUP \
      --hostname $CUSTOM_DOMAIN \
      --output none
  fi

  # check if a managed cert for the domain already exists
  # if it does not exist, provision one
  # if it does, save its name to use for binding it later
  MANAGED_CERTIFICATE_ID=$(
    az containerapp env certificate list \
      -g $ENV_RESOURCE_GROUP \
      -n $CONTAINER_APP_ENV_NAME \
      --managed-certificates-only \
      --query "[?properties.subjectName=='$CUSTOM_DOMAIN'].id" \
      --output tsv
  )
  if [ -z "${MANAGED_CERTIFICATE_ID}" ]; then
    MANAGED_CERTIFICATE_ID=$(
      az containerapp env certificate create \
        -g $ENV_RESOURCE_GROUP \
        -n $CONTAINER_APP_ENV_NAME \
        --hostname $CUSTOM_DOMAIN \
        --validation-method CNAME \
        --query "id" \
        --output tsv
    )
    echo "created cert for '$CUSTOM_DOMAIN'. waiting for it to provision now..."

    # poll azcli to check for the certificate status
    # this is better than waiting 5 minutes, because it could be
    # faster and we get to exit the script faster
    # ---
    # the default 20 tries means it'll check for 5 mins
    # at 15 second intervals
    tries=0
    until [ "$tries" -ge 20 ]; do
      STATE=$(
        az containerapp env certificate list \
          -g $ENV_RESOURCE_GROUP \
          -n $CONTAINER_APP_ENV_NAME \
          --managed-certificates-only \
          --query "[?properties.subjectName=='$CUSTOM_DOMAIN'].properties.provisioningState" \
          --output tsv
      )
      [[ $STATE == "Succeeded" ]] && break
      tries=$((tries + 1))

      sleep 15
    done
    if [ "$tries" -ge 20 ]; then
      die "waited for 5 minutes, checked the certificate status 20 times and its not done. check azure portal..."
    fi
  else
    echo "found existing cert in the env. proceeding to use that"
  fi

  # check if the cert has already been bound
  # if not, bind it then
  IS_CERT_ALREADY_BOUND=$(
    az containerapp hostname list \
      -n $CONTAINER_APP_NAME \
      -g $RESOURCE_GROUP \
      --query "[?name=='$CUSTOM_DOMAIN'].bindingType" \
      --output tsv
  )
  if [ $IS_CERT_ALREADY_BOUND = "SniEnabled" ]; then
    echo "cert is already bound, exiting..."
  else
    # try bind the cert to the container app
    echo "cert successfully provisioned. binding the cert id to the hostname"
    az containerapp hostname bind \
      -g $RESOURCE_GROUP \
      -n $CONTAINER_APP_NAME \
      --hostname $CUSTOM_DOMAIN \
      --environment $CONTAINER_APP_ENV_NAME \
      --certificate $MANAGED_CERTIFICATE_ID \
      --output none
    echo "finished binding. the domain is now secured and ready to use"
  fi
}

# split CUSTOM_DOMAINS by comma into an array
# loop through the array and bind each domain
IFS=', ' read -r -a DOMAINS <<<"$CUSTOM_DOMAINS"
for DOMAIN in "${DOMAINS[@]}"; do
  bind "$DOMAIN"
done
