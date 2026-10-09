"""Self-signed HTTPS certificate for the laptop's current LAN address.

Browsers only allow the microphone on secure (https) pages. With no internet there is no way to get
a publicly trusted certificate, so each phone accepts this one once ("Advanced -> Proceed").
"""

import datetime as dt
import ipaddress
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

VALID_DAYS = 30


def _covers(cert_path: Path, ip: str) -> bool:
    try:
        cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
        ips = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.IPAddress)
        return ipaddress.ip_address(ip) in ips and cert.not_valid_after_utc > dt.datetime.now(dt.timezone.utc)
    except (OSError, ValueError, x509.ExtensionNotFound):
        return False


def ensure_cert(directory: Path, ip: str) -> tuple[Path, Path]:
    """Return (cert, key) PEM paths valid for `ip`, creating new ones if missing, expired, or for another IP."""
    directory.mkdir(parents=True, exist_ok=True)
    cert_path, key_path = directory / "mappy-cert.pem", directory / "mappy-key.pem"
    if cert_path.exists() and key_path.exists() and _covers(cert_path, ip):
        return cert_path, key_path
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Mappy (local)")])
    now = dt.datetime.now(dt.timezone.utc)
    san = x509.SubjectAlternativeName([
        x509.IPAddress(ipaddress.ip_address(ip)),
        x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
        x509.DNSName("localhost"),
    ])
    cert = (x509.CertificateBuilder()
            .subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - dt.timedelta(minutes=5)).not_valid_after(now + dt.timedelta(days=VALID_DAYS))
            .add_extension(san, critical=False)
            .sign(key, hashes.SHA256()))
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                           serialization.NoEncryption()))
    return cert_path, key_path
