"""Create common project-maintenance files without executing project code."""
import json
import os
import re
import tempfile
from pathlib import Path

from .core import OctoShipError


# Each recipe is a separate starter workflow selected by output path and language.
RECIPES = {
    "readme": ("README.md", "# {project}\n\n{summary}\n\n## Getting started\n\n## Usage\n\n## Development\n\n## License\n"),
    "changelog": ("CHANGELOG.md", "# Changelog\n\nAll notable changes to {project} are recorded here.\n\n## Unreleased\n\n### Added\n\n### Changed\n\n### Fixed\n"),
    "contributing": ("CONTRIBUTING.md", "# Contributing to {project}\n\n## Report a bug\n\n## Propose a change\n\n## Development setup\n\n## Pull requests\n\nDescribe the change and how it was checked.\n"),
    "security_policy": ("SECURITY.md", "# Security policy\n\n## Supported versions\n\n| Version | Supported |\n| --- | --- |\n| Current | Yes |\n\n## Report a vulnerability\n\nContact the maintainers privately. Do not publish exploit details before a fix is available.\n"),
    "code_of_conduct": ("CODE_OF_CONDUCT.md", "# Community standards\n\nParticipants in {project} are expected to be respectful, constructive, and inclusive. Report concerns privately to the maintainers.\n"),
    "editorconfig": (".editorconfig", "root = true\n\n[*]\ncharset = utf-8\nend_of_line = lf\ninsert_final_newline = true\nindent_style = space\nindent_size = 4\n\n[*.md]\ntrim_trailing_whitespace = false\n"),
    "gitattributes": (".gitattributes", "* text=auto eol=lf\n*.png binary\n*.jpg binary\n*.zip binary\n"),
    "gitignore_python": (".gitignore", "__pycache__/\n*.py[cod]\n.venv/\nvenv/\n.env\n.pytest_cache/\ndist/\nbuild/\n"),
    "gitignore_node": (".gitignore", "node_modules/\ndist/\nbuild/\n.env\n.env.*\n!.env.example\n.npm/\n"),
    "gitignore_rust": (".gitignore", "/target/\n.env\n"),
    "gitignore_go": (".gitignore", "/bin/\n/vendor/\n.env\n"),
    "gitignore_java": (".gitignore", "*.class\n/target/\n/.gradle/\nbuild/\n.env\n"),
    "gitignore_dotnet": (".gitignore", "bin/\nobj/\n.vs/\n*.user\n.env\n"),
    "gitignore_docker": (".dockerignore", ".git\n.env\n.venv\nnode_modules\n__pycache__\n"),
    "ci_python": (".github/workflows/ci.yml", "name: Python CI\non:\n  push:\n  pull_request:\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - uses: actions/setup-python@v5\n        with:\n          python-version: '3.x'\n      - run: python -m unittest discover -s tests\n"),
    "ci_node": (".github/workflows/ci.yml", "name: Node CI\non:\n  push:\n  pull_request:\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - uses: actions/setup-node@v4\n        with:\n          node-version: 22\n          cache: npm\n      - run: npm ci\n      - run: npm test --if-present\n"),
    "ci_rust": (".github/workflows/ci.yml", "name: Rust CI\non:\n  push:\n  pull_request:\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - uses: dtolnay/rust-toolchain@stable\n      - run: cargo fmt --check\n      - run: cargo test --locked\n"),
    "ci_go": (".github/workflows/ci.yml", "name: Go CI\non:\n  push:\n  pull_request:\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - uses: actions/setup-go@v5\n        with:\n          go-version: stable\n      - run: go test ./...\n"),
    "bug_report": (".github/ISSUE_TEMPLATE/bug_report.yml", "name: Bug report\ndescription: Report a reproducible problem\nbody:\n  - type: textarea\n    id: summary\n    attributes:\n      label: What happened?\n    validations:\n      required: true\n  - type: textarea\n    id: steps\n    attributes:\n      label: Steps to reproduce\n    validations:\n      required: true\n"),
    "feature_request": (".github/ISSUE_TEMPLATE/feature_request.yml", "name: Feature request\ndescription: Suggest an improvement\nbody:\n  - type: textarea\n    id: problem\n    attributes:\n      label: Problem to solve\n    validations:\n      required: true\n  - type: textarea\n    id: proposal\n    attributes:\n      label: Proposed solution\n"),
    "pull_request_template": (".github/PULL_REQUEST_TEMPLATE.md", "## Summary\n\n## Validation\n\n## Checklist\n\n- [ ] Tests or checks are included\n- [ ] Documentation is updated\n- [ ] No secrets or generated files are included\n"),
    "dependabot": (".github/dependabot.yml", "version: 2\nupdates:\n  - package-ecosystem: pip\n    directory: /\n    schedule:\n      interval: weekly\n  - package-ecosystem: github-actions\n    directory: /\n    schedule:\n      interval: weekly\n"),
    "precommit": (".pre-commit-config.yaml", "repos:\n  - repo: https://github.com/pre-commit/pre-commit-hooks\n    rev: v5.0.0\n    hooks:\n      - id: check-yaml\n      - id: end-of-file-fixer\n      - id: trailing-whitespace\n"),
    "makefile_python": ("Makefile", ".PHONY: test lint\ntest:\n\tpython -m unittest discover -s tests\nlint:\n\tpython -m compileall -q .\n"),
    "dockerfile_python": ("Dockerfile", "FROM python:3.12-slim\nWORKDIR /app\nCOPY requirements.txt ./\nRUN pip install --no-cache-dir -r requirements.txt\nCOPY . .\nCMD [\"python\", \"-m\", \"your_package\"]\n"),
    "docker_compose": ("compose.yaml", "services:\n  app:\n    build: .\n    restart: unless-stopped\n    env_file:\n      - .env\n"),
    "license_mit": ("LICENSE", "MIT License\n\nCopyright (c) {year} {owner}\n\nPermission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the \"Software\"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:\n\nThe above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.\n\nTHE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.\n"),
    "coverage_python": (".coveragerc", "[run]\nbranch = True\nsource = .\nomit =\n    */tests/*\n    */site-packages/*\n\n[report]\nshow_missing = True\nskip_covered = True\n"),
    "renovate": ("renovate.json", "{\n  \"$schema\": \"https://docs.renovatebot.com/renovate-schema.json\",\n  \"extends\": [\"config:recommended\"],\n  \"schedule\": [\"before 5am on Monday\"]\n}\n"),
}

RECIPES.update({
    "python_pyproject": ("pyproject.toml", "[project]\nname = \"{slug}\"\nversion = \"0.1.0\"\ndescription = {summary_toml}\nrequires-python = \">=3.10\"\n\n[build-system]\nrequires = [\"setuptools>=68\"]\nbuild-backend = \"setuptools.build_meta\"\n"),
    "python_pytest": ("pytest.ini", "[pytest]\ntestpaths = tests\naddopts = -ra\n"),
    "python_ruff": ("ruff.toml", "line-length = 100\ntarget-version = \"py310\"\n\n[lint]\nselect = [\"E\", \"F\", \"I\"]\n"),
    "python_mypy": ("mypy.ini", "[mypy]\npython_version = 3.10\nwarn_unused_configs = True\nwarn_return_any = True\n"),
    "python_dev_requirements": ("requirements-dev.txt", "pytest>=8\nruff>=0.6\nmypy>=1.10\n"),
    "python_tox": ("tox.ini", "[tox]\nenvlist = py310, py311, py312\nskipsdist = true\n\n[testenv]\ncommands = python -m unittest discover -s tests\n"),
    "python_uv": ("uv.toml", "[pip]\nindex-url = \"https://pypi.org/simple\"\n"),
    "python_pip_conf": ("pip.conf", "[global]\nrequire-virtualenv = true\n"),
    "node_package": ("package.json", "{\n  \"name\": \"{slug}\",\n  \"version\": \"0.1.0\",\n  \"private\": true,\n  \"scripts\": {\"test\": \"node --test\"}\n}\n"),
    "node_typescript": ("tsconfig.json", "{\n  \"compilerOptions\": {\n    \"target\": \"ES2022\",\n    \"module\": \"NodeNext\",\n    \"strict\": true,\n    \"outDir\": \"dist\"\n  },\n  \"include\": [\"src/**/*.ts\"]\n}\n"),
    "node_eslint": ("eslint.config.js", "export default [\n  { ignores: [\"dist/**\", \"node_modules/**\"] },\n  { files: [\"**/*.js\", \"**/*.ts\"], rules: {} },\n];\n"),
    "node_prettier": (".prettierrc.json", "{\n  \"singleQuote\": true,\n  \"trailingComma\": \"all\",\n  \"printWidth\": 100\n}\n"),
    "node_npmrc": (".npmrc", "save-exact=true\nfund=false\n"),
    "node_vitest": ("vitest.config.ts", "import { defineConfig } from 'vitest/config';\n\nexport default defineConfig({\n  test: { environment: 'node', include: ['tests/**/*.test.ts'] },\n});\n"),
    "node_playwright": ("playwright.config.ts", "import { defineConfig } from '@playwright/test';\n\nexport default defineConfig({\n  testDir: './e2e',\n  use: { baseURL: 'http://127.0.0.1:3000' },\n  webServer: { command: 'npm run dev', url: 'http://127.0.0.1:3000', reuseExistingServer: !process.env.CI },\n});\n"),
    "node_dockerfile": ("Dockerfile", "FROM node:22-alpine\nWORKDIR /app\nCOPY package*.json ./\nRUN npm ci\nCOPY . .\nRUN npm run build --if-present\nCMD [\"npm\", \"start\"]\n"),
    "node_pnpm_workspace": ("pnpm-workspace.yaml", "packages:\n  - apps/*\n  - packages/*\n"),
    "node_changesets": (".changeset/config.json", "{\n  \"$schema\": \"https://unpkg.com/@changesets/config@3.0.0/schema.json\",\n  \"access\": \"restricted\",\n  \"baseBranch\": \"main\",\n  \"updateInternalDependencies\": \"patch\"\n}\n"),
    "rustfmt": ("rustfmt.toml", "edition = \"2021\"\nmax_width = 100\nuse_small_heuristics = \"Default\"\n"),
    "rust_clippy": (".cargo/config.toml", "[alias]\ncheck-all = \"clippy --all-targets --all-features -- -D warnings\"\n"),
    "rust_deny": ("deny.toml", "[bans]\nmultiple-versions = \"warn\"\n\n[licenses]\nallow = [\"MIT\", \"Apache-2.0\"]\n"),
    "go_makefile": ("Makefile", ".PHONY: test vet\ntest:\n\tgo test ./...\nvet:\n\tgo vet ./...\n"),
    "go_lint": (".golangci.yml", "version: \"2\"\nlinters:\n  default: standard\nrun:\n  timeout: 5m\n"),
    "go_dockerfile": ("Dockerfile", "FROM golang:1.23-alpine AS build\nWORKDIR /src\nCOPY go.mod go.sum ./\nRUN go mod download\nCOPY . .\nRUN go build -o /app ./...\nFROM alpine:3.20\nCOPY --from=build /app /app\nENTRYPOINT [\"/app\"]\n"),
    "java_pom": ("pom.xml", "<project xmlns=\"http://maven.apache.org/POM/4.0.0\"><modelVersion>4.0.0</modelVersion><groupId>example</groupId><artifactId>{slug}</artifactId><version>0.1.0</version><properties><maven.compiler.release>17</maven.compiler.release><project.build.sourceEncoding>UTF-8</project.build.sourceEncoding></properties></project>\n"),
    "java_gradle": ("build.gradle.kts", "plugins { java }\n\ngroup = \"example\"\nversion = \"0.1.0\"\n\njava { toolchain { languageVersion.set(JavaLanguageVersion.of(17)) } }\n\ntasks.test { useJUnitPlatform() }\n"),
    "dotnet_build_props": ("Directory.Build.props", "<Project><PropertyGroup><Nullable>enable</Nullable><ImplicitUsings>enable</ImplicitUsings><TreatWarningsAsErrors>true</TreatWarningsAsErrors></PropertyGroup></Project>\n"),
    "dotnet_global_json": ("global.json", "{\n  \"sdk\": {\n    \"version\": \"8.0.100\",\n    \"rollForward\": \"latestFeature\"\n  }\n}\n"),
    "vscode_settings": (".vscode/settings.json", "{\n  \"files.trimTrailingWhitespace\": true,\n  \"files.insertFinalNewline\": true,\n  \"editor.formatOnSave\": true\n}\n"),
    "vscode_extensions": (".vscode/extensions.json", "{\n  \"recommendations\": [],\n  \"unwantedRecommendations\": []\n}\n"),
    "vscode_tasks": (".vscode/tasks.json", "{\n  \"version\": \"2.0.0\",\n  \"tasks\": [{\n    \"label\": \"Run tests\",\n    \"type\": \"shell\",\n    \"command\": \"python -m unittest discover -s tests\",\n    \"problemMatcher\": []\n  }]\n}\n"),
    "vscode_launch": (".vscode/launch.json", "{\n  \"version\": \"0.2.0\",\n  \"configurations\": []\n}\n"),
    "github_codeql": (".github/workflows/codeql.yml", "name: CodeQL\non:\n  push:\n    branches: [main]\n  pull_request:\n  schedule:\n    - cron: '23 4 * * 1'\njobs:\n  analyze:\n    permissions:\n      security-events: write\n      packages: read\n      actions: read\n      contents: read\n    uses: github/codeql-action/.github/workflows/codeql.yml@v3\n"),
    "github_dependency_review": (".github/workflows/dependency-review.yml", "name: Dependency review\non:\n  pull_request:\njobs:\n  review:\n    runs-on: ubuntu-latest\n    permissions:\n      contents: read\n    steps:\n      - uses: actions/checkout@v4\n      - uses: actions/dependency-review-action@v4\n"),
    "github_stale": (".github/workflows/stale.yml", "name: Mark stale issues\non:\n  schedule:\n    - cron: '0 9 * * 1'\n  workflow_dispatch:\njobs:\n  stale:\n    permissions:\n      issues: write\n      pull-requests: write\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/stale@v9\n        with:\n          days-before-stale: 60\n          days-before-close: 14\n"),
    "github_release_notes": (".github/release.yml", "changelog:\n  categories:\n    - title: Features\n      labels:\n        - feature\n    - title: Fixes\n      labels:\n        - bug\n    - title: Other changes\n      labels:\n        - '*'\n"),
    "github_labeler": (".github/labeler.yml", "documentation:\n  - changed-files:\n      - any-glob-to-any-file: '**/*.md'\ntests:\n  - changed-files:\n      - any-glob-to-any-file: '**/test*'\n"),
    "k8s_deployment": ("k8s/deployment.yaml", "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: app\nspec:\n  replicas: 2\n  selector:\n    matchLabels:\n      app: app\n  template:\n    metadata:\n      labels:\n        app: app\n    spec:\n      containers:\n        - name: app\n          image: replace-with-reviewed-image\n          ports:\n            - containerPort: 8080\n"),
    "k8s_service": ("k8s/service.yaml", "apiVersion: v1\nkind: Service\nmetadata:\n  name: app\nspec:\n  selector:\n    app: app\n  ports:\n    - port: 80\n      targetPort: 8080\n  type: ClusterIP\n"),
    "k8s_namespace": ("k8s/namespace.yaml", "apiVersion: v1\nkind: Namespace\nmetadata:\n  name: app\n"),
    "terraform_variables": ("variables.tf", "variable \"region\" {\n  description = \"Deployment region\"\n  type        = string\n}\n\nvariable \"environment\" {\n  description = \"Environment name\"\n  type        = string\n  validation {\n    condition     = contains([\"dev\", \"staging\", \"prod\"], var.environment)\n    error_message = \"Choose dev, staging, or prod.\"\n  }\n}\n"),
    "terraform_outputs": ("outputs.tf", "output \"resource_id\" {\n  description = \"Created resource identifier\"\n  value       = null\n}\n"),
    "architecture_decision": ("docs/decisions/0001-record-template.md", "# ADR 0001: Record an architecture decision\n\n- Status: proposed\n- Date: {year}\n\n## Context\n\n## Decision\n\n## Consequences\n"),
    "support_policy": ("SUPPORT.md", "# Support\n\n## Supported versions\n\n## Ask a question\n\nInclude your OctoShip version, operating system, steps to reproduce, and relevant redacted logs. Do not attach tokens or secrets.\n"),
    "roadmap": ("ROADMAP.md", "# {project} roadmap\n\nThis roadmap describes current priorities and may change as project needs evolve.\n\n## Now\n\n## Next\n\n## Later\n"),
})

RECIPES.update({
    "python_pyright": ("pyrightconfig.json", "{\n  \"include\": [\"src\", \"tests\"],\n  \"typeCheckingMode\": \"standard\",\n  \"reportMissingImports\": true\n}\n"),
    "python_black": (".black", "[tool.black]\nline-length = 100\ntarget-version = ['py310']\n"),
    "python_pylint": (".pylintrc", "[MAIN]\npy-version=3.10\n\n[FORMAT]\nmax-line-length=100\n"),
    "python_nox": ("noxfile.py", "import nox\n\n@nox.session\ndef tests(session):\n    session.install('-r', 'requirements-dev.txt')\n    session.run('python', '-m', 'unittest', 'discover', '-s', 'tests')\n"),
    "python_requirements": ("requirements.txt", "# Add reviewed, pinned runtime dependencies here.\n"),
    "python_pipfile": ("Pipfile", "[[source]]\nurl = \"https://pypi.org/simple\"\nverify_ssl = true\nname = \"pypi\"\n\n[packages]\n\n[dev-packages]\n\n[requires]\npython_version = \"3.12\"\n"),
    "python_poetry": ("poetry.toml", "[virtualenvs]\nin-project = true\n"),
    "node_nvmrc": (".nvmrc", "22\n"),
    "node_node_version": (".node-version", "22\n"),
    "node_yarnrc": (".yarnrc.yml", "nodeLinker: node-modules\nenableGlobalCache: false\n"),
    "node_browserslist": (".browserslistrc", "> 0.5%\nlast 2 versions\nnot dead\n"),
    "node_stylelint": (".stylelintrc.json", "{\n  \"extends\": [\"stylelint-config-standard\"],\n  \"rules\": {\"selector-class-pattern\": null}\n}\n"),
    "node_jest": ("jest.config.js", "module.exports = {\n  testEnvironment: 'node',\n  testMatch: ['<rootDir>/tests/**/*.test.js'],\n  collectCoverageFrom: ['src/**/*.js'],\n};\n"),
    "node_cypress": ("cypress.config.js", "const { defineConfig } = require('cypress');\n\nmodule.exports = defineConfig({\n  e2e: { baseUrl: 'http://127.0.0.1:3000', specPattern: 'cypress/e2e/**/*.cy.js' },\n});\n"),
    "node_storybook": (".storybook/main.js", "export default {\n  stories: ['../src/**/*.stories.@(js|jsx|ts|tsx)'],\n  addons: [],\n  framework: { name: '@storybook/react-vite', options: {} },\n};\n"),
    "node_stylelint": (".stylelintignore", "node_modules\ndist\ncoverage\n"),
    "node_lint_staged": (".lintstagedrc.json", "{\n  \"*.{js,ts,tsx}\": [\"eslint --fix\"],\n  \"*.{css,scss}\": [\"stylelint --fix\"],\n  \"*.md\": [\"prettier --write\"]\n}\n"),
    "ruby_gemfile": ("Gemfile", "source 'https://rubygems.org'\n\nruby '>= 3.2'\n\ngroup :development, :test do\n  gem 'rubocop'\nend\n"),
    "ruby_rubocop": (".rubocop.yml", "AllCops:\n  NewCops: enable\n  TargetRubyVersion: 3.2\n  Exclude:\n    - vendor/**/*\n"),
    "ruby_rakefile": ("Rakefile", "require 'rake/testtask'\n\nRake::TestTask.new(:test) do |task|\n  task.pattern = 'test/**/*_test.rb'\nend\n\ntask default: :test\n"),
    "php_composer": ("composer.json", "{\n  \"name\": \"example/{slug}\",\n  \"description\": \"{summary}\",\n  \"type\": \"project\",\n  \"require\": {\"php\": \">=8.2\"},\n  \"scripts\": {\"test\": \"phpunit\"}\n}\n"),
    "php_phpunit": ("phpunit.xml", "<?xml version=\"1.0\"?>\n<phpunit bootstrap=\"vendor/autoload.php\" colors=\"true\"><testsuites><testsuite name=\"tests\"><directory>tests</directory></testsuite></testsuites></phpunit>\n"),
    "php_phpstan": ("phpstan.neon", "parameters:\n  level: 6\n  paths:\n    - src\n    - tests\n"),
    "php_phpcs": ("phpcs.xml", "<?xml version=\"1.0\"?><ruleset name=\"Project\"><rule ref=\"PSR12\"/><file>src</file><file>tests</file><exclude-pattern>vendor/*</exclude-pattern></ruleset>\n"),
    "php_dockerfile": ("Dockerfile", "FROM php:8.3-cli\nWORKDIR /app\nCOPY . .\nCMD [\"php\", \"-S\", \"0.0.0.0:8080\", \"-t\", \"public\"]\n"),
    "kotlin_gradle": ("build.gradle.kts", "plugins { kotlin(\"jvm\") version \"2.0.0\" }\n\nrepositories { mavenCentral() }\n\ndependencies { testImplementation(kotlin(\"test\")) }\n\ntasks.test { useJUnitPlatform() }\n"),
    "kotlin_settings": ("settings.gradle.kts", "rootProject.name = \"{slug}\"\n"),
    "swift_package": ("Package.swift", "// swift-tools-version: 5.9\nimport PackageDescription\n\nlet package = Package(\n    name: \"{project}\",\n    products: [.library(name: \"{project}\", targets: [\"{project}\"])],\n    targets: [.target(name: \"{project}\"), .testTarget(name: \"{project}Tests\", dependencies: [\"{project}\"])]\n)\n"),
    "cmake_project": ("CMakeLists.txt", "cmake_minimum_required(VERSION 3.20)\nproject({project} LANGUAGES CXX)\nset(CMAKE_CXX_STANDARD 20)\nset(CMAKE_CXX_STANDARD_REQUIRED ON)\n\nenable_testing()\n"),
    "c_cpp_clang_format": (".clang-format", "BasedOnStyle: LLVM\nIndentWidth: 4\nColumnLimit: 100\nAllowShortFunctionsOnASingleLine: Empty\n"),
    "c_cpp_clang_tidy": (".clang-tidy", "Checks: 'bugprone-*,clang-analyzer-*,performance-*,readability-*'\nWarningsAsErrors: ''\nHeaderFilterRegex: '.*'\nFormatStyle: file\n"),
    "github_license_check": (".github/workflows/license-check.yml", "name: License check\non:\n  pull_request:\njobs:\n  check:\n    runs-on: ubuntu-latest\n    permissions:\n      contents: read\n    steps:\n      - uses: actions/checkout@v4\n      - uses: apache/skywalking-eyes/header@v0.6.0\n"),
    "github_pr_size": (".github/workflows/pr-size.yml", "name: Pull request size\non:\n  pull_request:\njobs:\n  size:\n    runs-on: ubuntu-latest\n    permissions:\n      pull-requests: read\n    steps:\n      - uses: actions/checkout@v4\n      - uses: codelytv/pr-size-labeler@v1\n        with:\n          github_token: ${{ secrets.GITHUB_TOKEN }}\n"),
    "github_pages": (".github/workflows/pages.yml", "name: Pages\non:\n  push:\n    branches: [main]\n  workflow_dispatch:\npermissions:\n  contents: read\n  pages: write\n  id-token: write\nconcurrency:\n  group: pages\n  cancel-in-progress: true\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - uses: actions/upload-pages-artifact@v3\n        with:\n          path: ./site\n  deploy:\n    needs: build\n    environment:\n      name: github-pages\n      url: ${{ steps.deployment.outputs.page_url }}\n    runs-on: ubuntu-latest\n    steps:\n      - id: deployment\n        uses: actions/deploy-pages@v4\n"),
    "github_label_sync": (".github/labels.yml", "- name: bug\n  color: d73a4a\n  description: Something is not working\n- name: feature\n  color: a2eeef\n  description: New feature or request\n- name: documentation\n  color: 0075ca\n  description: Documentation improvements\n"),
    "github_funding": (".github/FUNDING.yml", "# Add reviewed sponsor handles here.\n"),
    "github_auto_assign": (".github/auto_assign.yml", "addReviewers: true\naddAssignees: author\nreviewers: []\nnumberOfReviewers: 1\n"),
    "github_pr_labels": (".github/pr-labels.yml", "feature:\n  - head-branch: ['^feature/', '^feat/']\nfix:\n  - head-branch: ['^fix/', '^bugfix/']\ndocumentation:\n  - changed-files:\n      - any-glob-to-any-file: '**/*.md'\n"),
    "github_codeowners": (".github/CODEOWNERS", "# Replace with real GitHub team or usernames before enabling.\n* @your-org/maintainers\n"),
    "github_discussion_template": (".github/DISCUSSION_TEMPLATE/ideas.yml", "title: Idea\nbody:\n  - type: textarea\n    id: idea\n    attributes:\n      label: What would you like to see?\n    validations:\n      required: true\n"),
    "github_issue_config": (".github/ISSUE_TEMPLATE/config.yml", "blank_issues_enabled: false\ncontact_links:\n  - name: Ask a question\n    url: https://github.com/replace-owner/replace-repo/discussions\n    about: Use discussions for support questions\n"),
    "vscode_profile": (".vscode/.gitignore", "*.code-workspace\n"),
    "vscode_snippets": (".vscode/project.code-snippets", "{\n  \"Log message\": {\n    \"prefix\": \"log\",\n    \"body\": [\"console.log($1);\"],\n    \"description\": \"Insert a log statement\"\n  }\n}\n"),
    "vscode_recommendations": (".vscode/extensions-recommended.json", "{\n  \"recommendations\": [\"editorconfig.editorconfig\"],\n  \"unwantedRecommendations\": []\n}\n"),
    "docker_healthcheck": ("docker-healthcheck.sh", "#!/bin/sh\nset -eu\ncurl --fail --silent http://127.0.0.1:8080/health >/dev/null\n"),
    "compose_dev": ("compose.dev.yaml", "services:\n  app:\n    build:\n      context: .\n      target: development\n    volumes:\n      - .:/app\n    ports:\n      - \"8080:8080\"\n"),
    "compose_test": ("compose.test.yaml", "services:\n  test:\n    build: .\n    command: [\"python\", \"-m\", \"unittest\", \"discover\", \"-s\", \"tests\"]\n"),
    "k8s_configmap": ("k8s/configmap.yaml", "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: app-config\ndata:\n  APP_MODE: production\n"),
    "k8s_ingress": ("k8s/ingress.yaml", "apiVersion: networking.k8s.io/v1\nkind: Ingress\nmetadata:\n  name: app\nspec:\n  rules:\n    - host: example.invalid\n      http:\n        paths:\n          - path: /\n            pathType: Prefix\n            backend:\n              service:\n                name: app\n                port:\n                  number: 80\n"),
    "k8s_hpa": ("k8s/hpa.yaml", "apiVersion: autoscaling/v2\nkind: HorizontalPodAutoscaler\nmetadata:\n  name: app\nspec:\n  scaleTargetRef:\n    apiVersion: apps/v1\n    kind: Deployment\n    name: app\n  minReplicas: 2\n  maxReplicas: 6\n  metrics:\n    - type: Resource\n      resource:\n        name: cpu\n        target:\n          type: Utilization\n          averageUtilization: 70\n"),
    "terraform_provider": ("versions.tf", "terraform {\n  required_version = \">= 1.6.0\"\n  required_providers {\n    aws = { source = \"hashicorp/aws\", version = \"~> 5.0\" }\n  }\n}\n"),
    "terraform_main": ("main.tf", "# Add reviewed resources after selecting a provider.\n"),
    "terraform_backend": ("backend.tf.example", "# Copy to backend.tf after choosing a secured remote state backend.\n# Never commit state files or credentials.\n"),
    "docs_architecture": ("docs/ARCHITECTURE.md", "# Architecture\n\n## Context\n\n## Components\n\n## Data flow\n\n## Trust boundaries\n\n## Failure handling\n"),
    "docs_runbook": ("docs/RUNBOOK.md", "# Operations runbook\n\n## Service overview\n\n## Health checks\n\n## Common failures\n\n## Recovery\n\n## Escalation\n"),
    "docs_release_process": ("docs/RELEASING.md", "# Release process\n\n1. Review changes and tests.\n2. Confirm version and changelog.\n3. Build artifacts in a clean environment.\n4. Verify checksums and signatures.\n5. Publish and verify the release.\n"),
    "docs_data_retention": ("docs/DATA-RETENTION.md", "# Data retention\n\nDocument the data collected, purpose, retention period, deletion process, and responsible owner for each data class.\n"),
    "docs_accessibility": ("docs/ACCESSIBILITY.md", "# Accessibility\n\n## Supported standards\n\n## Keyboard navigation\n\n## Screen reader behavior\n\n## Reporting an accessibility issue\n"),
    "docs_threat_model": ("docs/THREAT-MODEL.md", "# Threat model\n\n## Assets\n\n## Trust boundaries\n\n## Threat actors\n\n## Abuse cases\n\n## Mitigations\n\n## Residual risks\n"),
    "docs_privacy": ("docs/PRIVACY.md", "# Privacy notes\n\nDescribe data collected, local and remote processing, retention, third-party services, and deletion controls.\n"),
    "docs_support_matrix": ("docs/SUPPORT-MATRIX.md", "# Platform support\n\n| Platform | Supported version | Notes |\n| --- | --- | --- |\n| Linux | Specify | Specify |\n| Windows | Specify | Specify |\n| macOS | Specify | Specify |\n"),
    "docs_migration": ("docs/MIGRATIONS.md", "# Migration guide\n\n## Before upgrading\n\n## Migration steps\n\n## Rollback\n\n## Verification\n"),
    "docs_backup_restore": ("docs/BACKUP-RESTORE.md", "# Backup and restore\n\nDocument what must be backed up, encryption requirements, restore steps, and a periodic recovery test.\n"),
    "docs_glossary": ("docs/GLOSSARY.md", "# Glossary\n\n| Term | Definition |\n| --- | --- |\n"),
    "docs_test_strategy": ("docs/TESTING.md", "# Test strategy\n\n## Unit tests\n\n## Integration tests\n\n## End-to-end tests\n\n## Fixtures and test data\n\n## Running the checks\n"),
    "docs_api_guidelines": ("docs/API-GUIDELINES.md", "# API guidelines\n\nDocument authentication, validation, pagination, rate limits, error format, compatibility, and deprecation policy.\n"),
    "docs_incident_response": ("docs/INCIDENT-RESPONSE.md", "# Incident response\n\n## Triage\n\n## Containment\n\n## Recovery\n\n## Customer communication\n\n## Follow-up review\n"),
})

RECIPES.update({
    "flatpak_manifest": ("packaging/{project}.yml", "app-id: org.example.{slug}\nruntime: org.freedesktop.Platform\nruntime-version: '24.08'\nsdk: org.freedesktop.Sdk\ncommand: replace-command\nmodules: []\n"),
    "desktop_entry": ("packaging/{project}.desktop", "[Desktop Entry]\nType=Application\nName={project}\nComment={summary}\nExec=replace-command\nTerminal=false\nCategories=Utility;\n"),
    "systemd_service": ("packaging/{project}.service", "[Unit]\nDescription={project}\nAfter=network.target\n\n[Service]\nType=simple\nExecStart=/usr/bin/replace-command\nRestart=on-failure\n\n[Install]\nWantedBy=multi-user.target\n"),
    "systemd_user_service": ("packaging/{project}.user.service", "[Unit]\nDescription={project} user service\n\n[Service]\nType=simple\nExecStart=%h/.local/bin/replace-command\nRestart=on-failure\n\n[Install]\nWantedBy=default.target\n"),
    "rpm_spec": ("packaging/{project}.spec", "Name: {slug}\nVersion: 0.1.0\nRelease: 1%{?dist}\nSummary: {summary}\nLicense: MIT\nBuildArch: noarch\n\n%description\n{summary}\n\n%files\n"),
    "debian_control": ("packaging/debian/control", "Source: {slug}\nSection: utils\nPriority: optional\nMaintainer: {owner}\nBuild-Depends: debhelper-compat (= 13)\nStandards-Version: 4.6.2\n\nPackage: {slug}\nArchitecture: all\nDepends: ${{misc:Depends}}\nDescription: {summary}\n"),
    "debian_rules": ("packaging/debian/rules", "#!/usr/bin/make -f\n%:\n\tdh $@\n"),
    "debian_changelog": ("packaging/debian/changelog", "{slug} (0.1.0-1) unstable; urgency=medium\n\n  * Initial packaging.\n\n -- {owner}  {year}-01-01 00:00:00 +0000\n"),
    "flatpak_builder": ("packaging/flatpak-build.sh", "#!/bin/sh\nset -eu\nflatpak-builder --force-clean build-dir packaging/flatpak-manifest.yml\n"),
    "appimage_builder": ("packaging/appimage.yml", "version: 1\nAppDir:\n  path: ./AppDir\n  app_info:\n    id: org.example.{slug}\n    name: {project}\n    exec: replace-command\n"),
    "firebaserc": (".firebaserc.example", "{\n  \"projects\": {\n    \"default\": \"replace-with-reviewed-project-id\"\n  }\n}\n"),
    "firebase_hosting": ("firebase.json.example", "{\n  \"hosting\": {\n    \"public\": \"dist\",\n    \"ignore\": [\"firebase.json\", \"**/.*\", \"**/node_modules/**\"],\n    \"headers\": [{\n      \"source\": \"**\",\n      \"headers\": [{\"key\": \"X-Content-Type-Options\", \"value\": \"nosniff\"}]\n    }]\n  }\n}\n"),
    "firebase_rules": ("firestore.rules.example", "rules_version = '2';\nservice cloud.firestore {\n  match /databases/{database}/documents {\n    match /{document=**} {\n      allow read, write: if false; // Replace with reviewed, user-specific rules.\n    }\n  }\n}\n"),
    "firebase_storage_rules": ("storage.rules.example", "rules_version = '2';\nservice firebase.storage {\n  match /b/{bucket}/o {\n    match /{allPaths=**} {\n      allow read, write: if false; // Replace with reviewed, user-specific rules.\n    }\n  }\n}\n"),
    "firebase_functions_package": ("functions/package.json", "{\n  \"name\": \"{slug}-functions\",\n  \"private\": true,\n  \"engines\": {\"node\": \"22\"},\n  \"scripts\": {\"lint\": \"eslint .\", \"test\": \"node --test\"}\n}\n"),
    "firebase_emulators": ("firebase.emulator.json.example", "{\n  \"emulators\": {\n    \"auth\": {\"port\": 9099},\n    \"firestore\": {\"port\": 8080},\n    \"ui\": {\"enabled\": true}\n  }\n}\n"),
    "openapi": ("openapi.yaml", "openapi: 3.1.0\ninfo:\n  title: {project}\n  version: 0.1.0\n  description: {summary}\npaths:\n  /health:\n    get:\n      summary: Health status\n      responses:\n        '200':\n          description: Service is available\n"),
    "graphql_schema": ("schema.graphql", "type Query {\n  health: String!\n}\n"),
    "sql_migration": ("db/migrations/0001_initial.sql", "-- Add a reviewed, reversible schema migration here.\nBEGIN;\n\n-- CREATE TABLE example (id BIGINT PRIMARY KEY);\n\nCOMMIT;\n"),
    "sql_schema": ("db/schema.sql", "-- Schema source for a new local database. Review indexes and constraints.\nCREATE TABLE IF NOT EXISTS schema_version (\n  version INTEGER PRIMARY KEY,\n  applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP\n);\n"),
    "sql_transaction": ("db/transaction-example.sql", "BEGIN;\n-- Add validated statements here.\n-- ROLLBACK; -- use during review, then replace with COMMIT when ready\nROLLBACK;\n"),
    "prometheus_config": ("monitoring/prometheus.yml", "global:\n  scrape_interval: 30s\nscrape_configs:\n  - job_name: app\n    static_configs:\n      - targets: ['127.0.0.1:8080']\n"),
    "prometheus_alerts": ("monitoring/alerts.yml", "groups:\n  - name: app-availability\n    rules:\n      - alert: AppTargetDown\n        expr: up == 0\n        for: 5m\n        labels:\n          severity: warning\n        annotations:\n          summary: A monitored target is unavailable\n"),
    "grafana_dashboard": ("monitoring/dashboard.json", "{\n  \"title\": \"{project} overview\",\n  \"schemaVersion\": 39,\n  \"panels\": [],\n  \"annotations\": {\"list\": []}\n}\n"),
    "otel_collector": ("monitoring/otel-collector.yaml", "receivers:\n  otlp:\n    protocols:\n      grpc:\n      http:\nprocessors:\n  batch:\nexporters:\n  debug:\nservice:\n  pipelines:\n    traces:\n      receivers: [otlp]\n      processors: [batch]\n      exporters: [debug]\n"),
    "logrotate": ("packaging/logrotate.conf", "/var/log/{project}/*.log {\n  daily\n  rotate 14\n  compress\n  missingok\n  notifempty\n}\n"),
    "nginx_proxy": ("deploy/nginx.conf", "server {\n    listen 80;\n    server_name example.invalid;\n    location / {\n        proxy_pass http://127.0.0.1:8080;\n        proxy_set_header Host $host;\n        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n    }\n}\n"),
    "caddy_proxy": ("deploy/Caddyfile", "example.invalid {\n    reverse_proxy 127.0.0.1:8080\n}\n"),
    "nginx_static": ("deploy/nginx-static.conf", "server {\n    listen 8080;\n    root /usr/share/nginx/html;\n    index index.html;\n    location / { try_files $uri $uri/ /index.html; }\n    location ~ /\\. { deny all; }\n}\n"),
    "ansible_inventory": ("deploy/ansible/inventory.ini.example", "[app]\n# Add reviewed hostnames and connection settings.\n"),
    "ansible_playbook": ("deploy/ansible/site.yml", "- name: Configure application hosts\n  hosts: app\n  become: true\n  tasks:\n    - name: Ensure application directory exists\n      ansible.builtin.file:\n        path: /opt/{project}\n        state: directory\n        mode: '0750'\n"),
    "pulumi_project": ("Pulumi.yaml", "name: {slug}\nruntime: nodejs\ndescription: {summary}\n"),
    "helm_chart": ("deploy/helm/Chart.yaml", "apiVersion: v2\nname: {slug}\ndescription: {summary}\ntype: application\nversion: 0.1.0\nappVersion: \"0.1.0\"\n"),
    "helm_values": ("deploy/helm/values.yaml", "replicaCount: 2\nimage:\n  repository: replace-with-reviewed-image\n  tag: \"0.1.0\"\nservice:\n  type: ClusterIP\n  port: 80\nresources:\n  requests:\n    cpu: 100m\n    memory: 128Mi\n"),
    "helm_deployment": ("deploy/helm/templates/deployment.yaml", "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: app\nspec:\n  replicas: 2\n  selector:\n    matchLabels:\n      app: app\n  template:\n    metadata:\n      labels:\n        app: app\n    spec:\n      containers:\n        - name: app\n          image: \"{{ .Values.image.repository }}:{{ .Values.image.tag }}\"\n"),
    "github_security_scorecard": (".github/workflows/scorecard.yml", "name: Scorecard supply-chain security\non:\n  branch_protection_rule:\n  schedule:\n    - cron: '30 1 * * 6'\n  push:\n    branches: [main]\npermissions:\n  security-events: write\n  id-token: write\n  contents: read\njobs:\n  analysis:\n    uses: ossf/scorecard/.github/workflows/scorecard.yml@v5.0.0\n"),
    "github_secret_scan": (".github/workflows/secret-scan.yml", "name: Secret scan\non:\n  pull_request:\njobs:\n  scan:\n    runs-on: ubuntu-latest\n    permissions:\n      contents: read\n    steps:\n      - uses: actions/checkout@v4\n        with:\n          fetch-depth: 0\n      - uses: gitleaks/gitleaks-action@v2\n        env:\n          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}\n"),
    "github_docs_check": (".github/workflows/docs.yml", "name: Documentation checks\non:\n  pull_request:\njobs:\n  markdown:\n    runs-on: ubuntu-latest\n    permissions:\n      contents: read\n    steps:\n      - uses: actions/checkout@v4\n      - uses: DavidAnson/markdownlint-cli2-action@v19\n        with:\n          globs: '**/*.md'\n"),
    "github_yaml_check": (".github/workflows/yaml.yml", "name: YAML validation\non:\n  pull_request:\njobs:\n  validate:\n    runs-on: ubuntu-latest\n    permissions:\n      contents: read\n    steps:\n      - uses: actions/checkout@v4\n      - run: python -m pip install yamllint\n      - run: yamllint .\n"),
    "github_shell_check": (".github/workflows/shellcheck.yml", "name: Shell check\non:\n  pull_request:\njobs:\n  shellcheck:\n    runs-on: ubuntu-latest\n    permissions:\n      contents: read\n    steps:\n      - uses: actions/checkout@v4\n      - uses: ludeeus/action-shellcheck@master\n"),
    "github_spellcheck": (".github/workflows/spellcheck.yml", "name: Spell check\non:\n  pull_request:\njobs:\n  codespell:\n    runs-on: ubuntu-latest\n    permissions:\n      contents: read\n    steps:\n      - uses: actions/checkout@v4\n      - uses: codespell-project/actions-codespell@v2\n"),
    "github_pr_title": (".github/workflows/pr-title.yml", "name: Pull request title\non:\n  pull_request_target:\n    types: [opened, edited, synchronize]\njobs:\n  lint:\n    runs-on: ubuntu-latest\n    permissions:\n      pull-requests: read\n    steps:\n      - uses: amannn/action-semantic-pull-request@v5\n        env:\n          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}\n"),
    "github_size_labels": (".github/workflows/size-labels.yml", "name: Size labels\non:\n  pull_request:\njobs:\n  labels:\n    runs-on: ubuntu-latest\n    permissions:\n      pull-requests: write\n    steps:\n      - uses: cbrgm/pr-size-labeler@v1\n"),
    "github_workflow_permissions": (".github/workflows/permissions-check.yml", "name: Workflow security audit\non:\n  pull_request:\njobs:\n  audit:\n    runs-on: ubuntu-latest\n    permissions:\n      contents: read\n    steps:\n      - uses: actions/checkout@v4\n      - uses: zizmorcore/zizmor-action@v1\n"),
    "github_nightly": (".github/workflows/nightly.yml", "name: Nightly checks\non:\n  schedule:\n    - cron: '15 3 * * *'\n  workflow_dispatch:\njobs:\n  test:\n    runs-on: ubuntu-latest\n    permissions:\n      contents: read\n    steps:\n      - uses: actions/checkout@v4\n      - run: echo 'Replace with project-specific test commands.'\n"),
    "github_manual_release": (".github/workflows/release-manual.yml", "name: Manual release validation\non:\n  workflow_dispatch:\njobs:\n  validate:\n    runs-on: ubuntu-latest\n    permissions:\n      contents: read\n    steps:\n      - uses: actions/checkout@v4\n      - run: echo 'Add build and checksum verification commands.'\n"),
    "github_publish_package": (".github/workflows/publish-package.yml", "name: Publish package\non:\n  release:\n    types: [published]\npermissions:\n  contents: read\njobs:\n  publish:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - run: echo 'Add registry authentication through a protected environment.'\n"),
    "github_cache_cleanup": (".github/workflows/cache-cleanup.yml", "name: Cache cleanup\non:\n  workflow_dispatch:\njobs:\n  cleanup:\n    runs-on: ubuntu-latest\n    permissions:\n      actions: write\n    steps:\n      - uses: actions/checkout@v4\n      - run: echo 'Add scoped cleanup after reviewing retention requirements.'\n"),
    "gitmodules": (".gitmodules.example", "# Add submodules only after reviewing their repository and pinned commit.\n"),
    "gitmessage": (".gitmessage", "<type>(<scope>): <summary>\n\nExplain why the change is needed.\n"),
    "mailmap": (".mailmap.example", "# Canonical Name <canonical@example.invalid> Old Name <old@example.invalid>\n"),
    "gitignore_global": (".gitignore_global", ".DS_Store\nThumbs.db\n*.swp\n*~\n"),
    "gitattributes_merge": ("docs/snippets/gitattributes-merge.txt", "*.md merge=union\n*.lock -diff\n"),
    "security_advisories": ("docs/SECURITY-ADVISORIES.md", "# Security advisories\n\n| ID | Affected versions | Fixed version | Severity | Status |\n| --- | --- | --- | --- | --- |\n"),
    "security_key_rotation": ("docs/KEY-ROTATION.md", "# Key rotation procedure\n\n1. Identify key scope and dependents.\n2. Create a replacement using the approved secret manager.\n3. Deploy and verify the replacement.\n4. Revoke the old key.\n5. Record completion without recording secret values.\n"),
    "security_disclosure": (".well-known/security.txt", "Contact: mailto:security@example.invalid\nExpires: {year}-12-31T23:59:59Z\nPreferred-Languages: en\n"),
    "security_sbom_notes": ("docs/SBOM.md", "# Software bill of materials\n\nDocument the SBOM format, build process, artifact location, and verification procedure. Never include credentials.\n"),
    "security_third_party": ("docs/THIRD-PARTY.md", "# Third-party components\n\n| Component | Version | License | Source | Review date |\n| --- | --- | --- | --- | --- |\n"),
    "security_permissions": ("docs/PERMISSIONS.md", "# Permission inventory\n\n| Component | Permission | Purpose | Required? | Review date |\n| --- | --- | --- | --- | --- |\n"),
    "governance_maintainers": ("MAINTAINERS.md", "# Maintainers\n\n| Area | Maintainer | Backup |\n| --- | --- | --- |\n"),
    "governance_decisions": ("docs/decisions/README.md", "# Architecture decision records\n\nRecord significant decisions with context, options, consequences, and review date.\n"),
    "governance_change_policy": ("docs/CHANGE-POLICY.md", "# Change policy\n\nDocument review requirements, compatibility guarantees, release cadence, and deprecation notices.\n"),
    "governance_review_checklist": (".github/pull_request_template.md", "## Change summary\n\n## Risk and rollback\n\n## Validation\n\n- [ ] Scope is clear\n- [ ] Tests cover behavior\n- [ ] Secrets and personal data are excluded\n- [ ] Docs are updated\n"),
    "editor_markdown": (".markdownlint.json", "{\n  \"default\": true,\n  \"MD013\": false,\n  \"MD041\": false\n}\n"),
    "editor_yaml": (".yamllint", "extends: relaxed\nrules:\n  line-length:\n    max: 120\n  truthy:\n    allowed-values: ['true', 'false', 'on', 'off']\n"),
    "editor_sqlfluff": (".sqlfluff", "[sqlfluff]\ndialect = ansi\nmax_line_length = 100\n"),
    "editor_prettierignore": (".prettierignore", "node_modules\ndist\ncoverage\npackage-lock.json\n"),
    "editor_vscode_extensions": (".vscode/extensions.json", "{\n  \"recommendations\": [\"ms-python.python\", \"editorconfig.editorconfig\"],\n  \"unwantedRecommendations\": []\n}\n"),
})

def render_recipe(key, project="My Project", summary="Project description.", owner="Your Name", year="2026"):
    """Return a safe relative output path and UTF-8 bytes for one recipe."""
    if key not in RECIPES:
        raise OctoShipError("Choose a known project recipe.")
    path, template = RECIPES[key]
    values = {"project": project.strip() or "My Project", "summary": summary.strip() or "Project description.",
              "owner": owner.strip() or "Your Name", "year": str(year).strip() or "2026"}
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", values["project"]).strip(".-").lower() or "project"
    path = path.replace("{project}", safe_name)
    values["slug"] = safe_name
    # TOML descriptions must be quoted and escaped; ordinary recipes should
    # continue to receive the user's summary verbatim.
    values["summary_toml"] = json.dumps(values["summary"], ensure_ascii=False)
    for key, value in values.items():
        template = template.replace("{" + key + "}", value)
    return path, template.encode("utf-8")

def create_recipe(root, key, project="My Project", summary="Project description.", owner="Your Name", year="2026"):
    """Create a recipe atomically, refusing existing files and symlink traversal."""
    base = Path(root).expanduser().absolute()
    if not base.is_dir() or base.is_symlink():
        raise OctoShipError("Choose an existing project folder.")
    if any(parent.is_symlink() for parent in base.parents):
        raise OctoShipError("Choose a project folder without symbolic-link ancestors.")
    relative, data = render_recipe(key, project, summary, owner, year)
    target = base / relative
    current = base
    for part in Path(relative).parts[:-1]:
        current = current / part
        if current.exists() and (current.is_symlink() or not current.is_dir()):
            raise OctoShipError("Recipe path contains a non-directory or symbolic link.")
    current.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        raise OctoShipError("The target already exists. Review it before choosing another project folder.")
    fd, temp_name = tempfile.mkstemp(prefix=".octoship-recipe-", dir=current)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temp_name, target, follow_symlinks=False)
    except FileExistsError as exc:
        raise OctoShipError("The target already exists.") from exc
    finally:
        try: os.unlink(temp_name)
        except FileNotFoundError: pass
    return target
