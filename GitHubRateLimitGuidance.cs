using System;
using System.Globalization;
using System.Linq;
using System.Net;
using System.Net.Http;

/// <summary>Formats server-provided rate-limit wait guidance without retrying requests.</summary>
public static class GitHubRateLimitGuidance
{
    public static string? GetWaitMessage(HttpResponseMessage response, DateTimeOffset? now = null)
    {
        ArgumentNullException.ThrowIfNull(response);
        if (response.StatusCode != HttpStatusCode.TooManyRequests
            && !(response.StatusCode == HttpStatusCode.Forbidden
                 && response.Headers.TryGetValues("X-RateLimit-Remaining", out var remaining)
                 && remaining.Contains("0", StringComparer.Ordinal)))
            return null;

        var current = now ?? DateTimeOffset.UtcNow;
        DateTimeOffset? retryAt = response.Headers.RetryAfter?.Date;
        if (response.Headers.RetryAfter?.Delta is { } delta && delta > TimeSpan.Zero)
            retryAt = Max(retryAt, current + delta);
        if (response.Headers.TryGetValues("X-RateLimit-Reset", out var resets)
            && long.TryParse(resets.FirstOrDefault(), NumberStyles.None, CultureInfo.InvariantCulture, out var seconds)
            && seconds is > 0 and < 253402300799)
            retryAt = Max(retryAt, DateTimeOffset.FromUnixTimeSeconds(seconds).AddSeconds(5));

        if (retryAt is null) return "Wait for GitHub's rate limit to reset before retrying.";
        var remainingTime = retryAt.Value - current;
        if (remainingTime <= TimeSpan.Zero) return "GitHub's reported retry time has passed; retry the request.";
        if (remainingTime < TimeSpan.FromMinutes(1)) return "Retry in less than a minute.";
        var minutes = (long)Math.Ceiling(remainingTime.TotalMinutes);
        if (minutes < 60) return $"Retry in about {minutes} minute{(minutes == 1 ? "" : "s")}.";
        var hours = (long)Math.Ceiling(remainingTime.TotalHours);
        return $"Retry in about {hours} hour{(hours == 1 ? "" : "s")}.";
    }

    private static DateTimeOffset? Max(DateTimeOffset? first, DateTimeOffset second) => first is null || second > first ? second : first;
}
