using System.Net.Http;
using System.Threading;
using System.Threading.Tasks;

namespace FileToGitHub;

/// <summary>Stops new HTTP operations while the account workspace is locked.</summary>
public sealed class SessionLockHttpHandler : DelegatingHandler
{
    public SessionLockHttpHandler() : base(new HttpClientHandler()) { }
    protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
    {
        AccountSessionLock.ThrowIfLocked();
        return base.SendAsync(request, cancellationToken);
    }
}
