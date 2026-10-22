using System;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace FileToGitHub;

/// <summary>Credential-free local history for reviewed shipping actions.</summary>
internal sealed class ShippingOperationJournal
{
    private readonly string _root = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "OctoShipForGitHub", "OperationHistory");
    private string JournalPath => Path.Combine(_root, "shipping.json");
    internal sealed record Attempt(DateTime StartedUtc, string Repository, string Branch, int FileCount, long Bytes, string Fingerprint, string Outcome, string Summary);

    public Attempt[] Read()
    {
        try
        {
            if (!File.Exists(JournalPath) || new FileInfo(JournalPath).Length > 256 * 1024) return Array.Empty<Attempt>();
            return JsonSerializer.Deserialize<Attempt[]>(SecurityBoundaries.ReadBoundedJson(JournalPath, 256 * 1024))?.TakeLast(100).ToArray() ?? Array.Empty<Attempt>();
        }
        catch { return Array.Empty<Attempt>(); }
    }

    public void Append(Attempt attempt)
    {
        Directory.CreateDirectory(_root);
        if (attempt.Summary.Length > 800) attempt = attempt with { Summary = attempt.Summary[..800] + "…" };
        var rows = Read().Where(row => row.StartedUtc != attempt.StartedUtc || row.Fingerprint != attempt.Fingerprint || !row.Repository.Equals(attempt.Repository, StringComparison.OrdinalIgnoreCase))
            .Append(attempt).TakeLast(100).ToArray();
        var temporary = JournalPath + ".tmp";
        File.WriteAllText(temporary, JsonSerializer.Serialize(rows, new JsonSerializerOptions { WriteIndented = true }), new UTF8Encoding(false));
        File.Move(temporary, JournalPath, true);
    }

    public string Fingerprint(string repository, string branch, string commit, ReviewedShipFile[] files)
    {
        var material = repository.Trim().ToLowerInvariant() + "\n" + branch.Trim() + "\n" + commit + "\n" +
            string.Join("\n", files.OrderBy(f => f.Destination, StringComparer.Ordinal).Select(f => f.Destination + "\0" + f.BlobSha));
        return Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(material))).ToLowerInvariant();
    }

    public string Root => _root;
}
