# Chat-Distiller

## Running

Run the CLI directly from this directory:

```bash
python3 cli.py --store --url "https://chatgpt.com/share/<share_id>"
python3 cli.py --archive --input messages.json --output archive.json
```

If you see `ModuleNotFoundError: No module named 'requests'`, install dependencies in the same environment:

```bash
python3 -m pip install requests
```

### Merge two archives

Merge two existing `archive.json` files (archive A first, then archive B) into a new deterministic merged archive.
The merged file is saved as:

`data/<folder_a>__<folder_b>/archive.json`

and the command prints the merged directory path.

```bash
python3 cli.py --merge \
  --input-a data/<folder_a>/archive.json \
  --input-b data/<folder_b>/archive.json
```

### Note about `python` vs `python3`

On many Linux distros (including Debian/Ubuntu), `python` may not be installed by default.
Use `python3`.
