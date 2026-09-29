namespace AntigasLauncher;

internal static class BoundedStreamCopy
{
    public static long Copy(Stream input, Stream output, long maxBytes)
    {
        ArgumentNullException.ThrowIfNull(input);
        ArgumentNullException.ThrowIfNull(output);
        if (maxBytes < 0) throw new ArgumentOutOfRangeException(nameof(maxBytes));

        var buffer = new byte[128 * 1024];
        long copied = 0;
        int read;
        while ((read = input.Read(buffer, 0, buffer.Length)) > 0)
        {
            if (read > maxBytes - copied)
                throw new InvalidDataException("O conteúdo expandido excede o tamanho permitido.");

            output.Write(buffer, 0, read);
            copied += read;
        }

        return copied;
    }
}
