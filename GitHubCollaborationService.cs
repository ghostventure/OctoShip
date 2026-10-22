using System;
using System.Collections.Generic;
using System.Linq;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

namespace FileToGitHub;

/// <summary>Read-only GitHub collaboration views used by the repository hub.</summary>
public sealed class GitHubCollaborationService
{
    private readonly HttpClient _http;
    public GitHubCollaborationService(HttpClient http) => _http = http;

    public sealed record Repo(string Name, string DefaultBranch, string Visibility, bool Archived, bool CanPush, string Url);
    public sealed record Branch(string Name, string Sha, bool Protected);
    public sealed record PullRequest(int Number, string Title, string State, bool Draft, string Head, string Base, string HeadSha, string Updated, string Url, string MergeableState);
    public sealed record PullRequestReadiness(int Approvals, int ChangesRequested, int TotalChecks, int FailedChecks, int PendingChecks);
    public sealed record Release(int Id, string Tag, string Name, bool Draft, bool Prerelease, string Url, string Body, int AssetCount, string Target);
    public sealed record WorkflowRun(long Id, string Name, string Status, string Conclusion, string Branch, string Event, string Created, string Url, int RunNumber);
    public sealed record Artifact(string Name, long Size, string Expires, string Url);
    public sealed record Compare(string Base, string Head, int Ahead, int Behind, IReadOnlyList<string> Files);

    public async Task<IReadOnlyList<Repo>> RepositoriesAsync(string token, CancellationToken ct) =>
        await ArrayAsync("/user/repos?sort=updated&per_page=100", token, x => new Repo(S(x,"full_name"), S(x,"default_branch"), x.TryGetProperty("visibility",out var v)?v.GetString()??"unknown": "unknown", B(x,"archived"), B(x,"permissions", "push"), S(x,"html_url")), ct);

    public async Task<IReadOnlyList<Branch>> BranchesAsync(string repo, string token, CancellationToken ct) =>
        await ArrayAsync($"/repos/{RepoPath(repo)}/branches?per_page=100", token, x => new Branch(S(x,"name"), S(x,"commit","sha"), B(x,"protected")), ct);

    public async Task<Compare> CompareAsync(string repo, string baseBranch, string head, string token, CancellationToken ct)
    {
        using var doc = await GetAsync($"/repos/{RepoPath(repo)}/compare/{Uri.EscapeDataString(baseBranch)}...{Uri.EscapeDataString(head)}", token, ct);
        var root = doc.RootElement;
        var files = root.TryGetProperty("files", out var arr) && arr.ValueKind == JsonValueKind.Array ? arr.EnumerateArray().Select(x => $"{S(x,"status")}: {S(x,"filename")}").ToArray() : Array.Empty<string>();
        return new(baseBranch, head, I(root,"ahead_by"), I(root,"behind_by"), files);
    }

    public async Task<IReadOnlyList<PullRequest>> PullRequestsAsync(string repo, string token, CancellationToken ct) =>
        await ArrayAsync($"/repos/{RepoPath(repo)}/pulls?state=open&sort=updated&direction=desc&per_page=100", token, x => new PullRequest(I(x,"number"),S(x,"title"),S(x,"state"),B(x,"draft"),S(x,"head","ref"),S(x,"base","ref"),S(x,"head","sha"),S(x,"updated_at"),S(x,"html_url"),S(x,"mergeable_state")), ct);

    public async Task<PullRequestReadiness> PullRequestReadinessAsync(string repo, PullRequest pr, string token, CancellationToken ct)
    {
        using var reviews=await GetAsync($"/repos/{RepoPath(repo)}/pulls/{pr.Number}/reviews?per_page=100",token,ct);
        var latest=new Dictionary<string,string>(StringComparer.OrdinalIgnoreCase);
        if(reviews.RootElement.ValueKind==JsonValueKind.Array) foreach(var review in reviews.RootElement.EnumerateArray()) { var user=S(review,"user","login"); if(user.Length>0) latest[user]=S(review,"state"); }
        var approvals=latest.Values.Count(x=>x=="APPROVED"); var changes=latest.Values.Count(x=>x=="CHANGES_REQUESTED");
        using var checks=await GetAsync($"/repos/{RepoPath(repo)}/commits/{Uri.EscapeDataString(pr.HeadSha)}/check-runs?per_page=100",token,ct);
        var total=0;var failed=0;var pending=0;
        if(checks.RootElement.TryGetProperty("check_runs",out var runs)&&runs.ValueKind==JsonValueKind.Array) foreach(var check in runs.EnumerateArray()) { total++; var status=S(check,"status"); var conclusion=S(check,"conclusion"); if(status!="completed") pending++; else if(conclusion is "failure" or "timed_out" or "cancelled" or "action_required" or "startup_failure") failed++; }
        return new(approvals,changes,total,failed,pending);
    }

    public async Task<IReadOnlyList<Release>> ReleasesAsync(string repo, string token, CancellationToken ct) =>
        await ArrayAsync($"/repos/{RepoPath(repo)}/releases?per_page=100", token, x => new Release((int)L(x,"id"),S(x,"tag_name"),S(x,"name"),B(x,"draft"),B(x,"prerelease"),S(x,"html_url"),S(x,"body"),x.TryGetProperty("assets",out var a)&&a.ValueKind==JsonValueKind.Array?a.GetArrayLength():0,S(x,"target_commitish")), ct);

    public async Task<IReadOnlyList<WorkflowRun>> RunsAsync(string repo, string token, CancellationToken ct)
    {
        using var doc = await GetAsync($"/repos/{RepoPath(repo)}/actions/runs?per_page=50", token, ct);
        if (!doc.RootElement.TryGetProperty("workflow_runs", out var arr) || arr.ValueKind != JsonValueKind.Array) return Array.Empty<WorkflowRun>();
        return arr.EnumerateArray().Select(x => new WorkflowRun(L(x,"id"),S(x,"name"),S(x,"status"),S(x,"conclusion"),S(x,"head_branch"),S(x,"event"),S(x,"created_at"),S(x,"html_url"),I(x,"run_number"))).ToArray();
    }

    public async Task<IReadOnlyList<Artifact>> ArtifactsAsync(string repo, long runId, string token, CancellationToken ct)
    {
        using var doc = await GetAsync($"/repos/{RepoPath(repo)}/actions/runs/{runId}/artifacts?per_page=100", token, ct);
        if (!doc.RootElement.TryGetProperty("artifacts", out var arr) || arr.ValueKind != JsonValueKind.Array) return Array.Empty<Artifact>();
        return arr.EnumerateArray().Select(x => new Artifact(S(x,"name"),L(x,"size_in_bytes"),S(x,"expires_at"),S(x,"archive_download_url"))).ToArray();
    }

    public async Task<string> IdentityAsync(string token, CancellationToken ct)
    {
        using var doc = await GetAsync("/user", token, ct);
        return $"{S(doc.RootElement,"login")} ({S(doc.RootElement,"type")})";
    }

    private async Task<IReadOnlyList<T>> ArrayAsync<T>(string route, string token, Func<JsonElement,T> read, CancellationToken ct)
    {
        using var doc = await GetAsync(route, token, ct);
        if(doc.RootElement.ValueKind != JsonValueKind.Array) throw new InvalidOperationException("GitHub returned an unexpected list response.");
        return doc.RootElement.EnumerateArray().Select(read).ToArray();
    }
    private async Task<JsonDocument> GetAsync(string route, string token, CancellationToken ct)
    {
        if(string.IsNullOrWhiteSpace(token)||token.Any(char.IsControl)) throw new InvalidOperationException("Sign in to GitHub before loading collaboration details.");
        using var req=new HttpRequestMessage(HttpMethod.Get,"https://api.github.com"+route);
        req.Headers.Authorization=new AuthenticationHeaderValue("Bearer",token); req.Headers.UserAgent.ParseAdd("OctoShip-for-GitHub/1.6"); req.Headers.Accept.ParseAdd("application/vnd.github+json"); req.Headers.Add("X-GitHub-Api-Version","2022-11-28");
        using var res=await _http.SendAsync(req,ct);
        if(!res.IsSuccessStatusCode) throw new HttpRequestException($"GitHub returned HTTP {(int)res.StatusCode}. Check sign-in, repository access, and API quota.",null,res.StatusCode);
        return await JsonDocument.ParseAsync(await res.Content.ReadAsStreamAsync(ct),cancellationToken:ct);
    }
    private static string RepoPath(string repo) { RepositoryWorkflowService.ValidateRepository(repo); return string.Join("/",repo.Split('/').Select(Uri.EscapeDataString)); }
    private static string S(JsonElement x,string p) => x.TryGetProperty(p,out var v)&&v.ValueKind==JsonValueKind.String?v.GetString()??"":"";
    private static string S(JsonElement x,string p,string child) => x.TryGetProperty(p,out var v)&&v.TryGetProperty(child,out var c)&&c.ValueKind==JsonValueKind.String?c.GetString()??"":"";
    private static bool B(JsonElement x,string p) => x.TryGetProperty(p,out var v)&&v.ValueKind==JsonValueKind.True;
    private static bool B(JsonElement x,string p,string child) => x.TryGetProperty(p,out var v)&&v.TryGetProperty(child,out var c)&&c.ValueKind==JsonValueKind.True;
    private static int I(JsonElement x,string p) => x.TryGetProperty(p,out var v)&&v.TryGetInt32(out var n)?n:0;
    private static long L(JsonElement x,string p) => x.TryGetProperty(p,out var v)&&v.TryGetInt64(out var n)?n:0;
}
