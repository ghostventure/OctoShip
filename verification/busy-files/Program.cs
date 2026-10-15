using System;
using System.IO;
using System.Threading.Tasks;
using FileToGitHub;

internal static class Program
{
    private static int checks;
    private static void Check(bool condition, string name)
    {
        if (!condition) throw new Exception(name);
        Console.WriteLine("PASS " + name);
        checks++;
    }

    private static async Task Main()
    {
        var directory = Path.Combine(Path.GetTempPath(), "OctoShip-busy-file-checks-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(directory);
        try
        {
            var path = Path.Combine(directory, "source.txt");
            await File.WriteAllTextAsync(path, "reviewed bytes");
            var length = new FileInfo(path).Length;
            var modified = File.GetLastWriteTimeUtc(path);

            using (new FileStream(path, FileMode.Open, FileAccess.ReadWrite, FileShare.None))
            {
                Check(!BatchUploadSourceReadiness.TryValidate(path, length, modified, out var lockedError), "exclusive sharing lock blocks local preflight");
                Check(lockedError != null && lockedError.Contains("locked", StringComparison.OrdinalIgnoreCase), "lock failure explains retry action");
            }

            Check(BatchUploadSourceReadiness.TryValidate(path, length, modified, out var retryError) && retryError == null, "same reviewed file validates after lock release for retry");
            await File.WriteAllTextAsync(path, "different content with new length");
            Check(!BatchUploadSourceReadiness.TryValidate(path, length, modified, out var changedError), "changed source is rejected before upload");
            Check(changedError != null && changedError.Contains("changed", StringComparison.OrdinalIgnoreCase), "changed source requires review");

            File.Delete(path);
            Check(!BatchUploadSourceReadiness.TryValidate(path, length, modified, out var missingError), "missing source is rejected before upload");
            Check(missingError != null && missingError.Contains("missing", StringComparison.OrdinalIgnoreCase), "missing source reports restore-and-retry guidance");
            Console.WriteLine($"{checks} busy-file recovery checks passed. No network requests were sent.");
        }
        finally { Directory.Delete(directory, recursive: true); }
    }
}
