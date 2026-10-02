import pytest

from multimodal_agents.safe_url_fetch import UnsafeURLError, _is_public_ip, validate_remote_url


def test_cloud_metadata_address_is_rejected():
    assert _is_public_ip("169.254.169.254") is False


def test_loopback_address_is_rejected():
    assert _is_public_ip("127.0.0.1") is False


def test_private_network_addresses_are_rejected():
    for ip in ("10.0.0.5", "172.16.0.5", "192.168.1.5"):
        assert _is_public_ip(ip) is False


def test_a_real_public_address_is_accepted():
    assert _is_public_ip("8.8.8.8") is True


def test_non_http_scheme_is_rejected():
    with pytest.raises(UnsafeURLError):
        validate_remote_url("file:///etc/passwd")


def test_localhost_hostname_is_rejected_via_dns_resolution():
    with pytest.raises(UnsafeURLError):
        validate_remote_url("http://localhost/evidence.png")


def test_missing_hostname_is_rejected():
    with pytest.raises(UnsafeURLError):
        validate_remote_url("http:///path-with-no-host")


def test_allowlist_blocks_hosts_not_on_it(monkeypatch):
    monkeypatch.setenv("TENANT_FETCH_ALLOWED_HOSTS", "trusted-bucket.example.com")
    with pytest.raises(UnsafeURLError):
        validate_remote_url("https://example.com/evidence.png")
