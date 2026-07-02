"""Chat sessionization tests."""
import tempfile
from core.core.chat_store import ChatStore


def _store():
    return ChatStore(db_path=tempfile.mktemp(suffix=".db"))


def test_create_and_load():
    c = _store()
    sid = c.create_session("simha", "Chat A")
    c.save_messages(sid, [{"role": "user", "content": "hi"},
                          {"role": "assistant", "content": "hello"}])
    msgs = c.load_messages(sid)
    assert [m["role"] for m in msgs] == ["user", "assistant"]


def test_sessions_are_per_user():
    c = _store()
    c.create_session("simha")
    assert len(c.list_sessions("simha")) == 1
    assert c.list_sessions("indhumathi") == []


def test_rename_and_delete():
    c = _store()
    sid = c.create_session("u")
    c.rename_session(sid, "Renamed")
    assert c.list_sessions("u")[0]["title"] == "Renamed"
    c.delete_session(sid)
    assert c.list_sessions("u") == []


def test_derive_title_from_first_user_message():
    title = ChatStore.derive_title([{"role": "assistant", "content": "hi"},
                                    {"role": "user", "content": "what is the subsidy amount?"}])
    assert "subsidy" in title
