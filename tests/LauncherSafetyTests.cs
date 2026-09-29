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

Console.WriteLine("Launcher bounded I/O regression tests passed");
