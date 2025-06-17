# Push Replication Script

This repository contains a Python script, `push_replication.py`, designed to automate the process of pushing code or data from a local repository to a remote repository. The script streamlines replication tasks, ensuring consistency and reducing manual intervention.

## Features

- Automates the setup of push replication between JFrog Artifactory instances.
- Supports creating repositories on the target with new names using mapping files.
- Provides commands to trigger replication and check replication status.

## Requirements

- Python 3.13+
- `git` installed and available in your system's PATH
- Required Python packages (see below)

## Installation

1. Clone this repository:

   ```bash
   git clone <repository-url>
   cd push-replication
   ```

2. Create a virtual environment (recommended):

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install dependencies:

   ```bash
   pip3 install -r requirements.txt
   ```

## Usage

Run the script with the desired command and required arguments.

### Arguments

- `--source-url`: URL of the source JFrog Artifactory instance.
- `--source-token`: Access token for the source JFrog instance.
- `--target-url`: URL of the target JFrog Artifactory instance.
- `--target-token`: Access token for the target JFrog instance.
- `create_repos_with_new_names`: Command to create repositories on the target with new names.
  - `--repo_mapping_file`: Path to the file containing repository rename mappings.
- `create_push_replication_between_source_and_target`: Command to set up push replication between source and target.
  - `--repo_mapping_file`: Path to the file containing repository rename mappings.
  - `--replication_user`: Username for replication authentication.
  - `--replication_password`: Password for replication authentication.
- `trigger_push_replication_on_source`: Command to trigger replication on the source JFrog instance.
  - `--repo_mapping_file`: Path to the file containing repository rename mappings.
- `get_replication_status_between_source_and_target`: Command to get replication status between source and target.
  - `--repo_mapping_file`: Path to the file containing repository rename mappings.

Below are some common usage examples:

### 1. Create repositories with new names

```bash
python push_replication.py \
    --source-url <source-jfrog-url> \
    --source-token <source-token> \
    --target-url <target-jfrog-url> \
    --target-token <target-token> \
    --repo_mapping_file <path-to-repo-mapping> \
    create_repos_with_new_names
```

### 2. Create push replication between source and target

```bash
python push_replication.py \
    --source-url <source-jfrog-url> \
    --source-token <source-token> \
    --target-url <target-jfrog-url> \
    --target-token <target-token> \
    --repo_mapping_file <path-to-repo-mapping> \
    --replication_user <replication-username> \
    --replication_password <replication-password> \
    create_push_replication_between_source_and_target
```

### 3. Trigger replication on source

```bash
python push_replication.py \
    --source-url <source-jfrog-url> \
    --source-token <source-token> \
    --target-url <target-jfrog-url> \
    --target-token <target-token> \
    --repo_mapping_file <path-to-repo-mapping> \
    trigger_push_replication_on_source
```

### 4. Get replication status

```bash
python push_replication.py \
    --source-url <source-jfrog-url> \
    --source-token <source-token> \
    --target-url <target-jfrog-url> \
    --target-token <target-token> \
    --repo_mapping_file <path-to-repo-mapping> \
    get_replication_status_between_source_and_target
```

> **Replace placeholders (e.g., `<source-jfrog-url>`, `<source-token>`, etc.) with your actual values before running the commands.**

## Notes

- Ensure you have admin access to the source and target JFROG artifactory instances
