"""Read-only legacy status-protocol smoke check; no account credentials."""
import socket
import struct
import sys
import xml.etree.ElementTree as ET
host=sys.argv[1] if len(sys.argv)>1 else '127.0.0.1'
port=int(sys.argv[2]) if len(sys.argv)>2 else 7173
with socket.create_connection((host,port),timeout=10) as s:
    data=b'\xff\xffinfo'
    s.sendall(struct.pack('<H',len(data))+data)
    chunks=[]
    while True:
        chunk=s.recv(16384)
        if not chunk: break
        chunks.append(chunk)
root=ET.fromstring(b''.join(chunks))
assert root.tag=='tsqp'
print('PASS status:',root.find('serverinfo').attrib.get('servername'),
      'players=',root.find('players').attrib.get('online'),
      'uptime=',root.find('serverinfo').attrib.get('uptime'))
