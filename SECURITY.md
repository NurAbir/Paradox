# Security Policy

## Supported versions

The latest `main` branch is the supported version. Fixes are applied there and
in the most recent tagged release.

## Reporting a vulnerability

Please **do not open a public issue** for a security problem. Instead, use
GitHub's private vulnerability reporting on the repository:

1. Open the **Security** tab of the repository.
2. Choose **Report a vulnerability**.
3. Describe the issue, the steps to reproduce it, and the impact.

If private reporting is unavailable, open an issue that asks for a private
contact channel without including the details. Please allow a reasonable amount
of time before any public disclosure.

## Scope

Paradox runs entirely on the local machine:

- The TTS server binds to `127.0.0.1` only and is not reachable from the network.
- The extension requests access to Novel Phoenix and to loopback addresses only.
- No reading data, audio or credentials are sent to a third party.

Useful reports include: a way to make the server listen on a non-loopback
interface, a path-traversal or request-smuggling issue in `/tts`, a
cross-site request that can abuse the local server, or a way for page content
to execute code in the extension's context.

Out of scope: the content of websites you read, and issues that require an
already-compromised machine.