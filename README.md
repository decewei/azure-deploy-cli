# CC Scripts

Python CLI package for Climate Compass projects.

## Version Management

This project uses [setuptools-scm](https://setuptools-scm.readthedocs.io/) for automatic versioning based on git tags. The version number is dynamically determined from git history at build/install time. No manual version file updates are needed.

## Quick Start

**Install for development:**

```bash
cd /path/to/scripts
pip install -e ".[dev]"
ccc --help
```

**Use in another project:**

```bash
pip install -e /path/to/scripts
```

## Installation

| Method | Command |
|--------|---------|
| Local development | `pip install -e ".[dev]"` |
| Local changes | `pip install -e /path/to/scripts` |
| From PyPI | `pip install git+https://github.com/klimatekompass/scripts@main` |

## CLI Commands

### Azure Container Apps (ACA) Deployment

The ACA deployment process is split into two stages for better control:

#### Stage 1: Deploy Revision

Deploy a new container revision without affecting traffic:

```bash
ccc azaca deploy \
  --resource-group my-rg \
  --location westus2 \
  --container-app-env my-env \
  --logs-workspace-id <workspace-id> \
  --user-assigned-identity-name my-identity \
  --container-app my-app \
  --registry-server myregistry.azurecr.io \
  --image-name my-image \
  --stage prod \
  --target-port 8000 \
  --cpu 0.5 \
  --memory 1.0 \
  --min-replicas 1 \
  --max-replicas 10 \
  --keyvault-name my-keyvault \
  --dockerfile ./Dockerfile \
  --env-vars ENV_VAR1 ENV_VAR2 \
  --env-var-secrets SECRET1 SECRET2
```

This command:

- Creates or updates a new revision with 0% traffic
- Verifies the revision is healthy and active
- Outputs the revision name for use in traffic management

#### Stage 2: Update Traffic Weights

Update traffic distribution and deactivate old revisions:

```bash
ccc azaca update-traffic \
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
ccc azaca update-traffic --resource-group my-rg --container-app my-app \
  --label-stage-traffic prod=100 staging=0

# Canary Deployment (90% prod, 10% staging)
ccc azaca update-traffic --resource-group my-rg --container-app my-app \
  --label-stage-traffic prod=90 staging=10

# Multi-Environment (split traffic across multiple labels)
ccc azaca update-traffic --resource-group my-rg --container-app my-app \
  --label-stage-traffic prod=70 staging=20 dev=10
```

### Create Service Principal & Assign Roles

```bash
ccc create-and-assign \
  --sp-name my-app \
  --roles-config roles.json \
  --env-vars-files .env.local \
  --env-file .env.credentials \
  --print
```

### Reset Credentials

```bash
ccc reset-credentials --sp-name <SP_NAME> --env-file .env.credentials
```

### Login with Credentials

```bash
ccc login --env-file .env.credentials
```

## Python API

```python
from cc_scripts import create_sp, assign_roles, RoleConfig

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
ccc create-and-assign \
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

**In grantcompass-scraper:**

```bash
pip install -e ../scripts
# Then use: from cc_scripts import create_sp, assign_roles
```

**In grantcompass-webapp:**

```bash
pip install -e ../scripts
# Then use in scripts: ccc create-and-assign ...
```

## Scripting and Output Handling

This CLI is designed for both interactive use and automated scripting. To support this, it follows the standard practice of separating output streams:

- **`stderr`**: All human-readable logs, progress indicators, and error messages are sent to the standard error stream.
- **`stdout`**: All machine-readable output (e.g., revision names, IDs) is sent to the standard output stream.

This allows you to cleanly capture command output while still seeing logs in your terminal.

### Capturing Output

To save the parsable output to a file, redirect `stdout`:

```bash
ccc azaca deploy ... > deployment_output.txt
```

The `deployment_output.txt` file will contain only the `REVISION_NAME=...` and `REVISION_URL=...` lines, without any of the logging messages.

### Silencing Logs

If you want to completely suppress the log messages (e.g., in a CI/CD script), redirect `stderr` to `/dev/null`:

```bash
ccc azaca deploy ... 2>/dev/null
```

### Parsing Output in Scripts

You can pipe the output to standard Unix tools like `grep` and `cut` to extract specific values.

#### Example: Get the revision name

```bash
REVISION_NAME=$(ccc azaca deploy ... 2>/dev/null | grep REVISION_NAME | cut -d'=' -f2)
echo "Deployed revision: $REVISION_NAME"
```

### Controlling Log Verbosity

Use the `--log-level` option to control the verbosity of the log output. The default level is `info`.

Available levels: `debug`, `info`, `warning`, `error`, `critical`, `none`.

#### Example: Enable debug logging

```bash
ccc --log-level debug azaca deploy ...
```

#### Example: Suppress all logs

```bash
ccc --log-level none azaca deploy ...
```

## License

Proprietary - Climate Compass Team
