#!/bin/bash
build_repo="artifactory-build-info"
usage() {
   echo "Usage: $0 --JFROG_URL <jfrog_url> --JFROG_TOKEN <jfrog_token> --build_name <build_name> --build_number <build_number> [--sbom_format <sbom_format>] [--build_repo <build_repo>]"
   echo "  --JFROG_URL <jfrog_url>        : JFrog base URL (required)"
   echo "  --JFROG_TOKEN <jfrog_token>    : JFrog API token (required)"
   echo "  --build_name <build_name>      : Name of the build (required)"
   echo "  --build_number <build_number>  : Build number (required)"
   echo "  --sbom_format <sbom_format>    : SBOM format: cyclonedx or spdx (default: cyclonedx)"
   echo "  --build_repo <build_repo>      : Build repository (optional)"
   echo
   echo "Examples:"
   echo "  $0 --JFROG_URL https://my.jfrog.io --JFROG_TOKEN ABC123 --build_name my-build --build_number 123 --sbom_format cyclonedx"
   exit 1
}

# Default values
sbom_format="cyclonedx"

# Parse arguments
while [[ $# -gt 0 ]]; do
  key="$1"
  case $key in
    --JFROG_URL)
      jfrog_url="$2"
      shift 2
      ;;
    --JFROG_TOKEN)
      jfrog_token="$2"
      shift 2
      ;;
    --build_name)
      build_name="$2"
      shift 2
      ;;
    --build_number)
      build_number="$2"
      shift 2
      ;;
    --sbom_format)
      sbom_format="$2"
      shift 2
      ;;
    --build_repo)
      build_repo="$2"
      shift 2
      ;;
    *)
      usage
      ;;
  esac
done
# Validate required arguments
if [ -z "$jfrog_url" ] || [ -z "$jfrog_token" ] || [ -z "$build_name" ] || [ -z "$build_number" ]; then
   echo "Error: JFROG_URL, JFROG_TOKEN, build_name and build_number are required."
   usage
fi

# Validate sbom_format
if [[ "$sbom_format" != "cyclonedx" && "$sbom_format" != "spdx" ]]; then
   echo "Error: sbom_format must be either 'cyclonedx' or 'spdx'."
   usage
fi

# Get build sha256 using curl with Bearer token
buildsha256=$(curl -s -H "Content-Type: application/json" \
   -H "Authorization: Bearer $jfrog_token" \
   -X POST "$jfrog_url/xray/api/v1/dependencyGraph/build" \
   -d '{
   "build_name":"'$build_name'",
   "build_number":"'$build_number'",
   "build_repo":"'$build_repo'"
   }' | jq -r '.build.sha256')

echo "buildsha256: $buildsha256"
echo "Generating SBOM for build $build_name $build_number in $sbom_format format"

# Set SBOM format specific fields
if [ "$sbom_format" = "spdx" ]; then
   sbom_flag='"spdx": true, "spdx_format": "json",'
else
   sbom_flag='"cyclonedx": true, "cyclonedx_format": "json",'
fi

curl -s -X POST "$jfrog_url/xray/api/v1/component/exportDetails" \
   -H "Content-type: application/json" \
   -H "Authorization: Bearer $jfrog_token" \
   -d '{
         "violations": true,
         "include_ignored_violations": true,
         "license": true,
         "security": true,
         "exclude_unknown": true,
         '"$sbom_flag"'
         "component_name": "'"$build_name"':'"$build_number"'",
         "package_type": "build",
         "sha_256": "'"$buildsha256"'",
         "output_format": "json"
      }' \
   --output build-report-$build_name-$build_number.zip
