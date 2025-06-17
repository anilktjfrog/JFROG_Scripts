#!/bin/bash

set -e

usage() {
    echo "Usage: $0 --jfrog-url <url> --jfrog-token <token> --project-name <name> --release-bundle-name <name> --release-bundle-version <version> --signing-key-name <key> --builds <repo1:build1:build_number1,repo2:build2:build_number2,...>"
    echo ""
    echo "Arguments:"
    echo "  --jfrog-url                JFrog Artifactory URL (e.g., https://example.jfrog.io)"
    echo "  --jfrog-token              JFrog API Token"
    echo "  --project-name             JFrog Project Name"
    echo "  --release-bundle-name      Release Bundle Name"
    echo "  --release-bundle-version   Release Bundle Version"
    echo "  --signing-key-name         Signing Key Name"
    echo "  --builds                   Comma-separated list of repo:build_name:build_number"
    echo ""
    echo "Example:"
    echo "  $0 --jfrog-url https://example.jfrog.io --jfrog-token ABC123 --project-name default --release-bundle-name my-bundle --release-bundle-version 1.0.0 --signing-key-name my-key --builds repo1:build1:1,repo2:build2:2"
    exit 1
}

# Parse arguments
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
        --builds)
            BUILDS="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1"
            usage
            ;;
    esac
done

# Validate arguments
if [[ -z "${JFROG_URL}" || -z "${JFROG_TOKEN}" || -z "${PROJECT_NAME}" || -z "${RELEASE_BUNDLE_NAME}" || -z "${RELEASE_BUNDLE_VERSION}" || -z "${SIGNING_KEY_NAME}" || -z "${BUILDS}" ]]; then
    echo "Error: Missing required arguments."
    usage
fi

# Prepare builds JSON array
IFS=',' read -ra BUILD_PAIRS <<< "$BUILDS"
BUILDS_JSON=""
for PAIR in "${BUILD_PAIRS[@]}"; do
    IFS=':' read -ra PARTS <<< "$PAIR"
    if [[ ${#PARTS[@]} -ne 3 ]]; then
        echo "Error: Invalid build format in --builds. Expected repo:build_name:build_number"
        exit 1
    fi
    BUILD_REPOSITORY="${PARTS[0]}"
    BUILD_NAME="${PARTS[1]}"
    BUILD_NUMBER="${PARTS[2]}"
    if [[ -z "$BUILD_REPOSITORY" || -z "$BUILD_NAME" || -z "$BUILD_NUMBER" ]]; then
        echo "Error: Invalid build format in --builds. Expected repo:build_name:build_number"
        exit 1
    fi
    BUILDS_JSON="${BUILDS_JSON}{\"build_repository\":\"${BUILD_REPOSITORY}\",\"build_name\":\"${BUILD_NAME}\",\"build_number\":\"${BUILD_NUMBER}\",\"include_dependencies\":false},"
done
# Remove trailing comma
BUILDS_JSON="[${BUILDS_JSON%,}]"

# Create JSON payload file
JSON_PAYLOAD_FILE="aql.json"
cat <<EOF > "${JSON_PAYLOAD_FILE}"
{
    "release_bundle_name": "${RELEASE_BUNDLE_NAME}",
    "release_bundle_version": "${RELEASE_BUNDLE_VERSION}",
    "source_type": "builds",
    "source": {
        "builds": ${BUILDS_JSON}
    }
}
EOF

echo "JSON Payload:"
cat "${JSON_PAYLOAD_FILE}"

# Step 1: Create the Release Bundle using the REST API
echo "Creating Release Bundle: ${RELEASE_BUNDLE_NAME}, Version: ${RELEASE_BUNDLE_VERSION}"

curl --header "Authorization: Bearer ${JFROG_TOKEN}" \
     --request POST "${JFROG_URL}/lifecycle/api/v2/release_bundle?project=${PROJECT_NAME}&async=false" \
     --header "X-JFrog-Signing-Key-Name: ${SIGNING_KEY_NAME}" \
     --header "Content-Type: application/json" \
     --upload-file "${JSON_PAYLOAD_FILE}" \
     --output "response.json"

if [[ $? -eq 0 ]]; then
    echo "Successfully created Release Bundle: ${RELEASE_BUNDLE_NAME}"
    echo "Response: $(cat response.json)"
else
    echo "Failed to create Release Bundle. Check response.json for details."
    cat response.json
fi

rm -f "${JSON_PAYLOAD_FILE}" response.json