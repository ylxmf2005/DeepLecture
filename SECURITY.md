# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in DeepLecture, please report it responsibly.

**Do NOT open a public GitHub issue for security vulnerabilities.**

Instead, please use [GitHub Security Advisories](https://github.com/ylxmf2005/DeepLecture/security/advisories/new) to report vulnerabilities privately.

We will acknowledge your report within 48 hours and provide a timeline for a fix.

## Scope

DeepLecture is a self-hosted application. Security concerns include:

- API key exposure through configuration files or logs
- Path traversal or file access vulnerabilities
- Injection vulnerabilities in user-facing inputs
- Unsafe deserialization or command execution

## Best Practices for Users

- Never commit `config/conf.yaml` with real API keys (use `config/conf.default.yaml` as a template)
- Run DeepLecture on a trusted local network or behind a reverse proxy
- Keep dependencies up to date
