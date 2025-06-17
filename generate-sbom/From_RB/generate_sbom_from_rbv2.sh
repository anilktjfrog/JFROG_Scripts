#!/bin/bash
usage() {
    echo "Usage: $0 --JFROG_URL <jfrog_url> --JFROG_TOKEN <jfrog_token> --RELEASE_BUNDLE_NAME <name> --RELEASE_BUNDLE_VERSION <version> --RELEASE_BUNDLE_TYPE <V1|V2> [--OUTPUT_FILE <output_file>] [--SBOM_FORMAT <cyclonedx|spdx>]"
    echo ""
    echo "Arguments:"
    echo "  --JFROG_URL              The base URL of your JFrog instance (required)"
    echo "  --JFROG_TOKEN            The JFrog API token for authentication (required)"
    echo "  --RELEASE_BUNDLE_NAME    The name of the Release Bundle (required)"
    echo "  --RELEASE_BUNDLE_VERSION The version of the Release Bundle (required)"
    echo "  --RELEASE_BUNDLE_TYPE    The type of the Release Bundle: V1 or V2 (required)"
    echo "  --OUTPUT_FILE            The output file name for the SBOM report (optional, default: artifact-report-releaseBundleV2.zip)"
    echo "  --SBOM_FORMAT            The SBOM format: cyclonedx or spdx (optional, default: cyclonedx)"
    echo ""
    echo "Examples:"
    echo "  $0 --JFROG_URL https://my.jfrog.io --JFROG_TOKEN ABC123 --RELEASE_BUNDLE_NAME my-bundle --RELEASE_BUNDLE_VERSION 1.0.0 --RELEASE_BUNDLE_TYPE V2"
    echo "  $0 --JFROG_URL https://my.jfrog.io --JFROG_TOKEN ABC123 --RELEASE_BUNDLE_NAME my-bundle --RELEASE_BUNDLE_VERSION 1.0.0 --RELEASE_BUNDLE_TYPE V1 --OUTPUT_FILE sbom.zip --SBOM_FORMAT spdx"
    exit 1
}

# Default values
output_file=""
sbom_format="cyclonedx"

# Parse long options
while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        --JFROG_URL)
            JFROG_URL="$2"
            shift 2
            ;;
        --JFROG_TOKEN)
            JFROG_TOKEN="$2"
            shift 2
            ;;
        --RELEASE_BUNDLE_NAME)
            RB_NAME="$2"
            shift 2
            ;;
        --RELEASE_BUNDLE_VERSION)
            RB_VERSION="$2"
            shift 2
            ;;
        --RELEASE_BUNDLE_TYPE)
            RB_TYPE="$2"
            shift 2
            ;;
        --OUTPUT_FILE)
            output_file="$2"
            shift 2
            ;;
        --SBOM_FORMAT)
            sbom_format="$2"
            shift 2
            ;;
        *)
            usage
            ;;
    esac
done

# Validate required arguments
if [[ -z "$JFROG_URL" || -z "$JFROG_TOKEN" || -z "$RB_NAME" || -z "$RB_VERSION" || -z "$RB_TYPE" ]]; then
    usage
fi

# Validate RELEASE_BUNDLE_TYPE
if [[ "$RB_TYPE" != "V1" && "$RB_TYPE" != "V2" ]]; then
    echo "Error: --RELEASE_BUNDLE_TYPE must be 'V1' or 'V2'"
    exit 1
fi

# Validate SBOM format
if [[ "$sbom_format" != "cyclonedx" && "$sbom_format" != "spdx" ]]; then
    echo "Error: --SBOM_FORMAT must be 'cyclonedx' or 'spdx'"
    exit 1
fi

# Set output file name if not provided
if [[ -z "$output_file" ]]; then
    output_file="artifact-report-releaseBundle${RB_TYPE}.zip"
fi

component_name="${RB_NAME}:${RB_VERSION}"

if [[ "$RB_TYPE" == "V2" ]]; then
    package_type="releaseBundleV2"
    path="release-bundles-v2/${RB_NAME}"
else
    package_type="releaseBundle"
    path="release-bundles/${RB_NAME}"
fi

curl -H "Authorization: Bearer ${JFROG_TOKEN}" -L "${JFROG_URL}/xray/api/v2/component/exportDetails" \
    -H "Content-Type: application/json" \
    -H "Accept: application/octet-stream" \
    -d '{
        "component_name": "'"${component_name}"'",
        "package_type": "'"${package_type}"'",
        "path": "'"${path}"'",
        "spdx": '"$( [[ "$sbom_format" == "spdx" ]] && echo "true" || echo "false" )"',
        "spdx_format": "json",
        "cyclonedx": '"$( [[ "$sbom_format" == "cyclonedx" ]] && echo "true" || echo "false" )"',
        "cyclonedx_format": "json",
        "vex": false
    }' \
    -o "$output_file"

echo "SBOM report generated: $output_file"
