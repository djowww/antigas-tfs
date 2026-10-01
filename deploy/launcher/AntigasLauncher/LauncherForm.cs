using System.Diagnostics;
using System.Drawing;
using System.Text.Json;
using System.Windows.Forms;
namespace AntigasLauncher;

internal sealed class LauncherForm : Form
{
    private readonly string _root = Path.GetFullPath(AppContext.BaseDirectory).TrimEnd(Path.DirectorySeparatorChar);
    private readonly Label _status = new(), _detail = new();
    private readonly ClassicProgressBar _progress = new();
    private readonly Button _play = new ClassicButton(true), _retry = new ClassicButton(), _website = new ClassicButton();
    private readonly CancellationTokenSource _lifetime = new();
    private bool _checking;

    public LauncherForm(string[] args)
    {
        Text = "Antigas 7.4 Launcher";
        StartPosition = FormStartPosition.CenterScreen;
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = false; Icon = SystemIcons.Application;
        _status.Text = "Verificando atualizações…";
        _detail.Text = "Os pacotes são conferidos antes de instalar.";
        _progress.Maximum = 1000; _progress.Visible = false;
        _play.Text = "Jogar"; _play.Enabled = false; _play.Click += (_, _) => LaunchGame();
        _retry.Text = "Verificar novamente"; _retry.Click += async (_, _) => await CheckForUpdateAsync();
        _website.Text = "Fechar"; _website.Click += (_, _) => Close();
        ClassicLauncherTheme.Build(this, "Cliente oficial", _status, _detail, _progress, _play, _retry, _website);
        Shown += async (_, _) => { ClientPackage.CleanupOldStaging(); ClientPackage.CleanupOldBackups(); await CheckForUpdateAsync(); };
        FormClosing += (_, _) => _lifetime.Cancel();
    }

    private async Task CheckForUpdateAsync()
    {
        if (_checking || IsDisposed) return;
        _checking = true; _retry.Enabled = false; _play.Enabled = false; _progress.Visible = false; _progress.Value = 0;
        _play.Text = "Jogar"; _status.Text = "Verificando atualizações…"; _detail.Text = "Conferindo a versão e a assinatura oficial.";
        try
        {
            using var timeout = CancellationTokenSource.CreateLinkedTokenSource(_lifetime.Token);
            timeout.CancelAfter(TimeSpan.FromMinutes(7));
            var release = await ReleaseService.GetManifestAsync(timeout.Token);
            var installed = ClientPackage.ReadInstalledVersion(_root);
            if (release.Version <= installed && ClientPackage.HasRunnableClient(_root))
            {
                _status.Text = $"Cliente atualizado — v{installed}."; _detail.Text = "Nenhuma atualização é necessária.";
                _play.Enabled = ClientPackage.HasRunnableClient(_root); return;
            }
            if (ClientPackage.IsGameRunningFrom(_root))
            {
                _status.Text = $"A versão v{release.Version} está pronta para instalar.";
                _detail.Text = "Feche o jogo e clique em Verificar novamente para atualizar."; return;
            }
            _status.Text = $"Baixando atualização v{release.Version}…";
            _detail.Text = "O pacote será conferido antes de substituir qualquer arquivo."; _progress.Visible = true;
            var report = new Progress<double>(value => _progress.Value = Math.Clamp((int)(value * 1000), 0, 1000));
            var package = await ReleaseService.DownloadPackageAsync(release, report, timeout.Token);
            _status.Text = "Preparando arquivos…"; _detail.Text = "Criando uma cópia segura para a atualização."; _progress.Value = 1000;
            var stage = ClientPackage.ExtractToStaging(package);
            ClientPackage.ValidateStagedPackage(package, stage, release.Version);
            var stagedLauncher = Path.Combine(stage, "AntigasLauncher.exe");
            if (!File.Exists(stagedLauncher))
            {
                var currentLauncher = Path.Combine(_root, "AntigasLauncher.exe");
                if (!File.Exists(currentLauncher)) throw new InvalidDataException("Não encontrei o launcher atual para concluir a instalação.");
                File.Copy(currentLauncher, stagedLauncher, false);
            }
            var manifestPath = Path.Combine(Path.GetDirectoryName(package)!, $"release-v{release.Version}.json");
            await File.WriteAllTextAsync(manifestPath, JsonSerializer.Serialize(release), timeout.Token);
            var helper = new ProcessStartInfo(Path.Combine(stage, "AntigasLauncher.exe")) { UseShellExecute = false, CreateNoWindow = true, WorkingDirectory = stage };
            foreach (var argument in new[] { "--apply-update", package, manifestPath, stage, _root, release.Version.ToString(), Environment.ProcessId.ToString() })
                helper.ArgumentList.Add(argument);
            if (Process.Start(helper) is null) throw new InvalidOperationException("Não foi possível iniciar a instalação.");
            Application.ExitThread();
            return;
        }
        catch (OperationCanceledException) when (_lifetime.IsCancellationRequested) { }
        catch (Exception ex)
        {
            LauncherLog.Write("update-check", ex); _progress.Visible = false;
            _status.Text = "Não foi possível concluir a atualização.";
            if (ClientPackage.HasRunnableClient(_root))
            {
                _detail.Text = "A versão instalada foi preservada. Você pode jogar ou tentar de novo.";
                _play.Text = "Jogar versão instalada"; _play.Enabled = true;
            }
            else
            {
                _detail.Text = "Nenhum cliente instalado. Confira a conexão ou tente novamente."; _play.Enabled = false;
            }
        }
        finally
        {
            _checking = false;
            if (!_lifetime.IsCancellationRequested && !IsDisposed) _retry.Enabled = true;
        }
    }

    private void LaunchGame()
    {
        if (ClientPackage.IsGameRunningFrom(_root))
        {
            _status.Text = "O jogo já está aberto."; _detail.Text = "Feche a outra janela do Antigas antes de abrir novamente."; _play.Enabled = false; return;
        }
        var gl = Path.Combine(_root, "Antigas_gl.exe"); var dx = Path.Combine(_root, "Antigas_dx.exe");
        var exe = File.Exists(gl) ? gl : dx;
        if (!File.Exists(exe))
        {
            _status.Text = "Os arquivos do jogo não foram encontrados."; _detail.Text = "Clique em Verificar novamente para baixar o cliente."; _play.Enabled = false; return;
        }
        try { Process.Start(new ProcessStartInfo(exe) { UseShellExecute = true, WorkingDirectory = _root }); Close(); }
        catch (Exception ex)
        {
            LauncherLog.Write("launch-game", ex); _status.Text = "Não foi possível iniciar o jogo.";
            _detail.Text = "Confira as permissões da pasta e tente novamente.";
        }
    }

}
