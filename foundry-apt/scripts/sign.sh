#!/usr/bin/env bash
# Fetch the Foundry signing key from AWS SSM SecureString, import to a
# temp GPG home, sign the published Release file, then wipe the home.
#
# Used by CI only; locally you'd use your own key.
#
# Env:
#   AWS_REGION                  (default us-east-1)
#   SSM_PARAM_NAME              (default /foundry-apt/signing-key)
#   PUBLISH_DIR                 (default ./public/dists/resolute)

set -euo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"
SSM_PARAM_NAME="${SSM_PARAM_NAME:-/foundry-apt/signing-key}"
PUBLISH_DIR="${PUBLISH_DIR:-./public/dists/resolute}"

if [[ ! -f "$PUBLISH_DIR/Release" ]]; then
    echo "ERROR: $PUBLISH_DIR/Release not found. Did you run publish-local.sh?" >&2
    exit 1
fi

tmp_gnupg=$(mktemp -d)
trap 'rm -rf "$tmp_gnupg"' EXIT
export GNUPGHOME="$tmp_gnupg"
chmod 700 "$GNUPGHOME"

echo "Fetching signing key from SSM ($SSM_PARAM_NAME)..."
aws ssm get-parameter \
    --region "$AWS_REGION" \
    --name "$SSM_PARAM_NAME" \
    --with-decryption \
    --query 'Parameter.Value' \
    --output text | gpg --batch --import

key_id=$(gpg --list-secret-keys --with-colons | awk -F: '/^sec/ {print $5; exit}')
if [[ -z "$key_id" ]]; then
    echo "ERROR: imported key but couldn't find key ID" >&2
    exit 1
fi

echo "Signing Release with key $key_id..."
gpg --batch --yes --default-key "$key_id" \
    --detach-sign --armor \
    -o "$PUBLISH_DIR/Release.gpg" \
    "$PUBLISH_DIR/Release"

gpg --batch --yes --default-key "$key_id" \
    --clearsign \
    -o "$PUBLISH_DIR/InRelease" \
    "$PUBLISH_DIR/Release"

echo "Signed: $PUBLISH_DIR/{Release.gpg,InRelease}"
