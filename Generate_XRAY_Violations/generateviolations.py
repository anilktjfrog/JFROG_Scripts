import argparse
import json
import sys
import requests
from datetime import datetime
from tabulate import tabulate


def usage():
    print("Usage: generateviolations.py [OPTIONS]")
    print("")
    print("Required arguments:")
    print(
        "  --jfrog_url <url>                JFrog Xray URL (e.g., https://xray.example.com)"
    )
    print("  --jfrog_token <bearer_token>           Bearer token for authentication")
    print("  --watch_name <watch_name>        Name of the watch")
    print("  --violation_type <type>          Type of violation (e.g., Security)")
    print("  --min_severity <severity>        Minimum severity (e.g., High)")
    print(
        "  --created_from <timestamp>       Start date/time (e.g., 2025-06-16T18:22:04Z)"
    )
    print(
        "  --created_until <timestamp>      End date/time (e.g., 2025-07-17T18:22:04Z)"
    )
    print("  --bundle_name <name>             Release bundle name")
    print("  --bundle_version <version>       Release bundle version")
    print("  --project <project>              Project key")
    print("  --order_by <field>               Field to order by (e.g., created)")
    print("  --direction <asc|desc>           Order direction")
    print("  --limit <number>                 Number of results to return")
    print("  --offset <number>                Offset for pagination")
    print("")
    print("Example:")
    print(
        "python3  generateviolations.py --jfrog_url https://xray.example.com --jfrog_token YOUR_TOKEN --watch_name MyWatch --violation_type Security --min_severity High --created_from 2025-06-16T18:22:04Z --created_until 2025-07-17T18:22:04Z --bundle_name MyBundle --bundle_version 1.0.0 --project MyProject"
    )
    sys.exit(1)


# Validate created date
def validatecreateddate(date_text):
    """
    Validates created date is valid or not.

    Args:
        date_text (str): The scan date.
    """
    try:
        datetime.strptime(date_text, "%Y-%m-%dT%H:%M:%S%z")
        print("valid time")
        return True
    except ValueError:
        return False


def validateSeverity(severity):
    """
    Validates severity is valid or not.

    Args:
        severity (str): The severity level.
    """
    valid_severities = ["Critical", "High", "Medium", "Low", "Unknown"]
    if severity in valid_severities:
        return True
    else:
        print(
            f"Invalid severity: {severity}. Valid options are: {', '.join(valid_severities)}"
        )
        return False


def get_release_bundles_from_watch(jfrog_url, jfrog_token, watch_name):
    """
    Calls the JFrog Xray API to get release bundles for a given watch.

    Args:
        jfrog_url (str): Base URL of JFrog Xray.
        jfrog_token (str): Bearer token for authentication.
        watch_name (str): Name of the watch.

    Returns:
        list: List of release bundles under project_resources -> resources.
    """
    url = f"{jfrog_url}/xray/api/v2/watches/{watch_name}"
    headers = {
        "Authorization": f"Bearer {jfrog_token}",
        "Content-Type": "application/json",
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        resources = data.get("project_resources", {}).get("resources", [])
        return resources
    except Exception as e:
        print(f"Failed to fetch release bundles from watch: {e}")
        return []


def get_all_release_bundles(jfrog_url, jfrog_token):
    url = f"{jfrog_url}/lifecycle/api/v2/release_bundle/groups"
    headers = {
        "Authorization": f"Bearer {jfrog_token}",
        "Content-Type": "application/json",
    }
    release_bundles = []
    limit = 10
    offset = 0

    while True:
        params = {"limit": limit, "offset": offset}
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            bundles = data.get("release_bundles", [])
            release_bundles.extend(bundles)
            total = data.get("total", 0)
            offset += limit
            if offset >= total or not bundles:
                break
        except Exception as e:
            print(f"Failed to fetch release bundles: {e}")
            break

    return release_bundles


def get_bundle_details(jfrog_url, jfrog_token, bundle_name, release_bundles):
    for bundle in release_bundles:
        if (
            bundle.get("release_bundle_name") == bundle_name
            and "release_bundle_version_latest" in bundle
        ):
            return bundle


def main():
    parser = argparse.ArgumentParser(description="Generate violations from JFrog Xray")
    parser.add_argument(
        "--jfrog_url",
        help="JFrog Xray URL (e.g., https://xray.example.com)",
        required=True,
    )
    parser.add_argument(
        "--jfrog_token", required=True, help="Bearer token for authentication"
    )
    parser.add_argument("--watch_name", required=True, help="Name of the watch")
    parser.add_argument(
        "--violation_type", required=True, help="Type of violation (e.g., Security)"
    )
    parser.add_argument(
        "--min_severity", required=True, help="Minimum severity (e.g., High)"
    )
    parser.add_argument(
        "--created_from",
        required=True,
        help="Start date/time (e.g., 2025-06-16T18:22:04+00:00)",
    )
    parser.add_argument(
        "--created_until",
        required=True,
        help="End date/time (e.g., 2025-07-17T18:22:04+00:00)",
    )
    parser.add_argument("--order_by", default="created")
    parser.add_argument("--direction", default="asc")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--offset", type=int, default=1)
    args = parser.parse_args()

    # Validate created_from and created_until dates
    if not validatecreateddate(args.created_from):
        print(
            "Error: Invalid format for --created_from. Expected format: YYYY-MM-DDTHH:MM:SS+ZZZZ"
        )
        sys.exit(1)
    if not validatecreateddate(args.created_until):
        print(
            "Error: Invalid format for --created_until. Expected format: YYYY-MM-DDTHH:MM:SS+ZZZZ"
        )
        sys.exit(1)

    # Validate severity
    if not validateSeverity(args.min_severity):
        print("Error: Invalid severity level provided.")
        sys.exit(1)

    # Get release bundles from the watch
    release_bundles_from_watch = get_release_bundles_from_watch(
        args.jfrog_url, args.jfrog_token, args.watch_name
    )

    # Get all release bundles to find the latest version for each bundle name
    all_bundles = get_all_release_bundles(args.jfrog_url, args.jfrog_token)

    # Update each bundle in release_bundles_from_watch to use the latest version
    for bundle in release_bundles_from_watch:
        name = bundle.get("name", "")
        bundle_details = get_bundle_details(
            args.jfrog_url, args.jfrog_token, name, all_bundles
        )
        if bundle_details:
            latest_version = bundle_details.get("release_bundle_version_latest", "")
            project_key = bundle_details.get("project_key", "")
            bundle["version"] = latest_version
            bundle["project"] = project_key

    # Loop through each release bundle and generate violations, storing in separate JSON files
    for bundle in release_bundles_from_watch:
        bundle_name = bundle.get("name", "")
        bundle_version = bundle.get("version", "")
        bundle_project = bundle.get("project", "")
        # Frame the request body for this bundle
        body = {
            "filters": {
                "watch_name": args.watch_name,
                "violation_type": args.violation_type,
                "min_severity": args.min_severity,
                "created_from": args.created_from,
                "created_until": args.created_until,
                "resources": {
                    "release_bundles_v2": [
                        {
                            "name": bundle_name,
                            "version": bundle_version,
                            "project": bundle_project,
                        }
                    ]
                },
            },
            "pagination": {
                "order_by": args.order_by,
                "direction": args.direction,
                "limit": args.limit,
                "offset": args.offset,
            },
        }

        url = f"{args.jfrog_url}/xray/api/v1/violations"
        headers = {
            "Authorization": f"Bearer {args.jfrog_token}",
            "Content-Type": "application/json",
        }

        print(
            f"Requesting violations for bundle '{bundle_name}' from {url} with filters: {json.dumps(body, indent=2)}"
        )
        response = requests.post(url, headers=headers, data=json.dumps(body))
        output_file = f"{bundle_name}_violations.json"
        with open(output_file, "w") as f:
            try:
                json_response = response.json()
                json.dump(json_response, f, indent=2)
            except ValueError:
                f.write(response.text)

        print(f"Output stored in {output_file}")

        # Extract and display keys in table format
        try:
            with open(output_file, "r") as f:
                data = json.load(f)
            if (
                "violations" in data
                and isinstance(data["violations"], list)
                and data["violations"]
            ):
                all_keys = [
                    "severity",
                    "type",
                    "infected_components",
                    "created",
                    "watch_name",
                    "issue_id",
                    "impacted_artifacts",
                ]
                rows = []
                for v in data["violations"]:
                    row = [str(v.get(k, "")) for k in all_keys]
                    rows.append(row)
                print(f"\nViolation Keys Table for bundle '{bundle_name}':")
                print(tabulate(rows, headers=all_keys, tablefmt="grid"))
            else:
                print(f"No violations found in response for bundle '{bundle_name}'.")
        except Exception as e:
            print(
                f"Failed to extract/display violation keys for bundle '{bundle_name}': {e}"
            )


if __name__ == "__main__":
    main()
