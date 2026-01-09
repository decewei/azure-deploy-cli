# Azure Deploy CLI

Python CLI for Azure deployment automation - manage identities, roles, and Container Apps deployments.

## Version Management and Changelog

This project uses a dual-tool approach:

- **[setuptools-scm](https://setuptools-scm.readthedocs.io/)** - Automatic versioning based on git tags (dynamic at build time)
- **[commitizen](https://commitizen-tools.github.io/commitizen/)** - Version bumping and tagging with semantic versioning
- **[git-cliff](https://git-cliff.org/)** - Automatic changelog generation from conventional commits

**Release workflow:**
1. git-cliff generates changelog from commits since last tag
2. commitizen bumps version and creates git tag
3. New version is committed alongside updated changelog
4. Tag triggers PyPI publishing and GitHub Release

No manual version or changelog updates are needed.

## Quick Start

**Install for development:**

```bash
cd /path/to/azure-deploy-cli
pip install -e ".[dev]"
azd --help
```

**Use in another project:**

```bash
pip install -e /path/to/scripts
```

## Installation

| Method | Command |
|--------|----------|
| Local development | `pip install -e ".[dev]"` |
| Local changes | `pip install -e /path/to/azure-deploy-cli` |
| From PyPI | `pip install azure-deploy-cli` |

## CLI Commands

### Azure Container Apps (ACA) Deployment

The ACA deployment process uses YAML configuration for containers and is split into two stages for better control:

#### Stage 1: Deploy Revision

Deploy a new container revision from YAML configuration without affecting traffic:

```bash
azd azaca deploy \
  --resource-group my-rg \
  --location westus2 \
  --container-app-env my-env \
  --logs-workspace-id <workspace-id> \
  --user-assigned-identity-name my-identity \
  --container-app my-app \
  --registry-server myregistry.azurecr.io \
  --stage prod \
  --target-port 8080 \
  --min-replicas 1 \
  --max-replicas 10 \
  --keyvault-name my-keyvault \
  --container-config ./container-config.yaml \
  --env-var-secrets SECRET1 SECRET2
```

This command:

- Loads container configurations from YAML file
- Builds/pushes container images for all containers
- Creates or updates a new revision with 0% traffic
- Supports multiple containers with independent configurations
- Verifies the revision is healthy and active
- Outputs the revision name for use in traffic management

**Container Configuration YAML:**

The `--container-config` file specifies container settings including images, resources, environment variables, and health probes:

```yaml
containers:
  - name: my-app
    image_name: my-image
    cpu: 0.5
    memory: "1.0Gi"
    env_vars:
      - ENV_VAR1
      - ENV_VAR2
    # relative to the directory which command will run fromm
    dockerfile: ./Dockerfile
    probes:
      - type: Liveness
        http_get:
          path: /health
          port: 8080
        initial_delay_seconds: 10
        period_seconds: 30
      - type: Readiness
        http_get:
          path: /ready
          port: 8080
        initial_delay_seconds: 5
        period_seconds: 10

  - name: sidecar
    image_name: sidecar-image
    cpu: 0.25
    memory: "0.5Gi"
    env_vars:
      - SIDECAR_CONFIG
    existing_image_tag: v1.0.0  # Optional: retag from existing image
```

**Configuration Fields:**

- `containers` (required): List of container configurations
  - `name`: Container name (required)
  - `image_name`: Image name without registry/tag (required)
  - `cpu`: CPU allocation (required, e.g., 0.5)
  - `memory`: Memory allocation (required, e.g., "1.0Gi")
  - `env_vars`: List of environment variable names to load (optional)
  - `dockerfile`: Path to Dockerfile for building (required if existing_image_tag not provided)
  - `existing_image_tag`: Tag to retag from instead of building (required if dockerfile not provided)
  - `probes`: List of health probes (optional)

**Note:** Ingress configuration (target port) and scaling parameters (min/max replicas) are specified via CLI arguments, not in the YAML file.

#### Stage 2: Update Traffic Weights

Update traffic distribution and deactivate old revisions:

```bash
azd azaca update-traffic \
  --resource-group my-rg \
  --container-app my-app \
  --label-stage-traffic prod=100 staging=0
```

This command:

- Updates traffic weights across all specified labels
- Deactivates revisions not receiving traffic (use `--no-deactivate` to skip)
- Enables blue-green, canary, and other deployment strategies

**Example Deployment Strategies:**

```bash
# Blue-Green Deployment (100% to new prod)
azd azaca update-traffic --resource-group my-rg --container-app my-app \
  --label-stage-traffic prod=100 staging=0

# Canary Deployment (90% prod, 10% staging)
azd azaca update-traffic --resource-group my-rg --container-app my-app \
  --label-stage-traffic prod=90 staging=10

# Multi-Environment (split traffic across multiple labels)
azd azaca update-traffic --resource-group my-rg --container-app my-app \
  --label-stage-traffic prod=70 staging=20 dev=10
```

### Create Service Principal & Assign Roles

```bash
azd create-and-assign \
  --sp-name my-app \
  --roles-config roles.json \
  --env-vars-files .env.local \
  --env-file .env.credentials \
  --print
```

### Reset Credentials

```bash
azd reset-credentials --sp-name <SP_NAME> --env-file .env.credentials
```

### Login with Credentials

```bash
azd login --env-file .env.credentials
```

## Python API

```python
from azure_deploy_cli import create_sp, assign_roles, RoleConfig

# Create service principal
result = create_sp("my-app")
print(result.objectId)

# Assign roles from config
with open('roles.json') as f:
    config = json.load(f)
role_config = RoleConfig(**config)
assign_roles(object_id, subscription_id, role_config)
```

## Example: Complete Workflow

```bash
# 1. Create configuration files
cat > .env.local << 'EOF'
SUBSCRIPTION_ID=<YOUR_SUBSCRIPTION>
RESOURCE_GROUP=<YOUR_RG>
OPENAI_RESOURCE_NAME=<YOUR_OPENAI>
EOF

cat > roles-config.json << 'EOF'
{
  "description": "My App Roles",
  "roles": [
    {
      "type": "rbac",
      "role": "Cognitive Services User",
      "scope": "/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}/providers/Microsoft.CognitiveServices/accounts/${OPENAI_RESOURCE_NAME}"
    },
    {
      "type": "cosmos-db",
      "account": "${COSMOS_ACCOUNT}",
      "role": "Cosmos DB Built-in Data Contributor",
      "scope": "/"
    }
  ]
}
EOF

# 2. Create service principal and assign roles
azd create-and-assign \
  --sp-name my-app-sp \
  --roles-config roles-config.json \
  --env-vars-files .env.local \
  --env-file .env.credentials \
  --print
```

## Development

```bash
make install-dev    # Install with dev tools
make build          # Run lint + type-check + test
make lint           # Code linting with ruff
make format         # Auto-format code
make type-check     # Type checking with mypy
make test           # Run tests with pytest
make clean          # Remove build artifacts
```

Commit using [Conventional Commits](https://www.conventionalcommits.org/) format (e.g., `feat: add feature`, `fix: resolve bug`)

## Scripting and Output Handling

This CLI is designed for both interactive use and automated scripting. To support this, it follows the standard practice of separating output streams:

- **`stderr`**: All human-readable logs, progress indicators, and error messages are sent to the standard error stream.
- **`stdout`**: All machine-readable output (e.g., revision names, IDs) is sent to the standard output stream.

This allows you to cleanly capture command output while still seeing logs in your terminal.

### Capturing Output

To save the parsable output to a file, redirect `stdout`:

```bash
azd azaca deploy ... > deployment_output.txt
```

The `deployment_output.txt` file will contain only the `REVISION_NAME=...` and `REVISION_URL=...` lines, without any of the logging messages.

### Silencing Logs

If you want to completely suppress the log messages (e.g., in a CI/CD script), redirect `stderr` to `/dev/null`:

```bash
azd azaca deploy ... 2>/dev/null
```

### Parsing Output in Scripts

You can pipe the output to standard Unix tools like `grep` and `cut` to extract specific values.

#### Example: Get the revision name

```bash
REVISION_NAME=$(azd azaca deploy ... 2>/dev/null | grep REVISION_NAME | cut -d'=' -f2)
echo "Deployed revision: $REVISION_NAME"
```

### Controlling Log Verbosity

Use the `--log-level` option to control the verbosity of the log output. The default level is `info`.

Available levels: `debug`, `info`, `warning`, `error`, `critical`, `none`.

#### Example: Enable debug logging

```bash
azd --log-level debug azaca deploy ...
```

#### Example: Suppress all logs

```bash
azd --log-level none azaca deploy ...
```

## License

Mozilla Public License 2.0 - See LICENSE file for details
