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
        var isUpdatedRelaunch = args.Length == 2 && args[0] == "--updated" &&
            int.TryParse(args[1], out var updatedVersion) && updatedVersion is >= 1 and <= 1_000_000;
        var ownsMutex = false;
        // The update helper launches this process just before releasing its mutex.
        // Normal duplicate launches still fail immediately.
        var mutexWait = isUpdater ? TimeSpan.FromMinutes(2) :
            isUpdatedRelaunch ? TimeSpan.FromSeconds(10) : TimeSpan.Zero;
        try { ownsMutex = appMutex.WaitOne(mutexWait); }
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
