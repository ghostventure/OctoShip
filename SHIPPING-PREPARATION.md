# Preparation and inspection features (development build)

Open **Prepare & inspect** in the main header. This source work extends the packaged 1.5.0 application; it does not itself publish a GitHub release. Features 1–12 are described separately in [SHIPPING-WORKBENCH.md](SHIPPING-WORKBENCH.md).

| Requested feature | Available behavior and boundary |
|---|---|
| 13. Destination mapping | Drop files/folders on the destination field, inspect exact paths and edit destination cells. The folder planner retains existing exclusions and its 100-file limit. |
| 14. Selective publishing | Select a mapped UTF-8 file; load the fixed remote baseline; select independent edit blocks and stage the result. Unselected remote text and line endings survive. Local source remains unchanged. One selective file per workflow, up to 2,000 lines and 1 MiB; edits within a contiguous block are selected together. Publication rejects changed baseline/branch/repository/destination. |
| 15. Move detection | Folder comparison annotates unique identical-content pairs with `PossibleMoveFrom`. Original Local only/Remote only classifications remain for compatibility. This is a suggestion, not a rename commit; publishing does not delete the old path. |
| 16. Empty folders | Select an empty folder within the project to stage a `.gitkeep` at its mapped destination, without writing into the source folder. |
| 17. ZIP inspection | Lists entries, flags unsafe/sensitive paths and scans bounded contents for existing secret patterns without extraction. Limits: 512 MiB archive, 10,000 entries, 2 GiB declared expansion, 512 KiB content per entry and 8 MiB scanned total. Unscanned entries are explicit; no secret-free guarantee. |
| 18. Large files/LFS | Project check flags files over the uploader's 50 MiB limit and discovers `filter=lfs` in .gitattributes. Guidance sends LFS-tracked files through Git LFS and large downloadable assets through releases. No automatic LFS upload. |
| 19. Identity preview | Fresh authenticated login plus public profile name/email, with GitHub email privacy URL. API commits use GitHub defaults; exact commit email is not authoritatively available in this preview and is labelled accordingly. |
| 20. Visibility | Refresh displays current public/private/internal visibility and warns when it differs from a saved project/repository binding. Publication confirmation includes current visibility and warnings. |
| 21. Account binding | Save expected account per local project/repository. This preparation publisher blocks mismatches; binding does not change other upload workflows. |
| 22. Offline preparation | Map files, edit paths, save/load credential-free JSON plans while signed out. Local paths are included. Before publishing, refresh account/visibility, validate permissions and branch head, review contents and confirm destinations. Plans reference current local files; they are not frozen content snapshots. Selective plans cannot be saved. |
| 23. Uncertain publication | Shared atomic batch uploader reconciles a lost PATCH response against the current head/ancestry using a separate 20-second read budget. Exact head or confirmed descendant establishes success. No automatic PATCH retry; unresolved cases remain explicitly unconfirmed. Legacy per-file Contents API uploads retain their existing behavior. |
| 24. Version consistency | Scan .csproj Version/AssemblyVersion, package.json version, common Inno Setup version defines, and numeric versions in EXE/ZIP/MSI filenames against a supplied expected version/tag. Dynamic versions and arbitrary manifest formats are not inferred. |
| 25. Installer inspection | Inspect PE architecture/version and Windows Authenticode trust without executing the file. MSI architecture is explicitly unavailable; PE bootstrapper architecture may differ from its payload. Fixed an existing native WinTrustData layout/allocation bug discovered by this check. |
| 26. Download channel | Read the selected repository's latest 100 releases, select stable or prerelease, and check expected tag and exact asset name. This validates supplied expectations; it does not parse arbitrary application updater code or verify a live download. |
| 27. Markdown links | Check inline relative links/images for missing paths, project escape and capitalization mismatch. Excludes web, anchors and root-relative URLs. Not a complete Markdown parser; reference-style links, HTML and escaped/nested link syntax are outside current coverage. |
| 28. Support report | Preview and save a text bundle containing app/OS version, user-entered failure details, current status/report. Redacts common credential assignments, GitHub/Bearer tokens, private-key blocks, email, selected query credentials and home path. Review before sharing; arbitrary secrets cannot be guaranteed absent. No automatic credential/log collection. |

## Storage and safety

Explicitly saved account/visibility bindings are `%LOCALAPPDATA%\OctoShipForGitHub\project-bindings.json`. Prepared placeholder/selected-content copies are in `PreparedFiles` under the same directory and are retained for local plans. They may contain project content; neither is a credential store. Saved plans include local source paths. These explicit preparation saves are independent of search-history privacy mode. Do not commit them.

Publication is a user-confirmed atomic Git Data API operation (at most 100 files). It uses fresh access/head checks, sensitive-name blocking and existing content scanner, with an explicit warning for incompletely scanned contents. The source application updater, installation and external GitHub publications are separate actions.

## Verification

```powershell
dotnet run --project verification/preparation/PreparationChecks.csproj -c Release
dotnet run --project verification/repository-workflows/WorkflowTests.csproj -c Release
dotnet run --project verification/uploads/AtomicUploadChecks.csproj -c Release
dotnet build FileToGitHub.csproj -c Release
```

Preparation harness checks edit-block reconstruction (including 100 random repeated-line cases), Markdown case/missing links, version and LFS detection, ZIP name/content scanning without extraction, support redaction, unsigned PE inspection, fake-HTTP uncertain-publication reconciliation, and WPF rendering of all five tabs. HTTP is mocked; no live repository writes occur. UI publication, real releases and installed artifact behavior require separate explicit verification.
