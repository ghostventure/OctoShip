using System;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Security.Cryptography;

namespace FileToGitHub;

public static class UpdatePackage
{
    public static string Stage(byte[] bytes, string expectedHash, ReleaseVersion version, string updatesRoot)
    {
        if (bytes.LongLength > 250L * 1024 * 1024 || !string.Equals(Convert.ToHexString(SHA256.HashData(bytes)), expectedHash, StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("Update package size or SHA-256 verification failed.");
        var staging = Path.GetFullPath(Path.Combine(updatesRoot, version + "-" + Guid.NewGuid().ToString("N"), "package"));
        using var stream = new MemoryStream(bytes, writable: false);
        using var archive = new ZipArchive(stream, ZipArchiveMode.Read);
        if (archive.Entries.Count > 2000 || archive.Entries.Sum(entry => entry.Length) > 1024L * 1024 * 1024)
            throw new InvalidOperationException("The expanded update exceeds safety limits.");
        foreach (var entry in archive.Entries)
        {
            var target = Path.GetFullPath(Path.Combine(staging, entry.FullName));
            if (entry.FullName.Contains(':') || !target.StartsWith(staging + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("The update archive contains an unsafe file path.");
        }
        Directory.CreateDirectory(staging);
        archive.ExtractToDirectory(staging);
        if (!File.Exists(Path.Combine(staging, "OctoShip.exe")) || !File.Exists(Path.Combine(staging, "OctoShip.dll")))
            throw new InvalidOperationException("The release ZIP is missing OctoShip.exe or OctoShip.dll.");
        var actualVersion = FileVersionInfo.GetVersionInfo(Path.Combine(staging, "OctoShip.dll")).ProductVersion;
        if (actualVersion is null || ReleaseVersion.Parse(actualVersion).CompareTo(version) != 0)
            throw new InvalidOperationException("The packaged application version does not match its release tag.");
        return staging;
    }
}
