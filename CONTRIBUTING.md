# Contributing

Thanks for improving Windows Cleaner.

## Setup

```powershell
dotnet build WindowsCleaner.slnx
dotnet test WindowsCleaner.slnx
```

## Guidelines

- Prefer Scan → Dry-run → Clean semantics; never fake Clean success without verify
- Do not disable Windows Defender or `wuauserv`
- Keep bloatware / OEM / startup apps / startup services / perf modules opt-in (`default_enabled=False`)
- Do not add Defender, Windows Update, firewall, audio, Wi-Fi, Bluetooth, Windows Hello, or Hyper-V/WSL services to `startup_services`
- Update `Catalogs.g.cs` when adding user-visible allowlist rows or effect text
- Keep `README.md` and `CONTEXT.md` in sync when Status meanings or module IDs change
- Add tests under `tests/WindowsCleaner.Core.Tests` (no live system mutation)

## Tests

```powershell
dotnet test WindowsCleaner.slnx
```

## Portable build

```powershell
.\build.ps1
```

Upload `dist\WindowsCleaner-portable.zip` to a GitHub Release manually (no automated Release CI).
