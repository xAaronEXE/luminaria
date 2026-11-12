"""TLS identity for direct PC pairing, verified against a fingerprint shown on the host."""

import hashlib
import hmac
import os
import ssl
from datetime import datetime, timedelta, timezone

from .config import BASE_DATA


def identity():
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    folder = BASE_DATA / 'peer-tls'
    folder.mkdir(mode=0o700, exist_ok=True)
    cert, key = folder / 'certificate.pem', folder / 'key.pem'
    if not cert.is_file() or not key.is_file():
        private = ec.generate_private_key(ec.SECP256R1())
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Luminaria paired PC')])
        now = datetime.now(timezone.utc)
        signed = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
                  .public_key(private.public_key()).serial_number(x509.random_serial_number())
                  .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=1825))
                  .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
                  .sign(private, hashes.SHA256()))
        temp = key.with_suffix('.tmp')
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'wb') as out:
            out.write(private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                            serialization.NoEncryption()))
        os.replace(temp, key)
        cert.write_bytes(signed.public_bytes(serialization.Encoding.PEM))
    return cert, key


def fingerprint(pem):
    return hashlib.sha256(ssl.PEM_cert_to_DER_cert(pem)).hexdigest()


def verify_peer(address, port, expected):
    pem = ssl.get_server_certificate((address, port), timeout=8)
    if not hmac.compare_digest(fingerprint(pem), expected):
        raise ValueError('The certificate does not match the fingerprint on the other PC.')
    return pem


def client_context(pem):
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False  # Trust only the certificate verified during pairing.
    context.load_verify_locations(cadata=pem)
    return context
