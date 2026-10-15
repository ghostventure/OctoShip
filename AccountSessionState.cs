using System;
using System.IO;
using System.Text.Json;

namespace FileToGitHub;

/// <summary>Credential-free persistence and timeout policy for the local application session.</summary>
public sealed class AccountSessionState
{
    public static readonly TimeSpan IdleLimit = TimeSpan.FromMinutes(30);
    public DateTimeOffset LastActivityUtc { get; private set; }
    public bool IsLocked { get; private set; }
    public AccountSessionState(DateTimeOffset now) => LastActivityUtc = now;
    public bool CheckTimeout(DateTimeOffset now)
    {
        if (now < LastActivityUtc || now - LastActivityUtc >= IdleLimit) IsLocked = true;
        return IsLocked;
    }
    public void RecordActivity(DateTimeOffset now)
    {
        // Check before resetting: the first input after a sleep must not bypass expiry.
        if (!CheckTimeout(now)) LastActivityUtc = now;
    }
    public void Lock() => IsLocked = true;
    public void UnlockAfterVerification(DateTimeOffset now) { LastActivityUtc = now; IsLocked = false; }
    public void ResumeWithoutAuthentication(DateTimeOffset now) { LastActivityUtc = now; IsLocked = false; }
    public void Save(string path)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(path))!);
        var temp = path + "." + Guid.NewGuid().ToString("N") + ".tmp";
        try
        {
            using (var stream = new FileStream(temp, FileMode.CreateNew, FileAccess.Write, FileShare.None))
            { JsonSerializer.Serialize(stream, new Snapshot(1, LastActivityUtc, IsLocked)); stream.Flush(true); }
            File.Move(temp, path, true);
        }
        finally { if (File.Exists(temp)) File.Delete(temp); }
    }
    public static AccountSessionState Load(string path, DateTimeOffset now)
    {
        var state = new AccountSessionState(now);
        if (!File.Exists(path)) return state;
        try
        {
            if (new FileInfo(path).Length > 4096) throw new InvalidDataException();
            var value = JsonSerializer.Deserialize<Snapshot>(File.ReadAllText(path));
            if (value is null || value.Version != 1 || value.LastActivityUtc == default) throw new InvalidDataException();
            state.LastActivityUtc = value.LastActivityUtc;
            state.IsLocked = value.IsLocked;
            state.CheckTimeout(now);
        }
        catch { state.Lock(); } // An unreadable existing session is never treated as authenticated.
        return state;
    }
    private sealed record Snapshot(int Version, DateTimeOffset LastActivityUtc, bool IsLocked);
}
