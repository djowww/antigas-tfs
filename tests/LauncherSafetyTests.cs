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

Console.WriteLine("Launcher bounded-read regression tests passed");
