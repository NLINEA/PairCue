import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from check_docs import check_markdown_links  # noqa: E402
from check_secrets import scan_files  # noqa: E402


def test_repository_documentation_has_no_broken_local_links() -> None:
    root = Path(__file__).parents[1]

    assert check_markdown_links(root) == []


def test_documentation_check_reports_a_missing_target(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("[Missing](docs/missing.md)\n", encoding="utf-8")

    failures = check_markdown_links(tmp_path)

    assert len(failures) == 1
    assert "missing target" in failures[0]


def test_secret_check_reports_only_location_and_category() -> None:
    fake_key = "sk-" + "A" * 30

    findings = scan_files([(".env.local", f"SERVICE_API_KEY={fake_key}\n".encode())])

    assert (".env.local", "sensitive filename") in findings
    assert (".env.local", "OpenAI-style API key") in findings
    assert all(fake_key not in item for finding in findings for item in finding)


def test_secret_check_allows_public_certificate_bundles_but_not_private_keys() -> None:
    certificate = b"-----BEGIN CERTIFICATE-----\npublic-ca-data\n-----END CERTIFICATE-----\n"
    private_key = (
        b"-----BEGIN "
        + b"PRIVATE KEY-----\nprivate-material\n-----END "
        + b"PRIVATE KEY-----\n"
    )

    assert scan_files([("cacert.pem", certificate)]) == []
    assert scan_files([("identity.pem", private_key)]) == [("identity.pem", "private key")]
