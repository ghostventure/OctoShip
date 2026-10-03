using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace FileToGitHub;

/// <summary>Portable, credential-free preference import/export and publisher verification helpers.</summary>
public static class OctoCatPreferencesService
{
    private static readonly JsonSerializerOptions JsonOptions = new() { WriteIndented = true, PropertyNameCaseInsensitive = true };

    public static void Export(string filePath, OctoCatPreferences preferences)
    {
        if (string.IsNullOrWhiteSpace(filePath)) throw new ArgumentException("A preference file path is required.", nameof(filePath));
        ArgumentNullException.ThrowIfNull(preferences);
        var safe = Normalize(preferences);
        var json = JsonSerializer.Serialize(safe, JsonOptions);
        WriteAtomic(filePath, json);
    }

    public static OctoCatPreferences Import(string filePath)
    {
        if (string.IsNullOrWhiteSpace(filePath)) throw new ArgumentException("A preference file path is required.", nameof(filePath));
        using var stream = File.OpenRead(filePath);
        var imported = JsonSerializer.Deserialize<OctoCatPreferences>(stream, JsonOptions) ?? new OctoCatPreferences();
        return Normalize(imported);
    }

    public static OctoCatPreferences ClearHistory(OctoCatPreferences preferences, bool clearDestinations = true) => Normalize(preferences with
    {
        SearchHistory = Array.Empty<string>(),
        RecentRepositories = Array.Empty<string>(),
        Destinations = clearDestinations ? Array.Empty<string>() : preferences.Destinations
    });

    public static OctoCatPreferences Normalize(OctoCatPreferences value) => new()
    {
        SearchHistory = CleanList(value.SearchHistory, 12, 300),
        Destinations = CleanList(value.Destinations, 12, 2048),
        RecentRepositories = CleanList(value.RecentRepositories, 20, 200),
        DefaultUploadFolders = (value.DefaultUploadFolders ?? new Dictionary<string, string>())
            .Where(pair => IsRepository(pair.Key) && IsSafeRepoFolder(pair.Value))
            .Take(100).ToDictionary(pair => pair.Key, pair => pair.Value.Trim('/'), StringComparer.OrdinalIgnoreCase),
        PrivacyMode = value.PrivacyMode,
        UpdateChannel = value.UpdateChannel == OctoCatUpdateChannel.Preview ? OctoCatUpdateChannel.Preview : OctoCatUpdateChannel.Stable
    };

    /// <summary>Checks the Windows Authenticode signature and optional expected signer thumbprint.</summary>
    public static PublisherVerification VerifyPublisher(string executablePath, string? expectedSignerThumbprint = null)
    {
        if (!OperatingSystem.IsWindows()) return new(false, "Publisher signature verification requires Windows.", null);
        if (!File.Exists(executablePath)) return new(false, "File was not found.", null);
        try
        {
            var trustResult = WinVerifyTrust(IntPtr.Zero, ref GenericVerifyV2, new WinTrustData(executablePath));
            if (trustResult != 0) return new(false, $"Windows Authenticode verification failed (0x{trustResult:X8}).", null);
            using var cert = new System.Security.Cryptography.X509Certificates.X509Certificate2(System.Security.Cryptography.X509Certificates.X509Certificate.CreateFromSignedFile(executablePath));
            var signer = cert.Thumbprint?.Replace(" ", "", StringComparison.Ordinal).ToUpperInvariant();
            if (string.IsNullOrWhiteSpace(signer)) return new(false, "The file has no embedded publisher signature.", null);
            if (!string.IsNullOrWhiteSpace(expectedSignerThumbprint) && !string.Equals(signer, expectedSignerThumbprint.Replace(" ", "", StringComparison.Ordinal), StringComparison.OrdinalIgnoreCase))
                return new(false, "The signature is validly embedded but does not match the configured OctoShip publisher thumbprint.", signer);
            return new(true, "Windows Authenticode verification succeeded.", signer);
        }
        catch (System.Security.Cryptography.CryptographicException ex)
        {
            return new(false, string.IsNullOrWhiteSpace(ex.Message) ? "The file signature could not be verified." : ex.Message, null);
        }
        catch (IOException ex) { return new(false, ex.Message, null); }
    }

    private static IReadOnlyList<string> CleanList(IEnumerable<string>? values, int max, int maxLength) => (values ?? Array.Empty<string>())
        .Where(item => !string.IsNullOrWhiteSpace(item) && item.Length <= maxLength && !item.Any(char.IsControl))
        .Distinct(StringComparer.OrdinalIgnoreCase).Take(max).ToArray();
    private static bool IsRepository(string value)
    {
        if (string.IsNullOrWhiteSpace(value)) return false;
        var parts = value.Split('/');
        return parts.Length == 2 && SafeSegment(parts[0]) && SafeSegment(parts[1]);
    }
    private static bool IsSafeRepoFolder(string value) => value is not null && value.Length <= 1024 && !value.StartsWith('/') && !value.Contains('\\') && !value.Any(char.IsControl) && (value.Length == 0 || value.Split('/').All(segment => SafeSegment(segment)));
    private static bool SafeSegment(string segment) => segment.Length is > 0 and <= 100 && segment is not "." and not ".." && segment.All(c => char.IsLetterOrDigit(c) || c is '-' or '_' or '.');
    private static void WriteAtomic(string path, string content)
    {
        var full = Path.GetFullPath(path);
        Directory.CreateDirectory(Path.GetDirectoryName(full)!);
        var temp = full + ".tmp-" + Guid.NewGuid().ToString("N");
        try
        {
            using (var stream = new FileStream(temp, FileMode.CreateNew, FileAccess.Write, FileShare.None))
            using (var writer = new StreamWriter(stream)) { writer.Write(content); writer.Flush(); stream.Flush(true); }
            File.Move(temp, full, true);
        }
        finally { if (File.Exists(temp)) File.Delete(temp); }
    }

    private static Guid GenericVerifyV2 = new("00AAC56B-CD44-11D0-8CC2-00C04FC295EE");
    [System.Runtime.InteropServices.DllImport("wintrust.dll", ExactSpelling = true, CharSet = System.Runtime.InteropServices.CharSet.Unicode, SetLastError = true)]
    private static extern int WinVerifyTrust(IntPtr hwnd, ref Guid actionId, [System.Runtime.InteropServices.In] WinTrustData data);

    [System.Runtime.InteropServices.StructLayout(System.Runtime.InteropServices.LayoutKind.Sequential, CharSet = System.Runtime.InteropServices.CharSet.Unicode)]
    private sealed class WinTrustData : IDisposable
    {
        private readonly IntPtr _fileInfo;
        public uint Size;
        public IntPtr PolicyCallbackData;
        public IntPtr SIPClientData;
        public uint UIChoiceValue = 2;
        public uint RevocationChecks;
        public uint UnionChoice = 1;
        public IntPtr FileInfo;
        public uint StateAction;
        public IntPtr StateData;
        public IntPtr URLReference;
        public uint ProviderFlags = 0x00000010;
        public uint UIContext;
        public WinTrustData(string file)
        {
            var info = new WinTrustFileInfo(file);
            _fileInfo = System.Runtime.InteropServices.Marshal.AllocHGlobal(System.Runtime.InteropServices.Marshal.SizeOf<WinTrustFileInfo>());
            System.Runtime.InteropServices.Marshal.StructureToPtr(info, _fileInfo, false);
            FileInfo = _fileInfo;
            Size = (uint)System.Runtime.InteropServices.Marshal.SizeOf<WinTrustData>();
        }
        public void Dispose() => System.Runtime.InteropServices.Marshal.FreeHGlobal(_fileInfo);
    }

    [System.Runtime.InteropServices.StructLayout(System.Runtime.InteropServices.LayoutKind.Sequential, CharSet = System.Runtime.InteropServices.CharSet.Unicode)]
    private sealed class WinTrustFileInfo
    {
        public uint Size;
        [System.Runtime.InteropServices.MarshalAs(System.Runtime.InteropServices.UnmanagedType.LPWStr)]
        public string FilePath;
        public IntPtr FileHandle;
        public IntPtr KnownSubject;
        public WinTrustFileInfo(string path) { Size = (uint)System.Runtime.InteropServices.Marshal.SizeOf<WinTrustFileInfo>(); FilePath = path; }
    }
}

public enum OctoCatUpdateChannel { Stable, Preview }
public sealed record PublisherVerification(bool Trusted, string Message, string? SignerThumbprint);

/// <summary>Allow-listed, credential-free fields only. Tokens and account credentials are intentionally not representable.</summary>
public sealed record OctoCatPreferences
{
    public IReadOnlyList<string> SearchHistory { get; init; } = Array.Empty<string>();
    public IReadOnlyList<string> Destinations { get; init; } = Array.Empty<string>();
    public IReadOnlyList<string> RecentRepositories { get; init; } = Array.Empty<string>();
    public Dictionary<string, string> DefaultUploadFolders { get; init; } = new(StringComparer.OrdinalIgnoreCase);
    public bool PrivacyMode { get; init; }
    public OctoCatUpdateChannel UpdateChannel { get; init; } = OctoCatUpdateChannel.Stable;
}
