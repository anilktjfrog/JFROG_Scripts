#!/bin/bash

# Usage function
usage() {
    echo "Usage: $0 --jfrog-url <url> --jfrog-token <token> --project-name <project> --release-bundle-name <name> --release-bundle-version <version> --signing-key-name <key> --aql-query <aql>"
    echo ""
    echo "Arguments:"
    echo "  --jfrog-url               JFrog Artifactory URL (e.g., https://mycompany.jfrog.io)"
    echo "  --jfrog-token             JFrog API token"
    echo "  --project-name            JFrog project name"
    echo "  --release-bundle-name     Desired Release Bundle name"
    echo "  --release-bundle-version  Desired Release Bundle version"
    echo "  --signing-key-name        Signing key name"
    echo "  --aql-query               AQL query string (escape quotes as needed)"
    echo ""
    echo "Example:"
    echo "  $0 --jfrog-url https://mycompany.jfrog.io --jfrog-token ABC123 --project-name default --release-bundle-name my-bundle --release-bundle-version 1.0.0 --signing-key-name my-gpg-key --aql-query 'items.find({\"repo\": {\"\$eq\": \"my-repo\"}})'"
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
        --aql-query)
            AQL_QUERY="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1"
            usage
            ;;
    esac
done

# Validate arguments
if [[ -z "${JFROG_URL}" || -z "${JFROG_TOKEN}" || -z "${PROJECT_NAME}" || -z "${RELEASE_BUNDLE_NAME}" || -z "${RELEASE_BUNDLE_VERSION}" || -z "${SIGNING_KEY_NAME}" || -z "${AQL_QUERY}" ]]; then
    echo "Error: Missing required arguments."
    usage
fi

# Create JSON payload file
JSON_PAYLOAD_FILE="aql.json"
cat <<EOF > "${JSON_PAYLOAD_FILE}"
{
    "release_bundle_name": "${RELEASE_BUNDLE_NAME}",
    "release_bundle_version": "${RELEASE_BUNDLE_VERSION}",
    "skip_docker_manifest_resolution": false,
    "source_type": "aql",
    "source": {
        "aql": "${AQL_QUERY}"
    }
}
EOF

# Step 1: Create the Release Bundle using the REST API
echo "Creating Release Bundle: ${RELEASE_BUNDLE_NAME}, Version: ${RELEASE_BUNDLE_VERSION}"

# Perform the API call to create the Release Bundle
curl -H "Authorization: Bearer ${JFROG_TOKEN}" -X POST "${JFROG_URL}/lifecycle/api/v2/release_bundle?project=${PROJECT_NAME}&async=false" \
-H "X-JFrog-Signing-Key-Name: ${SIGNING_KEY_NAME}" \
-H "Content-Type: application/json" \
--upload-file "${JSON_PAYLOAD_FILE}" \
-o "response.json"

# Check if the request was successful
if [[ $? -eq 0 ]]; then
    echo "Successfully created Release Bundle: ${RELEASE_BUNDLE_NAME}"
    echo "Response: $(cat response.json)"
else
    echo "Failed to create Release Bundle. Check response.json for details."
    cat response.json
fi

# Cleanup
rm -f "${JSON_PAYLOAD_FILE}" response.json