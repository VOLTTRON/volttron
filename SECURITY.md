# Security Policy

## How to report a vulnerability

Report a suspected vulnerability in VOLTTRON privately, through GitHub's
private vulnerability reporting on this repository:

https://github.com/VOLTTRON/volttron/security/advisories/new

You need a signed-in GitHub account to open the form. The report is not
public: it is visible to you and to the people who manage this repository's
security.

Please do not report a security vulnerability through a public issue,
discussion, or pull request.

## What to include

Please include as much of the following as you can, so the report can be
triaged quickly:

* The type of issue (for example, buffer overflow, path traversal, or denial
  of service)
* Affected version(s)
* Impact of the issue, including how an attacker might exploit it
* Step-by-step instructions to reproduce the issue
* The location of the affected source code (tag, branch, commit, or direct URL)
* Full paths of the source file(s) related to the issue
* Configuration required to reproduce the issue
* Related log files, if possible
* Proof-of-concept or exploit code, if possible

## Supported versions

| Version | Supported |
| ------- | --------- |
| Latest 9.x release | Yes |
| Older 9.x releases | No |

Security fixes ship in the latest 9.x release, as a patch version or, when a
fix adds a capability, a minor version.

## What to expect

* The maintainers assess the report and, for a confirmed issue, work on a fix
  in a private advisory.
* When a fix is ready, it is released and the advisory is published, with
  credit to the reporter unless you ask otherwise.

This policy sets no fixed response time.
