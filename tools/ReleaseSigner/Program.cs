using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

const string KeyName = "Antigas.ClientRelease.Signing.P256.v1";
const string CanonicalPrefix = "ANTIGAS-CLIENT-RELEASE-V1";
const string PinnedPublicKey = "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAELyhqZ/vlL8gMrlo3VHBmfALsf3k/RZaJyErvum5sJjUFabJRQqVtzn4j9JqR/iYgU5VRyuKiG0tRP6pCo4btJg==";

if (args.Length == 2 && args[0] == "keygen")
{
    using var key = OpenOrCreateSigningKey();
    using var signer = new ECDsaCng(key);
    var publicKey = Convert.ToBase64String(signer.ExportSubjectPublicKeyInfo());
    File.WriteAllText(Path.GetFullPath(args[1]), publicKey + Environment.NewLine, new UTF8Encoding(false));
    Console.WriteLine("Created or opened the current-user signing key.");
    Console.WriteLine($"Public key written to: {Path.GetFullPath(args[1])}");
    Console.WriteLine("The private key remains non-exportable in the Windows user key store.");
    return;
}

if (args.Length == 5 && args[0] == "sign")
{
    if (!int.TryParse(args[1], NumberStyles.None, CultureInfo.InvariantCulture, out var version) || version < 1 || version > 1_000_000)
        throw new ArgumentException("Version must be an integer from 1 to 1000000.");
    var packagePath = Path.GetFullPath(args[2]);
    var package = args[3];
    var outputPath = Path.GetFullPath(args[4]);
    if (!string.Equals(package, Path.GetFileName(package), StringComparison.Ordinal) ||
        !string.Equals(package, $"Antigas-7.4-Update-v{version}.zip", StringComparison.Ordinal))
        throw new ArgumentException("Package name must match the selected version.");
    if (!File.Exists(packagePath)) throw new FileNotFoundException("Package not found.", packagePath);

    using var packageStream = File.OpenRead(packagePath);
    var hash = Convert.ToHexString(SHA256.HashData(packageStream)).ToLowerInvariant();
    var canonical = Encoding.UTF8.GetBytes($"{CanonicalPrefix}\n{version}\n{package}\n{hash}\n");
    using var key = OpenExistingSigningKey();
    using var signer = new ECDsaCng(key);
    var publicKey = signer.ExportSubjectPublicKeyInfo();
    if (!CryptographicOperations.FixedTimeEquals(publicKey, Convert.FromBase64String(PinnedPublicKey)))
        throw new CryptographicException("The local signing key does not match the public key pinned in the launcher.");
    var signature = Convert.ToBase64String(signer.SignData(canonical, HashAlgorithmName.SHA256, DSASignatureFormat.IeeeP1363FixedFieldConcatenation));
    using var verifier = ECDsa.Create();
    verifier.ImportSubjectPublicKeyInfo(publicKey, out _);
    if (!verifier.VerifyData(canonical, Convert.FromBase64String(signature), HashAlgorithmName.SHA256, DSASignatureFormat.IeeeP1363FixedFieldConcatenation))
        throw new CryptographicException("The generated release signature could not be verified.");
    var manifest = new ReleaseManifest(version, $"Antigas 7.4 v{version}", hash, package, "ECDSA-P256-SHA256-P1363", signature);
    var json = JsonSerializer.Serialize(manifest, new JsonSerializerOptions { WriteIndented = true }) + Environment.NewLine;
    Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
    File.WriteAllText(outputPath, json, new UTF8Encoding(false));
    Console.WriteLine($"Signed release {version}; package SHA-256: {hash}");
    Console.WriteLine($"Manifest written to: {outputPath}");
    return;
}

Console.Error.WriteLine("Usage:");
Console.Error.WriteLine("  ReleaseSigner keygen <public-key-output.txt>");
Console.Error.WriteLine("  ReleaseSigner sign <version> <package.zip> <package-name> <manifest-output.json>");
Environment.ExitCode = 2;

static CngKey OpenOrCreateSigningKey()
{
    try
    {
        return CngKey.Open(KeyName, CngProvider.MicrosoftSoftwareKeyStorageProvider, CngKeyOpenOptions.None);
    }
    catch (CryptographicException)
    {
        var parameters = new CngKeyCreationParameters
        {
            Provider = CngProvider.MicrosoftSoftwareKeyStorageProvider,
            KeyUsage = CngKeyUsages.Signing,
            ExportPolicy = CngExportPolicies.None,
            KeyCreationOptions = CngKeyCreationOptions.None
        };
        return CngKey.Create(CngAlgorithm.ECDsaP256, KeyName, parameters);
    }
}

static CngKey OpenExistingSigningKey() => CngKey.Open(KeyName, CngProvider.MicrosoftSoftwareKeyStorageProvider, CngKeyOpenOptions.None);

sealed record ReleaseManifest(int version, string name, string sha256, string package, string signatureAlgorithm, string signature);
