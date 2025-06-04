import collections
import contextlib
from datetime import datetime, timedelta
import socket
import os
import shutil
import subprocess
import sys
import tempfile
import time

import pytest

import labrad
from labrad import crypto
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa





@contextlib.contextmanager
def temp_tls_dirs():
    """Context manager to create temporary dirs for labrad TLS certs and keys.

    Also overrides the path labrad.crypto.CERTS_PATH where we look for trusted
    certs to correspond to the temporary directory. If we then also point the
    manager to this directory to store its generated self-signed certificates,
    then we will automatically trust those certificates.

    Yields (string, string):
        A tuple of paths for the TLS certs and keys, respectively.
    """
    user_dir = os.path.expanduser('~')
    cert_path = tempfile.mkdtemp(prefix='.labrad-test-certs', dir=user_dir)
    key_path = tempfile.mkdtemp(prefix='.labrad-test-keys', dir=user_dir)
    old_cert_path = crypto.CERTS_PATH
    crypto.CERTS_PATH = cert_path
    try:
        # generate a localhost certificate with SAN so hostname verification passes
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.utcnow() - timedelta(days=1))
            .not_valid_after(datetime.utcnow() + timedelta(days=1))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False)
            .sign(key, hashes.SHA256())
        )
        cert_file = os.path.join(cert_path, "localhost.cert")
        key_file = os.path.join(key_path, "localhost.key")
        with open(cert_file, "wb") as cf:
            cf.write(cert.public_bytes(serialization.Encoding.PEM))
        with open(key_file, "wb") as kf:
            kf.write(
                key.private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.TraditionalOpenSSL,
                    serialization.NoEncryption(),
                )
            )
        yield cert_path, key_path
    finally:
        crypto.CERTS_PATH = old_cert_path
        shutil.rmtree(cert_path)
        shutil.rmtree(key_path)


# Manager Info class returned by the run_manager cont
ManagerInfo = collections.namedtuple('ManagerInfo', ['port', 'tls_port', 'password'])


def _free_port():
    s = socket.socket()
    s.bind(('', 0))
    p = s.getsockname()[1]
    s.close()
    return p

@contextlib.contextmanager
def run_manager(tls_required, port=None, tls_port=None, startup_timeout=20):
    """Context manager to run the labrad manager in a subprocess.

    Will attempt to connect to the manager and fail if we cannot do so within
    the specified timeout. This ensures that the manager is actually running
    and listening for connections before we yield to execute the body of the
    with statement.

    Args:
        tls_required (boolean): Whether the manager should require TLS.
        port (int): The port on which to listen for upgradeable connections
            that start unencrypted and then use STARTTLS to secure the
            connection.
        tls_port (int): The port on which to listen for TLS connections that
            are encrpyted from the start.
        startup_timeout (float): Maximum number of seconds to allow for the
            manager to start before we fail.

    Yields (ManagerInfo):
        Info about the running manager.
    """
    if port is None:
        port = _free_port()
    if tls_port is None:
        tls_port = _free_port()
    with temp_tls_dirs() as (cert_path, key_path):
        password = 'DummyPassword'
        cert_file = os.path.join(cert_path, 'localhost.cert')
        key_file = os.path.join(key_path, 'localhost.key')
        manager = subprocess.Popen([
                'labrad',
                '--password={}'.format(password),
                '--port={}'.format(port),
                '--tls-port={}'.format(tls_port),
                '--tls-required={}'.format(tls_required),
                '--tls-required-localhost={}'.format(tls_required),
                '--tls-cert-path={}'.format(cert_path),
                '--tls-key-path={}'.format(key_path),
                '--tls-hosts=localhost?cert={}&key={}'.format(cert_file, key_file)])
        try:
            start = time.time()
            while True:
                try:
                    labrad.connect(port=tls_port, tls_mode='on', password=password, timeout=5)
                except Exception as e:
                    last_error = e
                else:
                    break
                elapsed = time.time() - start
                if elapsed > startup_timeout:
                    raise Exception('labrad failed to start within {} seconds. '
                                    'last_error={}'
                                    .format(startup_timeout, last_error))
                time.sleep(0.5)
            yield ManagerInfo(port, tls_port, password)
        finally:
            manager.terminate()
            try:
                manager.wait(timeout=5)
            except Exception:
                manager.kill()


# Test that we can establish encrypted TLS connections to the manager

def test_connect_with_starttls():
    with run_manager(tls_required=True) as m:
        with labrad.connect(port=m.port, tls_mode='starttls-force', password=m.password, timeout=5) as cxn:
            pass


def test_connect_with_optional_starttls():
    with run_manager(tls_required=False) as m:
        with labrad.connect(port=m.port, tls_mode='off', password=m.password, timeout=5) as cxn:
            pass


def test_connect_with_tls():
    with run_manager(tls_required=True) as m:
        with labrad.connect(port=m.tls_port, tls_mode='on', password=m.password, timeout=5) as cxn:
            pass


# Test that connecting to the manager fails if the client fails to
# use TLS when the manager expects it.

def test_expect_starttls_use_off():
    with run_manager(tls_required=True) as m:
        with pytest.raises(Exception):
            with labrad.connect(port=m.port, tls_mode='off', password=m.password, timeout=5) as cxn:
                pass


def test_expect_tls_use_off():
    with run_manager(tls_required=True) as m:
        with pytest.raises(Exception):
            with labrad.connect(port=m.tls_port, tls_mode='off', password=m.password, timeout=5) as cxn:
                pass


def test_expect_tls_use_starttls():
    with run_manager(tls_required=True) as m:
        with pytest.raises(Exception):
            with labrad.connect(port=m.tls_port, tls_mode='off', password=m.password, timeout=5) as cxn:
                pass


if __name__ == '__main__':
    pytest.main(['-v', __file__])
