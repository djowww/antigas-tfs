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
    private readonly ProgressBar _progress = new();
    private readonly Button _playOld = new(), _close = new();

    public UpdateApplyForm(string package, string manifestPath, string stage, string root, int version, int parentPid)
    {
        _package = package; _manifestPath = manifestPath; _stage = stage; _root = root; _version = version; _parentPid = parentPid;
        Text = "Antigas 7.4 — Atualização"; StartPosition = FormStartPosition.CenterScreen;
        FormBorderStyle = FormBorderStyle.FixedDialog; MaximizeBox = false; ClientSize = new Size(520, 210);
        BackColor = Color.FromArgb(28, 30, 32); ForeColor = Color.FromArgb(230, 225, 211); Font = new Font("Segoe UI", 9F);
        var title = new Label { Text = "Instalando atualização", Font = new Font("Segoe UI", 15F, FontStyle.Bold), ForeColor = Color.FromArgb(221, 174, 73), AutoSize = true, Location = new Point(26, 24) };
        _status.SetBounds(29, 74, 458, 26); _status.Text = "Aguardando o cliente fechar para trocar os arquivos…";
        _detail.SetBounds(29, 105, 458, 32); _detail.ForeColor = Color.FromArgb(174, 169, 157); _detail.Text = "As configurações e arquivos pessoais são preservados.";
        _progress.SetBounds(29, 146, 458, 13); _progress.Style = ProgressBarStyle.Marquee; _progress.MarqueeAnimationSpeed = 25;
        _playOld.Text = "Abrir versão anterior"; _playOld.SetBounds(29, 166, 160, 30); _playOld.Visible = false; _playOld.Click += (_, _) => LaunchOldClient();
        _close.Text = "Fechar"; _close.SetBounds(386, 166, 101, 30); _close.Visible = false; _close.Click += (_, _) => Close();
        Controls.AddRange([title, _status, _detail, _progress, _playOld, _close]);
        Shown += async (_, _) => await ApplyAsync();
    }

    private async Task ApplyAsync()
    {
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
