import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient
import qiskit_api
from types import SimpleNamespace

client = TestClient(qiskit_api.app)


class MockJob:
    def __init__(self, counts):
        self._counts = counts

    def result(self):
        return SimpleNamespace(get_counts=lambda: self._counts)


class MockSim:
    def __init__(self, counts_sequence=None):
        self.counts_sequence = counts_sequence or []
        self.calls = 0
        self.num_qubits = 2

    def run(self, *args, **kwargs):
        if self.calls < len(self.counts_sequence):
            counts = self.counts_sequence[self.calls]
        else:
            counts = {'00': 64, '11': 0, '01': 0, '10': 0}
        self.calls += 1
        return MockJob(counts)


def test_chsh_with_mock(monkeypatch):
    # Create deterministic counts to enforce a known S-value
    # Use shots=80 for convenience
    seq = [
        {'00': 80},   # E1 -> corr = 1
        {'01': 80},   # E2 -> corr = -1
        {'00': 80},   # E3 -> corr = 1
        {'00': 80},   # E4 -> corr = 1
    ]
    monkeypatch.setattr(qiskit_api, 'simulator', MockSim(counts_sequence=seq))
    # Avoid qiskit transpiler needing backend target metadata in unit tests
    monkeypatch.setattr(qiskit_api, 'transpile', lambda qc, backend: qc)

    res = client.post('/api/phase1/chsh', json={'shots': 80})
    assert res.status_code == 200
    data = res.json()
    assert abs(float(data['s_value']) - 4.0) < 1e-6
    assert data['violation'] is True


def test_attack_with_mock(monkeypatch):
    # Make attack produce a low S-value when intercept_prob=1
    seq = [
        {'01': 50, '10': 50},
        {'01': 50, '10': 50},
        {'01': 50, '10': 50},
        {'01': 50, '10': 50},
    ]
    monkeypatch.setattr(qiskit_api, 'simulator', MockSim(counts_sequence=seq))
    monkeypatch.setattr(qiskit_api, 'transpile', lambda qc, backend: qc)

    res = client.post('/api/phase3/attack', json={'shots': 100, 'intercept_prob': 1.0})
    assert res.status_code == 200
    data = res.json()
    assert 's_value' in data
    assert data['is_secure'] in (True, False)


def test_endpoints_validate_input():
    # Bad payload type should return 422
    res = client.post('/api/phase1/chsh', json={'shots': 'not-a-number'})
    assert res.status_code == 422


def test_simulator_exception_propagates(monkeypatch):
    # Force simulator.run to raise to ensure we get a 500
    def bad_run(*args, **kwargs):
        raise RuntimeError('simulator failed')

    monkeypatch.setattr(qiskit_api, 'simulator', SimpleNamespace(run=bad_run, num_qubits=2))
    monkeypatch.setattr(qiskit_api, 'transpile', lambda qc, backend: qc)
    # Prevent server exceptions from being re-raised by TestClient so we can assert the 500 response
    from fastapi.testclient import TestClient as LocalTestClient
    with LocalTestClient(qiskit_api.app, raise_server_exceptions=False) as c:
        res = c.post('/api/phase1/chsh', json={'shots': 10})
    assert res.status_code == 500