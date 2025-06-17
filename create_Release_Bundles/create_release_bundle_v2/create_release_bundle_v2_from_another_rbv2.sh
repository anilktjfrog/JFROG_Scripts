# Usage function
usage() {
    echo "Usage: $0 --jfrog-url <url> --jfrog-token <token> --project-name <project> --release-bundle-name <name> --release-bundle-version <version> --signing-key-name <key> --source-bundles <bundle1:version1,bundle2:version2,...>"
    echo ""
    echo "Arguments:"
    echo "  --jfrog-url              JFrog Artifactory URL"
    echo "  --jfrog-token            JFrog API Bearer token"
    echo "  --project-name           JFrog project name"
    echo "  --release-bundle-name    Desired Release Bundle name"
    echo "  --release-bundle-version Desired Release Bundle version"
    echo "  --signing-key-name       Signing key name"
    echo "  --source-bundles         Comma-separated list of source bundles in the format <name>:<version>"
    echo ""
    echo "Example:"
    echo "  $0 --jfrog-url https://example.jfrog.io --jfrog-token <token> --project-name myproject --release-bundle-name my-bundle --release-bundle-version 1.0.0 --signing-key-name my-key --source-bundles bundle1:1.0.0,bundle2:2.0.0"
    exit 1
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --jfrog-url) JFROG_URL="$2"; shift 2;;
        --jfrog-token) JFROG_TOKEN="$2"; shift 2;;
        --project-name) PROJECT_NAME="$2"; shift 2;;
        --release-bundle-name) RELEASE_BUNDLE_NAME="$2"; shift 2;;
        --release-bundle-version) RELEASE_BUNDLE_VERSION="$2"; shift 2;;
        --signing-key-name) SIGNING_KEY_NAME="$2"; shift 2;;
        --source-bundles) SOURCE_BUNDLES="$2"; shift 2;;
        --help) usage;;
        *) echo "Unknown argument: $1"; usage;;
    esac
done

# Validate arguments
if [[ -z "$JFROG_URL" || -z "$JFROG_TOKEN" || -z "$PROJECT_NAME" || -z "$RELEASE_BUNDLE_NAME" || -z "$RELEASE_BUNDLE_VERSION" || -z "$SIGNING_KEY_NAME" || -z "$SOURCE_BUNDLES" ]]; then
    echo "Error: Missing required arguments."
    usage
fi

# Prepare JSON payload file
JSON_PAYLOAD_FILE=$(mktemp)

# Convert SOURCE_BUNDLES to JSON array
IFS=',' read -ra BUNDLES <<< "$SOURCE_BUNDLES"
BUNDLES_JSON=""
for bundle in "${BUNDLES[@]}"; do
    NAME="${bundle%%:*}"
    VERSION="${bundle##*:}"
    if [[ -n "$BUNDLES_JSON" ]]; then
        BUNDLES_JSON+=","
    fi
    BUNDLES_JSON+="{\"name\":\"${NAME}\",\"version\":\"${VERSION}\"}"
done

cat > "${JSON_PAYLOAD_FILE}" <<EOF
{
  "name": "${RELEASE_BUNDLE_NAME}",
  "version": "${RELEASE_BUNDLE_VERSION}",
  "source_bundles": [
    ${BUNDLES_JSON}
  ]
}
EOF

# Step 1: Create the Release Bundle using the REST API
echo "Creating Release Bundle: ${RELEASE_BUNDLE_NAME}, Version: ${RELEASE_BUNDLE_VERSION}"

curl -X POST "${JFROG_URL}/lifecycle/api/v2/release_bundle?project=${PROJECT_NAME}&async=false" \
-H "Authorization: Bearer ${JFROG_TOKEN}" \
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
