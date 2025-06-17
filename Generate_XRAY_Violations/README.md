# generateviolations.py

A command-line tool to query and export violations from JFrog Xray using its REST API. For each release bundle under a specified watch, the script fetches violations and writes them to separate JSON files, displaying summary tables in the terminal.

## Requirements

- Python 3.x
- `requests`
- `tabulate`

Install dependencies:

```bash
pip install requests tabulate packaging
```

## Usage

```bash
python3 generateviolations.py [OPTIONS]
```

### Required Arguments

| Argument           | Description                                                       |
| ------------------ | ----------------------------------------------------------------- |
| `--jfrog_url`      | JFrog Xray URL (e.g., `https://xray.example.com`)                 |
| `--jfrog_token`    | Bearer token for authentication                                   |
| `--watch_name`     | Name of the watch                                                 |
| `--violation_type` | Type of violation (e.g., `Security`)                              |
| `--min_severity`   | Minimum severity (`Critical`, `High`, `Medium`, `Low`, `Unknown`) |
| `--created_from`   | Start date/time (e.g., `2025-06-16T18:22:04+00:00`)               |
| `--created_until`  | End date/time (e.g., `2025-07-17T18:22:04+00:00`)                 |

### Optional Arguments

| Argument      | Description                         | Default |
| ------------- | ----------------------------------- | ------- |
| `--order_by`  | Field to order by (e.g., `created`) | created |
| `--direction` | Order direction (`asc` or `desc`)   | asc     |
| `--limit`     | Number of results to return         | 100     |
| `--offset`    | Offset for pagination               | 1       |

### Example

```bash
python3 generateviolations.py \
    --jfrog_url https://xray.example.com \
    --jfrog_token YOUR_TOKEN \
    --watch_name MyWatch \
    --violation_type Security \
    --min_severity High \
    --created_from 2025-06-16T18:22:04Z \
    --created_until 2025-07-17T18:22:04Z
```

## Output

- For each release bundle under the specified watch, the script writes violations to `<bundle_name>_violations.json`.
- A summary table of key violation fields is printed for each bundle.

## Notes

- Date/time arguments must be in the format: `YYYY-MM-DDTHH:MM:SSZ` (e.g., `2025-06-16T18:22:04Z`)
- Valid severity levels: `Critical`, `High`, `Medium`, `Low`
- Ensure your JFrog Xray user has the necessary permissions.
