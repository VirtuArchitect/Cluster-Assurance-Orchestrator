"""TLS contract tests with temporary synthetic CA and server certificates."""
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from threading import Thread
from contextlib import contextmanager
import shutil,ssl,subprocess
import pytest
from app.core.config import Settings
from app.core.tls import prism_ssl_context
from app.adapters.nutanix import EndpointConfig,NutanixReadOnlyAdapter
from app.domain.discovery import EndpointKind
from app.services.admin_store import AdminStore,seal_secret,probe_connection_row

@pytest.fixture(scope='module')
def certs(tmp_path_factory):
    openssl=shutil.which('openssl') or ('C:/Program Files/Git/usr/bin/openssl.exe' if Path('C:/Program Files/Git/usr/bin/openssl.exe').exists() else None)
    if not openssl: pytest.skip('OpenSSL is required for real TLS fixture generation')
    root=tmp_path_factory.mktemp('synthetic-tls')
    def run(*args):subprocess.run([openssl,*args],cwd=root,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    run('req','-x509','-newkey','rsa:2048','-nodes','-keyout','ca.key','-out','ca.pem','-days','2','-subj','/CN=Example Test CA','-addext','basicConstraints=critical,CA:TRUE','-addext','keyUsage=critical,keyCertSign,cRLSign')
    run('req','-newkey','rsa:2048','-nodes','-keyout','server.key','-out','server.csr','-subj','/CN=localhost')
    (root/'server.ext').write_text('subjectAltName=DNS:localhost,IP:127.0.0.1\nbasicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n')
    run('x509','-req','-in','server.csr','-CA','ca.pem','-CAkey','ca.key','-CAcreateserial','-out','server.pem','-days','1','-extfile','server.ext')
    (root/'index.txt').write_text('')
    (root/'serial.txt').write_text('01')
    (root/'ca.conf').write_text('[ca]\ndefault_ca=issuer\n[issuer]\ndatabase=index.txt\nnew_certs_dir=.\ncertificate=ca.pem\nprivate_key=ca.key\nserial=serial.txt\ndefault_md=sha256\npolicy=names\n[names]\ncommonName=supplied\n[server_ext]\n'+(root/'server.ext').read_text())
    run('ca','-batch','-notext','-config','ca.conf','-in','server.csr','-out','expired.pem','-startdate','20200101000000Z','-enddate','20200102000000Z','-extensions','server_ext')
    return root

@contextmanager
def tls_server(certs,expired=False):
    requests=[]
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append((self.command,self.path));self.send_response(200);self.end_headers();self.wfile.write(b'{}')
        def log_message(self,*_):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(str(certs/('expired.pem' if expired else 'server.pem')),str(certs/'server.key'))
    server.socket=context.wrap_socket(server.socket,server_side=True)
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try:yield f'https://127.0.0.1:{server.server_port}',requests
    finally:server.shutdown();server.server_close();thread.join()

def test_private_ca_validates_both_probe_and_collector_without_disabling_identity(certs):
    with tls_server(certs) as (url,requests):
        settings=Settings(demo_mode=False,custom_ca_bundle=str(certs/'ca.pem'))
        row={'type':'Prism Element','url':url,'username':'example','secret_ciphertext':seal_secret('synthetic',settings.auth_secret),'tls_mode':'strict'}
        context=prism_ssl_context('strict',settings.custom_ca_bundle)
        assert context.check_hostname and context.verify_mode==ssl.CERT_REQUIRED
        assert probe_connection_row(row,settings.auth_secret,settings.custom_ca_bundle)[0]=='READY'
        response=NutanixReadOnlyAdapter(settings)._request(EndpointConfig(EndpointKind.PRISM_ELEMENT,'pe',url,'example','synthetic'),'GET','/PrismGateway/services/rest/v2.0/cluster/')
        assert response.status_code==200
        assert requests==[('GET','/PrismGateway/services/rest/v2.0/cluster/')]*2

def test_untrusted_or_expired_tls_never_sends_an_authenticated_http_request(certs):
    for expired in (False,True):
        with tls_server(certs,expired) as (url,requests):
            ca=str(certs/'ca.pem') if expired else ''
            settings=Settings(demo_mode=False,custom_ca_bundle=ca)
            row={'type':'Prism Element','url':url,'username':'example','secret_ciphertext':seal_secret('synthetic',settings.auth_secret),'tls_mode':'strict'}
            assert probe_connection_row(row,settings.auth_secret,ca)[0]=='TLS_FAILED'
            response=NutanixReadOnlyAdapter(settings)._request(EndpointConfig(EndpointKind.PRISM_ELEMENT,'pe',url,'example','synthetic'),'GET','/cluster/')
            assert response.status_code is None and response.error
            assert not requests

def test_wrong_hostname_is_rejected_even_with_trusted_ca(certs):
    import socket
    from urllib.parse import urlsplit
    with tls_server(certs) as (url,requests):
        context=prism_ssl_context('strict',str(certs/'ca.pem'))
        with socket.create_connection(('127.0.0.1',urlsplit(url).port)) as sock:
            with pytest.raises(ssl.SSLCertVerificationError):context.wrap_socket(sock,server_hostname='wrong.example.invalid')
        assert not requests

def test_missing_or_invalid_trust_fails_without_network_or_insecure_fallback(tmp_path,monkeypatch):
    row={'type':'Prism Element','url':'https://pe.example.invalid','username':'example','secret_ciphertext':seal_secret('synthetic','test'),'tls_mode':'strict'}
    def forbidden(*_,**__):raise AssertionError('No request may be sent with broken trust configuration')
    monkeypatch.setattr('app.services.admin_store.urlopen',forbidden)
    missing=tmp_path/'missing.pem'
    assert probe_connection_row(row,'test',str(missing))[0]=='TLS_FAILED'
    with pytest.raises(OSError):prism_ssl_context('strict',str(missing))
    missing.write_text('not a certificate')
    assert probe_connection_row(row,'test',str(missing))[0]=='TLS_FAILED'
    with pytest.raises(ValueError):prism_ssl_context('unexpected')

def test_strict_saved_connections_override_legacy_insecure_default(tmp_path):
    settings=Settings(tls_mode='insecure_skip_verify',admin_db_path=str(tmp_path/'admin.sqlite3'))
    store=AdminStore(settings)
    # Use the actual seeded admin principal through the normal authentication path.
    token=store.login('admin',settings.bootstrap_admin_password)['token']
    actor=store.principal_from_token(token)
    store.upsert_connection({'name':'Example PE','type':'Prism Element','url':'https://pe.example.invalid','username':'example','password':'synthetic','tls_mode':'strict'},actor)
    effective=store.inventory_settings_from_connections()
    assert effective.tls_mode=='strict' and effective.read_only_mode
    assert not effective.enable_ssh and not effective.enable_ncc
