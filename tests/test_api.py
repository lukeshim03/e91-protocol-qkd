import os
import sys
# ensure project root is importable when pytest runs from tests/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient
from qiskit_api import app

client = TestClient(app)


def test_index_served():
    res = client.get("/index.html")
    assert res.status_code == 200
    assert "E91 QKD SUITE" in res.text


def test_chsh_endpoint():
    res = client.post("/api/phase1/chsh", json={"shots": 64})
    assert res.status_code == 200
    data = res.json()
    assert "s_value" in data
    assert isinstance(data.get("correlations"), list) and len(data["correlations"]) == 4
    assert isinstance(data.get("violation"), bool)


def test_keygen_endpoint():
    n = 10
    res = client.post("/api/phase2/keygen", json={"count": n})
    assert res.status_code == 200
    data = res.json()
    assert len(data["alice_bases"]) == n
    assert len(data["bob_bases"]) == n
    assert len(data["raw_bits_a"]) == n
    assert len(data["raw_bits_b"]) == n
    # bits are 0 or 1
    for b in data["raw_bits_a"] + data["raw_bits_b"]:
        assert b in (0, 1)


def test_attack_endpoint():
    res = client.post("/api/phase3/attack", json={"shots": 64, "intercept_prob": 0.5})
    assert res.status_code == 200
    data = res.json()
    assert "s_value" in data
    assert "is_secure" in data
