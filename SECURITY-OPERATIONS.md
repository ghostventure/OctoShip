# OctoShip security and account operations

OctoShip is a local Windows desktop app for reviewing and transporting code to GitHub. It uses the GitHub account already managed by Git Credential Manager (GCM). It does not issue GitHub credentials, reduce an account's existing permissions, or store the token in ordinary OctoShip settings.

## Access guidance

Use the least powerful GitHub account or fine-grained token that supports the workflow you intend to run. For fine-grained tokens, the practical repository permission map is:

| OctoShip action | Minimum permission category to review |
| --- | --- |
| Find repositories and read repository/file details | Metadata: read; Contents: read for file contents |
| Upload reviewed files as a commit | Contents: write |
| Create a pull request | Pull requests: write; Contents: write when OctoShip must create or update the source branch |
| Create or update a release | Contents: write |
| Add or change workflow files while creating a release | Workflows: write may also be required |

GitHub organization rules, repository settings, and the chosen token type can add requirements. Start with only the actions you use, and follow the permission prompt shown by GitHub. OctoShip stops when GitHub denies access; it does not silently expand authorization. See GitHub's [fine-grained token permission reference](https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens), [pull request endpoint permissions](https://docs.github.com/en/rest/pulls/pulls), and [release endpoint permissions](https://docs.github.com/en/rest/releases/releases).

## Trust boundaries and misuse cases

| Boundary or abuse case | Expected control | Evidence/location |
| --- | --- | --- |
| Local files, filenames, links, and repository-supplied text are untrusted | Resolve and validate paths, bound input sizes, and show canonical repository context before a write | `SecurityBoundaries.cs`, `FileSafetyRules.cs`, and the preparation/upload checks |
| A saved GCM account differs from the selected GitHub identity | Compare the selected name with the credential and GitHub `/user`; stop before repository writes | `MainWindow.xaml.cs`, `SessionLockHttpHandler.cs`, credential and account checks |
| A repository changes visibility or the connected account becomes stale | Recheck the account and repository binding before every mutation; fail closed when state is unknown | `SessionLockHttpHandler.cs`, `PublicationBindings.cs`, P0 security checks |
| GitHub or another service returns credential-like text in an error | Redact active credentials and suppress unsafe server error bodies | `SecurityBoundaries.cs`, `SessionLockHttpHandler.cs`, P0 security checks |
| A downloaded updater package contains unsafe entries or changes after verification | Require GitHub HTTPS asset delivery and matching SHA-256 digest; validate archive paths and recheck staged/installed file hashes | `MainWindow.xaml.cs`, `UpdatePackage.cs`, `UpdateInstaller.cs`, P0 handoff |
| The workstation is left unattended | OctoShip's Windows-authentication inactivity lock is on by default and configurable; Windows account locking remains the system boundary | `AccountSessionLock.cs`, `AccountSessionState.cs`, session-lock checks |

The P0 handoff describes the verification scope and limitations. Fake HTTP transports were used for write-path checks; those checks did not publish changes to a user's GitHub repositories. They do not constitute a penetration test. A process running as the same compromised Windows user may inspect that user's process memory and credentials available to that identity.

## If a GitHub credential may be compromised

1. Revoke the affected token or OAuth authorization in GitHub. OctoShip's Sign out button clears its active session and preserves the GCM login; it does **not** revoke the remote credential.
2. Remove the saved GCM account if appropriate. For GitHub.com, GCM supports `git credential-manager github logout <account> --url https://github.com`. Use the exact account name shown in OctoShip; do not paste a token into a command or support report.
3. Review recent GitHub activity, repository commits, pull requests, releases, and organization audit records where available. Treat a timed-out write as uncertain until GitHub state is checked.
4. Replace any exposed keys or secrets at their issuing service. Removing a file in a later commit does not erase an earlier copy from Git history.
5. Reconnect in OctoShip only after the replacement account authorization is ready, and review its repository access before shipping.

Do not post tokens, passwords, private keys, or exploit details in a public issue. Use GitHub's private vulnerability-reporting route for the repository when it is available; otherwise contact the repository owner through a private channel. The availability of that route and the supported-version policy must be verified by the repository owner before this document is treated as a formal security-response commitment.
