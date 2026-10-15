# OctoShip improvement backlog

Created: 2026-10-14

**Status: Windows P0 work is recorded in [P0-HANDOFF.md](P0-HANDOFF.md). Seventeen P1 tasks are implemented in preview.13; 135 P1 tasks remain open by checkbox. The latest GitHub-published Windows release is preview.13, published 2026-10-15 after the Windows update release workflow passed. P2-P3 proposals remain unstarted. Publisher signing (030), signed update manifests (031), key rotation (217), and signed-metadata freshness (218) are optional distribution assurances outside OctoShip's core GitHub transport and update requirements. The current updater uses GitHub HTTPS and the GitHub asset SHA-256 digest. No remote publication is authorized by this backlog.**

Implementation tracking: 008, 032, 035, 038, 060, and 064 have Windows changes and passing targeted verification, with live/platform boundaries documented in the handoff. Their global checkboxes remain open pending those acceptance boundaries; this is not a claim that every P0 item is complete. Task 029 is checked only after installation verification. Task 399 tracks the still-unverified live GitHub account connection. Priority/category counts below count tasks, not unfinished work.

Scope: tasks 001–018 preserve the initial suggestions; 019–048 add operational, security, and performance improvements; 049–098, 099–198, and 199–398 record the later requested additions; 399 records live GitHub account-connection verification. This copy currently contains 395 task rows; IDs 062, 067, 132, and 209 are missing and must be recovered from the original agenda before claiming all 399 items are documented. They are not reconstructed here. Completion means meeting each task's stated outcome, with appropriate verification when implementation is authorized.

Priority is proposed, not an execution order: **P0** = security/support foundation; **P1** = core reliability and workflow; **P2** = useful expansion; **P3** = optional advanced capability. Code signing and signed update manifests are optional; they are not P0 blockers or requirements for GitHub transport, updater operation, or release publication. Items may build on existing functionality. Except where current local documentation explicitly establishes a limitation, these are proposals to assess, not findings that a feature is absent or defective. Check existing implementation before starting any task and extend it rather than duplicate it.

## Category and importance overview

Tasks are grouped by their primary category, then ordered P0, P1, P2, P3 within that category. Task IDs and priority assignments are preserved; checkboxes track completion. IDs reflect creation order, not execution order. Categories are navigation groups, not a ranking against one another; dependencies still govern implementation sequence.

| Importance | Meaning | Tasks |
| --- | --- | ---: |
| P0 | Critical priority - security and support foundations | 8 |
| P1 | High importance - reliability and core workflows | 152 |
| P2 | Medium importance - useful improvements | 214 |
| P3 | Lower importance - optional advanced capabilities | 21 |

| Category | P0 | P1 | P2 | P3 | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| [Security, privacy, and trust](#security-privacy-and-trust) | 8 | 51 | 5 | 4 | 68 |
| [Operations, queues, and recovery](#operations-queues-and-recovery) | 0 | 24 | 22 | 0 | 46 |
| [Shipping, synchronization, and automation](#shipping-synchronization-and-automation) | 0 | 10 | 20 | 2 | 32 |
| [Releases, packaging, and updates](#releases-packaging-and-updates) | 0 | 10 | 20 | 1 | 31 |
| [Performance and scalability](#performance-and-scalability) | 0 | 14 | 32 | 0 | 46 |
| [Local Git and repository management](#local-git-and-repository-management) | 0 | 0 | 13 | 3 | 16 |
| [File inspection, search, and comparison](#file-inspection-search-and-comparison) | 0 | 0 | 22 | 0 | 22 |
| [Collaboration, pull requests, and project tracking](#collaboration-pull-requests-and-project-tracking) | 0 | 2 | 12 | 1 | 15 |
| [Interface, accessibility, and usability](#interface-accessibility-and-usability) | 0 | 10 | 44 | 1 | 55 |
| [Notifications and attention management](#notifications-and-attention-management) | 0 | 11 | 18 | 2 | 31 |
| [Architecture, testing, and qualification](#architecture-testing-and-qualification) | 0 | 20 | 4 | 0 | 24 |
| [Platforms and integrations](#platforms-and-integrations) | 0 | 0 | 2 | 7 | 9 |
| **Total** | 8 | 152 | 214 | 21 | **395** |

## Security, privacy, and trust

### P0 - Critical priority - security and account foundations (8 tasks)

- [ ] **008 · P0 · Consistent account binding.** Apply expected account, repository, and visibility checks to every publishing path, including release and CLI-backed actions.
- [x] **029 · P0 · Supported Windows runtime.** Migrated to .NET 10 and installed self-contained Windows 1.6.1-preview.1; build, packaged launch, bundled runtime, profile preservation, and session checks verified. Live credential authentication remains an interactive boundary. See [P0 handoff](P0-HANDOFF.md).
- [ ] **032 · P0 · Credential-boundary audit.** Review credential retrieval, subprocess arguments, logging, error handling, and in-memory lifetimes; verify that tokens/passwords never enter ordinary settings or support bundles.
- [ ] **035 · P0 · Untrusted input and path audit.** Exercise archive traversal, symlink/junction changes, path races, malformed plans, and oversized metadata across import, extraction, and publication boundaries.
- [ ] **038 · P0 · Lock coverage across execution paths.** Audit background jobs, native dialogs, subprocess launches, and platform clients; define in-flight behavior and verify that new sensitive actions cannot bypass the lock.
- [ ] **060 · P0 · Cross-account data isolation.** Test switching/signing out across caches, previews, queues, and background requests; prevent stale private data from appearing in another account context.
- [ ] **064 · P0 · Safe subprocess execution.** Audit executable discovery and argument passing; reject shell injection and untrusted tool-path substitution while handling timeouts and child-process termination predictably.
- [ ] **399 · P0 · Live GitHub account connection qualification.** On the installed Windows build, verify Git Credential Manager sign-in, token-to-account identity matching, authenticated repository access, account switching, sign-out, reconnect, and lock gating. Use read-only GitHub requests, report only pass/fail and status codes, never display/store credentials, and record that no remote writes were tested.

### P1 - High importance - reliability and core workflows (51 tasks)

- [x] **033 · P1 · Least-privilege authorization guidance.** Added fine-grained token guidance for repository browsing, uploads, pull requests, and releases; documents organization-policy boundaries and avoids automatically requesting broader access.
- [ ] **034 · P1 · Protected local preparation data.** Assess owner-only permissions and optional OS-backed encryption for snapshots and prepared content; document recovery and deletion behavior.
- [ ] **036 · P1 · Safe previews and link handling.** Treat repository content as untrusted; disable executable preview behavior and validate external URL schemes and credential forwarding.
- [x] **037 · P1 · Dependency security inventory.** The Windows release workflow generates a CycloneDX 1.5 SBOM covering resolved .NET dependencies and shipped payload files, and attaches a transitive NuGet vulnerability-audit report. The preview.10 audit found no vulnerable packages from its configured sources; results are time- and source-dependent and do not prove the application is vulnerability-free. See [P1 handoff](P1-HANDOFF.md).
- [ ] **059 · P1 · Data-retention controls.** Set separate retention policies for journals, reports, snapshots, and search history; offer a previewable local-data purge that preserves credentials unless explicitly requested.
- [x] **061 Â· P1 Â· Sensitive clipboard controls.** Credentials are not copied by OctoShip. Optional 30-second, 1-minute, and 5-minute clearing applies to copied paths, hashes, and diagnostics; the clipboard is cleared only when it still contains the exact text OctoShip copied.
- [ ] **063 · P1 · Permission-change revalidation.** Recheck account, repository visibility, and write access immediately before sensitive actions when review state is stale; surface access changes clearly.
- [ ] **065 · P1 · Download redirect trust rules.** Constrain protocols, validate TLS, and prevent authorization headers from leaking across redirected hosts while allowing documented asset-download flows.
- [x] **066 Â· P1 Â· Unicode and filename ambiguity checks.** Batch review flags case-only destination collisions, reserved Windows names, trailing spaces or dots, Unicode normalization differences, mixed Latin/Greek/Cyrillic names, and invisible or direction-control characters before upload. Paths are preserved as reviewed; users explicitly confirm warnings.
- [ ] **068 · P1 · Release-build provenance.** Connect distributed artifacts to source revision and build identity, generate verifiable attestations where supported, and verify expected provenance separately from file checksums.
- [x] **129 · P1 · Threat model and trust-boundary map.** Added trust boundaries, misuse cases, mitigations, residual risks, and links to verification evidence in `SECURITY-OPERATIONS.md`.
- [ ] **130 · P1 · Import/parser fuzzing.** Exercise plan, recipe, archive-metadata, and API-response parsers with generated malformed inputs; retain minimal regression cases for crashes and resource exhaustion.
- [x] **131 Â· P1 Â· Scanner execution budgets.** Content scanning is capped at 2 MiB and two seconds per file, with 150 ms per rule; file read, decoding, and regex work share the overall budget. Timeout, cancellation, binary content, and size limits report an incomplete scan, never a clean result.
- [ ] **133 · P1 · Git hook and filter policy.** Identify local Git commands that may invoke hooks or filters, show their execution implications, and prevent downloaded repository content from gaining execution privileges silently.
- [ ] **134 · P1 · User-supplied URL access policy.** Define which inspection features may contact arbitrary URLs, reject unsafe schemes/credential-bearing URLs, and require deliberate configuration for private-network endpoints.
- [ ] **135 · P1 · Crash-dump privacy controls.** Make diagnostic dumps opt-in, explain that process memory may contain private data, and require preview/explicit consent before any upload; keep normal support reports dump-free.
- [x] **138 · P1 · Credential-compromise response guide.** Added a revocation, GCM logout, activity-review, and credential-replacement checklist in `SECURITY-OPERATIONS.md`; it distinguishes local sign-out from GitHub revocation.
- [ ] **199 · P1 · Sign-in attempt binding.** Bind each browser/device sign-in attempt to the initiating profile and host; reject callbacks or completions from cancelled or superseded attempts.
- [ ] **200 · P1 · Authentication expiry handling.** Detect expired access during multi-stage work, pause at a safe boundary, and revalidate identity and destination after renewed sign-in before continuing.
- [ ] **201 · P1 · Sign-out request revocation.** Cancel unsent account work and invalidate pending credential callbacks at sign-out; preserve already-sent write outcomes for later reconciliation.
- [ ] **202 · P1 · High-impact action reauthentication.** Define an optional fresh-unlock requirement for destructive operations and signing-key changes without repeatedly challenging ordinary read-only navigation.
- [x] **203 · P1 · Unlock attempt throttling.** Failed Windows authentication is throttled for five seconds; users can retry with Windows Hello/password or close the app. The app does not treat this throttle as OS credential protection.
- [ ] **204 · P1 · IPC caller authentication.** Authenticate any local interprocess command channel, restrict its ACL/socket permissions, and reject publication requests from untrusted processes.
- [ ] **205 · P1 · App deep-link validation.** Treat activation parameters as untrusted, allow only known navigation actions, and prohibit URI-triggered publication or credential changes.
- [ ] **206 · P1 · Redirected authentication endpoint checks.** Bind authentication traffic to the configured host and reject unexpected issuer/endpoint changes instead of forwarding secrets to a new destination.
- [ ] **207 · P1 · Session-state replay assessment.** Assess copied or restored local lock-state files and bind sensitive state to the intended OS user; document limits against an attacker controlling that user session.
- [x] **208 Â· P1 Â· Temporary-file ownership.** Queue journals and uniform preferences now use random temporary names, exclusive CreateNew handles, write-through flushes, atomic replacement, and cleanup limited to the current operation's file. Other settings and session temp files already follow the same pattern in the owner's LocalAppData profile.
- [ ] **210 · P1 · Repository display-name spoofing defenses.** Show canonical owner/name and host beside untrusted descriptions in confirmations so repository text cannot impersonate an application instruction.
- [x] **211 · P1 · Log redaction regression corpus.** Synthetic percent-encoded URL credential fixtures verify redaction in local Git inspection output, support-report preview, and diagnostic handling without real credentials.
- [x] **212 · P1 · Environment inheritance minimization.** TrustedProcess children now inherit only Windows/user-profile variables, PATH, and configured proxy settings; unrelated token/Git overrides are excluded. A 16-check harness verifies required values and a real git invocation.
- [ ] **213 · P1 · Shared-folder profile warning.** Detect settings or snapshot paths on broadly accessible locations where feasible; explain exposure and offer migration to a user-private directory.
- [ ] **214 · P1 · Workspace trust revocation.** Let users revoke granted repository trust and immediately disable dependent executions, while retaining non-executable inspection and existing user files.
- [ ] **215 · P1 · Trust exception expiry.** Add optional expiry and scope limits to security exceptions, and require renewed review when the matching content or destination changes.
- [ ] **216 · P1 · Security policy precedence.** Define predictable precedence for app, project, and organizational settings; display the effective rule and disallow lower-trust configuration from silently weakening mandatory checks.


- [ ] **219 · P1 · Package verification-to-install race protection.** Ensure installed bytes are the bytes whose signatures and hashes were verified, including when another process can modify the staging area.
- [ ] **220 · P1 · Restricted update helper.** Limit any update helper to validated install roots and operations; reject arbitrary command execution and unnecessary privilege elevation.
- [ ] **221 · P1 · Quarantined download workflow.** Keep unverified downloads separate from runnable installation content and promote them only after required verification succeeds.
- [ ] **222 · P1 · Native library loading audit.** Review application and helper DLL/shared-library search paths, remove writable-directory precedence where possible, and test malicious adjacent-library scenarios in fixtures.
- [ ] **223 · P1 · Build dependency source controls.** Pin intended package feeds and dependency origins, reject ambiguous package resolution, and review lockfile changes before release builds.
- [ ] **224 · P1 · CI credential isolation.** Separate untrusted pull-request checks from signing and publishing jobs; validate that untrusted workflow inputs cannot access release credentials.
- [ ] **225 · P1 · Release credential rotation drill.** Document and rehearse replacing compromised publishing credentials in a controlled environment without storing replacements in source or ordinary configuration.
- [ ] **227 · P1 · Personal-data inspection.** Offer opt-in detection of likely personal data in selected text, show redacted findings and false-positive controls, and explain that this is not a compliance certification.
- [x] **228 · P1 · File-content type verification.** Compare claimed extensions with bounded content signatures before choosing preview handlers; label mismatches and never launch a file based solely on its extension. Installed in 1.6.1-preview.9; see [P1 handoff](P1-HANDOFF.md).
- [ ] **229 · P1 · External resource suppression in previews.** Block implicit image/font/schema network loads from repository documents; require explicit consent for fetching each trusted origin.
- [ ] **230 · P1 · Nested archive resource limits.** Enforce cumulative depth, expansion, and time budgets across embedded archives, marking skipped nested content explicitly rather than treating it as scanned.
- [ ] **231 · P1 · Private-path disclosure controls.** Offer relative-path-only report exports and scrub usernames, network share names, and private repository identifiers according to a previewed sharing policy.
- [ ] **233 · P1 · Security event integrity boundaries.** Detect accidental or unexpected modification of local security-event records where feasible, while explicitly avoiding claims of tamper-proof auditing against the same OS user.
- [x] **234 · P1 · HTTP error-body minimization.** Limit and sanitize stored/displayed server error bodies, separating actionable messages from potentially secret-bearing request echoes or untrusted HTML. Installed in 1.6.1-preview.9; see [P1 handoff](P1-HANDOFF.md).
- [ ] **235 · P1 · Credentials in remote URL repair.** Detect embedded userinfo in configured Git remotes and offer a reviewed migration to credential-provider authentication without echoing the credential.
- [ ] **236 · P1 · Sensitive repository destination policy.** Let users mark projects as private-only and block their publication to public destinations across all workflows until the policy is deliberately changed.
- [ ] **238 · P1 · Secret finding remediation guidance.** Explain removal from a pending plan versus revocation of an already-exposed secret, with links to provider-owned guidance and no automatic history rewriting.


### P2 - Medium importance - useful improvements (5 tasks)

- [ ] **136 · P2 · Isolated risky preview decoders.** Evaluate a restricted worker process for complex image/archive previews, limit resources and filesystem/network access, and contain decoder crashes without losing the main session.
- [ ] **137 · P2 · Signed local commits.** Integrate an explicitly selected local signing mechanism, show verification results, and explain when API-created commits cannot use that same signing identity.
- [ ] **226 · P2 · Security exception ledger.** List active waivers with scope, reason, owner, and expiry locally; redact evidence and distinguish accepted risk from a passing security check.
- [ ] **232 · P2 · Screen-sharing privacy mode.** Provide a user-controlled display mode hiding sensitive names and previews across app surfaces; clearly state that it cannot guarantee capture prevention by the operating system.
- [ ] **237 · P2 · Organization rule profile import.** Import reviewed, versioned security rules with a clear source and effective-policy preview; do not allow a profile to introduce executable code or silently widen permissions.



### P3 - Lower importance - optional distribution assurances (4 tasks)

- [ ] **030 · P3 · Optional Windows publisher signing.** Assess code signing, timestamping, publisher identity display, renewal, and key rotation as an optional assurance for Windows downloads. OctoShip's GitHub transport and updater do not require signed executables.
- [ ] **031 · P3 · Optional signed update manifests.** Assess signed release manifests, publisher-key checks, and recovery as an optional trust layer. The current updater uses GitHub HTTPS and its SHA-256 asset digest; signed manifests are not a prerequisite.
- [ ] **217 · P3 · Optional signing-key rotation recovery.** If task 031 is adopted, specify authenticated key-transition records and recovery for updater trust keys. This task is out of core scope unless signed manifests are deliberately introduced.
- [ ] **218 · P3 · Optional signed-metadata freshness.** If task 031 is adopted, detect expired signed metadata and clock uncertainty. This does not apply to the current GitHub HTTPS plus asset-digest updater.

## Operations, queues, and recovery

### P1 - High importance - reliability and core workflows (24 tasks)

- [ ] **009 · P1 · Durable shipment recovery.** Persist confirmed stages of branch creation, upload, verification, and draft PR creation; reconcile uncertain outcomes before resuming after restart.
- [ ] **017 · P1 · Reusable cancellation.** Cancel an operation and start another in the same window; clean up resources and retain any uncertain remote outcome for reconciliation.
- [ ] **019 · P1 · Operation journal.** Record sanitized operation IDs, timestamps, destinations, confirmed outcomes, and recovery links; allow export and bounded retention without storing credentials.
- [x] **020 · P1 · Startup health checks.** The app runs a non-blocking startup check for Git/runtime, Git Credential Manager/account availability, profile-folder writability, and GitHub API connectivity, with actionable results in Updates & diagnostics.
- [ ] **021 · P1 · Rate-limit and outage handling.** Honor server retry guidance, display wait times, and distinguish safe read retries from writes requiring outcome reconciliation. Progress: upload/API errors now translate Retry-After and GitHub reset headers to a wait estimate and warn before retrying uncertain writes; safe-read retry policy remains open.
- [ ] **022 · P1 · Settings backup and migration.** Export credential-free preferences, validate imports, version schemas, and preserve a recoverable copy during upgrades.
- [ ] **024 · P1 · Dependency onboarding and repair.** Identify missing or incompatible prerequisites and provide guided repair with clear download sources and user-approved installation steps.
- [ ] **050 · P1 · Disk-space preflight.** Estimate space needed for staging, snapshots, downloads, and updates; stop safely when reserve requirements cannot be met and handle space loss mid-operation.
- [ ] **051 · P1 · Multi-instance coordination.** Prevent two OctoShip processes from writing the same queue, profile, or update directory concurrently; recover stale ownership after a crash.
- [ ] **052 · P1 · Crash-safe local state writes.** Use validated, versioned, atomic persistence for plans and queues; recover from truncated/corrupt files without silently losing pending work.
- [ ] **053 · P1 · Sleep and network-transition recovery.** Handle suspend/resume, VPN changes, disconnects, and reconnects with refreshed state and reconciliation of interrupted mutations.
- [ ] **141 · P1 · Duplicate submission detection.** Detect equivalent pending submissions by reviewed content and destination, offer reuse, and distinguish an intentional repeat from an uncertain earlier write.
- [ ] **143 · P1 · Removable-source handling.** Detect disconnected drives and unavailable network folders, retain queued plans, and require source revalidation after reconnection or drive-letter changes.
- [x] **144 · P1 · Busy-file recovery.** Identify files that cannot be read because another program holds them, offer retry/skip choices, and invalidate review when the set of published files changes. Installed in 1.6.1-preview.9; see [P1 handoff](P1-HANDOFF.md).
- [ ] **146 · P1 · Graceful shutdown coordinator.** Summarize active work before exit, distinguish safe cancellation from uncertain publication, and preserve recoverable state within a bounded shutdown interval.
- [ ] **309 · P1 · Job attempt lineage.** Link retries to their original operation while preserving each attempt's outcome, so users can distinguish a new execution from a resumed or reconciled one.
- [ ] **310 · P1 · Operation state transition rules.** Define legal transitions between preparing, waiting, running, uncertain, succeeded, failed, and cancelled; reject contradictory updates from stale callbacks.
- [ ] **311 · P1 · Per-destination work locks.** Coordinate jobs targeting the same repository/ref across workflow windows while allowing unrelated destinations to proceed independently.
- [ ] **314 · P1 · Checkpoint integrity verification.** Validate persisted operation checkpoints against source/destination identities and hashes before trusting them during recovery.
- [ ] **315 · P1 · Recovery decision preview.** Present which stages will be repeated, skipped, or inspected before a resumed shipment runs, including any uncertain remote effects.
- [ ] **318 · P1 · Local resource ownership registry.** Track temporary directories, downloaded assets, and handles per job so recovery and cleanup cannot delete another job's active resources.
- [ ] **321 · P1 · File-change explanation after review.** Identify exactly which reviewed sources changed and why review is invalid, retaining unaffected selections where safe.
- [ ] **323 · P1 · Partial-result preservation.** Preserve useful validated scan/inspection results when one independent item fails, while visibly separating incomplete results from a successful whole-project check.
- [ ] **327 · P1 · System clock anomaly diagnostics.** Surface large clock errors that affect authentication, signatures, or scheduling with remediation guidance; never bypass trust checks to compensate.

### P2 - Medium importance - useful improvements (22 tasks)

- [ ] **025 · P2 · Storage management.** Show disk use for caches, staged updates, snapshots, and reports; preview cleanup and protect active jobs and user-owned originals.
- [ ] **028 · P2 · Proxy and enterprise-network diagnostics.** Support approved proxy/custom-CA configuration and explain TLS or proxy failures without disabling certificate validation.
- [ ] **054 · P2 · Destination-change recovery.** Detect renamed/transferred repositories, deleted branches, and revoked access; guide explicit rebinding without silently redirecting queued publication.
- [ ] **055 · P2 · Portable project relocation.** Remap a moved local project root while validating relative paths and content; retain account/destination bindings and show unresolved files.
- [ ] **056 · P2 · Actionable error catalog.** Give common failures stable error codes, plain-language causes, and relevant recovery actions; preserve sanitized technical details for troubleshooting.
- [ ] **139 · P2 · Queue prioritization.** Reorder independent pending jobs with clear execution order; prevent changes that violate repository serialization or declared dependencies.
- [ ] **140 · P2 · Job dependencies.** Model explicit prerequisites between preparation, publication, verification, and release jobs; block dependent actions when prerequisites fail or remain uncertain.
- [ ] **142 · P2 · Pause queue after current safe stage.** Stop starting new jobs while allowing or cancelling the current stage according to its capabilities; preserve a truthful state for non-resumable transfers.
- [ ] **145 · P2 · Cloud-placeholder awareness.** Detect files not fully available locally, show the need to download their content, and avoid unexpected bulk hydration without user agreement.
- [ ] **147 · P2 · Configuration import conflict resolution.** Compare imported presets/bindings with existing values, allow per-item choices, and avoid silently overwriting account-specific destinations.
- [ ] **148 · P2 · Profile repair mode.** Start with a minimal safe configuration when preferences prevent normal launch, preserve a backup, and let users reset selected settings without deleting project data.
- [ ] **312 · P2 · Queue admission limits.** Set bounded limits for pending work and referenced bytes, explaining why a job cannot be added before exhausting local resources.
- [ ] **313 · P2 · Job expiration policies.** Let users expire stale prepared jobs automatically into a non-publishing review state, preserving enough context to recreate them deliberately.
- [ ] **316 · P2 · Failed-job isolation.** Keep a repeatedly failing independent job from blocking unrelated queued work, while preserving explicit dependency chains and a visible failure summary.
- [ ] **317 · P2 · User cancellation reasons.** Allow an optional local note when cancelling a job and preserve it in the operation record without sending it to external services.
- [ ] **319 · P2 · Session work summary.** Show unfinished drafts, running jobs, and staged updates at sign-out or shutdown with one place to inspect their persistence and recovery behavior.
- [ ] **320 · P2 · Workspace health report.** Aggregate broken source mappings, inaccessible destinations, and invalid recipes into a local repair checklist without attempting repairs automatically.
- [ ] **322 · P2 · Retry eligibility explanation.** Explain why an operation can be retried, requires reconciliation, or needs a new review instead of showing an unconditional retry button.
- [ ] **324 · P2 · Manual reconciliation assistant.** Let users inspect immutable commit/release evidence for uncertain operations and record a resolution with supporting references; never accept a guess as automatic verification.
- [ ] **325 · P2 · Workspace archive mode.** Mark inactive projects read-only and hide them from routine queue destinations without deleting their history or remotely archiving repositories.
- [ ] **326 · P2 · Per-workflow timeout settings.** Offer bounded advanced timeout overrides with clear units and defaults, and distinguish a timed-out response from a known failed remote mutation.
- [ ] **328 · P2 · Local diagnostic replay.** Reproduce sanitized operation-state transitions from saved fixtures without executing network writes, giving support a safe way to investigate recovery bugs.

## Shipping, synchronization, and automation

### P1 - High importance - reliability and core workflows (10 tasks)

- [ ] **001 · P1 · Conflict-resolution workspace.** Show original, local, and remote text; resolve differences and repeat review against the current branch head before publishing.
- [ ] **002 · P1 · File history and restore.** Browse and compare earlier file versions; restore selected content through a new reviewed commit without rewriting history.
- [ ] **003 · P1 · Complete folder synchronization.** Present additions, changes, moves, and deletions in one plan, with explicit deletion review. Existing move suggestions do not delete old paths.
- [ ] **010 · P1 · Offline content snapshots.** Optionally save the exact reviewed bytes with hashes and retention controls; support saving selective plans without silently substituting changed local files.
- [ ] **049 · P1 · Dry-run summary export.** Export a reviewable, credential-free summary of planned remote changes, exclusions, warnings, and estimated transfer volume; bind it to the reviewed plan revision.
- [ ] **330 · P1 · Destination collision detector.** Detect two local inputs resolving to the same remote path before staging and require an explicit choice rather than last-write-wins behavior.
- [ ] **333 · P1 · Deletion volume threshold.** Block or require renewed explicit review when a synchronization plan exceeds configured deletion counts or proportions, including after remote state changes.
- [ ] **334 · P1 · Empty-source synchronization guard.** Distinguish an intentionally empty folder from inaccessible/missing content so a scan failure cannot become a plan to delete every remote file.
- [ ] **342 · P1 · Remote-head movement explanation.** Compare the reviewed and current branch heads and identify affected paths so users understand why a shipment needs renewed review.
- [ ] **347 · P1 · LFS object availability preflight.** Before publishing LFS pointer changes, verify required object availability or upload completion; do not treat the pointer's successful commit as proof of usable content.

### P2 - Medium importance - useful improvements (20 tasks)

- [ ] **007 · P2 · Git LFS integration.** Guide installation and tracking rules, then upload and verify LFS objects as well as pointer files; surface applicable storage/bandwidth constraints.
- [ ] **011 · P2 · Multi-file selective publishing.** Select independent edit blocks across several files while preserving unselected remote content and checking each baseline.
- [ ] **013 · P2 · Folder watching.** Detect local changes and prepare reviewable plans; require explicit configuration before enabling any automatic publication.
- [ ] **094 · P2 · Ignore-rule editor.** Explain why each path is included/excluded, preview rule changes against the selected project, and preserve existing rules unless explicitly edited.
- [ ] **198 · P2 · Parameterized shipment recipes.** Extend reusable recipes with typed project/version/destination variables, validate expansion, and preview resolved values before use without allowing embedded shell execution.
- [ ] **329 · P2 · Multiple source-root mapping.** Combine selected folders into one reviewed destination plan, resolve overlapping relative paths explicitly, and preserve source attribution for every item.
- [ ] **331 · P2 · Include-only publishing rules.** Support explicit allowed-path patterns in addition to exclusions, preview their interaction, and indicate files omitted by the inclusion boundary.
- [ ] **332 · P2 · Publication policy profiles.** Save reviewed rules for file sizes, allowed types, destinations, and required checks; show the effective profile in each shipment review.
- [ ] **335 · P2 · Case-only rename planner.** Plan case changes safely for case-insensitive local filesystems and verify the final remote path without leaving an unintended duplicate.
- [ ] **336 · P2 · Rename conflict resolution.** Resolve moves whose target already exists, preview content preservation options, and reject implicit overwrite during synchronization.
- [ ] **337 · P2 · Publish from a pinned local revision.** Prepare content from a selected immutable Git commit rather than the working tree, making uncommitted edits clearly out of scope.
- [ ] **338 · P2 · Selected subtree shipment.** Review and publish a chosen project subtree with an explicit relative root, ensuring exclusions and path checks remain anchored correctly.
- [ ] **339 · P2 · Multi-repository shipment plan.** Group related destinations into an explicit multi-step plan, display per-repository results, and state clearly that independent repositories cannot form one atomic commit.
- [ ] **340 · P2 · Pre-publication check hooks.** Support explicitly trusted, user-configured local validation commands with timeouts and output redaction; never execute hooks imported from an untrusted recipe automatically.
- [ ] **341 · P2 · Post-publication verification profiles.** Select required remote content/download checks for a shipment and record their results independently of the commit's successful creation.
- [ ] **343 · P2 · Preparation plan revision history.** Retain bounded revisions of a saved plan and compare mapping/exclusion changes, without implying that an older review remains valid for current remote state.
- [ ] **344 · P2 · Reusable commit message templates.** Expand typed variables into editable messages, validate missing values, and preview issue-closing syntax before publication.
- [ ] **345 · P2 · Commit trailer editor.** Add reviewed structured trailers such as issue references or co-author lines with format checks and clear identity implications.
- [ ] **346 · P2 · Metadata-only change review.** Separate content edits from mode/path/attribute changes in shipment summaries so small-looking changes with significant behavior remain visible.
- [ ] **348 · P2 · Recipe compatibility migration.** Detect unsupported recipe versions and migrate supported fields through a preview, retaining the original and refusing silent loss of security or destination settings.

### P3 - Lower importance - optional advanced capabilities (2 tasks)

- [ ] **095 · P3 · Command-line companion.** Expose selected preparation, inspection, and reporting operations with stable exit codes and machine-readable output; require explicit flags for remote writes.
- [ ] **096 · P3 · Scheduled preparation and uploads.** Design per-job opt-in schedules, missed-run behavior, lock/account checks, and change-review policy; default schedules to preparation-only until publication is deliberately enabled.

## Releases, packaging, and updates

### P1 - High importance - reliability and core workflows (10 tasks)

- [ ] **015 · P1 · Automated release checklist.** Combine version, installer, asset, and download checks into a saved release report that distinguishes passed, failed, skipped, and unknown results.
- [ ] **016 · P1 · Guided draft-release repair.** Review mismatched or incomplete assets and explicitly replace selected assets without accidentally publishing or deleting unrelated content.
- [ ] **023 · P1 · Update recovery and rollback.** Retain a known-good installation, detect failed startup after update, and offer a controlled rollback compatible with profile-schema changes.
- [ ] **026 · P1 · Standard release pipeline.** Produce versioned packages through repeatable build, test, and artifact-verification stages; keep publication as a separate deliberate step. Code signing can be added independently as an optional distribution assurance.
- [ ] **124 · P1 · Withdrawn-update handling.** Define how a defective GitHub release is excluded from update selection and guide affected users to a reviewed replacement or compatible rollback, using available release metadata without requiring a signed feed.
- [ ] **350 · P1 · Tag-to-build consistency check.** Verify that a release's declared source commit matches the packaged build metadata and selected tag before reporting release readiness.
- [ ] **354 · P1 · Downloaded package semantic check.** Verify that an asset contains the expected app identity and platform payload in addition to matching a hash, using bounded inspection without execution.
- [ ] **356 · P1 · Asset replacement concurrency check.** Recheck a draft asset's identity before replacement so another contributor's intervening upload is not deleted based on stale review.
- [ ] **359 · P1 · Update profile-space reservation.** Reserve enough space for both package replacement and profile backup before update installation, preserving recovery options if disk space changes.
- [ ] **360 · P1 · Post-update health confirmation.** Verify a bounded set of startup and profile checks before treating an update as healthy, recording uncertainty when the app exits before checks finish.

### P2 - Medium importance - useful improvements (20 tasks)

- [ ] **057 · P2 · Release-channel controls.** Expose stable/preview selection, update deferral, installed/staged versions, and channel-switch behavior without bypassing HTTPS, asset-digest, archive, or package-version validation.
- [ ] **088 · P2 · Changelog assistant.** Assemble editable release notes from selected commits/merged PRs with source links; require review before publishing and avoid inventing changes.
- [ ] **119 · P2 · Release asset matrix.** Define expected operating-system/architecture/package combinations and identify missing or ambiguous assets before publication.
- [ ] **120 · P2 · Deterministic archive builder.** Build project release archives with stable ordering and controlled timestamps, explicit exclusions, and reproducible checksums from identical inputs.
- [ ] **121 · P2 · Release-to-release comparison.** Compare asset inventories, sizes, hashes, and declared compatibility across two releases; distinguish intentional changes from missing deliverables.
- [ ] **122 · P2 · Release retention planner.** Preview which old drafts/assets a configured policy would remove, protect designated releases, and require an explicit remote deletion action.
- [ ] **125 · P2 · Package contents manifest.** Generate a human-readable list of shipped files, hashes, sizes, and component versions; compare the manifest with the actual archive before release.
- [ ] **126 · P2 · Third-party notice packaging.** Collect dependency license/notice files into distributable packages, flag missing metadata for human review, and avoid claiming automated legal approval.
- [ ] **127 · P2 · Compatibility metadata editor.** Declare minimum supported OS/runtime and architecture per asset, validate required fields, and use those declarations in download selection.
- [ ] **128 · P2 · Release download instructions.** Generate editable installation/checksum-verification instructions from actual assets and platform metadata, including authentication requirements where relevant.
- [ ] **349 · P2 · Release version proposal.** Suggest a next version from user-selected versioning rules and existing tags, requiring review and preserving nonstandard version schemes when inference is unsafe.
- [ ] **351 · P2 · Release asset naming rules.** Validate configured names for platform, architecture, and version, detect collisions, and preview proposed renames without changing updater expectations silently.
- [ ] **352 · P2 · Checksum sidecar export.** Export selected asset hashes in documented machine-readable formats with deterministic ordering and exact filenames; verify regenerated files against the chosen artifacts.
- [ ] **353 · P2 · Release notes link audit.** Check release-note links against the intended tag, assets, and documentation version, marking inaccessible private resources separately from missing ones.
- [ ] **355 · P2 · Release draft change history.** Record local edits to draft metadata and assets so users can inspect what changed since a readiness check and rerun only invalidated checks.
- [ ] **357 · P2 · Installer prerequisite summary.** Extract or declare installation requirements and publish a reviewed human-readable summary alongside each asset, distinguishing bundled from external dependencies.
- [ ] **358 · P2 · Portable package behavior guide.** Define where portable builds save data, how they update, and how users remove them; verify those claims independently of installer behavior.
- [ ] **361 · P2 · Release promotion preview.** Preview moving a prerelease into a stable channel and its effects on updater selection and links; require explicit publication changes and fresh readiness checks.
- [ ] **362 · P2 · Distribution mirror assessment.** Define integrity and freshness requirements for an optional alternate asset host and demonstrate verification before adding fallback downloads.
- [ ] **363 · P2 · Release evidence bundle.** Export the source revision, asset manifests, verification outcomes, and signing/provenance references into a shareable redacted record tied to one release revision.

### P3 - Lower importance - optional advanced capabilities (1 task)

- [ ] **123 · P3 · Staged update rollout.** Design opt-in release cohorts, rollout percentages, and a pause mechanism without collecting persistent device identifiers by default.

## Performance and scalability

### P1 - High importance - reliability and core workflows (14 tasks)

- [ ] **004 · P1 · Larger-project handling.** Design a safe path beyond the documented 100-changed-file shipment limit, with early exclusions and scan progress; make any loss of single-commit atomicity explicit.
- [ ] **039 · P1 · Performance baseline suite.** Measure startup, folder review, diff rendering, memory, and transfer overhead on representative small/large projects; record hardware and repeatable budgets.
- [ ] **040 · P1 · Virtualized file and history lists.** Render visible rows and page results so large datasets remain responsive without retaining unnecessary UI objects. Progress: ListBox/DataGrid recycling virtualization is enabled and the two large main-window lists have bounded viewports; paging/history coverage remains open.
- [ ] **041 · P1 · Incremental hashing cache.** Reuse hashes only under valid cache conditions; revalidate reviewed bytes before publication so optimization cannot weaken correctness.
- [ ] **042 · P1 · Conditional API caching.** Use ETags/Last-Modified where supported and isolate caches by account, repository, and endpoint; show freshness and invalidate after writes.
- [ ] **043 · P1 · Bounded processing concurrency.** Limit concurrent hashing, scans, and suitable reads; keep branch mutations serialized and adapt to API throttling and local resource pressure.
- [ ] **044 · P1 · Streaming and memory limits.** Stream file transfers and archive inspection where possible, cap buffering and decoded payload sizes, and report progress for large content.
- [ ] **047 · P1 · Diff computation limits.** Use bounded/background diff processing with progressive results and explicit fallback for huge, repetitive, or binary content.
- [ ] **069 · P1 · API request deduplication.** Share identical in-flight reads across panels within the same authorization context without coupling independent cancellation or leaking data across accounts.
- [ ] **071 · P1 · Correct pagination at scale.** Traverse repository, branch, release, and workflow pages incrementally; preserve selections and explicitly report incomplete/truncated results.
- [x] **072 · P1 · Exclusion-aware directory traversal.** Prune ignored generated directories before descent, test nested/negated patterns, and bound traversal of inaccessible or unusual filesystem entries. Installed in 1.6.1-preview.9; see [P1 handoff](P1-HANDOFF.md).
- [ ] **076 · P1 · Resource-leak checks.** Exercise repeated window opens, cancellation, account switches, and transfers; detect growth in handles, event subscriptions, timers, and retained objects.
- [ ] **154 · P1 · Giant-line rendering limits.** Handle minified or single-line multi-megabyte text without blocking the UI; provide truncated/display-safe views while preserving full source bytes.
- [ ] **373 · P1 · Background exception containment.** Prevent a failed nonessential refresh from spawning repeated work or leaking tasks; preserve the affected panel's last-known state with a visible freshness warning.

### P2 - Medium importance - useful improvements (32 tasks)

- [ ] **045 · P2 · Background work scheduling.** Prioritize interactive operations, defer low-priority checks, and pause appropriate background activity while locked or under resource pressure.
- [ ] **046 · P2 · Debounced filtering and search.** Cancel obsolete searches, debounce rapid input, and prevent stale results from replacing newer selections.
- [ ] **048 · P2 · Lazy initialization.** Defer optional panels and heavyweight services until needed; verify startup improvements against the baseline without delaying essential lock/security checks.
- [ ] **070 · P2 · Adaptive polling.** Reduce polling for inactive windows, unchanged results, and completed runs; restore timely refresh when the user returns or relevant work starts.
- [ ] **073 · P2 · Shared content-read pipeline.** Where safe, compute hashes and scanner results from the same bounded read of identical bytes; preserve per-stage results and changed-file detection.
- [ ] **074 · P2 · Efficient progress reporting.** Batch UI progress updates so high file counts do not flood the dispatcher; keep cancellation and final results prompt and accurate.
- [ ] **075 · P2 · Bounded log and output views.** Rotate local logs and cap retained terminal/workflow output; support streaming search/export without loading entire histories into memory.
- [ ] **077 · P2 · Preview thumbnail cache.** Generate size-limited thumbnails off the UI thread, invalidate when content changes, and enforce disk/memory quotas and account isolation.
- [ ] **078 · P2 · Transfer resource controls.** Offer bandwidth and parallel-download limits with clear progress and remaining-work estimates; avoid claiming resumable uploads where the remote API does not support them.
- [ ] **149 · P2 · Lazy repository metadata loading.** Fetch optional owner avatars, counts, and descriptions only as needed; prioritize names/destinations and measure initial list responsiveness.
- [ ] **150 · P2 · Indexed local operation search.** Index bounded journal metadata for fast date/status/project queries, keep it rebuildable, and respect data-retention deletion immediately.
- [ ] **151 · P2 · Snapshot content deduplication.** Reuse identical stored snapshot blobs with reference tracking and integrity checks; verify that cleanup cannot remove content referenced by another retained plan.
- [ ] **152 · P2 · Small-file allocation reduction.** Profile per-file object/string allocation in large scans and reduce measured hot spots without weakening path validation or scan reporting.
- [ ] **153 · P2 · Archive directory indexing.** Read archive entry metadata once for navigation/search, reuse a bounded index, and revalidate the source archive before accessing indexed content.
- [ ] **155 · P2 · Filesystem watcher overflow recovery.** Detect dropped events, mark the watched state stale, and run a bounded reconciliation scan before preparing a new change plan.
- [ ] **156 · P2 · Slow-storage scan strategy.** Measure HDD/network-drive behavior and adapt read scheduling to reduce seek/congestion costs while maintaining cancellation and correctness.
- [ ] **157 · P2 · Battery-aware processing.** Offer a low-power policy for optional hashing, previews, and background refresh; never postpone mandatory pre-publication validation silently.
- [ ] **158 · P2 · Local performance diagnostics.** Provide opt-in local traces showing time spent in scanning, API waits, rendering, and hashing with redacted labels and no automatic telemetry upload.
- [ ] **364 · P2 · API response field projection.** Avoid retaining unused response fields in long-lived models, measuring allocation reductions while preserving required validation and diagnostic evidence.
- [ ] **365 · P2 · Tree comparison merge strategy.** Compare sorted path inventories incrementally to reduce memory overhead on large trees, preserving case/normalization rules and incomplete-result reporting.
- [ ] **366 · P2 · Reusable buffer pool.** Profile large-file read allocations and introduce bounded reusable buffers where beneficial, clearing buffers containing sensitive data before reuse where appropriate.
- [ ] **367 · P2 · Background worker fairness.** Prevent one large project from monopolizing local scan workers, and measure interactive latency while several independent projects are queued.
- [ ] **368 · P2 · Cache eviction effectiveness.** Track local cache hit rates and eviction costs without content telemetry, and choose bounded policies that avoid repeated expensive work under normal navigation.
- [ ] **369 · P2 · Incremental project statistics.** Update file counts and size summaries from validated changes instead of rescanning whole trees for each UI refresh; invalidate estimates after missed events.
- [ ] **370 · P2 · Deferred syntax highlighting.** Render readable plain text first and highlight visible ranges progressively, with strict work budgets for pathological token streams.
- [ ] **371 · P2 · Diff result reuse.** Cache comparisons by immutable input hashes and display options, invalidating when any relevant baseline changes rather than reusing a stale file-path-only entry.
- [ ] **372 · P2 · Preview prefetch budget.** Optionally prefetch nearby selected content within small account-scoped limits, yielding immediately to explicit work and avoiding unrequested large downloads.
- [ ] **374 · P2 · Startup network independence.** Make local navigation and offline preparation usable before optional remote catalogs finish loading, while retaining mandatory authentication gates for publication.
- [ ] **375 · P2 · Cold versus warm benchmark reporting.** Separate first-run/cache-miss measurements from warm-start results so optimization reports do not conceal slow initial user experiences.
- [ ] **376 · P2 · Memory pressure response.** Release disposable preview/cache data when memory is constrained, preserving unsaved drafts and job state; verify recovery without a forced application restart.
- [ ] **377 · P2 · Connection pool lifecycle tuning.** Measure HTTP connection reuse and DNS-change behavior, then tune client lifetimes without breaking proxy settings, cancellation, or account-specific headers.
- [ ] **378 · P2 · Performance regression thresholds.** Gate only stable representative benchmarks against documented tolerances, recording noisy measurements instead of treating random timing variance as a regression.

## Local Git and repository management

### P2 - Medium importance - useful improvements (13 tasks)

- [ ] **079 · P2 · Repository creation wizard.** Choose owner, visibility, initialization, and destination; review a final summary before creation and never default unpublished projects to public.
- [ ] **082 · P2 · Branch and tag manager.** Browse refs, compare targets, and create reviewed tags; separate destructive deletion actions and respect protection rules.
- [ ] **084 · P2 · Branch comparison workspace.** Compare two selected refs, summarize changed paths and commits, and open detailed diffs pinned to immutable revisions.
- [ ] **085 · P2 · Batch revert assistant.** Preview reversing a selected shipment or commit set through a new commit/PR, identify conflicts, and preserve unrelated subsequent work.
- [ ] **086 · P2 · Repository download manager.** Download an explicitly selected ref/path, validate extraction paths, handle destination collisions, and distinguish source archives from release assets.
- [ ] **087 · P2 · Project template library.** Apply reviewed starter layouts to a selected folder with a file-by-file overwrite preview and no implicit execution of template scripts.
- [ ] **099 · P2 · Clone workspace wizard.** Clone a selected repository into a reviewed local destination, show progress, handle existing directories, and distinguish a Git clone from the source downloads in 086.
- [ ] **100 · P2 · Git worktree management.** List and create worktrees for separate branches; inspect uncommitted changes before removal and never delete an occupied worktree silently.
- [ ] **101 · P2 · Stash management.** Preview, create, apply, and deliberately remove named stashes; preserve the original stash when application produces conflicts.
- [ ] **102 · P2 · Local staging area.** Show staged versus unstaged changes, support reviewed file/hunk staging, and avoid accidentally including pre-existing staged content in a shipment.
- [ ] **103 · P2 · Local commit composer.** Build a commit from the reviewed index with author preview and message validation; keep local commits distinct from remote API publication.
- [ ] **105 · P2 · Cherry-pick assistant.** Select commits to apply to a chosen local branch, preview impact, and expose continue/abort controls when conflicts occur.
- [ ] **107 · P2 · Submodule awareness.** Detect nested repository references, show pinned revisions and dirty states, and prevent accidental flattening of submodule content into ordinary uploaded files.

### P3 - Lower importance - optional advanced capabilities (3 tasks)

- [ ] **104 · P3 · Safe commit amendment.** Preview changes to the latest local commit, detect published history, and refuse implicit force pushes or silent replacement of unrelated staged changes.
- [ ] **106 · P3 · Guided regression bisection.** Help users mark known-good/bad revisions and track a Git bisect session; require separate trust approval before executing any project test command.
- [ ] **108 · P3 · Sparse-checkout configuration.** Preview selected paths and exclusions for an existing clone, handle dirty files safely, and explain which content remains outside the local working tree.

## File inspection, search, and comparison

### P2 - Medium importance - useful improvements (22 tasks)

- [ ] **092 · P2 · Image comparison.** Compare before/after assets with side-by-side, overlay, and zoom views; bound decoding resources and report unsupported formats.
- [ ] **093 · P2 · Structured-data inspection.** Provide bounded JSON/YAML tree views, syntax errors, and key-level comparisons without executing tags, schemas, or external references.
- [ ] **109 · P2 · Line attribution viewer.** Show commit/author attribution for selected text lines at a pinned revision and open the associated change without confusing attribution with ownership.
- [ ] **110 · P2 · Cross-repository content search.** Search explicitly selected accessible repositories, show coverage and result limits, and isolate results by account and host.
- [ ] **111 · P2 · Revision bookmarks.** Save named references to immutable commits and file paths for later comparisons, with clear handling of inaccessible or deleted repositories.
- [ ] **112 · P2 · Whitespace-aware diff controls.** Offer display-only whitespace filtering while preserving exact publication bytes and warning when hidden differences still exist.
- [ ] **113 · P2 · Encoding conversion preview.** Detect supported encodings and preview explicit conversions, flag lossy transformations, and preserve the source until the user applies a reviewed change.
- [ ] **114 · P2 · Executable-bit review.** Display and deliberately edit Git executable-mode changes, including when the local filesystem cannot represent them directly.
- [ ] **115 · P2 · Symlink inspection.** Display link targets and escape risks without following them; define a reviewed Git-link workflow separately from the existing rejection of filesystem links during folder upload.
- [ ] **116 · P2 · Line-ending normalization planner.** Explain mixed endings and repository expectations, preview normalization-only changes, and avoid modifying binary or unsupported files.
- [ ] **117 · P2 · Git attributes inspector.** Explain effective attributes per path, including LFS/text/binary handling; report unsupported rules without running custom filters automatically.
- [ ] **118 · P2 · Duplicate-content report.** Group identical files by verified content hash, estimate redundant transfer/storage, and suggest actions without deleting files or treating similar names as duplicates.
- [ ] **389 · P2 · Markdown rendering preview.** Render supported Markdown locally with external fetches and executable HTML disabled, and show differences between supported syntax and unsupported constructs.
- [ ] **390 · P2 · Markdown reference-link validation.** Extend link inspection to reference-style definitions and uses, flag duplicate/missing definitions, and keep unsupported parsing cases explicit.
- [ ] **391 · P2 · Anchor link inspection.** Validate supported local document anchors against generated heading identifiers, reporting renderer-dependent uncertainty rather than declaring every mismatch broken.
- [ ] **392 · P2 · Binary file summary.** Show bounded metadata such as size, detected type, hash, and changed/unchanged status when a meaningful text diff is unavailable.
- [ ] **393 · P2 · CSV table inspection.** Preview delimited data with configurable encoding/delimiter, bounded row loading, and no formula execution; expose malformed rows without silently rewriting source.
- [ ] **394 · P2 · Archive-to-folder comparison.** Compare safe archive entries with a selected local folder by paths and verified content where feasible, without extracting untrusted entries into the project.
- [ ] **395 · P2 · Ignore impact report.** Summarize counts and bytes excluded by each effective ignore rule, helping users spot rules that accidentally omit important deliverables.
- [ ] **396 · P2 · License presence check.** Identify recognized license/notice filenames and missing expected documents, offering review guidance without inferring legal rights from a filename alone.
- [ ] **397 · P2 · Repository documentation completeness.** Check a user-selected documentation checklist such as installation, usage, support, and contribution guides; distinguish missing files from unassessed content quality.
- [ ] **398 · P2 · Search result provenance.** Show the exact revision, local snapshot, or cached source behind each result and revalidate it before opening a publication-related action.

## Collaboration, pull requests, and project tracking

### P1 - High importance - reliability and core workflows (2 tasks)

- [ ] **005 · P1 · Pull-request dashboard.** Follow drafts, reviews, requested changes, checks, and merge readiness using current server state.
- [ ] **006 · P1 · GitHub Actions monitor.** Connect shipments to workflow runs, failed steps, logs, and downloadable artifacts.

### P2 - Medium importance - useful improvements (12 tasks)

- [ ] **080 · P2 · Issue-linked shipments.** Select related issues, add deliberate references to PRs/commits, and preview any closing syntax before publication.
- [ ] **081 · P2 · Review-request controls.** Select eligible reviewers/teams, explain access limitations, and require an explicit action before sending review requests.
- [ ] **083 · P2 · Repository favorites and groups.** Organize repositories by project/client/team, retain ordering, and handle removed access without showing stale private details.
- [ ] **159 · P2 · Pull-request comment composer.** Draft and preview comments, preserve unsent text locally under retention controls, and send only through an explicit user action.
- [ ] **160 · P2 · Batched review submission.** Collect pending inline review comments and a review decision, verify their revision context, and submit the complete review deliberately.
- [ ] **161 · P2 · Review suggestion application.** Preview supported code suggestions against the current file revision, detect stale/conflicting suggestions, and apply them through a reviewed change.
- [ ] **162 · P2 · Ownership guidance.** Read repository ownership rules and explain likely reviewers for changed paths, while distinguishing suggestions from server-enforced requirements.
- [ ] **163 · P2 · Issue creation from selected findings.** Turn a chosen inspection result into an editable issue draft with redacted evidence and a destination preview; never file reports automatically.
- [ ] **164 · P2 · Issue/PR template support.** Load applicable repository templates, validate supported required fields, and show unsupported form behavior instead of silently discarding it.
- [ ] **165 · P2 · Label management for shipments.** Select existing labels for a draft PR/issue, show permission failures, and keep creating new labels a separate explicit operation.
- [ ] **166 · P2 · Milestone assignment.** Display open milestones and assign one to a selected PR/issue after confirmation, with graceful handling when it closes or becomes inaccessible.
- [ ] **168 · P2 · Saved repository queries.** Save reusable filters for PRs, issues, and workflow runs; keep query state account-scoped and distinguish cached results from fresh ones.

### P3 - Lower importance - optional advanced capabilities (1 task)

- [ ] **167 · P3 · Project-board linking.** Assess supported project APIs and permissions, then let users explicitly attach a shipment's PR/issue to an accessible board with a field-change preview.

## Interface, accessibility, and usability

### P1 - High importance - reliability and core workflows (10 tasks)

- [ ] **090 · P1 · Accessibility verification matrix.** Verify keyboard-only operation, screen-reader order, focus recovery, high contrast, scaling, and reduced-motion behavior across core workflows on both platforms.
- [ ] **170 · P1 · Unsaved form recovery.** Recover interrupted commit messages and preparation form inputs after a crash, honoring privacy mode and distinguishing drafts from approved publication plans.
- [ ] **242 · P1 · Field-level validation messages.** Place actionable errors beside invalid inputs, preserve entered values, and focus the first blocking error after submission. Progress: sensitive-file pattern validation now preserves invalid input, shows inline guidance, and focuses the field; broader forms remain open.
- [ ] **245 · P1 · Destructive-action wording.** State the exact repository/path and consequence in delete/replace confirmations and use action-specific button labels instead of ambiguous affirmative choices. Progress: local history and destination-preset confirmations now show selected scope/consequence and safe action labels; other destructive workflows remain open.
- [ ] **247 · P1 · Persistent destination context.** Keep the selected account/host/repository visible during long workflows, including in detached dialogs, and highlight context changes before review continues.
- [x] **262 · P1 · Focus restoration after dialogs.** After a modal closes, restore focus to the initiating control or a surviving owner target; uniform UI checks cover both surviving and removed controls.
- [ ] **263 · P1 · Modal interaction consistency.** Prevent stacked dialogs from trapping keyboard users, retain access to cancellation, and define escape behavior without discarding unreviewed changes silently.
- [ ] **265 · P1 · Text scale overflow handling.** Verify enlarged text in forms, dialogs, and status areas and provide reflow/scrolling instead of clipped controls; implement the scaling part of 090.
- [ ] **266 · P1 · Screen-reader table semantics.** Expose meaningful row/column labels, selected counts, sorting state, and item actions in virtualized lists as a focused accessibility deliverable under 090.
- [ ] **267 · P1 · Accessible dynamic validation.** Announce newly appearing errors and operation results politely without repeatedly reading every progress update or stealing focus.

### P2 - Medium importance - useful improvements (44 tasks)

- [ ] **012 · P2 · Project home screen.** Show recent projects, pending shipments, failed operations, and last verified releases with clear next actions.
- [ ] **014 · P2 · Command palette.** Search commands, repositories, and recent projects with keyboard navigation and context-aware availability.
- [ ] **089 · P2 · Guided first shipment.** Provide a resumable walkthrough from account selection to verified draft PR, using plain language and an optional non-publishing practice mode.
- [ ] **091 · P2 · Workspace layout persistence.** Remember useful panel sizes and navigation state; restore windows on available monitors and keep private workspace state subject to privacy controls.
- [ ] **169 · P2 · Undo for local preparation edits.** Provide bounded undo/redo for destination mappings, exclusions, and selections; clearly exclude already-published remote actions from local undo.
- [ ] **171 · P2 · Context-preserving navigation.** Maintain back/forward navigation between files, diffs, PRs, and releases while preserving selection and showing when account/repository context changes.
- [ ] **172 · P2 · Destination breadcrumbs.** Show account, host, repository, branch, and folder as navigable breadcrumbs, with an unambiguous final destination during review.
- [ ] **173 · P2 · Shortcut customization.** Let users remap supported commands, detect conflicts, and export/reset bindings without overriding essential accessibility navigation.
- [ ] **175 · P2 · Time and timezone clarity.** Show local/UTC timestamps and explicit offsets in operation details, export unambiguous times, and test daylight-saving boundaries in scheduled views.
- [ ] **176 · P2 · Accessible status language.** Pair color indicators with text/icons, explain pending versus unknown versus failed, and apply the same vocabulary across uploads and release checks.
- [ ] **177 · P2 · External editor handoff.** Open selected local files in a user-configured editor through safe argument passing, then detect edits and invalidate stale review state on return.
- [ ] **178 · P2 · Read-only workspace mode.** Offer an inspect/download-only session that disables all publication commands consistently and clearly explains how to leave that mode.
- [ ] **239 · P2 · First-run experience level.** Let users select guided or experienced mode, changing explanatory detail while preserving identical validation and publication safeguards.
- [ ] **240 · P2 · Inline terminology help.** Explain branch, commit, draft PR, asset, and release concepts at their point of use with dismissible plain-language examples.
- [ ] **241 · P2 · Purposeful empty states.** Give separate next steps for a new workspace, no search matches, unavailable access, and genuinely empty repositories instead of one generic blank panel.
- [ ] **243 · P2 · Multi-error form summary.** Summarize all blocking validation errors with links to fields so users can fix a form without repeated failed submissions.
- [ ] **244 · P2 · Optional detail disclosure.** Keep routine choices visible and advanced settings collapsible, remembering user preference without concealing active overrides or warnings.
- [ ] **246 · P2 · Side-by-side publication summary.** Present source, destination, additions, changes, and removals in a compact review layout with direct links back to each editable choice.
- [ ] **248 · P2 · Selection scope indicators.** Distinguish selected visible rows from all selected results and show hidden selections when filters change; prevent accidental batch actions on unseen rows.
- [ ] **249 · P2 · Range and toggle selection.** Support consistent keyboard/mouse range selection in file lists with an accessible alternative and predictable behavior after sorting or refresh.
- [ ] **250 · P2 · Column customization.** Allow resizing, ordering, and hiding nonessential columns with reset controls; retain essential destination and outcome information in compact views.
- [ ] **251 · P2 · Long-path presentation.** Truncate long paths intelligibly while offering full-path inspection and copy; preserve the distinction between paths sharing the same filename.
- [ ] **252 · P2 · Diff navigation landmarks.** Jump between changed hunks, files, and unresolved conflicts with keyboard commands and clear current-position indicators.
- [ ] **253 · P2 · Independent diff scroll controls.** Offer synchronized or independent scrolling for comparisons while preserving visible line correspondence and current selection.
- [ ] **254 · P2 · Review progress markers.** Mark files as reviewed against their exact content revision and automatically invalidate that marker when relevant content changes.
- [ ] **255 · P2 · Context-sensitive help links.** Open help for the current error or operation with version/platform context and an offline explanation when documentation cannot be reached.
- [ ] **256 · P2 · Searchable settings.** Find settings by visible name and common terminology, jump to the matching control, and identify settings unavailable under an active policy.
- [ ] **257 · P2 · Settings change preview.** Show pending preference changes and their effects before applying them, supporting per-section reset without resetting unrelated settings.
- [ ] **258 · P2 · Configuration source badges.** Show whether a value comes from a default, user preference, project recipe, or enforced rule and link to its editable source.
- [ ] **259 · P2 · Guided recovery explanations.** Present what happened, what is known about remote state, and the next safe action together instead of exposing only a raw error code.
- [ ] **260 · P2 · Honest progress stages.** Separate scanning, uploading, verification, and publication phases; use indeterminate progress when completion cannot be estimated reliably.
- [ ] **261 · P2 · Remaining-time confidence.** Present transfer estimates as approximate, reset them after stalls or phase changes, and avoid counting server-side verification as byte-transfer time.
- [ ] **264 · P2 · Touch-friendly interaction option.** Provide optional larger targets and spacing for touch use without forcing desktop users away from the compact layout.
- [ ] **268 · P2 · Reduced-motion interactions.** Respect user motion preferences in transitions, progress animations, and loading indicators while retaining clear state changes.
- [ ] **269 · P2 · Theme-following behavior.** Offer dark, light, and system-following appearances; preserve contrast and user overrides across live system theme changes.
- [ ] **270 · P2 · Zoomable inspection views.** Provide per-view zoom/reset for previews independently of application-wide text scaling, retaining keyboard access and sensible bounds.
- [ ] **271 · P2 · Locale-aware numeric input.** Accept and display sizes, durations, and numeric settings consistently for the selected locale while saving unambiguous machine-readable values.
- [ ] **272 · P2 · Date range input assistance.** Offer presets and explicit inclusive/exclusive boundaries for activity filters, avoiding ambiguous date formats and invalid ranges.
- [ ] **273 · P2 · Account visual identifiers.** Assign user-chosen colors/icons to profiles alongside canonical identity text so similar organization names remain distinguishable without relying on color alone.
- [ ] **274 · P2 · Recently used destinations.** Offer scoped recent destinations with current access checks, clear-history controls, and no persistence while privacy mode forbids it.
- [ ] **275 · P2 · Comparison legend.** Explain added, changed, moved, ignored, unscanned, and unknown states inline, keeping the legend synchronized with actual comparison behavior.
- [ ] **276 · P2 · Draft exit choices.** Offer save draft, discard local edits, or continue editing when leaving a preparation workflow; do not confuse draft saving with publication approval.
- [ ] **277 · P2 · Multi-window context titles.** Name each work window by its project and operation, prevent accidental cross-window destination reuse, and apply privacy masking when locked.
- [ ] **278 · P2 · User-controlled tips.** Provide dismissible workflow tips with reset controls and no repetitive popups after a task is learned or deliberately declined.

### P3 - Lower importance - optional advanced capabilities (1 task)

- [ ] **174 · P3 · Localization infrastructure.** Externalize user-facing strings, support pluralization and layout expansion, and verify right-to-left rendering before claiming a locale is supported.

## Notifications and attention management

### P1 - High importance - reliability and core workflows (11 tasks)

- [ ] **279 · P1 · Notification event model.** Define stable event types and IDs for operation transitions, attention requests, and security notices; keep delivery separate from the authoritative job state.
- [ ] **283 · P1 · OS do-not-disturb respect.** Integrate native notification behavior without attempting to bypass platform focus settings, and retain useful in-app records when banners are suppressed.
- [ ] **285 · P1 · Repeated-alert deduplication.** Coalesce repeated reports of the same underlying incident and update the existing alert when its state changes.
- [ ] **286 · P1 · Notification storm limits.** Cap banner frequency during mass failures or reconnects, retain full in-app detail, and report how many low-priority alerts were grouped.
- [ ] **288 · P1 · Locked-session notification redaction.** Apply privacy rules to native banners, tray text, sounds, and notification history, including alerts already queued before the workspace locks.
- [ ] **289 · P1 · Notification action revalidation.** Treat a clicked action as a new request, recheck account/lock/current state, and navigate to review rather than executing a stale publication command.
- [ ] **290 · P1 · Notification activation routing.** Open the correct project and operation from a banner, handling cold start and another active account without exposing private content before authentication.
- [ ] **296 · P1 · Screen-reader alert pacing.** Announce important notification changes without interrupting active input or flooding speech output during bulk operations.
- [ ] **298 · P1 · Unsupported notification fallback.** Detect unavailable or denied desktop notification support and retain in-app alerts with a clear explanation instead of claiming successful delivery.
- [ ] **300 · P1 · Alert resolution lifecycle.** Update or remove obsolete native alerts when the underlying task succeeds, is cancelled, or becomes irrelevant, while retaining an accurate inbox history.
- [ ] **306 · P1 · Notification delivery diagnostics.** Distinguish generated, queued, submitted-to-OS, and opened events; never label OS submission as proof that a person saw the notification.

### P2 - Medium importance - useful improvements (18 tasks)

- [ ] **058 · P2 · Operation notification center.** Keep a dismissible history of completed, failed, and attention-needed operations; avoid sensitive filenames/content in lock-screen notifications.
- [ ] **280 · P2 · Per-event notification preferences.** Let users enable banners, inbox entries, or silence for each event class, showing the effective preference without disabling required in-workflow warnings.
- [ ] **281 · P2 · Per-project notification scope.** Allow project-specific notification overrides and mute settings, with clear inheritance from app defaults.
- [ ] **282 · P2 · Quiet-hour schedules.** Queue nonurgent alerts during user-defined quiet hours and handle timezone changes; expose any allowed exceptions explicitly.
- [ ] **284 · P2 · Notification digest.** Combine routine completions into an optional periodic summary with counts and links to individual outcomes rather than flooding the desktop.
- [ ] **287 · P2 · Severity presentation.** Use distinct text/icon treatment for information, action needed, warning, and failure; avoid labeling normal workflow interruptions as security emergencies.
- [ ] **291 · P2 · Read and unread state.** Track read status locally per profile, offer mark-all-read, and keep reading an alert separate from acknowledging or resolving its underlying issue.
- [ ] **292 · P2 · Snooze attention requests.** Snooze a particular actionable alert for a chosen interval; recheck whether the issue still exists before resurfacing it.
- [ ] **293 · P2 · Pin unresolved alerts.** Pin important events in the inbox without repeatedly displaying banners, and show when the underlying issue has since been resolved.
- [ ] **294 · P2 · Notification filtering.** Filter the inbox by project, event type, severity, time, and unread state with accessible counts and empty-state explanations.
- [ ] **295 · P2 · Sound controls.** Offer optional sound categories with silent defaults where appropriate, obey platform settings, and never make sound the only indicator of an important event.
- [ ] **297 · P2 · Notification preview and test.** Provide synthetic previews for each enabled delivery channel so users can verify privacy and appearance without creating real repository activity.
- [ ] **299 · P2 · Action-needed escalation.** Optionally remind users about unresolved blocking events after a configured interval, with capped repetition and no escalation to other people without a configured opt-in channel.
- [ ] **301 · P2 · Long-running task notices.** Offer configurable notices for unusually long operations based on elapsed phase time, distinguishing a slow but progressing task from a suspected stall.
- [ ] **302 · P2 · Connectivity restoration notices.** Summarize what became available after reconnection and which jobs still require review; do not imply that pending writes automatically resumed.
- [ ] **303 · P2 · Update readiness notices.** Notify when a verified update is staged and explain when installation can occur, linking to deferral and release notes without interrupting active work.
- [ ] **304 · P2 · Credential attention notices.** Notify about known expiration or authorization failures with a safe sign-in route, and never infer an expiry date unavailable from the credential provider.
- [ ] **305 · P2 · Notification retention limits.** Bound stored inbox content independently of operation journals, preview removal, and retain links gracefully when an older operation record no longer exists.

### P3 - Lower importance - optional advanced capabilities (2 tasks)

- [ ] **307 · P3 · Opt-in webhook notifications.** Define explicitly configured outgoing event endpoints with redacted payload previews, secure secret storage, bounded retries, and endpoint validation; ship disabled by default.
- [ ] **308 · P3 · Opt-in email summaries.** Assess a user-configured mail provider for selected event summaries, preview recipients/content, and require deliberate activation before sending any messages.

## Architecture, testing, and qualification

### P1 - High importance - reliability and core workflows (20 tasks)

- [ ] **018 · P1 · Windows/Linux parity tracking.** Maintain a feature/support matrix and shared behavioral scenarios, identifying intentional platform differences and verified package coverage.
- [ ] **027 · P1 · End-to-end integration fixtures.** Define disposable repository scenarios for upload, PR, release, recovery, and download checks, with explicit opt-in remote writes and cleanup boundaries.
- [ ] **097 · P1 · UI-independent workflow services.** Separate orchestration/state from large window code-behind, define shared contracts, and preserve behavior through focused service tests and platform smoke checks.
- [ ] **179 · P1 · Network fault-injection suite.** Simulate dropped responses, partial bodies, reordered completion, and throttling at controlled points; verify honest outcomes and absence of duplicate remote writes.
- [ ] **180 · P1 · Publication invariant tests.** Generate diverse file sets and assert preservation of unrelated remote paths, reviewed-byte identity, and no forced branch movement across supported upload operations.
- [ ] **181 · P1 · API compatibility matrix.** Pin intended API contracts, test optional/missing/unknown fields, and show unsupported server capabilities without treating them as empty successful results.
- [ ] **182 · P1 · Deterministic time tests.** Inject clocks into lock, retry, retention, and scheduling services; verify clock jumps and elapsed-time behavior without long real-time waits.
- [ ] **183 · P1 · Cancellation race tests.** Exercise cancellation immediately before/after writes and completion callbacks; verify each job reaches one coherent final or explicitly uncertain state.
- [ ] **184 · P1 · Profile migration matrix.** Test upgrades from supported historical profile schemas with representative queues and bindings; prove that failed migration preserves a recoverable original.
- [ ] **185 · P1 · Resource exhaustion qualification.** Simulate low disk, memory pressure, unavailable temp storage, and quota errors; verify useful diagnostics and preservation of pending work.
- [ ] **187 · P1 · Uninstall and reinstall qualification.** Verify launcher removal, optional data retention, reinstall recovery, and coexistence with another version in disposable environments.
- [ ] **188 · P1 · Standard-user installation qualification.** Test install, launch, update, and uninstall under a non-administrator account on clean supported systems; identify every dependency or elevation requirement accurately.
- [ ] **379 · P1 · Notification lifecycle test harness.** Test generation, deduplication, suppression, activation, and resolution using fake delivery adapters, including locked and signed-out states.
- [ ] **380 · P1 · UX task-completion studies.** Observe representative users preparing, reviewing, cancelling, and recovering a shipment; record confusion points and success measures before redesigning flows.
- [ ] **381 · P1 · Layout regression captures.** Capture core screens across supported sizes, text scales, and themes in deterministic fixtures; review meaningful visual differences rather than accepting screenshots blindly.
- [ ] **382 · P1 · Permission-denial scenario suite.** Exercise read-only repositories, revoked credentials, restricted branches, and unavailable organization endpoints with accurate unknown/denied outcomes.
- [ ] **383 · P1 · Notification privacy qualification.** Inspect real OS notification history and activation behavior during lock, account switch, and uninstall to verify private content is not left exposed.
- [ ] **384 · P1 · Data export round-trip checks.** Verify supported plans, recipes, preferences, and reports survive export/import without losing scope or security settings; reject incompatible versions clearly.
- [ ] **385 · P1 · Dependency failure isolation tests.** Simulate missing/crashing external tools and verify dependent actions fail clearly while unrelated app features remain available.
- [ ] **387 · P1 · Security misuse acceptance cases.** Turn the threat model into explicit disallowed behaviors and repeatable checks, prioritizing real trust-boundary crossings over superficial UI assertions.

### P2 - Medium importance - useful improvements (4 tasks)

- [ ] **098 · P2 · Versioned workflow contract fixtures.** Maintain shared representative inputs/expected outcomes for Windows and Linux clients, including error and recovery cases; validate schema/API evolution without sharing credentials.
- [ ] **186 · P2 · Independent build reproducibility check.** Build the same revision in clean environments, compare artifacts/manifests, and document intentional nondeterminism separately from unexplained differences.
- [ ] **386 · P2 · Long-duration idle qualification.** Run idle and intermittent-use scenarios across sleep, lock, refresh, and notifications, checking resource growth and unwanted network activity over time.
- [ ] **388 · P2 · Supported-environment evidence ledger.** Record which OS/runtime/tool combinations actually passed each release qualification, distinguish simulated from physical environments, and expire outdated evidence.

## Platforms and integrations

### P2 - Medium importance - useful improvements (2 tasks)

- [ ] **195 · P2 · Windows Explorer entry points.** Add optional context-menu actions that open a reviewed preparation view for selected files/folders; safely handle arguments and remove integration on uninstall.
- [ ] **196 · P2 · Linux desktop file actions.** Provide optional desktop/file-manager entry points with safe path handling and clear supported environments; never publish directly from an unreviewed shell action.

### P3 - Lower importance - optional advanced capabilities (7 tasks)

- [ ] **189 · P3 · GitHub Enterprise host profiles.** Assess custom-host API/authentication compatibility, isolate credentials and caches by host, and expose unsupported capabilities per server version.
- [ ] **190 · P3 · GitLab provider feasibility.** Map core upload/review/release operations to available provider contracts, document semantic gaps, and prototype a read-only adapter before proposing publication support.
- [ ] **191 · P3 · Bitbucket provider feasibility.** Separately assess supported deployment variants and repository/review APIs, document constraints, and prototype read-only browsing without claiming GitHub feature parity.
- [ ] **192 · P3 · macOS client feasibility.** Evaluate UI, credential storage, signing, update, and packaging options; produce a runnable inspection prototype and a realistic parity/cost assessment before committing to a port.
- [ ] **193 · P3 · Windows ARM64 distribution.** Assess runtime/native-tool compatibility, build the appropriate package, and verify installation plus core workflows on real ARM64 Windows hardware.
- [ ] **194 · P3 · Linux ARM64 distribution.** Audit bundled runtime/tool architectures, produce an ARM64 package, and verify desktop launch and core workflows on a supported ARM64 environment.
- [ ] **197 · P3 · Read-only extension interface.** Define versioned extension capabilities for inspection/reporting, permission prompts, isolation, and revocation; begin without credential access or remote-write permissions.

## Dependencies and scope boundaries

- 009 is shipment recovery; 019 is the user-facing operation journal; 052 is crash-safe persistence. Implement them as cooperating components rather than independent competing stores.
- 004 owns larger-project behavior; 072 owns its early-pruning implementation; 039 establishes measurements for all performance work.
- 003 and 085 depend on reliable comparisons and conflict handling (001/084). No automatic deletion or history rewriting is implied.
- 005/006 provide review/build visibility; 081 adds explicit reviewer requests; 015 consolidates release readiness rather than replacing existing verification tools.
- 010/022/034/059 share storage/privacy requirements. A settings export must not quietly include source snapshots or credentials.
- 021/042/043/069/070 must follow server limits, keep caches account-scoped, and never automatically replay uncertain remote writes.
- 029 and 037 cover the Windows runtime and release-component inventory. Tasks 030/031/217/218 are optional publisher-signing or signed-manifest extensions in P3. GitHub HTTPS plus its asset digest supports the active updater without requiring those extensions; checksum, publisher identity, and build provenance remain distinct assurances.
- 013/095/096 require explicit operation policies. Listing them here does not enable watchers, schedule tasks, or authorize unattended publication.
- 018 defines platform coverage; 090 checks accessibility; 097 separates services; 098 shares behavioral fixtures. These are related but distinct deliverables.
- 099–108 introduce local Git workflows; keep their index/history state separate from API-based uploads and apply hook/filter policy 133 before enabling commands that execute project-supplied behavior.
- 119–128 extend release distribution; 123/124 use GitHub release metadata and compatible recovery 023, without depending on optional signed update manifests. Staged rollout is optional and does not authorize telemetry collection.
- 130 tests parser robustness; 131 bounds scanner execution; 136 isolates risky decoders. These complement, rather than replace, input validation 035 and preview policy 036.
- 139–142 extend the queue from 009/052; dependencies and prioritization must not weaken serialization or uncertain-write reconciliation.
- 149–158 add focused optimizations to the baseline in 039. Deduplication 151 concerns stored content, not request deduplication 069 or duplicate submissions 141.
- 159–167 are explicit collaboration writes and require an individual in-app action. The backlog itself authorizes no comments, reviews, issues, labels, or board changes.
- 179–188 are focused qualification tasks that support the broader fixtures/pipeline in 026/027; reuse common infrastructure rather than creating parallel harnesses for the same scenario.
- 189–197 are optional expansion work. Provider/OS feasibility tasks must establish limitations before becoming feature-parity promises; they are not prerequisites for improving the current clients.
- Review existing tests before adding coverage. Prefer tests for meaningful boundaries, failures, and real workflows over assertions that merely mirror implementation.

- Tasks 199–398 add 40 security, 40 UX, 30 notification, 20 operational, 20 shipping, 15 release, 15 performance, 10 qualification, and 10 inspection tasks. Counts describe this addition, not whole-category totals.
- Some additions are deliberately smaller implementation or verification tasks under existing broad capabilities. They are not 200 independent product features or confirmed missing implementations. Count parent and child effort together when estimating.
- 199–207 refine authentication/session boundaries in 032/038/060; 208–238 refine local trust, release security, inspection privacy, and remediation. Validate applicability before treating any proposal as a vulnerability.
- 239–278 refine user-facing workflows; 262–268 are concrete accessibility work under 090. Preserve the existing behavior and preferences that already satisfy a task.
- 058 now sits in the dedicated notification category. It defines the inbox; 279–308 cover event delivery, preferences, privacy, and lifecycle, while 379/383 qualify that behavior. OS submission is not proof of human delivery.
- 307/308 remain disabled proposals for explicitly configured outbound channels; this document does not authorize sending webhooks, emails, or messages to anyone.
- 309–328 build on operation recovery and persistence; 329–348 refine synchronization and shipment planning; 349–363 extend release readiness and update recovery. Reuse the existing services and authoritative job state.
- 364–378 depend on measured baselines in 039; 379–388 qualify concrete failure and UX scenarios. 389–398 extend bounded inspection and require the preview trust rules in 036/229.

## Evidence used to propose this backlog

Local documents reviewed: [component roadmap](COMPONENT-ROADMAP.md), [shipping workbench](SHIPPING-WORKBENCH.md), [preparation features](SHIPPING-PREPARATION.md), [account/session behavior](ACCOUNT-SESSION.md), [developer guide](DEVELOPMENT.md), and [Windows project target](FileToGitHub.csproj). Documentation describes source behavior and does not establish that every feature is present in every distributed build.

Confirmed local limitations include the 100-changed-file shipment limit, non-deleting move suggestions, guidance-only LFS support, preparation-specific account binding, non-snapshot offline plans, one-file selective publishing, and cancellation requiring workbench reopening. The Windows project now targets `net10.0-windows10.0.19041.0`; task 029's migration and local installation evidence are recorded in [P0-HANDOFF.md](P0-HANDOFF.md) and [P1-HANDOFF.md](P1-HANDOFF.md).

Official references checked on 2026-10-14:

- [Microsoft .NET support policy](https://dotnet.microsoft.com/en-us/platform/support/policy/dotnet-core): checked 2026-10-14 when evaluating task 029; the project has since migrated to .NET 10. Recheck support policy when planning future runtime upgrades.
- [GitHub REST API best practices](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api): rate-limit backoff and conditional requests inform tasks 021 and 042.
- [Microsoft Authenticode timestamping](https://learn.microsoft.com/en-us/windows/win32/seccrypto/time-stamping-authenticode-signatures): optional design reference for task 030; Authenticode is not required by the current product workflow.
- [GitHub protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches): informs server-derived merge readiness and protected-ref handling.
- [GitHub Git LFS](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-git-large-file-storage): informs separate large-object and pointer-file handling in task 007.

- [Microsoft notification design guidance](https://learn.microsoft.com/en-us/windows/apps/design/shell/tiles-and-notifications/toast-ux-guidance): informs attention management and notification lifecycle proposals; verify API support for the actual Windows packaging model before implementation.
- [Microsoft accessible text guidance](https://learn.microsoft.com/en-us/windows/apps/design/accessibility/accessible-text-requirements): informs text readability, correct accessibility roles, and scaling work. These references guide proposals, not a claim of current accessibility conformance.

The original list was planning-only. Subsequent authorized Windows P0 implementation, build, and local installation work is documented separately in [P0-HANDOFF.md](P0-HANDOFF.md); no remote deployment or scheduled work was enabled.
