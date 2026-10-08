# Contributing

Thanks for improving Windows Cleaner.

## Setup

```powershell
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m windowscleaner
```

## Guidelines

- Prefer Scan → Dry-run → Clean semantics; never fake Clean success without verify
- Do not disable Windows Defender or `wuauserv`
- Keep bloatware / OEM / startup apps / startup services / perf modules opt-in (`default_enabled=False`)
- Do not add Defender, Windows Update, firewall, audio, Wi-Fi, Bluetooth, Windows Hello, or Hyper-V/WSL services to `startup_services`
- Update `modules/item_info.py` when adding user-visible items
- Keep `README.md` and `CONTEXT.md` in sync when Status meanings or module IDs change
- Add or extend smoke tests under `tests/` (no live system mutation in CI)

## Tests

```powershell
python -m pytest -q
```

## Portable build

```powershell
.\build.ps1
```

Upload `dist\WindowsCleaner-portable.zip` to a GitHub Release manually (no automated Release CI).
