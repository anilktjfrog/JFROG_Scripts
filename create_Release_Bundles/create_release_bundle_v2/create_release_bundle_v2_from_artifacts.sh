#!/bin/bash

# Usage function
usage() {
    echo "Usage: $0 --jfrog-url <url> --jfrog-token <token> --project-name <project> --release-bundle-name <name> --release-bundle-version <version> --signing-key-name <key> --artifact-paths <path1,path2,...>"
    echo ""
    echo "  --jfrog-url               JFrog Artifactory URL (e.g., https://example.jfrog.io)"
    echo "  --jfrog-token             JFrog API Token"
    echo "  --project-name            JFrog project name"
    echo "  --release-bundle-name     Release Bundle name"
    echo "  --release-bundle-version  Release Bundle version"
    echo "  --signing-key-name        Signing key name"
    echo "  --artifact-paths          Comma-separated list of artifact paths (e.g., repo/path/file1,repo/path/file2)"
    echo ""
    exit 1
}

# Argument parsing
while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        --jfrog-url)
            JFROG_URL="$2"
            shift 2
            ;;
        --jfrog-token)
            JFROG_TOKEN="$2"
            shift 2
            ;;
        --project-name)
            PROJECT_NAME="$2"
            shift 2
            ;;
        --release-bundle-name)
            RELEASE_BUNDLE_NAME="$2"
            shift 2
            ;;
        --release-bundle-version)
            RELEASE_BUNDLE_VERSION="$2"
            shift 2
            ;;
        --signing-key-name)
            SIGNING_KEY_NAME="$2"
            shift 2
            ;;
        --artifact-paths)
            ARTIFACT_PATHS="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1"
            usage
            ;;
    esac
done

# Validate arguments
if [[ -z "${JFROG_URL}" || -z "${JFROG_TOKEN}" || -z "${PROJECT_NAME}" || -z "${RELEASE_BUNDLE_NAME}" || -z "${RELEASE_BUNDLE_VERSION}" || -z "${SIGNING_KEY_NAME}" || -z "${ARTIFACT_PATHS}" ]]; then
    echo "Error: Missing required arguments."
    usage
fi

IFS=',' read -ra PATHS <<< "${ARTIFACT_PATHS}"

# Prepare artifacts array for JSON
ARTIFACTS_JSON=""

for ARTIFACT_PATH in "${PATHS[@]}"; do
    # Get SHA256 from Xray Dependency Graph API
    artifact_details=$(curl -s -H "Authorization: Bearer ${JFROG_TOKEN}" -H "Content-Type: application/json" \
        -XPOST "${JFROG_URL}/xray/api/v1/dependencyGraph/artifact" \
        -d "{\"path\":\"default/${ARTIFACT_PATH}\"}")

    SHA256=$(echo "$artifact_details" | jq -r '.artifact.sha256')

    if [[ -z "${SHA256}" || "${SHA256}" == "null" ]]; then
        echo "Error: Could not fetch sha256 for artifact: ${ARTIFACT_PATH}"
        exit 1
    fi
    ARTIFACTS_JSON="${ARTIFACTS_JSON}{\"path\": \"${ARTIFACT_PATH}\", \"sha256\": \"${SHA256}\"},"
done

# Remove trailing comma
ARTIFACTS_JSON="[${ARTIFACTS_JSON%,}]"

# Create JSON payload file
JSON_PAYLOAD_FILE="aql.json"
cat <<EOF > "${JSON_PAYLOAD_FILE}"
{
    "release_bundle_name": "${RELEASE_BUNDLE_NAME}",
    "release_bundle_version": "${RELEASE_BUNDLE_VERSION}",
    "skip_docker_manifest_resolution": false,
    "source_type": "artifacts",
    "source": {
        "artifacts": ${ARTIFACTS_JSON}
    }
}
EOF

echo "JSON Payload:"
cat "${JSON_PAYLOAD_FILE}"

# Step 1: Create the Release Bundle using the REST API
echo "Creating Release Bundle: ${RELEASE_BUNDLE_NAME}, Version: ${RELEASE_BUNDLE_VERSION}"

curl -H "Authorization: Bearer ${JFROG_TOKEN}" -X POST "${JFROG_URL}/lifecycle/api/v2/release_bundle?project=${PROJECT_NAME}&async=false" \
-H "X-JFrog-Signing-Key-Name: ${SIGNING_KEY_NAME}" \
-H "Content-Type: application/json" \
--upload-file "${JSON_PAYLOAD_FILE}" \
-o "response.json"

if [[ $? -eq 0 ]]; then
    echo "Successfully created Release Bundle: ${RELEASE_BUNDLE_NAME}"
    echo "Response: $(cat response.json)"
else
    echo "Failed to create Release Bundle. Check response.json for details."
    cat response.json
fi

rm -f "${JSON_PAYLOAD_FILE}" response.json