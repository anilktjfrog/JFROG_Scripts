# GitHub to JFrog NPM Package Migration

This script automates the migration of NPM packages from GitHub Packages to JFrog Artifactory.

---

## Prerequisites

- Python 3.7+
- [npm](https://www.npmjs.com/)
- [Jfrog CLI](https://jfrog.com/getcli/)
- GitHub Personal Access Token (PAT) with `read:packages` scope
- Access to JFrog Artifactory with permissions to upload NPM packages

---

## Environment Variables

Set the following environment variables before running the script:

```sh
export GITHUB_ORG="your-github-org"
export NPM_SCOPE="@your-npm-scope"
export GITHUB_ORG_TYPE="orgs"  # or "users" if using a user account
export GITHUB_PAT="your-github-pat"
export JFROG_NPM_REPO="your-jfrog-npm-repo"
export TEMP_DIR_PREFIX="npm_package_sync_"  # optional

export ARTIFACTORY_TOKEN="your-jfrog-access-token"

```

---

## JFrog CLI Configuration

Before running the script, configure the JFrog CLI to connect to your Artifactory instance. Use the following command:

```sh
jf config add koerber --url=https://krbr.jfrog.io --access-token=$ARTIFACTORY_TOKEN --interactive=false
```

---

## Installation

1. Clone this repository.
2. Create and activate a virtual environment:

   ```sh
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install all dependencies from `requirements.txt`:

   ```sh
   pip install -r requirements.txt
   ```

---

## Usage

1. Ensure all environment variables are set.
2. Run the script:

   ```sh
   python migrate_npm_from_github_to_jfrog.py
   ```

---

## What the Script Does

1. **Fetches all NPM packages** from your GitHub organization.
2. **Downloads every version** of each package using `npm pack`.
3. **Displays statistics** about the downloaded packages.
4. **Uploads all tarballs** to your JFrog Artifactory NPM repository using JFrog CLI.

---

## Output

- Downloaded packages are saved in `npm_packages_downloaded/`.
- Upload and download statistics are printed in the console.

---

## Troubleshooting

- Ensure your GitHub PAT has the correct permissions.
- Make sure JFrog CLI is configured (`jfrog rt c`).
- Check that your NPM scope and JFrog repo are correct.

---
