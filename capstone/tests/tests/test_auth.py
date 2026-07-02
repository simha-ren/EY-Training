"""Auth + sessionization tests."""
import tempfile
from core.core.auth import AuthStore


def _store():
    return AuthStore(db_path=tempfile.mktemp(suffix=".db"), seed_default=False)


def test_create_and_verify():
    a = _store()
    assert a.create_user("simha", "secret123")
    assert a.verify_password("simha", "secret123") is True
    assert a.verify_password("simha", "wrong") is False


def test_duplicate_user_rejected():
    a = _store()
    assert a.create_user("indhumathi", "pw123456")
    assert a.create_user("indhumathi", "pw123456") is False


def test_session_lifecycle():
    a = _store()
    a.create_user("u", "pw123456")
    tok = a.login("u", "pw123456")
    assert tok and a.validate_session(tok) == "u"
    a.end_session(tok)
    assert a.validate_session(tok) is None


def test_login_bad_credentials():
    a = _store()
    a.create_user("u", "pw123456")
    assert a.login("u", "nope") is None


def test_password_is_hashed_not_plaintext():
    a = _store()
    a.create_user("u", "plaintextpw")
    rec = a.get_user("u")
    assert rec["pwd_hash"] != b"plaintextpw"
