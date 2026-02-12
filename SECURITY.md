# Security Policy

## Reporting a Vulnerability

The security of the Dynamic Network Model is important to us. If you discover a security vulnerability, we appreciate your help in disclosing it to us responsibly.

### How to Report

**Please do NOT open a public GitHub issue for security vulnerabilities.**

Instead, please report security vulnerabilities by:

1. **Email**: Send details to [adam@sgridworks.com](mailto:adam@sgridworks.com)
2. **Subject**: Use "SECURITY: Dynamic Network Model - [Brief Description]"
3. **GitHub Security Advisory**: Use the [private vulnerability reporting feature](https://github.com/SGridworks/Dynamic-Network-Model/security/advisories/new)

### What to Include

Please include the following information:

- Description of the vulnerability
- Steps to reproduce the issue
- Potential impact
- Suggested fix (if you have one)
- Your contact information

### Response Timeline

- **Initial Response**: Within 48 hours
- **Status Update**: Within 5 business days
- **Fix Timeline**: Varies by severity, but we aim to address critical issues within 30 days

## Scope

This repository contains:
- Synthetic distribution network data (not real utility data)
- OpenDSS electrical models
- Jupyter notebooks with Python code
- Time-series datasets (Parquet/CSV)

### Security Concerns May Include:

- **Code vulnerabilities** in Python notebooks or scripts
- **Data injection attacks** in data processing pipelines
- **Malicious code** in contributed notebooks
- **Dependency vulnerabilities** in Python packages
- **File handling issues** that could affect users cloning/running the repo

### Out of Scope:

Since this is a **synthetic dataset** (not real utility data):
- There is no actual CEII (Critical Energy Infrastructure Information)
- There is no real customer PII (Personally Identifiable Information)
- Data "leaks" are not a concern as all data is fictional

However, we still take security seriously for the code and analysis tools.

## Supported Versions

We support the latest release with security updates. Older versions may not receive patches.

| Version | Supported          |
| ------- | ------------------ |
| Latest  | :white_check_mark: |
| Older   | :x:                |

## Security Best Practices for Users

When using this repository:

1. **Review code before running**: Always inspect Jupyter notebooks and scripts before execution
2. **Use virtual environments**: Isolate Python dependencies
3. **Keep dependencies updated**: Run `pip install --upgrade` regularly
4. **Don't commit secrets**: Never add API keys, credentials, or tokens to your fork
5. **Verify data integrity**: Check file hashes if provided

## Attribution

If you responsibly disclose a security issue and we fix it, we'll credit you in the release notes (unless you prefer to remain anonymous).

Thank you for helping keep the Dynamic Network Model and its users safe!
