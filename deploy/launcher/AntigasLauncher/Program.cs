using System.Windows.Forms;
namespace AntigasLauncher;

internal static class Program
{
    [STAThread]
    private static void Main(string[] args)
    {
        ApplicationConfiguration.Initialize();
        using var appMutex = new Mutex(false, @"Local\AntigasLauncher.v1");
        var isUpdater = args.Length > 0 && args[0] == "--apply-update";
        var ownsMutex = false;
        try { ownsMutex = appMutex.WaitOne(isUpdater ? TimeSpan.FromMinutes(2) : TimeSpan.Zero); }
        catch (AbandonedMutexException) { ownsMutex = true; }
        if (!ownsMutex)
        {
            if (!isUpdater) MessageBox.Show("O launcher do Antigas já está aberto.", "Antigas 7.4", MessageBoxButtons.OK, MessageBoxIcon.Information);
            return;
        }
        try
        {
            if (args.Length == 7 && isUpdater && int.TryParse(args[5], out var version) && int.TryParse(args[6], out var parentPid))
                Application.Run(new UpdateApplyForm(args[1], args[2], args[3], args[4], version, parentPid));
            else
                Application.Run(new LauncherForm(args));
        }
        finally { appMutex.ReleaseMutex(); }
    }
}
