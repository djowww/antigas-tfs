"""7.72 framed XTEA transport for staging tests; no login keys or fixtures.

The caller supplies an already connected socket, a four-word session key and
an empty bytes buffer. Login/RSA handling belongs to the staging harness.
"""
import socket
import struct
import time

MASK = 0xFFFFFFFF


def string(value):
    encoded = value.encode("latin1")
    return struct.pack("<H", len(encoded)) + encoded


def crypt(data, key, decrypt=False):
    output = bytearray()
    for offset in range(0, len(data), 8):
        a, b = struct.unpack_from("<II", data, offset)
        total = 0xC6EF3720 if decrypt else 0
        for _ in range(32):
            if decrypt:
                b = (b - ((((a << 4) ^ (a >> 5)) + a) ^ (total + key[(total >> 11) & 3]))) & MASK
                total = (total - 0x9E3779B9) & MASK
                a = (a - ((((b << 4) ^ (b >> 5)) + b) ^ (total + key[total & 3]))) & MASK
            else:
                a = (a + ((((b << 4) ^ (b >> 5)) + b) ^ (total + key[total & 3]))) & MASK
                total = (total + 0x9E3779B9) & MASK
                b = (b + ((((a << 4) ^ (a >> 5)) + a) ^ (total + key[(total >> 11) & 3]))) & MASK
        output += struct.pack("<II", a, b)
    return bytes(output)


class Client:
    def send(self, data):
        plain = struct.pack("<H", len(data)) + data
        plain += b"\0" * ((-len(plain)) % 8)
        encrypted = crypt(plain, self.key)
        self.sock.sendall(struct.pack("<H", len(encrypted)) + encrypted)

    def collect(self, seconds=2):
        end = time.monotonic() + seconds
        decoded = b""
        while time.monotonic() < end:
            self.sock.settimeout(max(0.05, end - time.monotonic()))
            try:
                data = self.sock.recv(65536)
            except socket.timeout:
                break
            if not data:
                break
            self.buffer += data
            while len(self.buffer) >= 2:
                size = struct.unpack_from("<H", self.buffer)[0]
                if len(self.buffer) < size + 2:
                    break
                packet = crypt(self.buffer[2:size + 2], self.key, True)
                self.buffer = self.buffer[size + 2:]
                count = struct.unpack_from("<H", packet)[0]
                payload = packet[2:count + 2]
                decoded += payload
                if payload == b"\x1d":
                    self.send(b"\x1e")
        return decoded
