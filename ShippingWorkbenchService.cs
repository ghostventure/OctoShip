using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Security.Cryptography;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;

namespace FileToGitHub;

public sealed record ProjectRecipe(int Version, string Repository, string BaseBranch, string DestinationFolder, string[] Exclusions, string ReleaseName);
public sealed record ReviewedShipFile(string Source, string Destination, string BlobSha, long Size, DateTime Modified, string Status);
public sealed record ShipReview(string Repository, string Branch, string Commit, IReadOnlyList<ReviewedShipFile> Files);
public sealed record ReleaseRecovery(long Id, string Tag, string Url, IReadOnlyList<string> Assets);

/// <summary>Shipping checks keep reviewed bytes and remote commits fixed. No automatic remote mutations.</summary>
public sealed class ShippingWorkbenchService
{
    private readonly HttpClient _http;
    public ShippingWorkbenchService(HttpClient http) => _http = http;
    public static string Root(string repository)
    {
        if (repository == null || !Regex.IsMatch(repository, @"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$") || repository.Split('/').Any(x => x is "." or "..")) throw new ArgumentException("Use owner/repository.");
        return "https://api.github.com/repos/" + repository;
    }
    private async Task<JsonDocument> Get(string url, string token, CancellationToken ct)
    {
        using var request = new HttpRequestMessage(HttpMethod.Get, url);
        request.Headers.UserAgent.ParseAdd("OctoShip/1.5");
        request.Headers.Accept.ParseAdd("application/vnd.github+json");
        if (!string.IsNullOrWhiteSpace(token)) request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
        using var response = await _http.SendAsync(request, ct);
        if (!response.IsSuccessStatusCode) throw new HttpRequestException(ExplainStatus((int)response.StatusCode, response.Headers.Contains("X-GitHub-SSO"), response.Headers.TryGetValues("X-RateLimit-Remaining", out var remaining) && remaining.Contains("0")), null, response.StatusCode);
        return JsonDocument.Parse(await response.Content.ReadAsStringAsync(ct));
    }
    public static string ExplainStatus(int status, bool sso = false, bool rateLimited = false) => $"GitHub HTTP {status}. " + (status switch
    {
        401 => "Authentication was rejected. Sign in again or replace the expired/revoked token.",
        403 when rateLimited => "API rate limit exhausted. Wait for the reset before retrying.",
        403 when sso => "Organization SSO authorization may be required. Authorize this token in GitHub Settings > Developer settings.",
        403 => "Access was refused. Check token repository permissions, organization policy, and account access; this response alone does not identify the cause.",
        404 => "Resource unavailable or hidden from this account. Check repository spelling, selected account, token repository selection and whether the feature is enabled.",
        422 => "GitHub rejected the requested data. Check branch rules, names and existing resources before retrying.",
        _ => "Retry after checking GitHub status and network connectivity."
    });
    public async Task<string> DiagnosticsAsync(string repository, string token, CancellationToken ct)
    {
        using var user = await Get("https://api.github.com/user", token, ct);
        var identity = "Authenticated account: " + user.RootElement.GetProperty("login").GetString();
        try
        {
            using var repo = await Get(Root(repository), token, ct);
            return identity + "\nRepository visibility: " + repo.RootElement.GetProperty("visibility").GetString() + "\nPermissions: " + (repo.RootElement.TryGetProperty("permissions", out var p) ? p.ToString() : "Not supplied; write access not confirmed.") + "\nToken settings: https://github.com/settings/tokens";
        }
        catch (HttpRequestException ex) { return identity + "\n" + ex.Message + "\nToken settings: https://github.com/settings/tokens"; }
    }
    public async Task<string> RulesAsync(string repository, string branch, string token, CancellationToken ct)
    {
        var output = new List<string>();
        try
        {
            for (int page = 1; page <= 100; page++)
            {
                using var rules = await Get(Root(repository) + "/rules/branches/" + Uri.EscapeDataString(branch) + $"?per_page=100&page={page}", token, ct);
                foreach (var rule in rules.RootElement.EnumerateArray())
                {
                    var type = rule.GetProperty("type").GetString();
                    var explanation = type switch { "pull_request" => "A pull request and configured reviews are required.", "required_signatures" => "Signed commits required; OctoShip API commits may be rejected.", "required_status_checks" => "Required checks must pass before this branch can advance.", "commit_message_pattern" => "Commit messages must match the configured pattern.", _ => "GitHub enforces this rule on matching updates." };
                    output.Add(type + ": " + explanation + (rule.TryGetProperty("parameters", out var parameters) ? "\n" + parameters : ""));
                }
                if (rules.RootElement.GetArrayLength() < 100) break;
                if (page == 100) output.Add("Rule listing limit reached; inspect GitHub for additional rules.");
            }
            if (output.Count == 0) output.Add("No active ruleset rules returned.");
        }
        catch (HttpRequestException ex) { output.Add("Ruleset check unavailable: " + ex.Message); }
        try
        {
            using var legacy = await Get(Root(repository) + "/branches/" + Uri.EscapeDataString(branch) + "/protection", token, ct);
            output.Add("Classic branch protection:\n" + legacy.RootElement.ToString());
        }
        catch (HttpRequestException ex) { output.Add("Classic protection not confirmed: " + ex.Message); }
        return string.Join("\n\n", output) + "\nGitHub remains authoritative; bypass rights and organization policies may affect the result.";
    }
    public async Task<ShipReview> ReviewAsync(string repository, string branch, string local, string destination, string[] exclusions, string token, CancellationToken ct)
    {
        ValidateRelative(destination, true);
        var comparison = await new RepositoryWorkflowService(_http).CompareAsync(repository, branch, destination, local, token, ct);
        using var remoteTree = await Get(Root(repository) + "/git/trees/" + comparison.Commit + "?recursive=1", token, ct);
        if (!remoteTree.RootElement.TryGetProperty("truncated", out var treeTruncated) || treeTruncated.GetBoolean()) throw new InvalidOperationException("Incomplete tree; review stopped.");
        var remoteHashes = remoteTree.RootElement.GetProperty("tree").EnumerateArray().Where(x => x.GetProperty("type").GetString() == "blob").ToDictionary(x => x.GetProperty("path").GetString()!, x => x.GetProperty("sha").GetString());
        var ignore = new FileSafetyRules(exclusions.Concat(new[] { ".git", ".git/*", "bin/*", "obj/*", "node_modules/*", "*/bin/*", "*/obj/*", "*/node_modules/*" }));
        foreach (var unsupported in comparison.Files.Where(x => x.Status.StartsWith("Unsupported", StringComparison.Ordinal) && ignore.Match(x.Path).Count == 0))
            if (File.Exists(Path.Combine(local, unsupported.Path.Replace('/', Path.DirectorySeparatorChar)))) throw new InvalidOperationException("Cannot replace a remote link or submodule: " + unsupported.Path + ". Exclude it or choose a different destination.");
        var safety = new FileSafetyRules();
        var files = new List<ReviewedShipFile>();
        foreach (var row in comparison.Files.Where(x => x.Status is "Local only" or "Changed content" or "Same content"))
        {
            if (ignore.Match(row.Path).Count != 0) continue;
            var path = Path.Combine(local, row.Path.Replace('/', Path.DirectorySeparatorChar));
            var info = new FileInfo(path);
            if (info.Length > 50L * 1024 * 1024) throw new InvalidOperationException("File exceeds 50 MiB: " + row.Path);
            if (safety.Match(row.Path).Count != 0) throw new InvalidOperationException("Sensitive filename requires exclusion before shipping: " + row.Path);
            var scan = await ContentSecretScanner.ScanAsync(path, ct);
            if (scan.HasFindings) throw new InvalidOperationException("Possible secret in " + row.Path + ": " + scan.Summary);
            var hash = await RepositoryWorkflowService.HashBlobAsync(path, ct);
            var remotePath = string.IsNullOrEmpty(destination) ? row.Path : destination + "/" + row.Path;
            var status = remoteHashes.TryGetValue(remotePath, out var remoteHash) ? (remoteHash == hash ? "Same content" : "Changed content") : "Local only";
            files.Add(new(path, remotePath, hash, info.Length, info.LastWriteTimeUtc, status + (!scan.Complete ? " (content scan incomplete)" : "")));
        }
        if (files.Count(x => !x.Status.StartsWith("Same content", StringComparison.Ordinal)) > 100) throw new InvalidOperationException("Select at most 100 changed files per shipment using exclusions or a smaller folder.");
        return new(repository, branch, comparison.Commit, files);
    }
    public async Task<string> ShipAsync(ShipReview review, string newBranch, string title, string token, CancellationToken ct)
    {
        if (string.IsNullOrWhiteSpace(title)) throw new ArgumentException("Enter a commit and pull-request title.");
        var selected = review.Files.Where(x => !x.Status.StartsWith("Same content", StringComparison.Ordinal)).ToArray();
        if (selected.Length == 0) return "No changed files to ship; no branch or pull request created.";
        foreach (var file in review.Files)
            if (await RepositoryWorkflowService.HashBlobAsync(file.Source, ct) != file.BlobSha) throw new InvalidOperationException("Local content changed after review: " + file.Destination);
        var parts = review.Repository.Split('/');
        var atomic = new GitHubAtomicBatchService(_http);
        if (await atomic.GetHeadAsync(parts[0], parts[1], review.Branch, token, ct) != review.Commit) throw new InvalidOperationException("Base branch changed. Review again.");
        var workflow = new RepositoryWorkflowService(_http);
        await workflow.CreateBranchAsync(review.Repository, review.Branch, newBranch, token, ct);
        // Creation re-resolves its source; refuse uploading if that source advanced during the request.
        if (await atomic.GetHeadAsync(parts[0], parts[1], newBranch, token, ct) != review.Commit) throw new InvalidOperationException("Source changed while creating branch. Review again; the empty branch remains on GitHub.");
        try
        {
            var results = await atomic.UploadAsync(parts[0], parts[1], newBranch, token, selected.Select(x => new BatchUploadFile(x.Source, x.Destination, title, x.Size, x.Modified)).ToArray(), title, review.Commit, ct: ct,
                validateContent: (path, bytes, _) =>
                {
                    var expected = selected.Single(x => x.Source == path);
                    if (BlobHash(bytes) != expected.BlobSha) throw new InvalidOperationException("File changed after review: " + expected.Destination);
                    var scan = ContentSecretScanner.ScanBytes(bytes);
                    if (scan.HasFindings) throw new InvalidOperationException("Possible secret in reviewed content: " + expected.Destination + "\n" + scan.Summary);
                    return Task.CompletedTask;
                });
            var commit = new Uri(results[0].Url!).Segments[4].Trim('/');
            var verified = await VerifyAsync(review, commit, token, ct);
            var pr = await workflow.CreatePullRequestAsync(review.Repository, newBranch, review.Branch, title, "Shipped with OctoShip.\n\n" + verified, true, token, ct);
            return "Draft pull request: " + pr + "\nCommit: " + commit + "\n" + verified;
        }
        catch (Exception ex) { throw new InvalidOperationException("Shipment stopped; inspect branch " + newBranch + " before retrying. It may contain a completed commit. " + ex.Message, ex); }
    }
    public static string BlobHash(byte[] bytes)
    {
        using var hash = IncrementalHash.CreateHash(HashAlgorithmName.SHA1);
        hash.AppendData(System.Text.Encoding.ASCII.GetBytes("blob " + bytes.Length.ToString(System.Globalization.CultureInfo.InvariantCulture) + "\0")); hash.AppendData(bytes);
        return Convert.ToHexString(hash.GetHashAndReset()).ToLowerInvariant();
    }
    public async Task<string> VerifyAsync(ShipReview review, string commit, string token, CancellationToken ct)
    {
        try
        {
            using var tree = await Get(Root(review.Repository) + "/git/trees/" + Uri.EscapeDataString(commit) + "?recursive=1", token, ct);
            if (!tree.RootElement.TryGetProperty("truncated", out var truncated) || truncated.GetBoolean()) return "Could not verify: incomplete GitHub tree.";
            var entries = tree.RootElement.GetProperty("tree").EnumerateArray().Where(x => x.GetProperty("type").GetString() == "blob").ToDictionary(x => x.GetProperty("path").GetString()!, x => x.GetProperty("sha").GetString());
            var mismatches = review.Files.Where(x => !entries.TryGetValue(x.Destination, out var sha) || sha != x.BlobSha).Select(x => x.Destination).ToArray();
            return mismatches.Length == 0 ? $"Verified: all {review.Files.Count} reviewed file contents match commit {commit}." : "Mismatch: " + string.Join(", ", mismatches);
        }
        catch (HttpRequestException ex) { return "Could not verify: " + ex.Message; }
    }
    public async Task<string> PagesAsync(string repository, string token, CancellationToken ct)
    {
        var sections = new List<string>();
        foreach (var endpoint in new[] { "pages", "pages/builds/latest", "pages/health" })
        {
            try { using var result = await Get(Root(repository) + "/" + endpoint, token, ct); sections.Add(endpoint + ":\n" + result.RootElement); }
            catch (HttpRequestException ex) { sections.Add(endpoint + ": unavailable. " + ex.Message); }
        }
        return string.Join("\n\n", sections);
    }
    public async Task<IReadOnlyList<ReleaseRecovery>> DraftsAsync(string repository, string token, CancellationToken ct)
    {
        var list = new List<ReleaseRecovery>();
        for (int page = 1; page <= 100; page++)
        {
            using var releases = await Get(Root(repository) + $"/releases?per_page=100&page={page}", token, ct);
            foreach (var release in releases.RootElement.EnumerateArray().Where(x => x.GetProperty("draft").GetBoolean()))
                list.Add(new(release.GetProperty("id").GetInt64(), release.GetProperty("tag_name").GetString()!, release.GetProperty("html_url").GetString()!, release.GetProperty("assets").EnumerateArray().Select(x => x.GetProperty("name").GetString()!).ToArray()));
            if (releases.RootElement.GetArrayLength() < 100) return list;
        }
        throw new InvalidOperationException("Release listing is incomplete. Narrow repository release history before recovery.");
    }
    public async Task<string> RecoverAsync(string repository, long id, string[] paths, string token, CancellationToken ct)
    {
        var parts = repository.Split('/');
        using var release = await Get(Root(repository) + "/releases/" + id, token, ct);
        if (!release.RootElement.GetProperty("draft").GetBoolean()) throw new InvalidOperationException("Recovery only accepts an existing draft release.");
        if (paths.Select(Path.GetFileName).Distinct(StringComparer.OrdinalIgnoreCase).Count() != paths.Length) throw new ArgumentException("Selected filenames must be unique.");
        var assets = release.RootElement.GetProperty("assets").EnumerateArray().ToDictionary(x => x.GetProperty("name").GetString()!, x => x.Clone(), StringComparer.OrdinalIgnoreCase);
        var report = new List<string>();
        foreach (var path in paths)
        {
            var name = Path.GetFileName(path);
            if (assets.TryGetValue(name, out var asset))
            {
                var check = await TestAssetAsync(asset, path, token, ct);
                report.Add(name + ": " + check + " Existing asset preserved.");
            }
            else
            {
                await new GitHubReleaseService(_http).UploadAssetAsync(parts[0], parts[1], token, id, path, ct);
                report.Add(name + ": uploaded missing asset to existing draft.");
            }
        }
        return string.Join("\n", report) + "\nDraft remains unpublished. No new draft was created.";
    }
    public async Task<string> TestReleaseAsync(string repository, string tag, string[] localAssets, string token, CancellationToken ct)
    {
        using var release = await Get(Root(repository) + "/releases/tags/" + Uri.EscapeDataString(tag), token, ct);
        var report = new List<string>();
        foreach (var asset in release.RootElement.GetProperty("assets").EnumerateArray())
        {
            var name = asset.GetProperty("name").GetString()!;
            var local = localAssets.FirstOrDefault(x => Path.GetFileName(x) == name);
            try
            {
                var verification = await TestAssetAsync(asset, local, token, ct);
                var browserUrl = new Uri(asset.GetProperty("browser_download_url").GetString()!);
                if (browserUrl.Scheme != "https" || browserUrl.Host != "github.com") throw new InvalidOperationException("Unexpected release download host.");
                using var publicRequest = new HttpRequestMessage(HttpMethod.Get, browserUrl);
                publicRequest.Headers.UserAgent.ParseAdd("OctoShip/1.5");
                using var publicResponse = await _http.SendAsync(publicRequest, HttpCompletionOption.ResponseHeadersRead, ct);
                report.Add(name + ": " + verification + $"\nBrowser download link (anonymous): HTTP {(int)publicResponse.StatusCode}. Private/draft assets may require GitHub sign-in.");
            }
            catch (HttpRequestException ex) { report.Add(name + ": Could not verify. " + ex.Message); }
        }
        foreach (var local in localAssets.Where(x => !release.RootElement.GetProperty("assets").EnumerateArray().Any(a => a.GetProperty("name").GetString() == Path.GetFileName(x)))) report.Add(Path.GetFileName(local) + ": missing release asset.");
        return report.Count == 0 ? "Release contains no assets to test." : string.Join("\n", report);
    }
    private async Task<string> TestAssetAsync(JsonElement asset, string? local, string token, CancellationToken ct)
    {
        var url = asset.GetProperty("url").GetString()!;
        var uri = new Uri(url);
        if (uri.Scheme != "https" || uri.Host != "api.github.com") throw new InvalidOperationException("Unexpected asset API host.");
        using var request = new HttpRequestMessage(HttpMethod.Get, uri);
        request.Headers.UserAgent.ParseAdd("OctoShip/1.5"); request.Headers.Accept.ParseAdd("application/octet-stream");
        if (!string.IsNullOrWhiteSpace(token)) request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
        using var response = await _http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, ct);
        response.EnsureSuccessStatusCode();
        await using var stream = await response.Content.ReadAsStreamAsync(ct);
        using var hash = IncrementalHash.CreateHash(HashAlgorithmName.SHA256); var buffer = new byte[81920]; long count = 0; int read;
        while ((read = await stream.ReadAsync(buffer.AsMemory(), ct)) != 0) { count += read; if (count > 2L * 1024 * 1024 * 1024) throw new InvalidOperationException("Download exceeds 2 GiB verification limit."); hash.AppendData(buffer, 0, read); }
        var digest = Convert.ToHexString(hash.GetHashAndReset()).ToLowerInvariant();
        if (count != asset.GetProperty("size").GetInt64()) return "Mismatch: downloaded size differs from release metadata.";
        string? expected = asset.TryGetProperty("digest", out var d) && d.ValueKind == JsonValueKind.String && d.GetString()!.StartsWith("sha256:", StringComparison.Ordinal) ? d.GetString()![7..] : null;
        if (local != null) { await using var file = File.OpenRead(local); using var sha = SHA256.Create(); expected = Convert.ToHexString(await sha.ComputeHashAsync(file, ct)).ToLowerInvariant(); }
        return (expected == null ? "Downloaded; no reference hash supplied, content not verified." : string.Equals(digest, expected, StringComparison.OrdinalIgnoreCase) ? "Verified download." : "Mismatch: SHA-256 differs.") + $" {count} bytes; SHA-256 {digest}";
    }
    public static void ValidateRecipe(ProjectRecipe recipe)
    {
        if (recipe.Version != 1) throw new ArgumentException("Unsupported recipe version.");
        Root(recipe.Repository); ValidateRelative(recipe.DestinationFolder, true);
        if (string.IsNullOrWhiteSpace(recipe.BaseBranch) || recipe.BaseBranch.Any(char.IsControl)) throw new ArgumentException("Recipe needs a base branch.");
        if (recipe.Exclusions == null || recipe.Exclusions.Length > 100) throw new ArgumentException("Recipe supports up to 100 exclusions.");
        foreach (var pattern in recipe.Exclusions) ValidateRelative(pattern, false);
        if (string.IsNullOrWhiteSpace(recipe.ReleaseName) || recipe.ReleaseName.IndexOfAny(new[] { '/', '\\', ':' }) >= 0 || recipe.ReleaseName.Any(char.IsControl)) throw new ArgumentException("Release name must be a portable name, such as v{version}.");
        if (ContentSecretScanner.ScanText(JsonSerializer.Serialize(recipe)).HasFindings) throw new ArgumentException("Recipe appears to contain a credential.");
    }
    public static void ValidateRelative(string path, bool empty)
    {
        if (path == null || (!empty && path.Length == 0) || path.Contains(':') || path.Contains('\\') || path.Any(char.IsControl) || path.StartsWith('/') || path.Split('/').Any(x => x is "." or ".." || (x.Length == 0 && path.Length != 0))) throw new ArgumentException("Use portable relative paths with forward slashes.");
    }
    public static async Task<string> LocalGitAsync(string folder, CancellationToken ct)
    {
        var status = await ProcessAsync("git", new[] { "-C", folder, "status", "--short", "--branch" }, ct);
        var remotes = await ProcessAsync("git", new[] { "-C", folder, "remote", "-v" }, ct);
        // Remote URLs sometimes contain embedded credentials; remove them before displaying.
        return status + "\n" + Regex.Replace(remotes, @"(https?://)[^\s/@]+@", "$1[redacted]@", RegexOptions.IgnoreCase);
    }
    public static Task<string> AttestationAsync(string repository, string artifact, CancellationToken ct)
    {
        Root(repository); if (!File.Exists(artifact)) throw new ArgumentException("Choose an existing artifact.");
        return ProcessAsync("gh", new[] { "attestation", "verify", Path.GetFullPath(artifact), "--repo", repository, "--format", "json" }, ct);
    }
    private static async Task<string> ProcessAsync(string executable, string[] arguments, CancellationToken ct)
    {
        var start = TrustedProcess.Create(executable);
        start.RedirectStandardOutput = start.RedirectStandardError = true;
        if (executable == "git")
            foreach (var argument in new[] { "--no-optional-locks", "-c", "core.fsmonitor=false", "-c", "core.untrackedCache=false" }) start.ArgumentList.Add(argument);
        foreach (var argument in arguments) start.ArgumentList.Add(argument);
        start.Environment["GH_PROMPT_DISABLED"] = "1";
        try
        {
            using var process = TrustedProcess.Start(start);
            var stdout = process.StandardOutput.ReadToEndAsync(); var stderr = process.StandardError.ReadToEndAsync();
            using var timeout = CancellationTokenSource.CreateLinkedTokenSource(ct); timeout.CancelAfter(TimeSpan.FromMinutes(2));
            try { await process.WaitForExitAsync(timeout.Token); }
            catch (OperationCanceledException) { try { process.Kill(true); } catch (InvalidOperationException) { } throw; }
            var output = await stdout; var error = await stderr;
            AccountSessionLock.ThrowIfLocked();
            return SecurityBoundaries.Redact((process.ExitCode == 0 ? "Succeeded" : "Failed / could not verify") + $" ({executable}, exit {process.ExitCode})\n" + output + "\n" + error);
        }
        catch (System.ComponentModel.Win32Exception) { return executable + " unavailable. Install it and authenticate if needed, then retry. Verification has not run."; }
    }
}
