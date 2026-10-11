# Shipping workbench (features 1–12)

Open **Ship project & delivery checks** from the main window. This window reuses the selected repository and account, and obtains the current token for each operation.

## Ship project

Choose a local folder, repository destination, exclusions, new branch and commit/PR title. Review pins the remote commit and local Git blob hashes, lists unchanged/changed files and incomplete content scans, and retrieves ruleset and classic branch protection details. Sensitive filenames and secret findings block the shipment; scanning is heuristic, with existing scanner size/binary limitations. Links/junctions are rejected by the underlying comparison. Git LFS conversion and deletion synchronization are not performed.

The explicit ship action checks reviewed bytes and branch state, creates a fresh branch, skips unchanged bytes, sends the changed files through the existing atomic uploader, verifies the returned immutable commit's file hashes and creates a draft PR. Verification reports Verified, Mismatch or Could not verify. A partial failure identifies the branch for recovery. Existing branch names fail without overwrite. The workbench supports 100 changed files and 50 MiB per file; full repository comparison supports 50,000 local files. Folder review may be slow for generated trees because the comparison enumerates before applying workbench exclusions.

## Delivery and account checks

- Account diagnostics identify the authenticated login and returned permissions. HTTP status, rate-limit and SSO evidence produce possible causes without guessing missing permission names.
- Branch rules show rule parameters, required PRs/checks/signatures and classic protection when accessible. Unsupported endpoints explicitly remain unknown.
- Pages checks show site URL, latest build and domain health; Open Pages uses the returned HTTPS site URL. Actions deployments may not expose a Pages build record.
- Artifact verification runs `gh attestation verify <artifact> --repo <owner/name> --format json`, with a two-minute timeout. It uses the GitHub CLI's account and trust mechanism. Missing CLI, missing authentication, absent attestations and nonzero exits never appear as verified. https://cli.github.com/manual/gh_attestation_verify
- Local Git inspection runs read-only status and remote commands, without hooks or shell command construction; URL userinfo is redacted.

## Release recovery and testing

Load existing drafts, choose one and select local assets. Recovery only uploads missing filenames to that release ID. Same-name assets are downloaded and compared; mismatches are preserved for manual resolution. Recovery never creates a draft or publishes it. Release publisher remains responsible for publishing. Interrupted asset uploads can leave an existing invalid/starter asset; recovery reports its mismatch instead of deleting it.

The release tester checks matching filenames, downloaded byte counts and SHA-256 against selected local assets or GitHub's recorded digest. Without a reference digest it says content is unverified. It separately checks the anonymous browser download link; private/draft links can require sign-in. Downloads stream without saving and stop at 2 GiB. API download access and public-link accessibility are reported separately.

## Recipes and accessibility

Version 1 recipes contain only repository, base branch, relative destination, exclusion globs and a release naming convention. They exclude local absolute folders and credentials; import is capped at 64 KiB and validates paths. The naming convention is portable metadata for reuse, not automatic version inference.

The workbench includes adjustable text size, compact spacing, named screen-reader inputs/buttons, standard keyboard navigation and a scrollable 430-pixel minimum-width layout. This setting applies to the workbench rather than replacing every legacy application window's styling. Cancellation stops the current operation; reopen the window for a fresh cancellation scope.

## Developer checks

`dotnet run --project verification/shipping-workbench/ShippingWorkbenchChecks.csproj -c Release`

The offline fake-HTTP checks cover changed/unchanged hashing, immutable commit mismatch/success/unknown, truncated trees, changed-after-review rejection, recipe path boundaries, diagnostic evidence and existing-draft recovery. An STA WPF smoke check renders the workbench at 450×500 and checks tabs and accessible input names. No live GitHub mutation is used for testing. Authenticated Pages/rules APIs, real uploads, release downloads and attestation trust verification require the user's account and suitable repository/artifacts for an end-to-end check.
