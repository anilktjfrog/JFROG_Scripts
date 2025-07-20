import os
import requests
import subprocess
from collections import defaultdict
from tabulate import tabulate

# --- Configuration ---
GITHUB_ORG = os.environ.get("GITHUB_ORG")  # GitHub organization/user name
NPM_SCOPE = os.environ.get("NPM_SCOPE")  # The npm scope for your packages
GITHUB_ORG_TYPE = os.environ.get("GITHUB_ORG_TYPE", "orgs")  # Default to "orgs"
GITHUB_PAT = os.environ.get("GITHUB_PAT")  # Get PAT from environment variable
JFROG_NPM_REPO = os.environ.get("JFROG_NPM_REPO")  # JFrog Artifactory npm repo name
TEMP_DIR_PREFIX = os.environ.get("TEMP_DIR_PREFIX", "npm_package_sync_")

if not GITHUB_PAT:
    print("Error: GITHUB_PAT environment variable not set.")
    print("Please set your GitHub Personal Access Token with 'read:packages' scope.")
    exit(1)

GITHUB_API_HEADERS = {
    "Accept": "application/vnd.github.v3+json",
    "Authorization": f"token {GITHUB_PAT}",
}


def get_npm_packages_from_github():
    """Fetches a list of npm packages for the given GitHub organization."""
    print(f"Querying GitHub Packages for organization: {GITHUB_ORG}...")
    packages_url = f"https://api.github.com/{GITHUB_ORG_TYPE}/{GITHUB_ORG}/packages?package_type=npm"
    response = requests.get(packages_url, headers=GITHUB_API_HEADERS)
    response.raise_for_status()
    return response.json()


def get_package_versions_from_github(package_name):
    """Fetches all versions for a given npm package from GitHub Packages."""
    print(f"  Fetching versions for package: {package_name}...")
    # The package name in GitHub API needs to be URL-encoded for scoped packages
    # npm_package_name is like '@scope/package-name'
    # The API expects package_name without the @scope/ prefix
    # So, we need to extract the actual package name from the scoped name.

    # Extract the base package name from the scoped name
    base_package_name = package_name.split("/")[-1]
    versions_url = f"https://api.github.com/{GITHUB_ORG_TYPE}/{GITHUB_ORG}/packages/npm/{base_package_name}/versions"
    response = requests.get(versions_url, headers=GITHUB_API_HEADERS)
    response.raise_for_status()
    return response.json()


def download_npm_package_version(package_name, version, download_path):
    """
    Downloads a specific version of an npm package using 'npm pack'.
    Returns the path to the created tarball.
    """
    print("\n" + "-" * 80)
    print(f"Downloading {NPM_SCOPE}/{package_name}@{version}")
    print("\n" + "-" * 80)
    print(f"    Downloading {NPM_SCOPE}/{package_name}@{version} to {download_path}...")
    original_cwd = os.getcwd()
    try:
        os.makedirs(download_path, exist_ok=True)
        os.chdir(download_path)
        print(f"Current working directory: {os.getcwd()}")

        # Configure npm to use GitHub Packages registry for the specific scope
        # This is crucial for npm pack to find the package.
        npmrc_content = f"@{GITHUB_ORG}:registry=https://npm.pkg.github.com/{GITHUB_ORG}\n//npm.pkg.github.com/:_authToken={GITHUB_PAT}"
        with open(".npmrc", "w") as f:
            f.write(npmrc_content)

        npm_pack_command = ["npm", "pack", f"{NPM_SCOPE}/{package_name}@{version}"]
        print(f"        npm pack command: {' '.join(npm_pack_command)}")

        # Clean up existing tarballs before packing to avoid confusion
        print("        Cleaning up existing tarballs in the download directory...")
        for f in os.listdir(download_path):
            if f.endswith(".tgz"):
                print(
                    f"        Removing existing tarball: {os.path.join(download_path, f)}"
                )
                os.remove(os.path.join(download_path, f))

        result = subprocess.run(
            npm_pack_command, check=True, capture_output=True, text=True
        )
        print("        npm pack Output:")
        print(result.stdout)
        if result.stderr:
            # Filter out deprecation warnings to reduce noise
            stderr_lines = result.stderr.split("\n")
            filtered_stderr = [
                line
                for line in stderr_lines
                if not (
                    "npm warn Unknown user config" in line
                    and ("email" in line or "always-auth" in line)
                )
            ]
            filtered_stderr_text = "\n".join(filtered_stderr).strip()
            if filtered_stderr_text:
                print("        npm pack Error Output (if any):")
                print(filtered_stderr_text)

        # Find the generated tarball
        tarball_name = ""
        for f in os.listdir(download_path):
            if f.endswith(".tgz"):
                tarball_name = f
                break

        if not tarball_name:
            raise FileNotFoundError(
                f"Could not find tarball for {package_name}@{version}"
            )

        return os.path.join(download_path, tarball_name)

    finally:
        os.chdir(original_cwd)  # Go back to the original directory


def upload_to_jfrog(tarball_path, package_name, version):
    """
    Uploads an npm package tarball to JFrog Artifactory using JFrog CLI's `jf rt upload`.
    """
    print(
        f"Uploading {package_name}@{version} to JFrog Artifactory ({JFROG_NPM_REPO})..."
    )

    # Construct the target path in JFrog Artifactory
    tarball_filename = os.path.basename(tarball_path).replace(
        f"{NPM_SCOPE.replace('@', '')}-", ""
    )
    target_path = (
        f"{JFROG_NPM_REPO}/{NPM_SCOPE}/{package_name}/{version}/{tarball_filename}"
    )

    upload_command = [
        "jfrog",
        "rt",
        "upload",
        tarball_path,
        target_path,
    ]

    try:
        # Set JFrog CLI output to warning level
        os.environ["JFROG_CLI_LOG_LEVEL"] = "WARN"
        print(f"Running command: {' '.join(upload_command)}")
        result = subprocess.run(
            upload_command, check=True, capture_output=True, text=True
        )
        print("        JFrog CLI Output:")
        print(result.stdout)
        if result.stderr:
            print("        JFrog CLI Error Output (if any):")
            print(result.stderr)
        print(f"      Successfully uploaded {package_name}@{version}.")
    except subprocess.CalledProcessError as e:
        print(f"        Error uploading {package_name}@{version}:")
        print(f"        Command: {' '.join(e.cmd)}")
        print(f"        Return Code: {e.returncode}")
        print(f"        STDOUT: {e.stdout}")
        print(f"        STDERR: {e.stderr}")
        raise


def upload_all_packages_to_jfrog(downloaded_packages):
    """
    Uploads all downloaded packages to JFrog Artifactory.
    """
    print("\n" + "=" * 80)
    print("STARTING UPLOAD TO JFROG ARTIFACTORY")
    print("=" * 80)

    successful_uploads = []
    failed_uploads = []

    print(f"Current working directory: {os.getcwd()}")

    for package_info in downloaded_packages:
        package_name = package_info["package_name"]
        version = package_info["version"]
        tarball_path = package_info["tarball_path"]

        try:
            upload_to_jfrog(tarball_path, package_name, version)
            successful_uploads.append(f"{package_name}@{version}")
        except Exception as e:
            failed_uploads.append(
                {"package": f"{package_name}@{version}", "error": str(e)}
            )
            print(f"    Failed to upload {package_name}@{version}: {e}")

    # Display upload summary
    print("\n" + "=" * 80)
    print("UPLOAD SUMMARY")
    print("=" * 80)
    print(f"Total packages processed: {len(downloaded_packages)}")
    print(f"Successfully uploaded: {len(successful_uploads)}")
    print(f"Failed uploads: {len(failed_uploads)}")

    if successful_uploads:
        print("\nSuccessfully uploaded packages:")
        for pkg in successful_uploads:
            print(f"  ✓ {pkg}")

    if failed_uploads:
        print("\nFailed uploads:")
        for failure in failed_uploads:
            print(f"  ✗ {failure['package']}: {failure['error']}")


def display_download_statistics(downloaded_packages):
    """
    Display statistics and table of downloaded packages.
    """
    if not downloaded_packages:
        print("No packages were downloaded.")
        return

    # Calculate statistics
    packages_by_name = defaultdict(list)
    for pkg in downloaded_packages:
        packages_by_name[pkg["package_name"]].append(pkg)

    total_packages = len(packages_by_name)
    total_versions = len(downloaded_packages)

    print("\n" + "=" * 80)
    print("DOWNLOAD STATISTICS")
    print("=" * 80)
    print(f"Total unique packages: {total_packages}")
    print(f"Total versions downloaded: {total_versions}")

    # Package summary table
    print("\nPackage Summary:")
    summary_data = []
    for package_name, versions in packages_by_name.items():
        summary_data.append(
            [package_name, len(versions), ", ".join([v["version"] for v in versions])]
        )

    print(
        tabulate(
            summary_data,
            headers=["Package Name", "Versions Count", "Versions"],
            tablefmt="grid",
            maxcolwidths=[40, 15, 50],
        )
    )

    # Detailed table of all downloaded files
    print("\nDetailed Download List:")
    detailed_data = []
    for pkg in downloaded_packages:
        tarball_filename = os.path.basename(pkg["tarball_path"])
        file_size = "N/A"
        if os.path.exists(pkg["tarball_path"]):
            file_size = f"{os.path.getsize(pkg['tarball_path']) / 1024:.1f} KB"

        detailed_data.append(
            [
                pkg["package_name"],
                pkg["version"],
                tarball_filename,
                file_size,
                pkg["download_dir"],
            ]
        )

    print(
        tabulate(
            detailed_data,
            headers=[
                "Package Name",
                "Version",
                "Tarball Filename",
                "Size",
                "Download Directory",
            ],
            tablefmt="grid",
            maxcolwidths=[30, 15, 40, 15, 40],
        )
    )


def main():
    temp_dir = None
    downloaded_packages = []  # List to store all downloaded package info

    try:
        output_dir = os.path.join(os.getcwd(), "npm_packages_downloaded")
        os.makedirs(output_dir, exist_ok=True)
        print("=" * 80)
        print(f"Using output directory: {output_dir}")

        temp_dir = output_dir

        npm_packages = get_npm_packages_from_github()

        # Filter packages by adding the scope manually to match the desired scope
        scoped_packages = [
            p
            for p in npm_packages
            if f"{NPM_SCOPE}/{p.get('name', '')}".startswith(f"{NPM_SCOPE}/")
        ]

        if not scoped_packages:
            print(
                f"No packages found with scope '{NPM_SCOPE}' in GitHub Packages for {GITHUB_ORG}."
            )
            return

        print(f"Found {len(scoped_packages)} packages with scope '{NPM_SCOPE}'.")
        print("\n" + "=" * 80)
        print("DOWNLOADING PACKAGES FROM GITHUB")
        print("=" * 80)

        # Display all packages with count before downloading
        print("\n" + "=" * 80)
        print("ALL PACKAGES FOUND")
        print("=" * 80)
        for idx, pkg in enumerate(scoped_packages, 1):
            print(f"{idx:3}. {pkg.get('name', '')}")
        print(f"\nTotal packages found: {len(scoped_packages)}\n")
        print("=" * 80)

        # Phase 1: Download all packages
        for package_info in scoped_packages:
            package_name = package_info.get(
                "name"
            )  # This will be like @scope/package-name
            if not package_name:
                continue

            print("=" * 80)
            print(f"\nProcessing package: {package_name}")
            try:
                versions = get_package_versions_from_github(package_name)

                if not versions:
                    print(f"  No versions found for {package_name}. Skipping.")
                    continue

                print(f"  Found {len(versions)} versions for {package_name}.")

                for version_info in versions:
                    version = version_info.get("name")
                    if not version:
                        continue

                    package_version_dir = os.path.join(
                        temp_dir,
                        package_name.replace("/", "_").replace("@", ""),
                        version,
                    )

                    try:
                        tarball_path = download_npm_package_version(
                            package_name, version, package_version_dir
                        )

                        # Store package info for later processing
                        downloaded_packages.append(
                            {
                                "package_name": package_name,
                                "version": version,
                                "tarball_path": tarball_path,
                                "download_dir": package_version_dir,
                            }
                        )

                        print(
                            f"    ✓ Successfully downloaded @{NPM_SCOPE}/{package_name}@{version}"
                        )
                    except Exception as e:
                        print(
                            f"    ✗ Failed to download @{NPM_SCOPE}/{package_name}@{version}: {e}"
                        )
                        # Continue to the next version/package even if one fails
            except Exception as e:
                print(f"Failed to get versions for package {package_name}: {e}")

        # Phase 2: Display download statistics
        display_download_statistics(downloaded_packages)

        # Phase 3: Upload all packages to JFrog
        if downloaded_packages:
            upload_all_packages_to_jfrog(downloaded_packages)
        else:
            print("\nNo packages were downloaded, skipping upload phase.")

    except requests.exceptions.RequestException as e:
        print(f"HTTP Request Error: {e}")
    except subprocess.CalledProcessError as e:
        print(f"Command execution failed: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        pass
        # if temp_dir and os.path.exists(temp_dir):
        #     print(f"\nCleaning up temporary directory: {temp_dir}")
        #     shutil.rmtree(temp_dir)


if __name__ == "__main__":
    main()
