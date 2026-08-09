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
- It does **not** claim to harden against malware or replace antivirus.
- Unsigned portable EXEs may trigger SmartScreen; code-sign your distribution build if you ship widely.
