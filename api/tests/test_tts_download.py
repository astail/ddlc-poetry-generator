"""Tests for atomic, integrity-checked Piper voice downloads (#65)."""

import hashlib
from pathlib import Path

import pytest

from app import tts


def _fake_retrieve(content_by_suffix):
    """Build a urlretrieve stub that writes bytes based on the URL suffix."""

    def fake(url, filename):
        data = content_by_suffix[".json" if url.endswith(".json") else ".onnx"]
        Path(filename).write_bytes(data)

    return fake


def test_download_atomic_success(tmp_path, monkeypatch):
    data = b"piper-model-bytes"
    monkeypatch.setattr(tts.urllib.request, "urlretrieve", _fake_retrieve({".onnx": data}))
    dest = tmp_path / "v.onnx"
    tts._download_atomic(
        "http://x/v.onnx",
        dest,
        expected_size=len(data),
        expected_sha256=hashlib.sha256(data).hexdigest(),
    )
    assert dest.read_bytes() == data
    assert not (tmp_path / "v.onnx.part").exists()  # temp cleaned up


def test_download_atomic_size_mismatch_leaves_no_files(tmp_path, monkeypatch):
    monkeypatch.setattr(tts.urllib.request, "urlretrieve", _fake_retrieve({".onnx": b"short"}))
    dest = tmp_path / "v.onnx"
    with pytest.raises(OSError, match="size mismatch"):
        tts._download_atomic("http://x/v.onnx", dest, expected_size=9999)
    assert not dest.exists()  # never placed
    assert not (tmp_path / "v.onnx.part").exists()  # partial removed


def test_download_atomic_sha_mismatch_leaves_no_files(tmp_path, monkeypatch):
    monkeypatch.setattr(tts.urllib.request, "urlretrieve", _fake_retrieve({".onnx": b"data"}))
    dest = tmp_path / "v.onnx"
    with pytest.raises(OSError, match="sha256 mismatch"):
        tts._download_atomic("http://x/v.onnx", dest, expected_sha256="00" * 32)
    assert not dest.exists()
    assert not (tmp_path / "v.onnx.part").exists()


def test_ensure_voice_redownloads_truncated_cache(tmp_path, monkeypatch):
    name = "fake-voice"
    content = b"x" * 256
    monkeypatch.setitem(tts.VOICE_URLS, name, "http://x/fake.onnx")
    monkeypatch.setitem(tts.VOICE_SIZE, name, len(content))
    monkeypatch.setitem(tts.VOICE_SHA256, name, hashlib.sha256(content).hexdigest())
    monkeypatch.setattr(
        tts.urllib.request,
        "urlretrieve",
        _fake_retrieve({".onnx": content, ".json": b"{}"}),
    )

    syn = tts.PiperSynthesizer(data_dir=tmp_path)
    vd = tmp_path / "voices"
    vd.mkdir(parents=True)
    # A truncated cached model from an interrupted download must NOT be trusted.
    (vd / f"{name}.onnx").write_bytes(b"truncated")
    (vd / f"{name}.onnx.json").write_bytes(b"{}")

    onnx = syn._ensure_voice(name)
    assert onnx.read_bytes() == content  # self-healed via re-download


def test_ensure_voice_reuses_valid_cache_without_download(tmp_path, monkeypatch):
    name = "fake-voice"
    content = b"y" * 128
    monkeypatch.setitem(tts.VOICE_SIZE, name, len(content))
    # No VOICE_URLS entry: a download attempt would raise ValueError, so a clean
    # return proves the valid cache was reused.

    def boom(*a, **k):
        raise AssertionError("should not download a valid cache")

    monkeypatch.setattr(tts.urllib.request, "urlretrieve", boom)

    syn = tts.PiperSynthesizer(data_dir=tmp_path)
    vd = tmp_path / "voices"
    vd.mkdir(parents=True)
    (vd / f"{name}.onnx").write_bytes(content)
    (vd / f"{name}.onnx.json").write_bytes(b"{}")

    assert syn._ensure_voice(name) == vd / f"{name}.onnx"
