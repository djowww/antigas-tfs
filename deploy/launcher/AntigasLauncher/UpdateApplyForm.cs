using System.Diagnostics;
using System.Drawing;
using System.Security.Cryptography;
using System.Windows.Forms;
namespace AntigasLauncher;

internal sealed class UpdateApplyForm : Form
{
    private readonly string _package, _manifestPath, _stage, _root;
    private readonly int _version, _parentPid;
    private readonly Label _status = new(), _detail = new();
    private readonly ClassicProgressBar _progress = new();
    private readonly Button _playOld = new ClassicButton(true), _close = new ClassicButton();
    private bool _updateInProgress = true;

    public UpdateApplyForm(string package, string manifestPath, string stage, string root, int version, int parentPid)
    {
        _package = package; _manifestPath = manifestPath; _stage = stage; _root = root; _version = version; _parentPid = parentPid;
        Text = "Antigas 7.4 — Atualização"; StartPosition = FormStartPosition.CenterScreen;
        MaximizeBox = false;
        _status.Text = "Aguardando o cliente fechar para trocar os arquivos…";
        _detail.Text = "As configurações e arquivos pessoais são preservados.";
        _progress.Style = ProgressBarStyle.Marquee; _progress.MarqueeAnimationSpeed = 25;
        _playOld.Text = "Abrir versão anterior"; _playOld.Visible = false; _playOld.Click += (_, _) => LaunchOldClient();
        _close.Text = "Fechar"; _close.Visible = false; _close.Click += (_, _) => Close();
        ClassicLauncherTheme.Build(this, "Instalando atualização", _status, _detail, _progress, _playOld, null, _close);
        Shown += async (_, _) => await ApplyAsync();
    }

    protected override void OnFormClosing(FormClosingEventArgs e)
    {
        base.OnFormClosing(e);
        if (_updateInProgress) e.Cancel = true;
    }

    private async Task ApplyAsync()
    {
        _updateInProgress = true;
        try
        {
            var manifest = ReleaseService.ReadAndVerifyManifest(_manifestPath);
            if (manifest.Version != _version) throw new InvalidDataException("A versão do manifesto não corresponde à atualização solicitada.");
            var actual = await ReleaseService.HashFileAsync(_package);
            if (!CryptographicOperations.FixedTimeEquals(Convert.FromHexString(actual), Convert.FromHexString(manifest.Sha256)))
                throw new CryptographicException("O pacote mudou depois da validação inicial.");
            ClientPackage.ValidateStagedPackage(_package, _stage, _version, requireLauncher: true);
            _status.Text = "Finalizando o cliente anterior…";
            await WaitForParentAsync(_parentPid);
            if (ClientPackage.ReadInstalledVersion(_root) >= _version)
                throw new InvalidOperationException("A versão instalada mudou; a atualização foi cancelada.");
            _status.Text = $"Instalando cliente v{_version}…";
            await Task.Run(() => ClientPackage.ApplyStagedUpdate(_stage, _root, _version, new Progress<int>(_ => { })));
            _progress.Style = ProgressBarStyle.Continuous; _progress.Value = 100;
            _status.Text = $"Atualização v{_version} instalada."; _detail.Text = "Abrindo o launcher atualizado…";

            var start = new ProcessStartInfo(Path.Combine(Path.GetFullPath(_root), "AntigasLauncher.exe")) { UseShellExecute = true, WorkingDirectory = Path.GetFullPath(_root) };
            start.ArgumentList.Add("--updated"); start.ArgumentList.Add(_version.ToString());
            Process.Start(start);
            _updateInProgress = false;
            Close();
        }
        catch (Exception ex)
        {
            LauncherLog.Write("apply-update", ex); _progress.Style = ProgressBarStyle.Blocks;
            _status.Text = "A atualização não foi aplicada.";
            var rollbackFailed = ex is AggregateException;
            _detail.Text = rollbackFailed ? "A recuperação automática precisa de atenção. Consulte launcher.log." : "Os arquivos anteriores foram restaurados. Você pode abrir a versão instalada.";
            _playOld.Visible = !rollbackFailed && ClientPackage.HasRunnableClient(_root); _close.Visible = true;
        }
        finally { _updateInProgress = false; }
    }

    private static async Task WaitForParentAsync(int pid)
    {
        var deadline = DateTime.UtcNow.AddMinutes(2);
        while (DateTime.UtcNow < deadline)
        {
            try
            {
                using var parent = Process.GetProcessById(pid);
                if (parent.HasExited) return;
            }
            catch (ArgumentException) { return; }
            await Task.Delay(250);
        }
        throw new TimeoutException("O launcher anterior não encerrou a tempo.");
    }

    private void LaunchOldClient()
    {
        try
        {
            var gl = Path.Combine(Path.GetFullPath(_root), "Antigas_gl.exe");
            var dx = Path.Combine(Path.GetFullPath(_root), "Antigas_dx.exe");
            var exe = File.Exists(gl) ? gl : dx;
            if (File.Exists(exe)) Process.Start(new ProcessStartInfo(exe) { UseShellExecute = true, WorkingDirectory = Path.GetFullPath(_root) });
            Close();
        }
        catch (Exception ex) { LauncherLog.Write("launch-existing-client", ex); }
    }
}
