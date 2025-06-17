#!/bin/bash

# Usage function
usage() {
    echo "Usage: $0 --jfrog-url <url> --jfrog-token <token> --project-name <project> --release-bundle-name <name> --release-bundle-version <version> --signing-key-name <key> --storing-repository <repository> --aql <aql_query>"
    echo ""
    echo "Arguments:"
    echo "  --jfrog-url             JFrog Artifactory URL (e.g., https://example.jfrog.io)"
    echo "  --jfrog-token           JFrog API token"
    echo "  --project-name          JFrog project name"
    echo "  --release-bundle-name   Release Bundle name"
    echo "  --release-bundle-version Release Bundle version"
    echo "  --signing-key-name      Signing key name"
    echo "  --storing-repository    Repository to store the Release Bundle"
    echo "  --aql                   AQL query for artifacts (as a single line string)"
    echo ""
    echo "Example:"
    echo "  $0 --jfrog-url https://example.jfrog.io --jfrog-token <token> --project-name default --release-bundle-name mybundle --release-bundle-version 1.0.0 --signing-key-name mykey --storing-repository release-bundles --aql 'items.find({\"repo\": \"libs-release-local\", \"name\": {\"\$match\": \"*.jar\"}})'"
    echo ""
    exit 1
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --jfrog-url) JFROG_URL="$2"; shift 2 ;;
        --jfrog-token) JFROG_TOKEN="$2"; shift 2 ;;
        --project-name) PROJECT_NAME="$2"; shift 2 ;;
        --release-bundle-name) RELEASE_BUNDLE_NAME="$2"; shift 2 ;;
        --release-bundle-version) RELEASE_BUNDLE_VERSION="$2"; shift 2 ;;
        --signing-key-name) SIGNING_KEY_NAME="$2"; shift 2 ;;
        --storing-repository) RELEASE_BUNDLE_STORING_REPOSITORY="$2"; shift 2 ;;
        --aql) AQL_QUERY="$2"; shift 2 ;;
        *) echo "Unknown argument: $1"; usage ;;
    esac
done

# Validate arguments
if [[ -z "$JFROG_URL" || -z "$JFROG_TOKEN" || -z "$PROJECT_NAME" || -z "$RELEASE_BUNDLE_NAME" || -z "$RELEASE_BUNDLE_VERSION" || -z "$SIGNING_KEY_NAME" || -z "$RELEASE_BUNDLE_STORING_REPOSITORY" || -z "$AQL_QUERY" ]]; then
    echo "Error: Missing required arguments."
    usage
fi

# Create JSON payload file
JSON_PAYLOAD_FILE="aql.json"
cat <<EOF > "${JSON_PAYLOAD_FILE}"
{
    "name": "${RELEASE_BUNDLE_NAME}",
    "version": "${RELEASE_BUNDLE_VERSION}",
    "dry_run": false,
    "sign_immediately": true,
    "storing_repository": "${RELEASE_BUNDLE_STORING_REPOSITORY}",
    "description": "Release Bundle via API",
    "release_notes": {
        "syntax": "markdown",
        "content": "## Release bundle created via script"
    },
    "spec": {
        "queries": [
            {
                "aql": "${AQL_QUERY}",
                "query_name": "query-1"
            }
        ]
    }
}
EOF

echo "JSON Payload:"
cat "${JSON_PAYLOAD_FILE}"

# Create the Release Bundle using the REST API
echo "Creating Release Bundle: ${RELEASE_BUNDLE_NAME}, Version: ${RELEASE_BUNDLE_VERSION}"

curl -H "Authorization: Bearer ${JFROG_TOKEN}" \
     -X POST "${JFROG_URL}/distribution/api/v1/release_bundle" \
     -H "X-GPG-PASSPHRASE: ${SIGNING_KEY_NAME}" \
     -H "Content-Type: application/json" \
     -H "Accept: application/json" \
     -T "${JSON_PAYLOAD_FILE}" \
     -o "response.json"

if [[ $? -eq 0 ]]; then
    echo "Successfully created Release Bundle: ${RELEASE_BUNDLE_NAME}"
    echo "Response: $(cat response.json)"
else
    echo "Failed to create Release Bundle. Check response.json for details."
    cat response.json
fi

rm -f "${JSON_PAYLOAD_FILE}" response.json