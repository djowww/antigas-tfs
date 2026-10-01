using AntigasLauncher;

const int limit = 65536;
var accepted = Enumerable.Range(0, limit).Select(i => (byte)i).ToArray();
await using (var stream = new MemoryStream(accepted))
{
    var read = await BoundedContentReader.ReadAsync(stream, limit, CancellationToken.None);
    if (!read.SequenceEqual(accepted)) throw new InvalidOperationException("The exact-limit body changed while reading.");
}

await using (var stream = new MemoryStream(new byte[limit + 1]))
{
    try
    {
        await BoundedContentReader.ReadAsync(stream, limit, CancellationToken.None);
        throw new InvalidOperationException("An oversized body was accepted.");
    }
    catch (InvalidDataException)
    {
    }
}

await using (var input = new MemoryStream(accepted))
await using (var output = new MemoryStream())
{
    var copied = BoundedStreamCopy.Copy(input, output, limit);
    if (copied != limit || !output.ToArray().SequenceEqual(accepted))
        throw new InvalidOperationException("The exact-limit stream copy changed the content.");
}

await using (var input = new MemoryStream(new byte[limit + 1]))
await using (var output = new MemoryStream())
{
    try
    {
        BoundedStreamCopy.Copy(input, output, limit);
        throw new InvalidOperationException("An oversized stream copy was accepted.");
    }
    catch (InvalidDataException)
    {
        if (output.Length > limit) throw new InvalidOperationException("The stream copy wrote beyond its configured limit.");
    }
}

var manifest = new ReleaseManifest { Version = 54, Package = "Antigas-7.4-Update-v54.zip" };
var stagingBase = new Uri("https://tibia74.tech/staging/v54/");
var stagingPackage = ReleaseService.ResolvePackageUri(manifest, stagingBase);
if (stagingPackage.AbsoluteUri != "https://tibia74.tech/staging/v54/Antigas-7.4-Update-v54.zip")
    throw new InvalidOperationException("The signed package must resolve beside the staging manifest.");
var stagingSubdomainPackage = ReleaseService.ResolvePackageUri(manifest, new Uri("https://staging.tibia74.tech/releases/v54/"));
if (stagingSubdomainPackage.AbsoluteUri != "https://staging.tibia74.tech/releases/v54/Antigas-7.4-Update-v54.zip")
    throw new InvalidOperationException("An official staging subdomain must remain usable.");
if (!ReleaseService.IsStagingManifestUri(new Uri("https://tibia74.tech/staging/v54/client-release.json")) ||
    !ReleaseService.IsStagingManifestUri(new Uri("https://staging.tibia74.tech/client-release.json")))
    throw new InvalidOperationException("Supported staging manifest locations must be accepted.");
if (ReleaseService.IsStagingManifestUri(new Uri("https://tibia74.tech/client-release.json")) ||
    ReleaseService.IsStagingManifestUri(new Uri("https://downloads.tibia74.tech/client-release.json")) ||
    ReleaseService.IsStagingManifestUri(new Uri("https://tibia74.tech/staging/client-release.json?cache=1")) ||
    ReleaseService.IsStagingManifestUri(new Uri("https://user@staging.tibia74.tech/client-release.json")) ||
    ReleaseService.IsStagingManifestUri(new Uri("https://staging.tibia74.tech:444/client-release.json")) ||
    ReleaseService.IsStagingManifestUri(new Uri("https://staging.tibia74.tech/client-release.json#fragment")))
    throw new InvalidOperationException("Production, unmarked subdomains, or credential/port/query/fragment-based manifest URLs must not count as staging.");

foreach (var unsafeBase in new[]
{
    new Uri("http://tibia74.tech/staging/v54/"),
    new Uri("https://attacker.example/staging/v54/"),
    new Uri("https://evil-tibia74.tech/staging/v54/"),
    new Uri("https://tibia74.tech.attacker.example/staging/v54/"),
    new Uri("https://user@tibia74.tech/staging/v54/"),
    new Uri("https://tibia74.tech:444/staging/v54/"),
    new Uri("https://tibia74.tech/staging/v54?redirect=1"),
    new Uri("https://tibia74.tech/staging/v54"),
})
{
    try
    {
        ReleaseService.ResolvePackageUri(manifest, unsafeBase);
        throw new InvalidOperationException("An unsafe staging package base was accepted: " + unsafeBase);
    }
    catch (InvalidDataException)
    {
    }
}

try
{
    ReleaseService.ResolvePackageUri(new ReleaseManifest { Version = 54, Package = "../outside.zip" }, stagingBase);
    throw new InvalidOperationException("A package path outside the signed version name was accepted.");
}
catch (InvalidDataException)
{
}

Console.WriteLine("Launcher bounded I/O and staging URL regression tests passed");
