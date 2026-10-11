using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.RegularExpressions;

namespace FileToGitHub;

public sealed class SelectiveTextChange
{
    public bool Include { get; set; } = true;
    public string Description { get; init; } = "";
    public int Start { get; init; }
    public int Removed { get; init; }
    public string[] Added { get; init; } = Array.Empty<string>();
}

public static class SelectiveTextChanges
{
    // Keep terminators attached so an unselected edit does not normalize line endings.
    public static string[] Lines(string text) => Regex.Matches(text, @"[^\r\n]*(?:\r\n|\r|\n)|[^\r\n]+$").Select(m => m.Value).ToArray();
    public static IReadOnlyList<SelectiveTextChange> Compare(string before, string after)
    {
        var a = Lines(before); var b = Lines(after);
        if (a.Length > 2000 || b.Length > 2000) throw new ArgumentException("Selective publishing supports up to 2,000 lines per file.");
        var length = new int[a.Length + 1, b.Length + 1];
        for (int i = a.Length - 1; i >= 0; i--) for (int j = b.Length - 1; j >= 0; j--)
            length[i, j] = a[i] == b[j] ? length[i + 1, j + 1] + 1 : Math.Max(length[i + 1, j], length[i, j + 1]);
        var result = new List<SelectiveTextChange>(); int x = 0, y = 0;
        while (x < a.Length || y < b.Length)
        {
            if (x < a.Length && y < b.Length && a[x] == b[y]) { x++; y++; continue; }
            var start = x; var added = new List<string>();
            while (x < a.Length || y < b.Length)
            {
                if (x < a.Length && y < b.Length && a[x] == b[y]) break;
                if (y < b.Length && (x == a.Length || length[x, y + 1] >= length[x + 1, y])) added.Add(b[y++]); else x++;
            }
            var preview = string.Concat(a.Skip(start).Take(x - start).Select(s => "- " + s)) + string.Concat(added.Select(s => "+ " + s));
            result.Add(new() { Start = start, Removed = x - start, Added = added.ToArray(), Description = $"Line {start + 1}: remove {x - start}, add {added.Count}\n{preview}" });
        }
        return result;
    }
    public static string Apply(string before, IReadOnlyList<SelectiveTextChange> changes)
    {
        var lines = Lines(before); var result = new System.Text.StringBuilder(); var position = 0;
        foreach (var change in changes)
        {
            foreach (var line in lines.Skip(position).Take(change.Start - position)) result.Append(line);
            foreach (var line in change.Include ? change.Added : lines.Skip(change.Start).Take(change.Removed)) result.Append(line);
            position = change.Start + change.Removed;
        }
        foreach (var line in lines.Skip(position)) result.Append(line);
        return result.ToString();
    }
}
