#!/usr/bin/env bash
# Deploy Terraform stack to a target environment.
# Usage: bash scripts/deploy.sh <dev|staging|prod>

set -euo pipefail

TARGET="${1:-dev}"

if [[ ! "$TARGET" =~ ^(dev|staging|prod)$ ]]; then
    echo "Usage: $0 <dev|staging|prod>" >&2
    exit 1
fi

TFVARS="infra/terraform/envs/${TARGET}.tfvars"
BACKEND="infra/terraform/envs/${TARGET}.backend.hcl"

for f in "$TFVARS" "$BACKEND"; do
    if [[ ! -f "$f" ]]; then
        echo "[error] Missing $f" >&2
        echo "Copy the .example file and fill in real values." >&2
        exit 1
    fi
done

echo "⚠️  You are about to deploy to $TARGET."
echo "⚠️  This will create BILLED AWS resources (~\$720/month at prod scale)."
echo "⚠️  Read docs/COST_ANALYSIS.md before proceeding."
read -r -p "Type the target environment name to confirm: " confirm

if [[ "$confirm" != "$TARGET" ]]; then
    echo "[abort] Confirmation failed"
    exit 1
fi

terraform -chdir=infra/terraform init -backend-config="envs/${TARGET}.backend.hcl"
terraform -chdir=infra/terraform plan -var-file="envs/${TARGET}.tfvars"

read -r -p "Apply this plan? (yes/no): " apply_confirm
if [[ "$apply_confirm" == "yes" ]]; then
    terraform -chdir=infra/terraform apply -var-file="envs/${TARGET}.tfvars" -auto-approve
    echo "[done] Deployment to $TARGET complete."
    echo "[next] Populate Secrets Manager with real DB credentials before running the pipeline."
else
    echo "[abort] Apply skipped."
fi
