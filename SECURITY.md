# Security

## Supported versions

Use the latest release from this repository. Older builds may lack Admin/status fixes.

## Reporting a vulnerability

If you believe you found a security issue in Windows Cleaner (for example elevation misuse, unintended data loss, or unsafe defaults):

1. Prefer a private report (email the maintainer listed on the GitHub profile / repo) rather than a public issue with exploit detail.
2. Include OS version, app version (`python -m windowscleaner --cli doctor` / About), and reproduction steps.
3. Do not attach secrets or personal data dumps.

## Scope notes

- This tool intentionally changes registry policies, services, scheduled tasks, files, and (opt-in) AppX/winget packages.
- **Standard** does not enable app removal or optional service changes. Those are opt-in: `bloatware`, `bloatware_oem`, `startup_services` (Debloat preset), `startup_apps`, and `perf_services` (SysMain / Windows Search). See README “Debloat: default apps and startup services”.
- `startup_services` may set optional services to Disabled or Manual (Fax, Xbox/Game Bar, print spooler, Remote Desktop listener, Phone Link helpers, and similar). It does **not** change Windows Defender, Windows Update, BITS, firewall, SmartScreen, audio, Wi-Fi, Bluetooth, Windows Hello, Store licensing, or Hyper-V / WSL.
- Service changes are reversible in `services.msc`. Store app removal is not, short of reinstalling the app.
- A default profile or a never-touch component (Defender, Update, firewall, Hello) changing when it should not is in scope for a report. An opt-in Debloat row doing what its repercussion text says is intended behavior.
- It does **not** claim to harden against malware or replace antivirus.
- Unsigned portable EXEs may trigger SmartScreen; code-sign your distribution build if you ship widely.
