using System.Diagnostics;
using System.IO.Compression;
using System.Security.Cryptography;
using System.Text.RegularExpressions;

namespace AntigasLauncher;

internal static class ClientPackage
{
    private const long MaxExpandedBytes = 500L * 1024 * 1024;
    private const int MaxArchiveEntries = 20000;
    private static readonly string LocalRoot = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "AntigasLauncher");
    private static readonly Regex VersionPattern = new(@"^\s*APP_VERSION\s*=\s*(\d+)\b", RegexOptions.Multiline | RegexOptions.CultureInvariant | RegexOptions.Compiled);

    public static string GetStagingRoot()
    {
        var root = Path.Combine(LocalRoot, "staging");
        Directory.CreateDirectory(root);
        return root;
    }

    public static string ExtractToStaging(string packagePath)
    {
        var stageRoot = GetStagingRoot();
        var stage = Path.Combine(stageRoot, Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(stage);
        try
        {
            using var archive = ZipFile.OpenRead(packagePath);
            if (archive.Entries.Count is < 1 or > MaxArchiveEntries) throw new InvalidDataException("O pacote tem uma quantidade inesperada de arquivos.");
            long total = 0;
            var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            foreach (var entry in archive.Entries)
            {
                var relative = NormalizeEntryPath(entry.FullName);
                if (relative.Length == 0) continue;
                var isDirectory = entry.FullName.EndsWith('/') || entry.FullName.EndsWith('\\');
                var destination = ResolveChildPath(stage, relative);
                if (isDirectory)
                {
                    Directory.CreateDirectory(destination);
                    continue;
                }
                if (IsUnixSymlink(entry)) throw new InvalidDataException("O pacote contém um tipo de arquivo não permitido.");
                if (!seen.Add(relative)) throw new InvalidDataException("O pacote contém caminhos duplicados.");
                if (entry.Length < 0 || entry.Length > 150L * 1024 * 1024) throw new InvalidDataException("Um arquivo do pacote excede o tamanho permitido.");
                total += entry.Length;
                if (total > MaxExpandedBytes) throw new InvalidDataException("O conteúdo expandido excede o tamanho permitido.");
                Directory.CreateDirectory(Path.GetDirectoryName(destination)!);
                using var input = entry.Open();
                using var output = new FileStream(destination, FileMode.CreateNew, FileAccess.Write, FileShare.None);
                input.CopyTo(output);
                if (output.Length != entry.Length) throw new InvalidDataException("Um arquivo do pacote foi expandido incompletamente.");
            }
            ValidateClientRoot(stage, requireLauncher: false);
            return stage;
        }
        catch
        {
            TryDeleteDirectory(stage);
            throw;
        }
    }

    public static void ValidateStagedPackage(string packagePath, string stage, int expectedVersion, bool requireLauncher = false)
    {
        ValidateClientRoot(stage, requireLauncher);
        if (ReadInstalledVersion(stage) != expectedVersion) throw new InvalidDataException("A versão dentro do pacote não corresponde ao manifesto assinado.");
        using var archive = ZipFile.OpenRead(packagePath);
        var expected = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var entry in archive.Entries)
        {
            var relative = NormalizeEntryPath(entry.FullName);
            if (relative.Length == 0 || entry.FullName.EndsWith('/') || entry.FullName.EndsWith('\\')) continue;
            if (!expected.Add(relative)) throw new InvalidDataException("O pacote contém caminhos duplicados.");
            var stagedFile = ResolveChildPath(stage, relative);
            if (!File.Exists(stagedFile) || new FileInfo(stagedFile).Length != entry.Length)
                throw new InvalidDataException("Os arquivos extraídos não correspondem ao pacote.");
            using var entryStream = entry.Open();
            using var stagedStream = new FileStream(stagedFile, FileMode.Open, FileAccess.Read, FileShare.Read);
            var archiveHash = SHA256.HashData(entryStream);
            var stageHash = SHA256.HashData(stagedStream);
            if (!CryptographicOperations.FixedTimeEquals(archiveHash, stageHash))
                throw new CryptographicException("Um arquivo preparado para atualização foi alterado.");
        }
        var stagedFiles = Directory.EnumerateFiles(stage, "*", SearchOption.AllDirectories)
            .Select(path => Path.GetRelativePath(stage, path).Replace(Path.DirectorySeparatorChar, '/'))
            .ToHashSet(StringComparer.OrdinalIgnoreCase);
        var extra = stagedFiles.Except(expected, StringComparer.OrdinalIgnoreCase).ToArray();
        if (extra.Length > 0 && !(requireLauncher && extra.Length == 1 && extra[0].Equals("AntigasLauncher.exe", StringComparison.OrdinalIgnoreCase)))
            throw new InvalidDataException("A pasta temporária contém arquivos inesperados.");
    }

    public static int ReadInstalledVersion(string root)
    {
        var marker = Path.Combine(root, "client.version");
        if (File.Exists(marker) && int.TryParse(File.ReadAllText(marker).Trim(), out var version) && version is >= 1 and <= 1_000_000)
            return version;
        var init = Path.Combine(root, "init.lua");
        if (!File.Exists(init)) return 0;
        var match = VersionPattern.Match(File.ReadAllText(init));
        return match.Success && int.TryParse(match.Groups[1].Value, out version) ? version : 0;
    }

    public static bool HasRunnableClient(string root) =>
        File.Exists(Path.Combine(root, "Antigas_gl.exe")) || File.Exists(Path.Combine(root, "Antigas_dx.exe"));

    public static bool IsGameRunningFrom(string root)
    {
        var fullRoot = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
        foreach (var name in new[] { "Antigas_gl", "Antigas_dx" })
        {
            foreach (var process in Process.GetProcessesByName(name))
            {
                using (process)
                {
                    try
                    {
                        var executable = Path.GetFullPath(process.MainModule?.FileName ?? "");
                        if (executable.StartsWith(fullRoot, StringComparison.OrdinalIgnoreCase)) return true;
                    }
                    catch (Exception ex) when (ex is InvalidOperationException or System.ComponentModel.Win32Exception or NotSupportedException or ArgumentException)
                    {
                        // If a matching game process is present but its path cannot be inspected, do not replace files underneath it.
                        return true;
                    }
                }
            }
        }
        return false;
    }

    public static string ApplyStagedUpdate(string stage, string installRoot, int expectedVersion, IProgress<int> progress)
    {
        stage = Path.GetFullPath(stage);
        installRoot = Path.GetFullPath(installRoot).TrimEnd(Path.DirectorySeparatorChar);
        if (installRoot.Length < 4 || !Directory.Exists(installRoot)) throw new InvalidOperationException("A pasta instalada do cliente não está disponível.");
        ValidateClientRoot(stage, requireLauncher: true);
        if (ReadInstalledVersion(stage) != expectedVersion) throw new InvalidDataException("A versão preparada não corresponde à atualização.");
        if (IsGameRunningFrom(installRoot)) throw new InvalidOperationException("Feche o cliente do jogo antes de substituir os arquivos.");

        var backupRoot = Path.Combine(LocalRoot, "backups", DateTime.UtcNow.ToString("yyyyMMdd-HHmmss") + "-v" + expectedVersion);
        Directory.CreateDirectory(backupRoot);
        var files = Directory.EnumerateFiles(stage, "*", SearchOption.AllDirectories).ToArray();
        var changes = new List<FileChange>();
        try
        {
            var completed = 0;
            foreach (var source in files)
            {
                var relative = Path.GetRelativePath(stage, source);
                if (IsPreservedUserData(relative)) { completed++; progress.Report(completed); continue; }
                var target = ResolveChildPath(installRoot, relative.Replace(Path.DirectorySeparatorChar, '/'));
                EnsureNoReparsePath(installRoot, Path.GetDirectoryName(target)!);
                Directory.CreateDirectory(Path.GetDirectoryName(target)!);
                var existed = File.Exists(target);
                if (existed && (File.GetAttributes(target) & FileAttributes.ReparsePoint) != 0) throw new IOException("A atualização encontrou um arquivo vinculado e foi cancelada por segurança.");
                var backup = ResolveChildPath(backupRoot, relative.Replace(Path.DirectorySeparatorChar, '/'));
                if (existed)
                {
                    Directory.CreateDirectory(Path.GetDirectoryName(backup)!);
                    File.Copy(target, backup, false);
                }
                var change = new FileChange(target, backup, existed);
                var temporary = target + ".antigas-update-" + Guid.NewGuid().ToString("N");
                try
                {
                    File.Copy(source, temporary, false);
                    File.Move(temporary, target, true);
                    changes.Add(change);
                }
                finally
                {
                    if (File.Exists(temporary)) File.Delete(temporary);
                }
                completed++;
                progress.Report(completed);
            }
            return backupRoot;
        }
        catch (Exception updateError)
        {
            var rollbackErrors = new List<Exception>();
            foreach (var change in changes.AsEnumerable().Reverse())
            {
                try
                {
                    if (change.Existed)
                    {
                        var temporary = change.Target + ".antigas-rollback-" + Guid.NewGuid().ToString("N");
                        File.Copy(change.Backup, temporary, false);
                        File.Move(temporary, change.Target, true);
                    }
                    else if (File.Exists(change.Target))
                    {
                        File.Delete(change.Target);
                    }
                }
                catch (Exception rollbackError) { rollbackErrors.Add(rollbackError); }
            }
            if (rollbackErrors.Count > 0)
                throw new AggregateException($"A atualização falhou e houve erro ao restaurar arquivos. Cópias de segurança em: {backupRoot}", new[] { updateError }.Concat(rollbackErrors));
            throw new IOException($"A atualização falhou; os arquivos anteriores foram restaurados. Backup: {backupRoot}", updateError);
        }
    }

    public static void CleanupOldBackups()
    {
        var root = Path.Combine(LocalRoot, "backups");
        if (!Directory.Exists(root)) return;
        var keep = Directory.EnumerateDirectories(root).OrderByDescending(Directory.GetCreationTimeUtc).Take(3).ToHashSet(StringComparer.OrdinalIgnoreCase);
        foreach (var directory in Directory.EnumerateDirectories(root))
        {
            try { if (!keep.Contains(directory)) Directory.Delete(directory, true); } catch { }
        }
    }
    public static void CleanupOldStaging()
    {
        var root = Path.Combine(LocalRoot, "staging");
        if (!Directory.Exists(root)) return;
        foreach (var directory in Directory.EnumerateDirectories(root))
        {
            try
            {
                if (Directory.GetCreationTimeUtc(directory) < DateTime.UtcNow.AddDays(-2)) Directory.Delete(directory, true);
            }
            catch { }
        }
    }

    private static bool IsPreservedUserData(string relative)
    {
        var normalized = relative.Replace('\\', '/');
        var first = normalized.Split('/')[0];
        return first.Equals("userdata", StringComparison.OrdinalIgnoreCase) ||
               first.Equals("screenshots", StringComparison.OrdinalIgnoreCase) ||
               first.Equals("logs", StringComparison.OrdinalIgnoreCase) ||
               normalized.EndsWith(".log", StringComparison.OrdinalIgnoreCase);
    }

    private static string NormalizeEntryPath(string entry)
    {
        if (string.IsNullOrWhiteSpace(entry) || entry.StartsWith('/') || entry.StartsWith('\\') || entry.Contains(':'))
            throw new InvalidDataException("O pacote contém um caminho inválido.");
        var normalized = entry.Replace('\\', '/');
        var parts = normalized.Split('/');
        if (parts.Any(part => part is ".." or "." || part.Length == 0 && !entry.EndsWith('/') && !entry.EndsWith('\\')))
            throw new InvalidDataException("O pacote contém um caminho fora da pasta do cliente.");
        return string.Join(Path.DirectorySeparatorChar, parts.Where(part => part.Length > 0));
    }

    private static string ResolveChildPath(string root, string relative)
    {
        var fullRoot = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
        var fullPath = Path.GetFullPath(Path.Combine(fullRoot, relative.Replace('/', Path.DirectorySeparatorChar)));
        if (!fullPath.StartsWith(fullRoot, StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("O pacote tentou sair da pasta permitida.");
        return fullPath;
    }

    private static void ValidateClientRoot(string root, bool requireLauncher)
    {
        var full = Path.GetFullPath(root);
        if (requireLauncher && !File.Exists(Path.Combine(full, "AntigasLauncher.exe"))) throw new InvalidDataException("A pasta preparada não contém AntigasLauncher.exe.");
        if (!File.Exists(Path.Combine(full, "init.lua"))) throw new InvalidDataException("O pacote não contém init.lua.");
        if (!HasRunnableClient(full)) throw new InvalidDataException("O pacote não contém um executável de jogo.");
        var version = ReadInstalledVersion(full);
        if (version < 1) throw new InvalidDataException("Não foi possível identificar a versão do cliente.");
    }

    private static bool IsUnixSymlink(ZipArchiveEntry entry) => ((entry.ExternalAttributes >> 16) & 0xF000) == 0xA000;

    private static void EnsureNoReparsePath(string root, string directory)
    {
        var fullRoot = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar);
        var current = Path.GetFullPath(directory);
        if (!current.StartsWith(fullRoot, StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("O caminho de instalação saiu da pasta do cliente.");
        while (current.Length >= fullRoot.Length)
        {
            if (Directory.Exists(current) && (File.GetAttributes(current) & FileAttributes.ReparsePoint) != 0)
                throw new IOException("A atualização encontrou um atalho de pasta e foi cancelada por segurança.");
            if (string.Equals(current, fullRoot, StringComparison.OrdinalIgnoreCase)) break;
            current = Path.GetDirectoryName(current) ?? fullRoot;
        }
    }

    private static void TryDeleteDirectory(string path)
    {
        try { if (Directory.Exists(path)) Directory.Delete(path, true); } catch { }
    }

    private sealed record FileChange(string Target, string Backup, bool Existed);
}
