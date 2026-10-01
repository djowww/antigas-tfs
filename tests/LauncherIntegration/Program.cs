using AntigasLauncher;
using System.IO.Compression;
using System.Net;
using System.Security.Cryptography;
using System.Text.Json.Nodes;

// Explicit opt-in: reads a signed release over HTTPS, installs only in a new
// disposable directory, and never starts the game or edits a real installation.
if (args.Length != 3 || args[0] != "--signed-manifest")
    throw new ArgumentException("Usage: --signed-manifest <staging manifest URL> <built-launcher.exe>");
var uri = new Uri(args[1]);
if (!ReleaseService.IsStagingManifestUri(uri))
    throw new ArgumentException("A clean HTTPS staging URL is required: use /staging/ on tibia74.tech or staging.tibia74.tech");
var launcher = Path.GetFullPath(args[2]);
if (!File.Exists(launcher)) throw new FileNotFoundException("Build the launcher first", launcher);
var root = Path.Combine(Path.GetTempPath(), "AntigasUpdaterValidation-" + Guid.NewGuid().ToString("N"));
Directory.CreateDirectory(root);
var stage = "";
var checks = new List<string>();
try
{
    using var handler = new HttpClientHandler { AllowAutoRedirect = false, CheckCertificateRevocationList = true, AutomaticDecompression = DecompressionMethods.None };
    using var http = new HttpClient(handler) { Timeout = TimeSpan.FromSeconds(30) };
    using var response = await http.GetAsync(uri, HttpCompletionOption.ResponseHeadersRead);
    response.EnsureSuccessStatusCode();
    await using var body = await response.Content.ReadAsStreamAsync();
    var bytes = await BoundedContentReader.ReadAsync(body, 65536, CancellationToken.None);
    var manifestPath = Path.Combine(root, "manifest.json");
    await File.WriteAllBytesAsync(manifestPath, bytes);
    var manifest = ReleaseService.ReadAndVerifyManifest(manifestPath);
    checks.Add("HTTPS staging manifest and pinned ECDSA signature");
    var packageBaseUri = new Uri(uri, ".");
    var expectedPackageUri = new Uri(packageBaseUri, manifest.Package);
    Require(ReleaseService.ResolvePackageUri(manifest, packageBaseUri) == expectedPackageUri, "Package URL must resolve beside the signed staging manifest");
    var package = await ReleaseService.DownloadPackageAsync(manifest, new InlineProgress<double>(_ => { }), CancellationToken.None, Path.Combine(root, "download"), packageBaseUri);
    checks.Add("Staging HTTPS package path and signed SHA-256 verification");

    var altered = JsonNode.Parse(bytes)!.AsObject();
    altered["sha256"] = new string('0', 64);
    File.WriteAllText(manifestPath, altered.ToJsonString());
    Reject<CryptographicException>(() => ReleaseService.ReadAndVerifyManifest(manifestPath));
    checks.Add("Altered manifest signature rejected");

    var malicious = Path.Combine(root, "traversal.zip");
    using (var zip = ZipFile.Open(malicious, ZipArchiveMode.Create))
    using (var writer = new StreamWriter(zip.CreateEntry("../escape.txt").Open())) writer.Write("rejected");
    Reject<InvalidDataException>(() => ClientPackage.ExtractToStaging(malicious, Path.Combine(root, "staging")));
    checks.Add("ZIP path traversal rejected");

    stage = ClientPackage.ExtractToStaging(package, Path.Combine(root, "staging"));
    ClientPackage.ValidateStagedPackage(package, stage, manifest.Version);
    var init = Path.Combine(stage, "init.lua");
    var originalInit = File.ReadAllBytes(init);
    var tamperedInit = originalInit.ToArray();
    tamperedInit[^1] ^= 1;
    File.WriteAllBytes(init, tamperedInit);
    Reject<CryptographicException>(() => ClientPackage.ValidateStagedPackage(package, stage, manifest.Version));
    File.WriteAllBytes(init, originalInit);
    checks.Add("Post-extraction tampering rejected");
    File.Copy(launcher, Path.Combine(stage, "AntigasLauncher.exe"), true);
    ClientPackage.ValidateStagedPackage(package, stage, manifest.Version, requireLauncher: true);
    var installed = Path.Combine(root, "clean-install");
    Directory.CreateDirectory(installed);
    File.WriteAllText(Path.Combine(installed, "init.lua"), "APP_VERSION = 1\n");
    Directory.CreateDirectory(Path.Combine(installed, "userdata"));
    File.WriteAllText(Path.Combine(installed, "userdata", "sentinel.txt"), "preserve-me");
    ClientPackage.ApplyStagedUpdate(stage, installed, manifest.Version, new InlineProgress<int>(_ => { }), Path.Combine(root, "backups"));
    Require(ClientPackage.ReadInstalledVersion(installed) == manifest.Version, "Installed version mismatch");
    Require(File.ReadAllText(Path.Combine(installed, "userdata", "sentinel.txt")) == "preserve-me", "User data changed");
    foreach (var file in Directory.EnumerateFiles(stage, "*", SearchOption.AllDirectories))
    {
        var relative = Path.GetRelativePath(stage, file);
        if (relative.StartsWith("userdata" + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase) || relative.EndsWith(".log", StringComparison.OrdinalIgnoreCase)) continue;
        Require(Hash(file) == Hash(Path.Combine(installed, relative)), "Installed content mismatch: " + relative);
    }
    checks.Add("Clean installation, version, installed hashes and user-data preservation");

    var rollbackInstall = Path.Combine(root, "rollback-install");
    Directory.CreateDirectory(rollbackInstall);
    var stagedFiles = Directory.EnumerateFiles(stage, "*", SearchOption.AllDirectories).ToArray();
    for (int i = 0; i < stagedFiles.Length; ++i)
    {
        if (i == 1) continue; // Verify removal of a newly installed file too.
        var relative = Path.GetRelativePath(stage, stagedFiles[i]);
        var target = Path.Combine(rollbackInstall, relative);
        Directory.CreateDirectory(Path.GetDirectoryName(target)!);
        File.WriteAllText(target, "previous content of " + relative);
    }
    var before = Snapshot(rollbackInstall);
    Reject<IOException>(() => ClientPackage.ApplyStagedUpdate(stage, rollbackInstall, manifest.Version,
        new InlineProgress<int>(count => { if (count >= 3) throw new IOException("injected test failure"); }), Path.Combine(root, "backups")));
    var after = Snapshot(rollbackInstall);
    Require(before.Count == after.Count && before.All(pair => after.TryGetValue(pair.Key, out var value) && value == pair.Value), "Rollback changed installation");
    checks.Add("Injected installation failure rolls back all applied files");
    Console.WriteLine(System.Text.Json.JsonSerializer.Serialize(new { status = "passed", version = manifest.Version, checks }, new System.Text.Json.JsonSerializerOptions { WriteIndented = true }));
}
finally
{
    // All install, download, staging and backup paths belong to this invocation.
    if (stage.Length > 0 && Directory.Exists(stage)) Directory.Delete(stage, true);
    if (Directory.Exists(root)) Directory.Delete(root, true);
}

static string Hash(string file) => Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(file)));
static Dictionary<string, string> Snapshot(string root) => Directory.EnumerateFiles(root, "*", SearchOption.AllDirectories).ToDictionary(file => Path.GetRelativePath(root, file), Hash);
static void Require(bool condition, string message) { if (!condition) throw new InvalidOperationException(message); }
static void Reject<T>(Action action) where T : Exception
{
    try { action(); } catch (T) { return; }
    throw new InvalidOperationException("Expected rejection: " + typeof(T).Name);
}
sealed class InlineProgress<T>(Action<T> callback) : IProgress<T> { public void Report(T value) => callback(value); }
