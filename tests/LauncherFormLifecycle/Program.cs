using AntigasLauncher;
using System.Reflection;
using System.Windows.Forms;

internal static class Program
{
    [STAThread]
    private static void Main()
    {
        // Construct controls without showing the form, then exercise its real
        // closing override and failure path. Every update input is nonexistent.
        var root = Path.Combine(Path.GetTempPath(), "AntigasLauncherLifecycle-" + Guid.NewGuid().ToString("N"));
        using var form = new UpdateApplyForm(
            Path.Combine(root, "missing-package.zip"),
            Path.Combine(root, "missing-manifest.json"),
            Path.Combine(root, "missing-stage"),
            Path.Combine(root, "missing-install"), 53, 0);
        Require(!form.Visible && !form.IsHandleCreated, "The regression must not show an updater window.");

        var onFormClosing = typeof(UpdateApplyForm).GetMethod("OnFormClosing", BindingFlags.Instance | BindingFlags.NonPublic)
            ?? throw new MissingMethodException(nameof(UpdateApplyForm), "OnFormClosing");
        var applyAsync = typeof(UpdateApplyForm).GetMethod("ApplyAsync", BindingFlags.Instance | BindingFlags.NonPublic)
            ?? throw new MissingMethodException(nameof(UpdateApplyForm), "ApplyAsync");

        // The override must keep the guard even after other closing handlers.
        form.FormClosing += (_, args) => args.Cancel = false;
        var pendingClose = new FormClosingEventArgs(CloseReason.UserClosing, false);
        onFormClosing.Invoke(form, [pendingClose]);
        Require(pendingClose.Cancel, "Closing must be cancelled while validation, installation or rollback is pending.");

        var failedUpdate = applyAsync.Invoke(form, null) as Task
            ?? throw new InvalidOperationException("ApplyAsync did not return its task.");
        failedUpdate.GetAwaiter().GetResult();
        var status = typeof(UpdateApplyForm).GetField("_status", BindingFlags.Instance | BindingFlags.NonPublic)?.GetValue(form) as Label;
        Require(status?.Text == "A atualização não foi aplicada.", "The real missing-file update failure path was not reached.");

        var finishedClose = new FormClosingEventArgs(CloseReason.UserClosing, false);
        onFormClosing.Invoke(form, [finishedClose]);
        Require(!finishedClose.Cancel, "Closing must be allowed after the update failure has completed.");
        Require(!form.Visible && !form.IsHandleCreated, "The regression unexpectedly opened an updater window.");
        Require(!Directory.Exists(root), "The missing-file update attempt created an installation or staging directory.");
        Console.WriteLine("Launcher form lifecycle passed: pending close cancelled; real missing-file failure unlocks closing without showing a window or launching the client.");
    }

    private static void Require(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException(message);
    }
}
