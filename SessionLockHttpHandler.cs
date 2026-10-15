using System;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

namespace FileToGitHub;

/// <summary>Stops new HTTP operations while the account workspace is locked.</summary>
public sealed class SessionLockHttpHandler : DelegatingHandler
{
    private readonly Func<string?>? _token;
    private readonly Func<string?>? _account;
    private readonly string? _bindings;
    public SessionLockHttpHandler(Func<string?>? token = null, Func<string?>? account = null,
        HttpMessageHandler? transport = null, string? bindingsPath = null)
        : base(transport ?? new HttpClientHandler()) { _token = token; _account = account; _bindings = bindingsPath; }

    private void Check(string? token)
    {
        AccountSessionLock.ThrowIfLocked();
        if (token != null && _token != null && !string.Equals(token, _token(), StringComparison.Ordinal))
            throw new InvalidOperationException("Account session changed. Close this workflow and review again using the selected account.");
    }
    protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken ct)
    {
        var token = request.Headers.Authorization?.Parameter;
        Check(token);
        var uri = request.RequestUri ?? throw new InvalidOperationException("Missing request destination.");
        if (token != null && (uri.Scheme != "https" || uri.UserInfo.Length != 0 || uri.Port != 443 || uri.Host is not ("api.github.com" or "uploads.github.com")))
            throw new InvalidOperationException("Credentials may only be sent to the supported GitHub API hosts.");
        if (request.Method != HttpMethod.Get && request.Method != HttpMethod.Head)
        {
            var parts = uri.AbsolutePath.Split('/', StringSplitOptions.RemoveEmptyEntries);
            if (token == null || _account == null || string.IsNullOrWhiteSpace(_account()) || parts.Length < 3 || parts[0] != "repos")
                throw new InvalidOperationException("A connected, verified account and repository are required for publication.");
            var repository = Uri.UnescapeDataString(parts[1]) + "/" + Uri.UnescapeDataString(parts[2]);
            RepositoryWorkflowService.ValidateRepository(repository);
            using var identity = await ReadAsync("user", token, ct);
            var login = identity.RootElement.GetProperty("login").GetString() ?? "";
            if (!string.Equals(login, _account(), StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("The credential identity differs from the selected account. Reconnect before publishing.");
            using var repo = await ReadAsync("repos/" + repository, token, ct);
            var visibility = repo.RootElement.TryGetProperty("visibility", out var value) ? value.GetString() : repo.RootElement.GetProperty("private").GetBoolean() ? "private" : "public";
            PublicationBindings.Validate(repository, login, visibility ?? throw new InvalidOperationException("Repository visibility is unknown."), _bindings);
            Check(token);
        }
        var response = await base.SendAsync(request, ct);
        try { Check(token); }
        catch { response.Dispose(); throw; }
        // Never return server-controlled error bodies that could echo credentials.
        if (!response.IsSuccessStatusCode && token != null)
        {
            response.Content.Dispose();
            response.Content = new StringContent("{\"message\":\"Request rejected. Check access and repository rules.\"}");
        }
        return response;
    }
    private async Task<JsonDocument> ReadAsync(string route, string token, CancellationToken ct)
    {
        Check(token);
        using var request = new HttpRequestMessage(HttpMethod.Get, "https://api.github.com/" + route);
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
        request.Headers.UserAgent.ParseAdd("OctoShip/1.6.1");
        using var response = await base.SendAsync(request, ct);
        Check(token);
        if (!response.IsSuccessStatusCode) throw new InvalidOperationException("Publication identity/visibility could not be verified. No publication request was sent.");
        return JsonDocument.Parse(await response.Content.ReadAsStringAsync(ct));
    }
}
