import ipaddress

from cryptography import x509

from mappy.tls import ensure_cert


def sans(cert_path):
    cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
    ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    return set(ext.get_values_for_type(x509.IPAddress))


def test_creates_cert_for_lan_ip(tmp_path):
    cert, key = ensure_cert(tmp_path, "192.168.43.10")
    assert cert.exists() and key.exists()
    assert ipaddress.ip_address("192.168.43.10") in sans(cert)
    assert ipaddress.ip_address("127.0.0.1") in sans(cert)


def test_reuses_cert_for_same_ip(tmp_path):
    cert, _ = ensure_cert(tmp_path, "192.168.43.10")
    first = cert.read_bytes()
    cert2, _ = ensure_cert(tmp_path, "192.168.43.10")
    assert cert2.read_bytes() == first


def test_new_cert_when_ip_changes(tmp_path):
    ensure_cert(tmp_path, "192.168.43.10")
    cert, _ = ensure_cert(tmp_path, "10.0.0.5")
    assert ipaddress.ip_address("10.0.0.5") in sans(cert)
