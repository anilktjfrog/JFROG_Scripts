# Version 0.9 - Nov 5 2024

import requests
import urllib3
import sys
import argparse
import json
import threading
import os

from tabulate import tabulate

urllib3.disable_warnings()

# Single lock for all file operations
file_lock = threading.Lock()

##########################################################################
# Common Functions -- START
##########################################################################


def thread_safe_log(message, file_path):
    """Thread-safe logging to a file"""
    with file_lock:
        with open(file_path, "a") as f:
            f.write(f"{message}\n")


def debug_request(
    method, url, auth=None, headers=None, data=None, json_data=None, debug=False
):
    """Print equivalent curl command for a request if debug mode is enabled"""
    if not debug:
        return

    curl_command = f'curl -X {method} "{url}"'

    if headers:
        for key, value in headers.items():
            curl_command += f' -H "{key}: {value}"'
    elif auth:  # Fallback for old auth method
        if isinstance(auth, tuple):
            if auth[0] == "_token":
                curl_command += f' -H "Authorization: Bearer {auth[1]}"'
            else:
                curl_command += f' -u "{auth[0]}:{auth[1]}"'

    if json_data:
        json_str = json.dumps(json_data)
        json_str = json_str.replace('"', '\\"')
        curl_command += f' -d "{json_str}"'
    elif data:
        data_str = str(data).replace('"', '\\"')
        curl_command += f' -d "{data_str}"'

    print("\nDebug - Equivalent curl command:")
    print(curl_command)
    print()


##########################################################################
# Common Functions -- END
##########################################################################


##########################################################################
# Artifactory Class
##########################################################################
# This class defines an Artifactory object that carries its own information
# This helps with readability, re-usability, and to reduce the need to hard code information
class Artifactory:
    def __init__(self, url, auth, name, debug=False):

        ###################################################
        # Artifactory Instance Information
        ###################################################
        self.url = url
        self.auth = auth
        self.name = name
        self.debug = debug
        print(f"\nInitializing {name} Artifactory connection:")
        print(f"URL: {url}")
        print(f"Auth type: {'Bearer token' if auth[0] == '_token' else 'Basic auth'}")

        # Create standard headers with auth
        self.headers = {
            "Authorization": f"Bearer {auth[1]}",
            "Content-Type": "application/json",
        }

        # Get storage information of the Artifactory instance
        self.storage = self.storage()

        ###################################################
        # Gather Repository Info from Artifactory Instance
        ###################################################
        self.gather_repository_info()

    ##########################################################################
    # Repositories Functions -- START
    ##########################################################################

    def get_repo_list(self):
        """Get list of repository keys"""
        url = self.url + "/artifactory/api/repositories"
        debug_request("GET", url, headers=self.headers, debug=self.debug)
        repos = requests.get(url, headers=self.headers, verify=False)
        if repos.status_code != 200:
            print(f"Error getting repository list: {repos.status_code} - {repos.text}")
            return []
        return [repo["key"] for repo in repos.json()]

    def get_repo_details(self):
        """Get repository details from storage info"""
        try:
            return self.storage.get("repositoriesSummaryList", [])
        except (KeyError, AttributeError):
            return []

    def get_filtered_repos_storage(self):
        """Get filtered repository storage information"""
        l, r, f = {}, {}, {}
        for summary in self.repo_details:
            try:
                if summary["repoType"] == "LOCAL":
                    l[summary["repoKey"]] = summary
                elif summary["repoType"] == "FEDERATED":
                    f[summary["repoKey"]] = summary
                elif summary["repoType"] == "CACHE":
                    r[summary["repoKey"]] = summary
            except KeyError:
                continue
        return l, r, f

    def gather_repository_info(self):

        self.repository_configurations = self.get_repository_configurations()

        # Get the names of all repositories
        self.repos = self.get_repo_list()

        # Get repository details from storage info
        self.repo_details = self.get_repo_details()

        # Get filtered repository storage information
        self.local_storage, self.remote_storage, self.federated_storage = (
            self.get_filtered_repos_storage()
        )

        # Get filtered repository configurations
        (
            self.local_configs,
            self.federated_configs,
            self.remote_configs,
            self.virtual_configs,
        ) = self.get_filtered_repo_configs()

    def get_repository_configurations(self):
        repos = requests.get(
            self.url + "/artifactory/api/repositories/configurations",
            headers=self.headers,
            verify=False,
        )
        return repos.json()

    def get_filtered_repo_configs(self):
        l, f, r, v = {}, {}, {}, {}

        try:
            for repo in self.repository_configurations["LOCAL"]:
                repo_name = repo["key"]
                l[repo_name] = repo
        except KeyError:
            l = {}

        try:
            for repo in self.repository_configurations["FEDERATED"]:
                repo_name = repo["key"]
                f[repo_name] = repo
        except KeyError:
            f = {}

        try:
            for repo in self.repository_configurations["REMOTE"]:
                repo_name = repo["key"]
                r[repo_name] = repo
        except KeyError:
            r = {}

        try:
            for repo in self.repository_configurations["VIRTUAL"]:
                repo_name = repo["key"]
                v[repo_name] = repo
        except KeyError:
            v = {}

        return l, f, r, v

    def assign_repo_to_project(self, repo_name, project_key):
        """Assign a repository to a project"""
        url = f"{self.url}/access/api/v1/projects/_/attach/repositories/{repo_name}/{project_key}?force=true"
        debug_request("PUT", url, headers=self.headers, debug=self.debug)
        resp = requests.put(url, headers=self.headers, verify=False)
        return resp.status_code == 204, resp

    def check_repo_exists(self, repo_name, package_type=None):
        """
        Check if a repository exists in target Artifactory
        Args:
            repo_name: Name of the repository to check
            package_type: Package type of the repository (e.g. "docker")
        Returns:
            bool: True if repository exists, False otherwise
        """
        # For docker repos, check with hyphenated name
        if package_type == "docker":
            repo_name = repo_name.replace("_", "-").replace(".", "-")

        resp = requests.get(
            f"{self.url}/artifactory/api/repositories/{repo_name}",
            headers=self.headers,
            verify=False,
        )
        return resp.status_code == 200

    ##########################################################################
    # Repositories Functions -- END
    ##########################################################################

    ##########################################################################
    # Storage Info Functions -- START

    # This section contains functions such as:
    # - storage: Get storage information
    # - refresh_storage_summary: Refresh storage summary
    ##########################################################################
    def storage(self):
        url = self.url + "/artifactory/api/storageinfo"
        debug_request("GET", url, headers=self.headers, debug=self.debug)
        storage = requests.get(url, headers=self.headers, verify=False)
        if storage.status_code != 200:
            print(f"Error getting storage info: {storage.status_code} - {storage.text}")
            return {}
        return storage.json()

    def refresh_storage_summary(self):
        headers = {
            "content-type": "application/json",
        }
        resp = requests.post(
            self.url + "/artifactory/api/storageinfo/calculate",
            headers=headers,
            verify=False,
        )
        if resp.status_code != 202:
            print("Non-202 response:", resp.status_code)
            print(resp.text)

        self.local_storage, self.remote_storage, self.federated_storage = (
            self.get_filtered_repos_storage()
        )

    ##########################################################################
    # Storage Info Functions -- END
    ##########################################################################


###########################################################################
# Artifactory Helper Class
###########################################################################


class ArtifactoryHelper:

    def __init__(self, rt1, rt2):
        self.rt1 = rt1
        self.rt2 = rt2

    ####################################################################################
    # Create repositories between source and target based on repo naming file -- START
    ####################################################################################

    def jfrog_resource_rename_mapping_tulples(
        self,
        filename=None,
        jfrog_resource_type=None,
        error_file=None,
        success_file=None,
        delimiter=",",
    ):
        try:
            with open(filename, "r") as f:
                repo_tuples = [
                    line.strip().split(delimiter) for line in f if line.strip()
                ]
        except FileNotFoundError:
            print(f"Error: File {filename} not found")
            return
        except Exception as e:
            print(f"Error reading file {filename}: {str(e)}")
            return

        print(f"Found {len(repo_tuples)} {jfrog_resource_type} tuples to process")
        thread_safe_log(
            f"Found {len(repo_tuples)} {jfrog_resource_type} tuples to process",
            success_file,
        )

        # Validate the format of each tuple
        valid_tuples = []
        for i, tuple_data in enumerate(repo_tuples):
            if len(tuple_data) != 2:
                error_msg = f"Invalid format at line {i+1}: {','.join(tuple_data)}. Expected format: oldname,newname"
                print(error_msg)
                thread_safe_log(error_msg, error_file)
                continue
            old_name, new_name = tuple_data
            if not old_name or not new_name:
                error_msg = f"Empty {jfrog_resource_type} name at line {i+1}: {','.join(tuple_data)}"
                print(error_msg)
                thread_safe_log(error_msg, error_file)
                continue
            valid_tuples.append((old_name.strip(), new_name.strip()))

        print(f"Processing {len(valid_tuples)} valid {jfrog_resource_type} tuples")

        # Create a mapping of old names to new names for quick lookup
        rename_mapping = {old_name: new_name for old_name, new_name in valid_tuples}

        return valid_tuples, rename_mapping

    def create_repos_with_new_names(self, repo_mapping_file=None):
        """
        Create repositories with new names based on a file containing tuples of old and new names.
        The file should contain one tuple per line in the format "oldname,newname".
        """
        error_file = "./create_renamed_repos_errors.log"
        success_file = "./create_renamed_repos_success.log"

        # Get repo_valid_tuples and repo_mapping_file
        print(f"\nCreating repositories with new names from file: {repo_mapping_file}")
        repo_valid_tuples, repo_mapping_file = (
            self.jfrog_resource_rename_mapping_tulples(
                filename=repo_mapping_file,
                jfrog_resource_type="repository",
                error_file=error_file,
                success_file=success_file,
            )
        )

        # Process each repository tuple
        for old_name, new_name in repo_valid_tuples:
            # Determine the repository type
            repo_type = None
            if old_name in self.rt1.local_configs:
                repo_type = "local"
            elif old_name in self.rt1.remote_configs:
                repo_type = "remote"
            elif old_name in self.rt1.virtual_configs:
                repo_type = "virtual"
            elif old_name in self.rt1.federated_configs:
                repo_type = "federated"

            if not repo_type:
                error_msg = f"Repository {old_name} not found in source"
                print(error_msg)
                thread_safe_log(error_msg, error_file)
                continue

            # Create the repository with the new name
            print(f"Creating {repo_type} repository: {new_name} (from {old_name})")

            # Get source configuration based on repo type
            source_config = None
            if repo_type == "local":
                # continue
                source_config = self.rt1.local_configs[old_name]
            elif repo_type == "remote":
                # continue
                source_config = self.rt1.remote_configs[old_name]
            elif repo_type == "virtual":
                source_config = self.rt1.virtual_configs[old_name]
            elif repo_type == "federated":
                source_config = self.rt1.federated_configs[old_name]

            repo = source_config.copy()

            # Set common properties
            repo["rclass"] = repo_type
            repo["dockerApiVersion"] = "V2"
            repo["packageType"] = repo.get("packageType", "maven")
            repo["repoLayoutRef"] = repo.get("repoLayoutRef", "maven-2-default")
            repo["key"] = new_name  # Set the new repository name

            # Handle type-specific configurations
            if repo_type == "remote":
                remote_repo_value = True
                repo["password"] = ""  # Clear password for safety
            elif repo_type == "virtual":
                # Check for dependent repositories
                if "repositories" in repo:
                    missing_deps = []
                    for dep_repo in repo["repositories"]:
                        # Check if the dependent repository exists with its original name
                        if not self.rt2.check_repo_exists(
                            dep_repo, repo["packageType"]
                        ):
                            # Check if the dependent repository has a new name in the mapping
                            if dep_repo in repo_mapping_file:
                                new_dep_name = repo_mapping_file[dep_repo]
                                if self.rt2.check_repo_exists(
                                    new_dep_name, repo["packageType"]
                                ):
                                    # Update the dependency to use the new name
                                    repo["repositories"][
                                        repo["repositories"].index(dep_repo)
                                    ] = new_dep_name
                                    print(
                                        f"Updated dependency {dep_repo} to use new name {new_dep_name}"
                                    )
                                    continue

                            missing_deps.append(dep_repo)
                            print(
                                f"Warning: Dependent repository {dep_repo} for virtual repo {new_name} does not exist"
                            )

                    if missing_deps:
                        error_msg = f"Cannot create virtual repository {new_name} - missing dependent repositories: {', '.join(missing_deps)}"
                        print(error_msg)
                        thread_safe_log(error_msg, error_file)
                        continue

                # Check and update defaultDeploymentRepo if it exists and has a new name in the mapping
                if (
                    "defaultDeploymentRepo" in repo
                    and repo["defaultDeploymentRepo"] in repo_mapping_file
                ):
                    old_default_repo = repo["defaultDeploymentRepo"]
                    new_default_repo = repo_mapping_file[old_default_repo]
                    if self.rt2.check_repo_exists(
                        new_default_repo, repo["packageType"]
                    ):
                        repo["defaultDeploymentRepo"] = new_default_repo
                        print(
                            f"Updated defaultDeploymentRepo {old_default_repo} to use new name {new_default_repo}"
                        )
            elif repo_type == "federated":
                repo["members"] = [
                    {"url": f"{self.rt1.url}/artifactory/{old_name}", "enabled": "true"}
                ]

            # Create repository
            resp = requests.put(
                f"{self.rt2.url}/artifactory/api/repositories/{new_name}",
                json=repo,
                headers=self.rt2.headers,
                verify=False,
            )
            repo_exists_in_target = False
            if resp.status_code == 400:
                print("Error: Repository already exists in target")
                repo_exists_in_target = True

            if resp.status_code == 200 or repo_exists_in_target:
                success_msg = f"Successfully created {repo_type} repository: {new_name} (from {old_name})"
                print(success_msg)
                thread_safe_log(success_msg, success_file)
            else:
                error_msg = f"Failed to create {repo_type} repository {new_name} (from {old_name}): {resp.status_code} - {resp.text}"
                print(error_msg)
                thread_safe_log(error_msg, error_file)

    ####################################################################################
    # Create repositories between source and target based on repo naming file -- END
    ####################################################################################

    #############################################################################
    # Create Repository Functions -- END
    #############################################################################

    #############################################################################
    # Create Repository Replication -- START

    # This section consists of:
    # 1. create_push_replication_between_source_and_target - Creates push replication between source and target for repositories
    # 2. trigger_push_replication_on_source - Triggers push replication for repositories
    # 3. get_replication_status_between_source_and_target - Gets the replication status between source and target for repositories
    #############################################################################

    def create_push_replication_between_source_and_target(
        self,
        repo_mapping_file=None,
        replication_user=None,
        replication_password=None,
        dry_run="YES",
    ):
        """
        Create push replication between source and target for repositories.
        """
        error_file = "./create_push_replication_errors.log"
        success_file = "./create_push_replication_success.log"

        # Get repo_valid_tuples and repo_mapping_file
        print(
            f"\nRead the repository mapping file to find out the source and target repo: {repo_mapping_file}"
        )
        repo_valid_tuples, repo_mapping_file = (
            self.jfrog_resource_rename_mapping_tulples(
                filename=repo_mapping_file,
                jfrog_resource_type="repository",
                error_file=error_file,
                success_file=success_file,
            )
        )

        # Crontime configuration
        ## Dont change the default timer. The below schedules replication for all repos 2 minutes apart
        max = 60
        maxhr = 24
        cronmin = 0
        mininterval = 2
        cronhr = 0
        reset = 0

        # Store all replication configurations to JSON Files under folder ./replication_configs
        replication_configs = {}
        # Create the directory if it doesn't exist
        os.makedirs("replication_configs", exist_ok=True)

        # print
        for key in self.rt1.local_configs.keys():
            if "build-info" in key:
                print(key)

        # Process each repository tuple
        for old_name, new_name in repo_valid_tuples:
            # Determine the repository type
            repo_type = None
            if old_name in self.rt1.local_configs:
                repo_type = "local"
            elif old_name in self.rt1.remote_configs:
                repo_type = "remote"
            elif old_name in self.rt1.virtual_configs:
                repo_type = "virtual"
            elif old_name in self.rt1.federated_configs:
                repo_type = "federated"

            if not repo_type:
                error_msg = f"Repository {old_name} not found in source"
                print(error_msg)
                thread_safe_log(error_msg, error_file)
                continue

            # Check target repository existence
            if not self.rt2.check_repo_exists(new_name):
                error_msg = f"Target repository {new_name} does not exist in target"
                print(error_msg)
                thread_safe_log(error_msg, error_file)
                continue

            # Create the push replication
            print(
                f"Creating push replication between {repo_type} source repository:{old_name} to target new repository: {new_name}"
            )

            # Get source configuration based on repo type
            source_config = None
            if repo_type == "local":
                source_config = self.rt1.local_configs[old_name]
            elif repo_type == "remote":
                source_config = self.rt1.remote_configs[old_name]
            elif repo_type == "virtual":
                source_config = self.rt1.virtual_configs[old_name]
            elif repo_type == "federated":
                source_config = self.rt1.federated_configs[old_name]

            # Enable push replication for local repositories
            if repo_type == "local":
                # Check if replication is already set up on the source to the target repo
                replication_url = (
                    f"{self.rt1.url}/artifactory/api/replications/{old_name}"
                )

                # Get the replication configuration from the source
                resp = requests.get(
                    replication_url,
                    headers=self.rt1.headers,
                    verify=False,
                )

                source_replication_exists = False
                if resp.status_code == 200:
                    replication_data = resp.json()

                    # Loop through the replication data to check for existing configurations
                    for replication in replication_data:

                        # Check if the replication URL matches the target repository
                        if (
                            replication.get("url")
                            == f"{self.rt2.url}/artifactory/{new_name}"
                        ):
                            # Replication already exists
                            print(
                                f"Push replication already exists between {repo_type} repository: {old_name} and target repo: {new_name}"
                            )
                            source_replication_exists = True
                            continue
                        else:
                            # Replication exists but not for the new target
                            print(
                                f"Push replication already exists for {repo_type} repository: {old_name}, but not for the new target {new_name}"
                            )

                # Continue to create a new replication configuration
                if not source_replication_exists:
                    # Cron time is set to run every 2 minutes
                    if cronmin < max and cronhr < maxhr:
                        cronmin += mininterval
                        if cronmin == max:
                            cronhr += 1
                            cronmin = reset
                    elif cronmin == max:
                        cronhr += 1
                        cronmin = reset
                    elif cronhr == maxhr:
                        cronhr = reset
                        cronmin = reset
                    # Set the cron expression
                    cron_exp = f"{cronmin} {cronhr} {reset} * * ?"

                    # Push replication configuration on source
                    replication_config = {
                        "url": f"{self.rt2.url}/artifactory/{new_name}",
                        "username": replication_user,
                        "password": replication_password,
                        "enabled": True,
                        "cronExp": cron_exp,
                        "repoKey": new_name,
                        "disableProxy": True,
                        "enableEventReplication": True,
                        "syncDeletes": False,
                        "syncProperties": True,
                        "syncStatistics": True,
                    }

                    # Store the replication configuration in a JSON file
                    replication_configs[old_name] = replication_config

                    with open(
                        f"replication_configs/{old_name}_replication_config.json",
                        "w",
                    ) as f:
                        json.dump(replication_config, f, indent=4)

                    if not dry_run:
                        # Create push replication on source
                        resp = requests.put(
                            f"{self.rt1.url}/artifactory/api/replications/{old_name}",
                            json=replication_config,
                            headers=self.rt1.headers,
                            verify=False,
                        )
                        if resp.status_code in range(200, 202):
                            success_msg = f"Successfully created push replication for {repo_type} repository: {new_name} (from {old_name})"
                            print(success_msg)
                            thread_safe_log(success_msg, success_file)
                        else:
                            error_msg = f"Failed to create push replication for {repo_type} repository {new_name} (from {old_name}): {resp.status_code} - {resp.text}"
                            print(error_msg)
                            thread_safe_log(error_msg, error_file)
                    else:
                        success_msg = f"DRY RUN: Push replication for {repo_type} repository {new_name} (from {old_name}) would be created"
                        print(success_msg)
                        thread_safe_log(success_msg, success_file)

    def trigger_push_replication_on_source(self, repo_mapping_file=None):
        """
        Trigger push replication for repositories.
        """
        error_file = "./trigger_push_replication_on_source_errors.log"
        success_file = "./trigger_push_replication_on_source_success.log"

        # Get repo_valid_tuples and repo_mapping_file
        print(
            f"\nRead the repository mapping file to find out the source and target repo: {repo_mapping_file}"
        )
        repo_valid_tuples, repo_mapping_file = (
            self.jfrog_resource_rename_mapping_tulples(
                filename=repo_mapping_file,
                jfrog_resource_type="repository",
                error_file=error_file,
                success_file=success_file,
            )
        )

        # Process each repository tuple
        table = []
        for old_name, new_name in repo_valid_tuples:
            # Determine the repository type
            repo_type = None
            if old_name in self.rt1.local_configs:
                repo_type = "local"
            elif old_name in self.rt1.remote_configs:
                repo_type = "remote"
            elif old_name in self.rt1.virtual_configs:
                repo_type = "virtual"
            elif old_name in self.rt1.federated_configs:
                repo_type = "federated"

            if not repo_type:
                error_msg = f"Repository {old_name} not found in source"
                print(error_msg)
                thread_safe_log(error_msg, error_file)
                continue

            # Check target repository existence
            if not self.rt2.check_repo_exists(new_name):
                error_msg = f"Target repository {new_name} does not exist in target"
                print(error_msg)
                thread_safe_log(error_msg, error_file)
                continue

            # Trigger push replication
            print(
                f"Triggering push replication for {repo_type} source repository:{old_name} to target new repository: {new_name}"
            )

            # Trigger replication on source
            trigger_replication_url = (
                f"{self.rt1.url}/artifactory/api/replication/execute/{old_name}"
            )

            resp = requests.post(
                trigger_replication_url,
                headers=self.rt1.headers,
                verify=False,
            )

            try:
                resp_json = resp.json()
                # If the response contains a "messages" key, extract and print in table format
                if "messages" in resp_json and isinstance(resp_json["messages"], list):

                    for msg in resp_json["messages"]:
                        level = msg.get("level", "")
                        message = msg.get("message", "")
                        table.append([level, message])
                else:
                    print("No messages found in response.")
            except Exception as e:
                print(f"Error parsing replication trigger response: {e}")

            if resp.status_code in range(200, 204):
                success_msg = f"Successfully triggered push replication for {repo_type} repository: {new_name} (from {old_name})"
                print(success_msg)
                thread_safe_log(success_msg, success_file)
            else:
                error_msg = f"Failed to trigger push replication for {repo_type} repository {new_name} (from {old_name}): {resp.status_code} - {resp.text}"
                print(error_msg)
                thread_safe_log(error_msg, error_file)

        print("\nReplication Trigger Output:")
        print(tabulate(table, headers=["Level", "Message"], tablefmt="grid"))

    def get_replication_status_between_source_and_target(self, repo_mapping_file=None):
        """
        Get the replication status between source and target for repositories.
        """
        error_file = "./get_replication_status_errors.log"
        success_file = "./get_replication_status_success.log"

        # Get repo_valid_tuples and repo_mapping_file
        print(
            f"\nRead the repository mapping file to find out the source and target repo: {repo_mapping_file}"
        )
        repo_valid_tuples, repo_mapping_file = (
            self.jfrog_resource_rename_mapping_tulples(
                filename=repo_mapping_file,
                jfrog_resource_type="repository",
                error_file=error_file,
                success_file=success_file,
            )
        )

        # Prepare table data
        table_data = []
        headers = [
            "Source Repo",
            "Target Repo URL",
            "Replication Status",
            "Last Completed",
        ]

        # Process each repository tuple
        for old_name, new_name in repo_valid_tuples:
            # Determine the repository type
            repo_type = None
            if old_name in self.rt1.local_configs:
                repo_type = "local"
            elif old_name in self.rt1.remote_configs:
                repo_type = "remote"
            elif old_name in self.rt1.virtual_configs:
                repo_type = "virtual"
            elif old_name in self.rt1.federated_configs:
                repo_type = "federated"

            if not repo_type:
                error_msg = f"Repository {old_name} not found in source"
                print(error_msg)
                thread_safe_log(error_msg, error_file)
                continue

            # Check target repository existence
            if not self.rt2.check_repo_exists(new_name):
                error_msg = f"Target repository {new_name} does not exist in target"
                print(error_msg)
                thread_safe_log(error_msg, error_file)
                continue

            # Get replication status
            print(
                f"Getting replication status between {repo_type} source repository:{old_name} to target new repository: {new_name}"
            )

            # Get replication configuration from source
            replication_url = f"{self.rt1.url}/artifactory/api/replications/{old_name}"

            # Get the replication status
            replication_status_url = (
                f"{self.rt1.url}/artifactory/api/replication/{old_name}"
            )

            resp = requests.get(
                replication_url,
                headers=self.rt1.headers,
                verify=False,
            )

            replication_resp = requests.get(
                replication_status_url,
                headers=self.rt1.headers,
                verify=False,
            )

            if resp.status_code == 200:
                replication_data = resp.json()
                for replication in replication_data:
                    if (
                        replication.get("url")
                        == f"{self.rt2.url}/artifactory/{new_name}"
                    ):
                        status = None
                        lastCompleted = None
                        try:
                            replication_status_json = json.loads(
                                replication_resp._content.decode("utf-8")
                            )
                            status = replication_status_json.get("status", "Unknown")
                            lastCompleted = replication_status_json.get(
                                "lastCompleted", "Unknown"
                            )
                        except Exception as e:
                            status = f"Error parsing status: {e}"
                        table_data.append(
                            [old_name, replication.get("url"), status, lastCompleted]
                        )
                        success_msg = f"Replication status for {repo_type} repository {old_name} to target {new_name}: {status}"
                        print(success_msg)
                        thread_safe_log(success_msg, success_file)
                    else:
                        error_msg = f"Replication not set up for {repo_type} repository {old_name} to target {new_name}"
                        print(error_msg)
                        thread_safe_log(error_msg, error_file)
            else:
                error_msg = f"Failed to get replication status for {repo_type} repository {old_name}: {resp.status_code} - {resp.text}"
                print(error_msg)
                thread_safe_log(error_msg, error_file)

        # Display the table
        if table_data:
            print("\nReplication Status Table:")
            print(tabulate(table_data, headers=headers, tablefmt="grid"))
        else:
            print("\nNo replication data available.")

    #############################################################################
    # Create Repository Replication -- END
    #############################################################################


##########################################################################
# This function is parses command-line arguments
##########################################################################
def parse_args():

    parser = argparse.ArgumentParser(
        description="Script to replicate repositories and configurations between two Artifactory instances."
    )

    # Required arguments
    parser.add_argument("--source-url", required=True, help="Source Artifactory URL")
    parser.add_argument(
        "--source-token", required=True, help="Source Artifactory access token"
    )
    parser.add_argument("--target-url", required=True, help="Target Artifactory URL")
    parser.add_argument(
        "--target-token", required=True, help="Target Artifactory access token"
    )

    # Command argument
    parser.add_argument(
        "command",
        choices=[
            "create_repos_with_new_names",
            "create_push_replication_between_source_and_target",
            "trigger_push_replication_on_source",
            "get_replication_status_between_source_and_target",
        ],
        help="Command to execute",
    )

    # Add argument for repository rename file
    parser.add_argument(
        "--repo_mapping_file",
        help='File containing repository name tuples in format "oldname,newname" (one per line)',
    )

    # Add argument for specifying the replication_user
    parser.add_argument(
        "--replication_user",
        help="Username for replication configuration (required for create_push_replication)",
    )

    # Add argument for specifying the replication_password
    parser.add_argument(
        "--replication_password",
        help="Password for replication configuration (required for create_push_replication)",
    )

    # Add dry_run argument
    parser.add_argument(
        "--dry_run",
        action="store_true",
        help="List repositories that would be deleted without actually deleting them",
    )

    # Add debug argument
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug output including curl commands",
    )

    return parser.parse_args()


#########################################################################
# Main Function -- START
#########################################################################


def main():
    args = parse_args()

    # Create authentication tuples for each instance
    if args.source_token.startswith("Bearer "):
        source_token = args.source_token[7:]  # Remove 'Bearer ' prefix
    else:
        source_token = args.source_token

    if args.target_token.startswith("Bearer "):
        target_token = args.target_token[7:]  # Remove 'Bearer ' prefix
    else:
        target_token = args.target_token

    source_auth = ("_token", source_token)
    target_auth = ("_token", target_token)

    if args.debug:
        print("\nSource URL:", args.source_url)
        print("Target URL:", args.target_url)
        print(
            "Source token type:",
            (
                "Bearer token"
                if args.source_token.startswith("Bearer ")
                else "Access token"
            ),
        )
        print(
            "Target token type:",
            (
                "Bearer token"
                if args.target_token.startswith("Bearer ")
                else "Access token"
            ),
        )

    # Initialize the objects that help us interact
    source = Artifactory(args.source_url, source_auth, "source", debug=args.debug)
    target = Artifactory(args.target_url, target_auth, "target", debug=args.debug)
    helper = ArtifactoryHelper(source, target)

    # Execute the requested command
    if args.command == "create_repos_with_new_names":
        if not args.repo_mapping_file:
            print(
                "Error: --rename-file is required for create_repos_with_new_names command"
            )
            sys.exit(1)
        helper.create_repos_with_new_names(repo_mapping_file=args.repo_mapping_file)

    elif args.command == "create_push_replication_between_source_and_target":
        if not args.repo_mapping_file:
            print(
                "Error: --repo_mapping_file is required for create_push_replication_between_source_and_target command"
            )
            sys.exit(1)
        if not args.replication_user:
            print(
                "Error: --replication_user is required for create_push_replication_between_source_and_target command"
            )
            sys.exit(1)
        if not args.replication_password:
            print(
                "Error: --replication_password is required for create_push_replication_between_source_and_target command"
            )
            sys.exit(1)

        helper.create_push_replication_between_source_and_target(
            repo_mapping_file=args.repo_mapping_file,
            replication_user=args.replication_user,
            replication_password=args.replication_password,
            dry_run=args.dry_run,
        )

    elif args.command == "trigger_push_replication_on_source":
        if not args.repo_mapping_file:
            print(
                "Error: --repo_mapping_file is required for trigger_push_replication_on_source command"
            )
            sys.exit(1)
        helper.trigger_push_replication_on_source(
            repo_mapping_file=args.repo_mapping_file,
        )

    elif args.command == "get_replication_status_between_source_and_target":
        if not args.repo_mapping_file:
            print(
                "Error: --repo_mapping_file is required for get_replication_status_between_source_and_target command"
            )
            sys.exit(1)
        helper.get_replication_status_between_source_and_target(
            repo_mapping_file=args.repo_mapping_file,
        )


#########################################################################
# Main Function -- END
#########################################################################


if __name__ == "__main__":
    # Call the main function to start the script
    main()
