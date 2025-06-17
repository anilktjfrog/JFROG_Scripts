#!/bin/bash

usage() {
    echo "Usage: $0 --JFROG_URL <jfrog_url> --JFROG_TOKEN <token> --ARTIFACT_PATH <artifact_path1>[,<artifact_path2>,...] [--OUTPUT_FILE <output_file>] [--SBOM_FORMAT <sbom_format>]"
    echo
    echo "Arguments:"
    echo "  --JFROG_URL      JFrog instance URL (e.g., https://mycompany.jfrog.io/artifactory)"
    echo "  --JFROG_TOKEN    JFrog API token"
    echo "  --ARTIFACT_PATH  Comma-separated artifact paths (e.g., libs-release-local/com/example/app/1.0.0/app-1.0.0.jar,libs-release-local/com/example/lib/2.0.0/lib-2.0.0.jar)"
    echo "  --OUTPUT_FILE    (Optional) Output file name for the report (e.g., my-sbom.zip)"
    echo "  --SBOM_FORMAT    (Optional) SBOM format: cyclonedx (default) or spdx"
    echo
    echo "Examples:"
    echo "  $0 --JFROG_URL https://mycompany.jfrog.io/artifactory --JFROG_TOKEN ABC123 --ARTIFACT_PATH libs-release-local/com/example/app/1.0.0/app-1.0.0.jar"
    echo "  $0 --JFROG_URL https://mycompany.jfrog.io/artifactory --JFROG_TOKEN ABC123 --ARTIFACT_PATH path1.jar,path2.jar --OUTPUT_FILE report.zip --SBOM_FORMAT spdx"
    exit 1
}

sbom_format="cyclonedx"

while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        --JFROG_URL)
            JFURL="$2"
            shift 2
            ;;
        --JFROG_TOKEN)
            token="$2"
            shift 2
            ;;
        --ARTIFACT_PATH)
            artifact_paths="$2"
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
        -*|--*)
            usage
            ;;
        *)
            break
            ;;
    esac
done

if [[ -z "$JFURL" || -z "$token" || -z "$artifact_paths" ]]; then
    echo "Error: Missing required arguments."
    usage
fi

if [[ "$sbom_format" != "cyclonedx" && "$sbom_format" != "spdx" ]]; then
    echo "Error: Invalid SBOM format. Use 'cyclonedx' or 'spdx'."
    usage
fi

IFS=',' read -ra paths <<< "$artifact_paths"

json_array="["

for artifact_path in "${paths[@]}"; do
    artifact_details=$(curl -s -H "Authorization: Bearer $token" -H "Content-Type: application/json" \
        -XPOST "$JFURL/xray/api/v1/dependencyGraph/artifact" \
        -d '{"path":"default/'$artifact_path'"}')

    sha256=$(echo "$artifact_details" | jq -r '.artifact.sha256')
    pkg_type=$(echo "$artifact_details" | jq -r '.artifact.pkg_type')
    cname=$(echo "$artifact_details" | jq -r '.artifact.component_id')

    if [[ -z "$sha256" || -z "$pkg_type" || -z "$cname" || "$sha256" == "null" || "$pkg_type" == "null" || "$cname" == "null" ]]; then
        echo "Error: Failed to retrieve artifact details for $artifact_path"
        exit 2
    fi

    # Set SBOM flags
    if [[ "$sbom_format" == "cyclonedx" ]]; then
        cyclonedx=true
        spdx=false
    else
        cyclonedx=false
        spdx=true
    fi

    json_array+=$(
        jq -nc \
            --arg cname "$cname" \
            --arg pkg_type "$pkg_type" \
            --arg path "$artifact_path" \
            --argjson cyclonedx "$cyclonedx" \
            --argjson spdx "$spdx" \
            '{"component_name":$cname,"package_type":$pkg_type,"path":$path,"cyclonedx":$cyclonedx,"spdx":$spdx,"cyclonedx_format":"json","vex":false}'
    )
    json_array+=","
done

json_array="${json_array%,}]"

if [[ -z "$output_file" ]]; then
    safe_cname=$(echo "${paths[0]}" | tr ':/' '_')
    output_file="artifact-report-${safe_cname}.zip"
fi

echo $json_array

curl -s -H "Authorization: Bearer $token" -XPOST "$JFURL/xray/api/v2/component/exportDetails" \
    -H "Content-type: application/json" \
    -H "Accept: application/octet-stream" \
    -d "$json_array" \
    -o "$output_file"

if [[ $? -eq 0 ]]; then
    echo "Report generated: $output_file"
else
    echo "Failed to generate report."
    exit 2
fi
