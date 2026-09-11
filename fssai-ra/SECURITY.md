# Security policy

## Supported version

Security corrections are applied to the latest tagged release and the `main` branch.
The project is a teaching reference and is not production-certified.

The exact-action module contains an intentionally public demonstration HMAC key.
It must never be treated as a secret or used outside synthetic teaching tests.

## Reporting a vulnerability

Do not disclose an unpatched vulnerability, secret, or personal record in a public
issue. Use GitHub's private vulnerability reporting for this repository when it is
available. If that channel is unavailable, contact the maintainer through the GitHub
profile without including exploit details in a public message.

For threat assumptions and known limitations, read [`docs/SECURITY.md`](docs/SECURITY.md)
and [`docs/ASSURANCE.md`](docs/ASSURANCE.md) before evaluating or deploying the code.
