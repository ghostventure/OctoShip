using System;
using System.IO;

namespace FileToGitHub;

public enum PreviewContentKind { Unknown, Text, Png, Jpeg, Gif, Bitmap, Tiff, Pdf }

/// <summary>Identifies previewable file formats from a bounded signature read, not a filename alone.</summary>
public static class FileContentTypeAudit
{
    public const int SignatureBytes = 16;

    public static PreviewContentKind Detect(ReadOnlySpan<byte> bytes)
    {
        if (bytes.Length >= 8 && bytes[..8].SequenceEqual(new byte[] { 0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a })) return PreviewContentKind.Png;
        if (bytes.Length >= 3 && bytes[0] == 0xff && bytes[1] == 0xd8 && bytes[2] == 0xff) return PreviewContentKind.Jpeg;
        if (bytes.Length >= 6 && (bytes[..6].SequenceEqual("GIF87a"u8) || bytes[..6].SequenceEqual("GIF89a"u8))) return PreviewContentKind.Gif;
        if (bytes.Length >= 2 && bytes[0] == (byte)'B' && bytes[1] == (byte)'M') return PreviewContentKind.Bitmap;
        if (bytes.Length >= 4 && (bytes[..4].SequenceEqual(new byte[] { (byte)'I', (byte)'I', 42, 0 }) || bytes[..4].SequenceEqual(new byte[] { (byte)'M', (byte)'M', 0, 42 }))) return PreviewContentKind.Tiff;
        if (bytes.Length >= 5 && bytes[..5].SequenceEqual("%PDF-"u8)) return PreviewContentKind.Pdf;
        if (!bytes.Contains((byte)0)) return PreviewContentKind.Text;
        return PreviewContentKind.Unknown;
    }

    public static PreviewContentKind ClaimedKind(string extension) => extension.ToLowerInvariant() switch
    {
        ".png" => PreviewContentKind.Png,
        ".jpg" or ".jpeg" => PreviewContentKind.Jpeg,
        ".gif" => PreviewContentKind.Gif,
        ".bmp" => PreviewContentKind.Bitmap,
        ".tif" or ".tiff" => PreviewContentKind.Tiff,
        ".pdf" => PreviewContentKind.Pdf,
        _ => PreviewContentKind.Unknown
    };

    public static bool HasKnownExtensionMismatch(string extension, PreviewContentKind detected)
    {
        var claimed = ClaimedKind(extension);
        return claimed != PreviewContentKind.Unknown && claimed != detected;
    }

    public static PreviewContentKind Read(string path)
    {
        Span<byte> prefix = stackalloc byte[SignatureBytes];
        using var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read, SignatureBytes, FileOptions.SequentialScan);
        var count = stream.Read(prefix);
        return Detect(prefix[..count]);
    }
}
