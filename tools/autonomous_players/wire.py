"""Bounded legacy Antigas 772 transport; see src/networkmessage.cpp.

Each connection owns one FrameCodec. A malformed frame poisons that connection:
callers must reconnect and reconstruct their observed world before acting again.
"""
import struct
from dataclasses import dataclass, field

MASK = 0xffffffff
MAX_FRAME = 65528


class ProtocolError(ValueError):
    pass


class Reader:
    def __init__(self, data):
        self.data = memoryview(data)
        self.offset = 0

    @property
    def remaining(self):
        return len(self.data) - self.offset

    def take(self, count):
        if count < 0 or count > self.remaining:
            raise ProtocolError('truncated packet')
        start = self.offset
        self.offset += count
        return bytes(self.data[start:self.offset])

    def u8(self):
        return self.take(1)[0]

    def u16(self):
        return struct.unpack('<H', self.take(2))[0]

    def u32(self):
        return struct.unpack('<I', self.take(4))[0]

    def u64(self):
        return struct.unpack('<Q', self.take(8))[0]

    def string(self, limit=8192):
        size = self.u16()
        if size > limit:
            raise ProtocolError('oversized string')
        return self.take(size).decode('latin1')


class Writer:
    def __init__(self):
        self.data = b''

    def raw(self, data):
        self.data += bytes(data)
        return self

    def _number(self, value, width):
        if not isinstance(value, int) or not 0 <= value < (1 << (width * 8)):
            raise ValueError('unsigned integer out of range')
        return self.raw(value.to_bytes(width, 'little'))

    def u8(self, value):
        return self._number(value, 1)

    def u16(self, value):
        return self._number(value, 2)

    def u32(self, value):
        return self._number(value, 4)

    def string(self, value):
        encoded = value.encode('latin1')
        return self.u16(len(encoded)).raw(encoded)


def crypt(data, key, decrypt=False):
    if len(data) % 8 or len(key) != 4 or any(not 0 <= v <= MASK for v in key):
        raise ValueError('invalid XTEA block or key')
    output = bytearray()
    for a, b in struct.iter_unpack('<II', data):
        total = 0xc6ef3720 if decrypt else 0
        for _ in range(32):
            if decrypt:
                b = (b - ((((a << 4) ^ (a >> 5)) + a) ^ (total + key[(total >> 11) & 3]))) & MASK
                total = (total - 0x9e3779b9) & MASK
                a = (a - ((((b << 4) ^ (b >> 5)) + b) ^ (total + key[total & 3]))) & MASK
            else:
                a = (a + ((((b << 4) ^ (b >> 5)) + b) ^ (total + key[total & 3]))) & MASK
                total = (total + 0x9e3779b9) & MASK
                b = (b + ((((a << 4) ^ (a >> 5)) + a) ^ (total + key[(total >> 11) & 3]))) & MASK
        output.extend(struct.pack('<II', a, b))
    return bytes(output)


class FrameCodec:
    def __init__(self, key):
        crypt(b'', key)
        self.key = tuple(key)
        self.buffer = bytearray()
        self.failed = False

    def encode(self, payload):
        if len(payload) > MAX_FRAME - 2:
            raise ValueError('oversized payload')
        plain = struct.pack('<H', len(payload)) + payload
        plain += bytes((-len(plain)) % 8)
        encrypted = crypt(plain, self.key)
        return struct.pack('<H', len(encrypted)) + encrypted

    def feed(self, incoming):
        if self.failed:
            raise ProtocolError('connection already invalid')
        if len(incoming) + len(self.buffer) > 1048576:
            self.failed = True
            raise ProtocolError('receive buffer limit')
        self.buffer.extend(incoming)
        output = []
        try:
            while len(self.buffer) >= 2:
                size = struct.unpack_from('<H', self.buffer)[0]
                if not size or size % 8 or size > MAX_FRAME:
                    raise ProtocolError('invalid encrypted frame length')
                if len(self.buffer) < size + 2:
                    break
                plain = crypt(self.buffer[2:size + 2], self.key, True)
                count = struct.unpack_from('<H', plain)[0]
                if count > size - 2:
                    raise ProtocolError('invalid inner payload length')
                output.append(plain[2:2 + count])
                del self.buffer[:size + 2]
        except ProtocolError:
            self.failed = True
            self.buffer.clear()
            raise
        return output


def rsa_block(plain, modulus):
    if len(plain) > 128 or not plain or plain[0] != 0 or modulus.bit_length() != 1024:
        raise ValueError('invalid 1024-bit login block')
    number = int.from_bytes(plain.ljust(128, b'\0'), 'big')
    if number >= modulus:
        raise ValueError('RSA plaintext out of range')
    return pow(number, 65537, modulus).to_bytes(128, 'big')


@dataclass(frozen=True)
class LoginCredentials:
    account: int
    character: str
    password: str = field(repr=False)

    def packet(self, key, modulus):
        plain = Writer().u8(0)
        for value in key:
            plain.u32(value)
        plain.u8(0).u32(self.account).string(self.character).string(self.password)
        packet = Writer().u8(0x0a).u16(11).u16(772).raw(rsa_block(plain.data, modulus)).data
        return Writer().u16(len(packet)).raw(packet).data
