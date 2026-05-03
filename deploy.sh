#!/usr/bin/env bash
set -euo pipefail

# deploy.sh — Deploy the s3-pypi-server CloudFormation stack.
#
# Usage:
#   ./deploy.sh <stack-name> [parameter-overrides...]
#
# Examples:
#   ./deploy.sh my-pypi
#   ./deploy.sh my-pypi StackNamePrefix=custom CacheTTL=600

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <stack-name> [ParameterKey=Value ...]" >&2
    exit 2
fi

STACK_NAME="$1"
shift

# Build parameter overrides from remaining arguments
OVERRIDES=()
if [[ $# -gt 0 ]]; then
    OVERRIDES=("--parameter-overrides" "$@")
fi

TEMPLATE_FILE="template.yaml"

echo "Deploying stack '${STACK_NAME}' from ${TEMPLATE_FILE}..."

if aws cloudformation deploy \
    --template-file "${TEMPLATE_FILE}" \
    --stack-name "${STACK_NAME}" \
    --capabilities CAPABILITY_IAM \
    "${OVERRIDES[@]+"${OVERRIDES[@]}"}"; then
    echo "Stack '${STACK_NAME}' deployed successfully."

    # Print outputs
    echo ""
    echo "Stack outputs:"
    aws cloudformation describe-stacks \
        --stack-name "${STACK_NAME}" \
        --query "Stacks[0].Outputs[*].[OutputKey, OutputValue]" \
        --output table
else
    echo "Deployment failed for stack '${STACK_NAME}'." >&2
    echo "" >&2
    echo "Recent failure events:" >&2
    aws cloudformation describe-stack-events \
        --stack-name "${STACK_NAME}" \
        --query "StackEvents[?ResourceStatus=='CREATE_FAILED' || ResourceStatus=='UPDATE_FAILED'].[LogicalResourceId, ResourceStatusReason]" \
        --output table >&2
    exit 1
fi
