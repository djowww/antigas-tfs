"""Generate an installation-specific RSA key, then run only the local server."""
import os
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import rsa
state=Path('/local-state');state.mkdir(exist_ok=True)
key=state/'rsa.txt'
if not key.exists():
    n=rsa.generate_private_key(public_exponent=65537,key_size=1024).private_numbers()
    fd=os.open(key,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:f.write(str(n.p)+'\n'+str(n.q)+'\n')
p,q=map(int,key.read_text().split());(state/'public-modulus.txt').write_text(str(p*q))
os.execv('./tfs',['./tfs'])
