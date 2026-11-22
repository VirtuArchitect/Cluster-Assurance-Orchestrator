"""Shared Prism TLS policy. A custom CA adds trust; it never disables identity checks."""
import ssl


def prism_ssl_context(tls_mode: str, custom_ca_bundle: str = '') -> ssl.SSLContext:
    if tls_mode == 'insecure_skip_verify':
        return ssl._create_unverified_context()
    if tls_mode != 'strict':
        raise ValueError('Unsupported Prism TLS mode')
    context = ssl.create_default_context()
    if custom_ca_bundle:
        context.load_verify_locations(cafile=custom_ca_bundle)
    return context
