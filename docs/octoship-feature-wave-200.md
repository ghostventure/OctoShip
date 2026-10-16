# OctoShip local diagnostics feature wave

This source branch adds five diagnostics workbenches to the Linux
client. Together they expose **214 individually named checks**, tracked below
by their stable code and implementation. These are diagnostic checks within
five user-facing tools, rather than 214 unrelated screens or remote actions.

It also adds **208 create-new project recipes** with preview and safe
no-overwrite behavior. They are inventoried separately below and are not
included in the diagnostic count.

## User-facing tools

| Tool | Where to find it | Entry point | Test evidence |
| --- | --- | --- | --- |
| Local Git insights | Repository Tools → Local Git | `git_insights.inspect_repository()` | `linux/tests/test_git_insights.py` |
| Project readiness audit | Repository Tools → Project Audit | `project_audit.audit_project()` | `linux/tests/test_project_audit.py` |
| Release artifact audit and checksum generation | Repository Tools → Release Audit | `release_audit.audit_release()`; `create_checksum_manifest()` | `linux/tests/test_release_audit.py` |
| Saved workspace audit | Repository Tools → Workspace | `workspace_audit.audit_workspace()` | `linux/tests/test_workspace_audit.py` |
| Offline environment doctor | Terminal: `./linux/octoship-linux --doctor`; add `--doctor-format json` for JSON | `diagnostics.environment_report()` and `format_report()` | `linux/tests/test_diagnostics.py` |
| Project file recipe generator | Repository Tools → Recipes | `project_recipes.render_recipe()` / `create_recipe()` | `linux/tests/test_project_recipes.py` |

The four Repository Tools audit views run in OctoShip's background worker. They do
not contact GitHub or perform writes, except the Release Audit view can save a
user-selected SHA-256 manifest after an explicit save action. The environment doctor makes no network
requests and does not inspect authentication output or collect credential
values; it creates missing XDG folders and a temporary file to verify local
writability. The Git insights view runs bounded, read-only Git queries and
redacts remote URLs. Project and release audits have file/count/byte limits;
they do not execute project code, extract archives, or upload artifacts. The
workspace audit checks queue metadata and verifies referenced files within its
declared limits; it never resumes or edits a queue.

Reports can contain local paths, branch names, filenames, and project metadata.
Review them before sharing. A clean report means only that the implemented,
bounded checks found no issue; it does not certify source code, a release, or a
publisher as trustworthy.

Each graphical audit table supports text filtering, status filtering, sortable
columns, copying a selected row, and saving the full report as JSON after a
privacy prompt. Release Audit can also generate a SHA-256 manifest atomically;
it refuses symlinked artifact folders/files and caps inputs at 500 artifacts,
2 GiB per artifact, and 5 GiB total. These are additional user workflows; they
are not added to the 214-check inventory.

## 208 project file recipes

Project Recipes provides one-click previews and create-new writes for each
entry below. It never overwrites a file, rejects symbolic-link traversal,
writes atomically, and creates output only after the user chooses the project
folder. Language-specific variants can intentionally share a conventional
output path; each variant has separately reviewed content and a stable key.
These files are starter templates; review and adapt the contents to the
project's actual build, security, and deployment needs before using them.

| # | Recipe | Output path |
| ---: | --- | --- |
| 001 | `readme` | `README.md` |
| 002 | `changelog` | `CHANGELOG.md` |
| 003 | `contributing` | `CONTRIBUTING.md` |
| 004 | `security_policy` | `SECURITY.md` |
| 005 | `code_of_conduct` | `CODE_OF_CONDUCT.md` |
| 006 | `editorconfig` | `.editorconfig` |
| 007 | `gitattributes` | `.gitattributes` |
| 008 | `gitignore_python` | `.gitignore` |
| 009 | `gitignore_node` | `.gitignore` |
| 010 | `gitignore_rust` | `.gitignore` |
| 011 | `gitignore_go` | `.gitignore` |
| 012 | `gitignore_java` | `.gitignore` |
| 013 | `gitignore_dotnet` | `.gitignore` |
| 014 | `gitignore_docker` | `.dockerignore` |
| 015 | `ci_python` | `.github/workflows/ci.yml` |
| 016 | `ci_node` | `.github/workflows/ci.yml` |
| 017 | `ci_rust` | `.github/workflows/ci.yml` |
| 018 | `ci_go` | `.github/workflows/ci.yml` |
| 019 | `bug_report` | `.github/ISSUE_TEMPLATE/bug_report.yml` |
| 020 | `feature_request` | `.github/ISSUE_TEMPLATE/feature_request.yml` |
| 021 | `pull_request_template` | `.github/PULL_REQUEST_TEMPLATE.md` |
| 022 | `dependabot` | `.github/dependabot.yml` |
| 023 | `precommit` | `.pre-commit-config.yaml` |
| 024 | `makefile_python` | `Makefile` |
| 025 | `dockerfile_python` | `Dockerfile` |
| 026 | `docker_compose` | `compose.yaml` |
| 027 | `license_mit` | `LICENSE` |
| 028 | `coverage_python` | `.coveragerc` |
| 029 | `renovate` | `renovate.json` |
| 030 | `python_pyproject` | `pyproject.toml` |
| 031 | `python_pytest` | `pytest.ini` |
| 032 | `python_ruff` | `ruff.toml` |
| 033 | `python_mypy` | `mypy.ini` |
| 034 | `python_dev_requirements` | `requirements-dev.txt` |
| 035 | `python_tox` | `tox.ini` |
| 036 | `python_uv` | `uv.toml` |
| 037 | `python_pip_conf` | `pip.conf` |
| 038 | `node_package` | `package.json` |
| 039 | `node_typescript` | `tsconfig.json` |
| 040 | `node_eslint` | `eslint.config.js` |
| 041 | `node_prettier` | `.prettierrc.json` |
| 042 | `node_npmrc` | `.npmrc` |
| 043 | `node_vitest` | `vitest.config.ts` |
| 044 | `node_playwright` | `playwright.config.ts` |
| 045 | `node_dockerfile` | `Dockerfile` |
| 046 | `node_pnpm_workspace` | `pnpm-workspace.yaml` |
| 047 | `node_changesets` | `.changeset/config.json` |
| 048 | `rustfmt` | `rustfmt.toml` |
| 049 | `rust_clippy` | `.cargo/config.toml` |
| 050 | `rust_deny` | `deny.toml` |
| 051 | `go_makefile` | `Makefile` |
| 052 | `go_lint` | `.golangci.yml` |
| 053 | `go_dockerfile` | `Dockerfile` |
| 054 | `java_pom` | `pom.xml` |
| 055 | `java_gradle` | `build.gradle.kts` |
| 056 | `dotnet_build_props` | `Directory.Build.props` |
| 057 | `dotnet_global_json` | `global.json` |
| 058 | `vscode_settings` | `.vscode/settings.json` |
| 059 | `vscode_extensions` | `.vscode/extensions.json` |
| 060 | `vscode_tasks` | `.vscode/tasks.json` |
| 061 | `vscode_launch` | `.vscode/launch.json` |
| 062 | `github_codeql` | `.github/workflows/codeql.yml` |
| 063 | `github_dependency_review` | `.github/workflows/dependency-review.yml` |
| 064 | `github_stale` | `.github/workflows/stale.yml` |
| 065 | `github_release_notes` | `.github/release.yml` |
| 066 | `github_labeler` | `.github/labeler.yml` |
| 067 | `k8s_deployment` | `k8s/deployment.yaml` |
| 068 | `k8s_service` | `k8s/service.yaml` |
| 069 | `k8s_namespace` | `k8s/namespace.yaml` |
| 070 | `terraform_variables` | `variables.tf` |
| 071 | `terraform_outputs` | `outputs.tf` |
| 072 | `architecture_decision` | `docs/decisions/0001-record-template.md` |
| 073 | `support_policy` | `SUPPORT.md` |
| 074 | `roadmap` | `ROADMAP.md` |
| 075 | `python_pyright` | `pyrightconfig.json` |
| 076 | `python_black` | `.black` |
| 077 | `python_pylint` | `.pylintrc` |
| 078 | `python_nox` | `noxfile.py` |
| 079 | `python_requirements` | `requirements.txt` |
| 080 | `python_pipfile` | `Pipfile` |
| 081 | `python_poetry` | `poetry.toml` |
| 082 | `node_nvmrc` | `.nvmrc` |
| 083 | `node_node_version` | `.node-version` |
| 084 | `node_yarnrc` | `.yarnrc.yml` |
| 085 | `node_browserslist` | `.browserslistrc` |
| 086 | `node_stylelint` | `.stylelintignore` |
| 087 | `node_jest` | `jest.config.js` |
| 088 | `node_cypress` | `cypress.config.js` |
| 089 | `node_storybook` | `.storybook/main.js` |
| 090 | `node_lint_staged` | `.lintstagedrc.json` |
| 091 | `ruby_gemfile` | `Gemfile` |
| 092 | `ruby_rubocop` | `.rubocop.yml` |
| 093 | `ruby_rakefile` | `Rakefile` |
| 094 | `php_composer` | `composer.json` |
| 095 | `php_phpunit` | `phpunit.xml` |
| 096 | `php_phpstan` | `phpstan.neon` |
| 097 | `php_phpcs` | `phpcs.xml` |
| 098 | `php_dockerfile` | `Dockerfile` |
| 099 | `kotlin_gradle` | `build.gradle.kts` |
| 100 | `kotlin_settings` | `settings.gradle.kts` |
| 101 | `swift_package` | `Package.swift` |
| 102 | `cmake_project` | `CMakeLists.txt` |
| 103 | `c_cpp_clang_format` | `.clang-format` |
| 104 | `c_cpp_clang_tidy` | `.clang-tidy` |
| 105 | `github_license_check` | `.github/workflows/license-check.yml` |
| 106 | `github_pr_size` | `.github/workflows/pr-size.yml` |
| 107 | `github_pages` | `.github/workflows/pages.yml` |
| 108 | `github_label_sync` | `.github/labels.yml` |
| 109 | `github_funding` | `.github/FUNDING.yml` |
| 110 | `github_auto_assign` | `.github/auto_assign.yml` |
| 111 | `github_pr_labels` | `.github/pr-labels.yml` |
| 112 | `github_codeowners` | `.github/CODEOWNERS` |
| 113 | `github_discussion_template` | `.github/DISCUSSION_TEMPLATE/ideas.yml` |
| 114 | `github_issue_config` | `.github/ISSUE_TEMPLATE/config.yml` |
| 115 | `vscode_profile` | `.vscode/.gitignore` |
| 116 | `vscode_snippets` | `.vscode/project.code-snippets` |
| 117 | `vscode_recommendations` | `.vscode/extensions-recommended.json` |
| 118 | `docker_healthcheck` | `docker-healthcheck.sh` |
| 119 | `compose_dev` | `compose.dev.yaml` |
| 120 | `compose_test` | `compose.test.yaml` |
| 121 | `k8s_configmap` | `k8s/configmap.yaml` |
| 122 | `k8s_ingress` | `k8s/ingress.yaml` |
| 123 | `k8s_hpa` | `k8s/hpa.yaml` |
| 124 | `terraform_provider` | `versions.tf` |
| 125 | `terraform_main` | `main.tf` |
| 126 | `terraform_backend` | `backend.tf.example` |
| 127 | `docs_architecture` | `docs/ARCHITECTURE.md` |
| 128 | `docs_runbook` | `docs/RUNBOOK.md` |
| 129 | `docs_release_process` | `docs/RELEASING.md` |
| 130 | `docs_data_retention` | `docs/DATA-RETENTION.md` |
| 131 | `docs_accessibility` | `docs/ACCESSIBILITY.md` |
| 132 | `docs_threat_model` | `docs/THREAT-MODEL.md` |
| 133 | `docs_privacy` | `docs/PRIVACY.md` |
| 134 | `docs_support_matrix` | `docs/SUPPORT-MATRIX.md` |
| 135 | `docs_migration` | `docs/MIGRATIONS.md` |
| 136 | `docs_backup_restore` | `docs/BACKUP-RESTORE.md` |
| 137 | `docs_glossary` | `docs/GLOSSARY.md` |
| 138 | `docs_test_strategy` | `docs/TESTING.md` |
| 139 | `docs_api_guidelines` | `docs/API-GUIDELINES.md` |
| 140 | `docs_incident_response` | `docs/INCIDENT-RESPONSE.md` |
| 141 | `flatpak_manifest` | `packaging/{project}.yml` |
| 142 | `desktop_entry` | `packaging/{project}.desktop` |
| 143 | `systemd_service` | `packaging/{project}.service` |
| 144 | `systemd_user_service` | `packaging/{project}.user.service` |
| 145 | `rpm_spec` | `packaging/{project}.spec` |
| 146 | `debian_control` | `packaging/debian/control` |
| 147 | `debian_rules` | `packaging/debian/rules` |
| 148 | `debian_changelog` | `packaging/debian/changelog` |
| 149 | `flatpak_builder` | `packaging/flatpak-build.sh` |
| 150 | `appimage_builder` | `packaging/appimage.yml` |
| 151 | `firebaserc` | `.firebaserc.example` |
| 152 | `firebase_hosting` | `firebase.json.example` |
| 153 | `firebase_rules` | `firestore.rules.example` |
| 154 | `firebase_storage_rules` | `storage.rules.example` |
| 155 | `firebase_functions_package` | `functions/package.json` |
| 156 | `firebase_emulators` | `firebase.emulator.json.example` |
| 157 | `openapi` | `openapi.yaml` |
| 158 | `graphql_schema` | `schema.graphql` |
| 159 | `sql_migration` | `db/migrations/0001_initial.sql` |
| 160 | `sql_schema` | `db/schema.sql` |
| 161 | `sql_transaction` | `db/transaction-example.sql` |
| 162 | `prometheus_config` | `monitoring/prometheus.yml` |
| 163 | `prometheus_alerts` | `monitoring/alerts.yml` |
| 164 | `grafana_dashboard` | `monitoring/dashboard.json` |
| 165 | `otel_collector` | `monitoring/otel-collector.yaml` |
| 166 | `logrotate` | `packaging/logrotate.conf` |
| 167 | `nginx_proxy` | `deploy/nginx.conf` |
| 168 | `caddy_proxy` | `deploy/Caddyfile` |
| 169 | `nginx_static` | `deploy/nginx-static.conf` |
| 170 | `ansible_inventory` | `deploy/ansible/inventory.ini.example` |
| 171 | `ansible_playbook` | `deploy/ansible/site.yml` |
| 172 | `pulumi_project` | `Pulumi.yaml` |
| 173 | `helm_chart` | `deploy/helm/Chart.yaml` |
| 174 | `helm_values` | `deploy/helm/values.yaml` |
| 175 | `helm_deployment` | `deploy/helm/templates/deployment.yaml` |
| 176 | `github_security_scorecard` | `.github/workflows/scorecard.yml` |
| 177 | `github_secret_scan` | `.github/workflows/secret-scan.yml` |
| 178 | `github_docs_check` | `.github/workflows/docs.yml` |
| 179 | `github_yaml_check` | `.github/workflows/yaml.yml` |
| 180 | `github_shell_check` | `.github/workflows/shellcheck.yml` |
| 181 | `github_spellcheck` | `.github/workflows/spellcheck.yml` |
| 182 | `github_pr_title` | `.github/workflows/pr-title.yml` |
| 183 | `github_size_labels` | `.github/workflows/size-labels.yml` |
| 184 | `github_workflow_permissions` | `.github/workflows/permissions-check.yml` |
| 185 | `github_nightly` | `.github/workflows/nightly.yml` |
| 186 | `github_manual_release` | `.github/workflows/release-manual.yml` |
| 187 | `github_publish_package` | `.github/workflows/publish-package.yml` |
| 188 | `github_cache_cleanup` | `.github/workflows/cache-cleanup.yml` |
| 189 | `gitmodules` | `.gitmodules.example` |
| 190 | `gitmessage` | `.gitmessage` |
| 191 | `mailmap` | `.mailmap.example` |
| 192 | `gitignore_global` | `.gitignore_global` |
| 193 | `gitattributes_merge` | `docs/snippets/gitattributes-merge.txt` |
| 194 | `security_advisories` | `docs/SECURITY-ADVISORIES.md` |
| 195 | `security_key_rotation` | `docs/KEY-ROTATION.md` |
| 196 | `security_disclosure` | `.well-known/security.txt` |
| 197 | `security_sbom_notes` | `docs/SBOM.md` |
| 198 | `security_third_party` | `docs/THIRD-PARTY.md` |
| 199 | `security_permissions` | `docs/PERMISSIONS.md` |
| 200 | `governance_maintainers` | `MAINTAINERS.md` |
| 201 | `governance_decisions` | `docs/decisions/README.md` |
| 202 | `governance_change_policy` | `docs/CHANGE-POLICY.md` |
| 203 | `governance_review_checklist` | `.github/pull_request_template.md` |
| 204 | `editor_markdown` | `.markdownlint.json` |
| 205 | `editor_yaml` | `.yamllint` |
| 206 | `editor_sqlfluff` | `.sqlfluff` |
| 207 | `editor_prettierignore` | `.prettierignore` |
| 208 | `editor_vscode_extensions` | `.vscode/extensions.json` |


## Numbered implementation inventory

Each row maps to the check's stable key. The key is emitted directly by the
corresponding module's report builder; the entry point, UI view, and test file
are listed above. Diagnostic severity is advisory unless the row explicitly
reports an error.

| # | Tool | Check key | Code entry point | Test file |
| ---: | --- | --- | --- | --- |
| 001 | Local Git | `repository` | `git_insights.inspect_repository` | `linux/tests/test_git_insights.py` |
| 002 | Local Git | `branch` | `git_insights.inspect_repository` | `linux/tests/test_git_insights.py` |
| 003 | Local Git | `head` | `git_insights.inspect_repository` | `linux/tests/test_git_insights.py` |
| 004 | Local Git | `head_date` | `git_insights.inspect_repository` | `linux/tests/test_git_insights.py` |
| 005 | Local Git | `commit_count` | `git_insights.inspect_repository` | `linux/tests/test_git_insights.py` |
| 006 | Local Git | `branch_count` | `git_insights.inspect_repository` | `linux/tests/test_git_insights.py` |
| 007 | Local Git | `tag_count` | `git_insights.inspect_repository` | `linux/tests/test_git_insights.py` |
| 008 | Local Git | `contributor_count` | `git_insights.inspect_repository` | `linux/tests/test_git_insights.py` |
| 009 | Local Git | `tracked_count` | `git_insights.inspect_repository` | `linux/tests/test_git_insights.py` |
| 010 | Local Git | `remote_count` | `git_insights.inspect_repository` | `linux/tests/test_git_insights.py` |
| 011 | Local Git | `remotes` | `git_insights.inspect_repository` | `linux/tests/test_git_insights.py` |
| 012 | Local Git | `upstream` | `git_insights.inspect_repository` | `linux/tests/test_git_insights.py` |
| 013 | Local Git | `ahead` | `git_insights.inspect_repository` | `linux/tests/test_git_insights.py` |
| 014 | Local Git | `behind` | `git_insights.inspect_repository` | `linux/tests/test_git_insights.py` |
| 015 | Local Git | `staged` | `git_insights.inspect_repository` | `linux/tests/test_git_insights.py` |
| 016 | Local Git | `unstaged` | `git_insights.inspect_repository` | `linux/tests/test_git_insights.py` |
| 017 | Local Git | `untracked` | `git_insights.inspect_repository` | `linux/tests/test_git_insights.py` |
| 018 | Local Git | `conflicts` | `git_insights.inspect_repository` | `linux/tests/test_git_insights.py` |
| 019 | Local Git | `shallow` | `git_insights.inspect_repository` | `linux/tests/test_git_insights.py` |
| 020 | Local Git | `object_store` | `git_insights.inspect_repository` | `linux/tests/test_git_insights.py` |
| 021 | Local Git | `default_branch` | `git_insights.inspect_repository` | `linux/tests/test_git_insights.py` |
| 022 | Local Git | `hooks_path` | `git_insights.inspect_repository` | `linux/tests/test_git_insights.py` |
| 023 | Local Git | `lock_files` | `git_insights.inspect_repository` | `linux/tests/test_git_insights.py` |
| 024 | Local Git | `large_files` | `git_insights.inspect_repository` | `linux/tests/test_git_insights.py` |
| 025 | Local Git | `sensitive_names` | `git_insights.inspect_repository` | `linux/tests/test_git_insights.py` |
| 026 | Local Git | `readme` | `git_insights.inspect_repository` | `linux/tests/test_git_insights.py` |
| 027 | Local Git | `license` | `git_insights.inspect_repository` | `linux/tests/test_git_insights.py` |
| 028 | Local Git | `gitignore` | `git_insights.inspect_repository` | `linux/tests/test_git_insights.py` |
| 029 | Local Git | `gitattributes` | `git_insights.inspect_repository` | `linux/tests/test_git_insights.py` |
| 030 | Local Git | `lfs` | `git_insights.inspect_repository` | `linux/tests/test_git_insights.py` |
| 031 | Local Git | `editorconfig` | `git_insights.inspect_repository` | `linux/tests/test_git_insights.py` |
| 032 | Local Git | `ci` | `git_insights.inspect_repository` | `linux/tests/test_git_insights.py` |
| 033 | Local Git | `security_policy` | `git_insights.inspect_repository` | `linux/tests/test_git_insights.py` |
| 034 | Local Git | `contributing` | `git_insights.inspect_repository` | `linux/tests/test_git_insights.py` |
| 035 | Local Git | `codeowners` | `git_insights.inspect_repository` | `linux/tests/test_git_insights.py` |
| 036 | Local Git | `author_config` | `git_insights.inspect_repository` | `linux/tests/test_git_insights.py` |
| 037 | Local Git | `credential_helper` | `git_insights.inspect_repository` | `linux/tests/test_git_insights.py` |
| 038 | Local Git | `signing` | `git_insights.inspect_repository` | `linux/tests/test_git_insights.py` |
| 039 | Local Git | `ignored_count` | `git_insights.inspect_repository` | `linux/tests/test_git_insights.py` |
| 040 | Local Git | `clean` | `git_insights.inspect_repository` | `linux/tests/test_git_insights.py` |
| 041 | Project audit | `META_README` | `project_audit.audit_project` | `linux/tests/test_project_audit.py` |
| 042 | Project audit | `META_LICENSE` | `project_audit.audit_project` | `linux/tests/test_project_audit.py` |
| 043 | Project audit | `META_SECURITY` | `project_audit.audit_project` | `linux/tests/test_project_audit.py` |
| 044 | Project audit | `META_CONTRIBUTING` | `project_audit.audit_project` | `linux/tests/test_project_audit.py` |
| 045 | Project audit | `META_CODE_OF_CONDUCT` | `project_audit.audit_project` | `linux/tests/test_project_audit.py` |
| 046 | Project audit | `META_CHANGELOG` | `project_audit.audit_project` | `linux/tests/test_project_audit.py` |
| 047 | Project audit | `META_GITIGNORE` | `project_audit.audit_project` | `linux/tests/test_project_audit.py` |
| 048 | Project audit | `META_EDITORCONFIG` | `project_audit.audit_project` | `linux/tests/test_project_audit.py` |
| 049 | Project audit | `META_CODEOWNERS` | `project_audit.audit_project` | `linux/tests/test_project_audit.py` |
| 050 | Project audit | `META_ISSUE_TEMPLATE` | `project_audit.audit_project` | `linux/tests/test_project_audit.py` |
| 051 | Project audit | `META_PR_TEMPLATE` | `project_audit.audit_project` | `linux/tests/test_project_audit.py` |
| 052 | Project audit | `META_CI` | `project_audit.audit_project` | `linux/tests/test_project_audit.py` |
| 053 | Project audit | `FILE_TOO_LARGE` | `project_audit.audit_project` | `linux/tests/test_project_audit.py` |
| 054 | Project audit | `MANIFEST_PACKAGE_JSON` | `project_audit.audit_project` | `linux/tests/test_project_audit.py` |
| 055 | Project audit | `MANIFEST_PACKAGE_VERSION` | `project_audit.audit_project` | `linux/tests/test_project_audit.py` |
| 056 | Project audit | `MANIFEST_PACKAGE_TEST` | `project_audit.audit_project` | `linux/tests/test_project_audit.py` |
| 057 | Project audit | `MANIFEST_PACKAGE_BUILD` | `project_audit.audit_project` | `linux/tests/test_project_audit.py` |
| 058 | Project audit | `MANIFEST_PACKAGE_LOCK` | `project_audit.audit_project` | `linux/tests/test_project_audit.py` |
| 059 | Project audit | `MANIFEST_PYPROJECT` | `project_audit.audit_project` | `linux/tests/test_project_audit.py` |
| 060 | Project audit | `MANIFEST_REQUIREMENTS_EMPTY` | `project_audit.audit_project` | `linux/tests/test_project_audit.py` |
| 061 | Project audit | `MANIFEST_REQUIREMENTS_EDITABLE` | `project_audit.audit_project` | `linux/tests/test_project_audit.py` |
| 062 | Project audit | `MANIFEST_CSPROJ_XML` | `project_audit.audit_project` | `linux/tests/test_project_audit.py` |
| 063 | Project audit | `MANIFEST_CSPROJ_FRAMEWORK` | `project_audit.audit_project` | `linux/tests/test_project_audit.py` |
| 064 | Project audit | `MANIFEST_DOTNET_SDK` | `project_audit.audit_project` | `linux/tests/test_project_audit.py` |
| 065 | Project audit | `MANIFEST_BUILD_PROPS` | `project_audit.audit_project` | `linux/tests/test_project_audit.py` |
| 066 | Project audit | `PATH_WHITESPACE` | `project_audit.audit_project` | `linux/tests/test_project_audit.py` |
| 067 | Project audit | `PATH_SENSITIVE_NAME` | `project_audit.audit_project` | `linux/tests/test_project_audit.py` |
| 068 | Project audit | `FILE_EMPTY` | `project_audit.audit_project` | `linux/tests/test_project_audit.py` |
| 069 | Project audit | `TEXT_FINAL_NEWLINE` | `project_audit.audit_project` | `linux/tests/test_project_audit.py` |
| 070 | Project audit | `TEXT_TRAILING_SPACE` | `project_audit.audit_project` | `linux/tests/test_project_audit.py` |
| 071 | Project audit | `TEXT_MIXED_EOL` | `project_audit.audit_project` | `linux/tests/test_project_audit.py` |
| 072 | Project audit | `TEXT_CONFLICT_MARKER` | `project_audit.audit_project` | `linux/tests/test_project_audit.py` |
| 073 | Project audit | `PATH_CASE_COLLISION` | `project_audit.audit_project` | `linux/tests/test_project_audit.py` |
| 074 | Project audit | `PATH_SYMLINK` | `project_audit.audit_project` | `linux/tests/test_project_audit.py` |
| 075 | Project audit | `CI_WRITE_ALL` | `project_audit.audit_project` | `linux/tests/test_project_audit.py` |
| 076 | Project audit | `CI_MUTABLE_REF` | `project_audit.audit_project` | `linux/tests/test_project_audit.py` |
| 077 | Project audit | `CI_PR_TARGET` | `project_audit.audit_project` | `linux/tests/test_project_audit.py` |
| 078 | Project audit | `CI_CONTENTS_WRITE` | `project_audit.audit_project` | `linux/tests/test_project_audit.py` |
| 079 | Project audit | `CI_TAG_PIN` | `project_audit.audit_project` | `linux/tests/test_project_audit.py` |
| 080 | Project audit | `CI_PERMISSIONS` | `project_audit.audit_project` | `linux/tests/test_project_audit.py` |
| 081 | Release artifacts | `directory` | `release_audit.audit_release` | `linux/tests/test_release_audit.py` |
| 082 | Release artifacts | `artifact_count` | `release_audit.audit_release` | `linux/tests/test_release_audit.py` |
| 083 | Release artifacts | `artifact_limit` | `release_audit.audit_release` | `linux/tests/test_release_audit.py` |
| 084 | Release artifacts | `symlinks` | `release_audit.audit_release` | `linux/tests/test_release_audit.py` |
| 085 | Release artifacts | `empty_files` | `release_audit.audit_release` | `linux/tests/test_release_audit.py` |
| 086 | Release artifacts | `total_size` | `release_audit.audit_release` | `linux/tests/test_release_audit.py` |
| 087 | Release artifacts | `artifact_size_limit` | `release_audit.audit_release` | `linux/tests/test_release_audit.py` |
| 088 | Release artifacts | `artifact_total_limit` | `release_audit.audit_release` | `linux/tests/test_release_audit.py` |
| 089 | Release artifacts | `filename_case_duplicates` | `release_audit.audit_release` | `linux/tests/test_release_audit.py` |
| 090 | Release artifacts | `artifact_extensions` | `release_audit.audit_release` | `linux/tests/test_release_audit.py` |
| 091 | Release artifacts | `unknown_extensions` | `release_audit.audit_release` | `linux/tests/test_release_audit.py` |
| 092 | Release artifacts | `filename_versions` | `release_audit.audit_release` | `linux/tests/test_release_audit.py` |
| 093 | Release artifacts | `version_consistency` | `release_audit.audit_release` | `linux/tests/test_release_audit.py` |
| 094 | Release artifacts | `expected_version` | `release_audit.audit_release` | `linux/tests/test_release_audit.py` |
| 095 | Release artifacts | `version_mismatches` | `release_audit.audit_release` | `linux/tests/test_release_audit.py` |
| 096 | Release artifacts | `checksum_manifests` | `release_audit.audit_release` | `linux/tests/test_release_audit.py` |
| 097 | Release artifacts | `checksum_manifest_names` | `release_audit.audit_release` | `linux/tests/test_release_audit.py` |
| 098 | Release artifacts | `checksum_entries` | `release_audit.audit_release` | `linux/tests/test_release_audit.py` |
| 099 | Release artifacts | `checksum_manifest_errors` | `release_audit.audit_release` | `linux/tests/test_release_audit.py` |
| 100 | Release artifacts | `checksum_manifest_budget` | `release_audit.audit_release` | `linux/tests/test_release_audit.py` |
| 101 | Release artifacts | `checksum_path_safety` | `release_audit.audit_release` | `linux/tests/test_release_audit.py` |
| 102 | Release artifacts | `checksum_duplicate_paths` | `release_audit.audit_release` | `linux/tests/test_release_audit.py` |
| 103 | Release artifacts | `checksum_missing_artifacts` | `release_audit.audit_release` | `linux/tests/test_release_audit.py` |
| 104 | Release artifacts | `checksum_unlisted_artifacts` | `release_audit.audit_release` | `linux/tests/test_release_audit.py` |
| 105 | Release artifacts | `checksum_unlisted_rows` | `release_audit.audit_release` | `linux/tests/test_release_audit.py` |
| 106 | Release artifacts | `checksum_verified` | `release_audit.audit_release` | `linux/tests/test_release_audit.py` |
| 107 | Release artifacts | `checksum_mismatch` | `release_audit.audit_release` | `linux/tests/test_release_audit.py` |
| 108 | Release artifacts | `checksum_read_budget` | `release_audit.audit_release` | `linux/tests/test_release_audit.py` |
| 109 | Release artifacts | `checksum_algorithm` | `release_audit.audit_release` | `linux/tests/test_release_audit.py` |
| 110 | Release artifacts | `checksum_absent` | `release_audit.audit_release` | `linux/tests/test_release_audit.py` |
| 111 | Release artifacts | `zip_count` | `release_audit.audit_release` | `linux/tests/test_release_audit.py` |
| 112 | Release artifacts | `zip_entry_count` | `release_audit.audit_release` | `linux/tests/test_release_audit.py` |
| 113 | Release artifacts | `zip_expanded_size` | `release_audit.audit_release` | `linux/tests/test_release_audit.py` |
| 114 | Release artifacts | `zip_integrity` | `release_audit.audit_release` | `linux/tests/test_release_audit.py` |
| 115 | Release artifacts | `zip_layout` | `release_audit.audit_release` | `linux/tests/test_release_audit.py` |
| 116 | Release artifacts | `platform_coverage` | `release_audit.audit_release` | `linux/tests/test_release_audit.py` |
| 117 | Release artifacts | `linux_packages` | `release_audit.audit_release` | `linux/tests/test_release_audit.py` |
| 118 | Release artifacts | `deb_archive_format` | `release_audit.audit_release` | `linux/tests/test_release_audit.py` |
| 119 | Release artifacts | `signatures` | `release_audit.audit_release` | `linux/tests/test_release_audit.py` |
| 120 | Release artifacts | `standalone_installers` | `release_audit.audit_release` | `linux/tests/test_release_audit.py` |
| 121 | Saved workspace | `STATE_PATH` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 122 | Saved workspace | `STATE_EXISTS` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 123 | Saved workspace | `STATE_DIRECTORY` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 124 | Saved workspace | `STATE_OWNER` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 125 | Saved workspace | `STATE_MODE` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 126 | Saved workspace | `STATE_READ` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 127 | Saved workspace | `STATE_WRITE` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 128 | Saved workspace | `STATE_SYMLINK` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 129 | Saved workspace | `QUEUE_FOLDER` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 130 | Saved workspace | `QUEUE_FILE_COUNT` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 131 | Saved workspace | `QUEUE_FILENAME` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 132 | Saved workspace | `QUEUE_PRIVATE_MODE` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 133 | Saved workspace | `QUEUE_PARSE` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 134 | Saved workspace | `QUEUE_SIZE` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 135 | Saved workspace | `STATE_TOTAL_SIZE` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 136 | Saved workspace | `QUEUE_SCHEMA` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 137 | Saved workspace | `QUEUE_ROWS` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 138 | Saved workspace | `QUEUE_DESTINATION_DUPLICATE` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 139 | Saved workspace | `QUEUE_DESTINATION_PATH` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 140 | Saved workspace | `QUEUE_SENSITIVE_DESTINATION` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 141 | Saved workspace | `QUEUE_REPOSITORY` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 142 | Saved workspace | `QUEUE_BRANCH` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 143 | Saved workspace | `QUEUE_ENTRY_STATUS` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 144 | Saved workspace | `QUEUE_SOURCE_MISSING` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 145 | Saved workspace | `QUEUE_SOURCE_CHANGED` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 146 | Saved workspace | `QUEUE_SOURCE_HASH_BUDGET` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 147 | Saved workspace | `QUEUE_OLD` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 148 | Saved workspace | `QUEUE_SECRET_PATTERN` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 149 | Saved workspace | `STATE_DUPLICATE_NAMES` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 150 | Saved workspace | `BINDING_FILE` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 151 | Saved workspace | `BINDING_COUNT` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 152 | Saved workspace | `BINDING_SCHEMA` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 153 | Saved workspace | `STATE_CONTENT_FILES` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 154 | Saved workspace | `STATE_TOKEN_FIELDS` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 155 | Saved workspace | `QUEUE_TEMPORARIES` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 156 | Saved workspace | `STATE_TEMPORARIES` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 157 | Saved workspace | `QUEUE_FILE_COUNT_CAP` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 158 | Saved workspace | `STATE_PRIVATE_PARENT` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 159 | Saved workspace | `STATE_JSON_ONLY` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 160 | Saved workspace | `QUEUE_ACCOUNT_SCOPE` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 161 | Saved workspace | `QUEUE_APPROVAL_PERSISTENCE` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 162 | Saved workspace | `QUEUE_CONTENT_PERSISTENCE` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 163 | Saved workspace | `QUEUE_HASH_FORMAT` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 164 | Saved workspace | `QUEUE_SOURCE_ABSOLUTE` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 165 | Saved workspace | `QUEUE_MODE` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 166 | Saved workspace | `QUEUE_MESSAGE_LENGTH` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 167 | Saved workspace | `QUEUE_REPO_BRANCH_KEY` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 168 | Saved workspace | `QUEUE_FILES_REGULAR` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 169 | Saved workspace | `BINDING_CREDENTIALS` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 170 | Saved workspace | `WORKSPACE_AUDIT_SCOPE` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 171 | Saved workspace | `STATE_FILES_CAPPED` | `workspace_audit.audit_workspace` | `linux/tests/test_workspace_audit.py` |
| 172 | Environment doctor | `Linux host` | `diagnostics.environment_report` | `linux/tests/test_diagnostics.py` |
| 173 | Environment doctor | `Supported CPU family` | `diagnostics.environment_report` | `linux/tests/test_diagnostics.py` |
| 174 | Environment doctor | `Python version` | `diagnostics.environment_report` | `linux/tests/test_diagnostics.py` |
| 175 | Environment doctor | `Tk version` | `diagnostics.environment_report` | `linux/tests/test_diagnostics.py` |
| 176 | Environment doctor | `TLS support` | `diagnostics.environment_report` | `linux/tests/test_diagnostics.py` |
| 177 | Environment doctor | `Certificate bundle` | `diagnostics.environment_report` | `linux/tests/test_diagnostics.py` |
| 178 | Environment doctor | `Home folder` | `diagnostics.environment_report` | `linux/tests/test_diagnostics.py` |
| 179 | Environment doctor | `Private state folder` | `diagnostics.environment_report` | `linux/tests/test_diagnostics.py` |
| 180 | Environment doctor | `Temporary storage` | `diagnostics.environment_report` | `linux/tests/test_diagnostics.py` |
| 181 | Environment doctor | `GitHub CLI` | `diagnostics.environment_report` | `linux/tests/test_diagnostics.py` |
| 182 | Environment doctor | `Git` | `diagnostics.environment_report` | `linux/tests/test_diagnostics.py` |
| 183 | Environment doctor | `VS Code CLI` | `diagnostics.environment_report` | `linux/tests/test_diagnostics.py` |
| 184 | Environment doctor | `Desktop URL handler` | `diagnostics.environment_report` | `linux/tests/test_diagnostics.py` |
| 185 | Environment doctor | `Debian package tools` | `diagnostics.environment_report` | `linux/tests/test_diagnostics.py` |
| 186 | Environment doctor | `SHA-256 utility` | `diagnostics.environment_report` | `linux/tests/test_diagnostics.py` |
| 187 | Environment doctor | `Tar utility` | `diagnostics.environment_report` | `linux/tests/test_diagnostics.py` |
| 188 | Environment doctor | `Graphical session` | `diagnostics.environment_report` | `linux/tests/test_diagnostics.py` |
| 189 | Environment doctor | `GitHub CLI sign-in` | `diagnostics.environment_report` | `linux/tests/test_diagnostics.py` |
| 190 | Environment doctor | `GitHub API network` | `diagnostics.environment_report` | `linux/tests/test_diagnostics.py` |
| 191 | Environment doctor | `Bundled runtime` | `diagnostics.environment_report` | `linux/tests/test_diagnostics.py` |
| 192 | Environment doctor | `Locale` | `diagnostics.environment_report` | `linux/tests/test_diagnostics.py` |
| 193 | Environment doctor | `CPU count` | `diagnostics.environment_report` | `linux/tests/test_diagnostics.py` |
| 194 | Environment doctor | `Python module: tkinter` | `diagnostics.environment_report` | `linux/tests/test_diagnostics.py` |
| 195 | Environment doctor | `Python module: fcntl` | `diagnostics.environment_report` | `linux/tests/test_diagnostics.py` |
| 196 | Environment doctor | `Runtime lock folder` | `diagnostics.environment_report` | `linux/tests/test_diagnostics.py` |
| 197 | Environment doctor | `Proxy configuration` | `diagnostics.environment_report` | `linux/tests/test_diagnostics.py` |
| 198 | Environment doctor | `Host name` | `diagnostics.environment_report` | `linux/tests/test_diagnostics.py` |
| 199 | Environment doctor | `Free space` | `diagnostics.environment_report` | `linux/tests/test_diagnostics.py` |
| 200 | Environment doctor | `UI runtime selection` | `diagnostics.environment_report` | `linux/tests/test_diagnostics.py` |
| 201 | Environment doctor | `Python override variables` | `diagnostics.environment_report` | `linux/tests/test_diagnostics.py` |
| 202 | Environment doctor | `Tcl/Tk override variables` | `diagnostics.environment_report` | `linux/tests/test_diagnostics.py` |
| 203 | Environment doctor | `Wayland session` | `diagnostics.environment_report` | `linux/tests/test_diagnostics.py` |
| 204 | Environment doctor | `X11 session` | `diagnostics.environment_report` | `linux/tests/test_diagnostics.py` |
| 205 | Environment doctor | `Desktop session type` | `diagnostics.environment_report` | `linux/tests/test_diagnostics.py` |
| 206 | Environment doctor | `Config folder` | `diagnostics.environment_report` | `linux/tests/test_diagnostics.py` |
| 207 | Environment doctor | `Data folder` | `diagnostics.environment_report` | `linux/tests/test_diagnostics.py` |
| 208 | Environment doctor | `Cache folder` | `diagnostics.environment_report` | `linux/tests/test_diagnostics.py` |
| 209 | Environment doctor | `Runtime folder privacy` | `diagnostics.environment_report` | `linux/tests/test_diagnostics.py` |
| 210 | Environment doctor | `Bundle Python executable` | `diagnostics.environment_report` | `linux/tests/test_diagnostics.py` |
| 211 | Environment doctor | `Bundle GitHub CLI` | `diagnostics.environment_report` | `linux/tests/test_diagnostics.py` |
| 212 | Environment doctor | `Bundle certificate file` | `diagnostics.environment_report` | `linux/tests/test_diagnostics.py` |
| 213 | Environment doctor | `Package manager` | `diagnostics.environment_report` | `linux/tests/test_diagnostics.py` |
| 214 | Environment doctor | `UTF-8 locale` | `diagnostics.environment_report` | `linux/tests/test_diagnostics.py` |

**Inventory count: 214.** The tools cover environment readiness (43), local Git insights (40), project readiness (40), release artifact integrity (40), and saved workspace state (51).
