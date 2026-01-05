#!/bin/bash

# functions below taken from: https://stackoverflow.com/a/25515370
yell() { echo "$0: $*" >&2; }
die() {
  yell "$*"
  exit 111
}

az --verison

destroy() {
  CUSTOM_DOMAIN=$1
  echo "destroying domain: $CUSTOM_DOMAIN"
  # get the managed cert using the custom domain
  CERTIFICATE_ID=$(
    az containerapp env certificate list \
      -g $ENV_RESOURCE_GROUP \
      -n $CONTAINER_APP_ENV_NAME \
      --managed-certificates-only \
      --query "[?properties.subjectName=='$CUSTOM_DOMAIN'].id" \
      --output tsv
  )

  # destroy the cert
  az containerapp env certificate delete \
    -g $ENV_RESOURCE_GROUP \
    -n $CONTAINER_APP_ENV_NAME \
    --certificate $CERTIFICATE_ID --yes
  echo "destroyed the managed certificate"

  # remove the custom domain from the container app
  az containerapp hostname delete --hostname $CUSTOM_DOMAIN \
    -g $RESOURCE_GROUP \
    -n $CONTAINER_APP_NAME
  echo "removed the custom domain from the container app"
}

# split CUSTOM_DOMAINS by comma with whitespaces
# loop through each domain and destroy it
IFS=', ' read -r -a DOMAINS <<<"$CUSTOM_DOMAINS"
for DOMAIN in "${DOMAINS[@]}"; do
  destroy "$DOMAIN"
done
