# Chat-Distiller

## Running

This repo is a single Python package directory named `chat_distiller/`.

### Option A (recommended): run as a module from the parent directory

From the directory that contains the `chat_distiller/` folder:

```bash
python3 -m chat_distiller.cli --archive --input chat_distiller/messages.json --output chat_distiller/archive.json
python3 -m chat_distiller.cli --store --url "https://chatgpt.com/share/<share_id>"
```

If you run `python3 -m chat_distiller.cli ...` from _inside_ the `chat_distiller/` directory, Python will fail with:

`ModuleNotFoundError: No module named 'chat_distiller'`

because `chat_distiller` must be importable as a package from the current working directory.

### Option B: run the script directly from inside the package directory

If your current directory is `chat_distiller/`:

```bash
python3 cli.py --archive --input messages.json --output archive.json
python3 cli.py --store --url "https://chatgpt.com/share/<share_id>"
```

### Note about `python` vs `python3`

On many Linux distros (including Debian/Ubuntu), `python` may not be installed by default.
Use `python3`.
