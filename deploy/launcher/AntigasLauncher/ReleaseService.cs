using System.Net;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace AntigasLauncher;

internal sealed class ReleaseManifest
{
    [JsonPropertyName("version")] public int Version { get; init; }
    [JsonPropertyName("name")] public string Name { get; init; } = "";
    [JsonPropertyName("sha256")] public string Sha256 { get; init; } = "";
    [JsonPropertyName("package")] public string Package { get; init; } = "";
    [JsonPropertyName("signatureAlgorithm")] public string SignatureAlgorithm { get; init; } = "";
    [JsonPropertyName("signature")] public string Signature { get; init; } = "";
}

internal static class ReleaseService
{
    private const string ManifestUrl = "https://tibia74.tech/client-release.json";
    private const string SignatureAlgorithm = "ECDSA-P256-SHA256-P1363";
    private const string CanonicalPrefix = "ANTIGAS-CLIENT-RELEASE-V1";
    // Public verification key only. Its matching private key is held by the release publisher in Windows CNG.
    private const string PublicKeyBase64 = "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAELyhqZ/vlL8gMrlo3VHBmfALsf3k/RZaJyErvum5sJjUFabJRQqVtzn4j9JqR/iYgU5VRyuKiG0tRP6pCo4btJg==";
    private static readonly Uri SiteUri = new("https://tibia74.tech/");
    private static readonly HttpClient Http = new(new HttpClientHandler
    {
        AllowAutoRedirect = false,
        CheckCertificateRevocationList = true,
        AutomaticDecompression = DecompressionMethods.None
    }) { Timeout = TimeSpan.FromMinutes(5) };

    public static async Task<ReleaseManifest> GetManifestAsync(CancellationToken cancellationToken)
    {
        var uri = new Uri(ManifestUrl + "?launcher=1&ts=" + DateTimeOffset.UtcNow.ToUnixTimeSeconds());
        using var request = new HttpRequestMessage(HttpMethod.Get, uri);
        request.Headers.CacheControl = new System.Net.Http.Headers.CacheControlHeaderValue { NoCache = true, NoStore = true };
        using var response = await Http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, cancellationToken);
        EnsureNoRedirect(response);
        response.EnsureSuccessStatusCode();
        if (response.Content.Headers.ContentLength is > 65536) throw new InvalidDataException("O manifesto excede o tamanho permitido.");
        await using var stream = await response.Content.ReadAsStreamAsync(cancellationToken);
        var bytes = await BoundedContentReader.ReadAsync(stream, 65536, cancellationToken);
        return ParseAndVerify(bytes);
    }

    public static ReleaseManifest ReadAndVerifyManifest(string path)
    {
        var file = new FileInfo(path);
        if (file.Length > 65536) throw new InvalidDataException("O manifesto local excede o tamanho permitido.");
        var bytes = File.ReadAllBytes(path);
        return ParseAndVerify(bytes);
    }

    private static ReleaseManifest ParseAndVerify(byte[] json)
    {
        var manifest = JsonSerializer.Deserialize<ReleaseManifest>(json, new JsonSerializerOptions { PropertyNameCaseInsensitive = false })
            ?? throw new InvalidDataException("O manifesto está vazio ou inválido.");
        if (manifest.Version is < 1 or > 1_000_000) throw new InvalidDataException("A versão do cliente no manifesto é inválida.");
        if (!string.Equals(manifest.Package, $"Antigas-7.4-Update-v{manifest.Version}.zip", StringComparison.Ordinal))
            throw new InvalidDataException("O nome do pacote não corresponde à versão publicada.");
        if (manifest.Sha256.Length != 64 || !manifest.Sha256.All(Uri.IsHexDigit))
            throw new InvalidDataException("O SHA-256 do pacote é inválido.");
        if (!string.Equals(manifest.SignatureAlgorithm, SignatureAlgorithm, StringComparison.Ordinal))
            throw new InvalidDataException("O algoritmo de assinatura não é aceito.");

        byte[] signature;
        try { signature = Convert.FromBase64String(manifest.Signature); }
        catch (FormatException ex) { throw new InvalidDataException("A assinatura do manifesto é inválida.", ex); }
        if (signature.Length != 64) throw new InvalidDataException("O tamanho da assinatura do manifesto é inválido.");
        var canonical = Encoding.UTF8.GetBytes($"{CanonicalPrefix}\n{manifest.Version}\n{manifest.Package}\n{manifest.Sha256.ToLowerInvariant()}\n");
        using var verifier = ECDsa.Create();
        verifier.ImportSubjectPublicKeyInfo(Convert.FromBase64String(PublicKeyBase64), out _);
        if (!verifier.VerifyData(canonical, signature, HashAlgorithmName.SHA256, DSASignatureFormat.IeeeP1363FixedFieldConcatenation))
            throw new CryptographicException("A assinatura do manifesto não confere.");
        return manifest;
    }

    public static async Task<string> DownloadPackageAsync(ReleaseManifest manifest, IProgress<double> progress, CancellationToken cancellationToken)
    {
        var packageUri = new Uri(SiteUri, manifest.Package);
        if (packageUri.Scheme != Uri.UriSchemeHttps || !string.Equals(packageUri.Host, SiteUri.Host, StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("O endereço do pacote não pertence ao site oficial.");

        var downloadDirectory = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "AntigasLauncher", "downloads");
        Directory.CreateDirectory(downloadDirectory);
        var target = Path.Combine(downloadDirectory, manifest.Package);
        var temporary = target + ".partial";
        try
        {
            using var request = new HttpRequestMessage(HttpMethod.Get, packageUri);
            request.Headers.CacheControl = new System.Net.Http.Headers.CacheControlHeaderValue { NoCache = true };
            using var response = await Http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, cancellationToken);
            EnsureNoRedirect(response);
            response.EnsureSuccessStatusCode();
            const long maxPackageBytes = 400L * 1024 * 1024;
            var expectedLength = response.Content.Headers.ContentLength;
            if (expectedLength is > maxPackageBytes) throw new InvalidDataException("O pacote excede o tamanho máximo permitido.");
            await using var input = await response.Content.ReadAsStreamAsync(cancellationToken);
            await using (var output = new FileStream(temporary, FileMode.Create, FileAccess.Write, FileShare.None, 128 * 1024, FileOptions.Asynchronous | FileOptions.SequentialScan))
            {
                var chunk = new byte[128 * 1024];
                long total = 0;
                int read;
                while ((read = await input.ReadAsync(chunk, cancellationToken)) > 0)
                {
                    total += read;
                    if (total > maxPackageBytes) throw new InvalidDataException("O pacote excede o tamanho máximo permitido.");
                    await output.WriteAsync(chunk.AsMemory(0, read), cancellationToken);
                    if (expectedLength is > 0) progress.Report(Math.Clamp((double)total / expectedLength.Value, 0, 1));
                }
                await output.FlushAsync(cancellationToken);
                output.Flush(true);
            }
            if (expectedLength.HasValue && new FileInfo(temporary).Length != expectedLength.Value)
                throw new EndOfStreamException("O download terminou antes de receber todos os dados.");
            var actualHash = await HashFileAsync(temporary, cancellationToken);
            var expectedHash = Convert.FromHexString(manifest.Sha256);
            var actualBytes = Convert.FromHexString(actualHash);
            if (!CryptographicOperations.FixedTimeEquals(expectedHash, actualBytes))
                throw new CryptographicException("O pacote baixado não corresponde ao SHA-256 assinado.");
            File.Move(temporary, target, true);
            progress.Report(1);
            return target;
        }
        catch
        {
            try { if (File.Exists(temporary)) File.Delete(temporary); } catch { }
            throw;
        }
    }

    public static async Task<string> HashFileAsync(string path, CancellationToken cancellationToken = default)
    {
        await using var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read, 128 * 1024, FileOptions.Asynchronous | FileOptions.SequentialScan);
        var hash = await SHA256.HashDataAsync(stream, cancellationToken);
        return Convert.ToHexString(hash).ToLowerInvariant();
    }

    private static void EnsureNoRedirect(HttpResponseMessage response)
    {
        if ((int)response.StatusCode is >= 300 and < 400)
            throw new HttpRequestException("O servidor tentou redirecionar o download para outro endereço.");
    }
}
