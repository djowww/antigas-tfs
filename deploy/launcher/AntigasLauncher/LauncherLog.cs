namespace AntigasLauncher;
internal static class LauncherLog
{
    private static readonly string LogPath = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "AntigasLauncher", "launcher.log");
    public static void Write(string action, Exception exception)
    {
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(LogPath)!);
            File.AppendAllText(LogPath, $"{DateTimeOffset.UtcNow:O} [{action}] {exception.GetType().Name}: {exception.Message}{Environment.NewLine}");
        }
        catch { }
    }
}
