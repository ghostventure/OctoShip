using System;
using System.Linq;
using System.Text.RegularExpressions;

namespace FileToGitHub;

public sealed record ReleaseVersion(Version Core, string[] Preview) : IComparable<ReleaseVersion>
{
    public static ReleaseVersion Parse(string value)
    {
        var match = Regex.Match(value, @"^[vV]?(\d+\.\d+\.\d+)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$");
        if (!match.Success || !Version.TryParse(match.Groups[1].Value, out var core))
            throw new InvalidOperationException("Release tags must use a version such as v1.6.0 or v1.6.0-preview.2.");
        return new(core, match.Groups[2].Success ? match.Groups[2].Value.Split('.') : Array.Empty<string>());
    }
    public int CompareTo(ReleaseVersion? other)
    {
        if (other is null) return 1;
        var core = Core.CompareTo(other.Core); if (core != 0) return core;
        if (Preview.Length == 0 || other.Preview.Length == 0)
            return Preview.Length == other.Preview.Length ? 0 : Preview.Length == 0 ? 1 : -1;
        for (var i = 0; i < Math.Min(Preview.Length, other.Preview.Length); i++)
        {
            var left = Preview[i]; var right = other.Preview[i];
            var ln = left.All(char.IsDigit); var rn = right.All(char.IsDigit);
            var result = ln && rn ? CompareNumber(left, right) : ln != rn ? (ln ? -1 : 1) : string.CompareOrdinal(left, right);
            if (result != 0) return result;
        }
        return Preview.Length.CompareTo(other.Preview.Length);
    }
    private static int CompareNumber(string left, string right)
    {
        left = left.TrimStart('0'); right = right.TrimStart('0');
        return left.Length != right.Length ? left.Length.CompareTo(right.Length) : string.CompareOrdinal(left, right);
    }
    public override string ToString() => Core + (Preview.Length == 0 ? "" : "-" + string.Join(".", Preview));
}
