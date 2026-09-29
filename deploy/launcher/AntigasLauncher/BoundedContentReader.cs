using System.IO;

namespace AntigasLauncher;

internal static class BoundedContentReader
{
    public static async Task<byte[]> ReadAsync(Stream input, int maxBytes, CancellationToken cancellationToken)
    {
        if (maxBytes < 0) throw new ArgumentOutOfRangeException(nameof(maxBytes));

        using var output = new MemoryStream(Math.Min(maxBytes, 8192));
        var chunk = new byte[8192];
        int read;
        while ((read = await input.ReadAsync(chunk.AsMemory(), cancellationToken)) > 0)
        {
            if (output.Length + read > maxBytes)
                throw new InvalidDataException("O conteúdo excede o tamanho permitido.");
            await output.WriteAsync(chunk.AsMemory(0, read), cancellationToken);
        }

        return output.ToArray();
    }
}
