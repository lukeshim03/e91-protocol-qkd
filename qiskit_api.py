from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import numpy as np

# Qiskit 라이브러리 임포트
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator

app = FastAPI(title="E91 QKD Simulator API")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 시뮬레이터 초기화
simulator = AerSimulator()

# --- 데이터 모델 정의 ---
class CHSHRequest(BaseModel):
    shots: int = 1024

class KeyGenRequest(BaseModel):
    count: int = 50

class EveRequest(BaseModel):
    shots: int = 1000
    intercept_prob: float = 0.5

# --- Phase 1: CHSH 부등식 검증 (FIXED) ---
@app.post("/api/phase1/chsh")
async def run_chsh(req: CHSHRequest):
    """
    Qiskit을 사용하여 CHSH 부등식 위반(S-value)을 계산합니다.
    
    FIX: 측정 전에 classical registers를 제대로 추가
    """
    # CHSH 각도 설정
    pairs = [
        (0, 22.5),   # E1
        (0, 67.5),   # E2
        (45, 22.5),  # E3
        (45, 67.5)   # E4
    ]
    
    correlations = []
    
    for theta_a, theta_b in pairs:
        # FIX: QuantumCircuit에 classical registers 명시
        qc = QuantumCircuit(2, 2)  # 2 qubits, 2 classical bits
        
        # 1. 벨 상태 생성 |Phi+> = (|00> + |11>)/√2
        qc.h(0)
        qc.cx(0, 1)
        
        # 2. 측정 기저 회전
        # FIX: 각도를 라디안으로 변환하고 올바른 방향으로 회전
        qc.ry(-2 * np.radians(theta_a), 0)
        qc.ry(-2 * np.radians(theta_b), 1)
        
        # 3. 측정 (FIX: measure_all() 대신 명시적 측정)
        qc.measure(0, 0)
        qc.measure(1, 1)
        
        # 4. 시뮬레이션 실행
        transpiled_qc = transpile(qc, simulator)
        job = simulator.run(transpiled_qc, shots=req.shots)
        counts = job.result().get_counts()
        
        # 5. 상관계수 계산
        # Qiskit bit order: rightmost is qubit 0
        # '00' means both measured 0, '11' means both measured 1
        n_same = counts.get('00', 0) + counts.get('11', 0)
        n_diff = counts.get('01', 0) + counts.get('10', 0)
        
        # E = (N_same - N_diff) / Total
        corr = (n_same - n_diff) / req.shots
        correlations.append(round(corr, 4))
    
    # S = E1 - E2 + E3 + E4 (no absolute value first)
    s_raw = correlations[0] - correlations[1] + correlations[2] + correlations[3]
    s_value = abs(s_raw)
    
    print(f"DEBUG Phase1: Correlations = {correlations}, S = {s_value}")
    
    return {
        "s_value": round(s_value, 4),
        "correlations": correlations,
        "violation": s_value > 2.0,
        "source": "Qiskit AerSimulator"
    }

# --- Phase 2: 키 생성 (Raw Key Sifting) ---
@app.post("/api/phase2/keygen")
async def run_keygen(req: KeyGenRequest):
    """
    Alice와 Bob의 무작위 기저 선택 및 측정 결과를 시뮬레이션합니다.
    """
    alice_bases = []
    bob_bases = []
    raw_bits_a = []
    raw_bits_b = []
    
    # Alice와 Bob의 기저 각도 후보
    basis_opts_a = [0, 45, 90]
    basis_opts_b = [45, 90, 135]
    
    for _ in range(req.count):
        # 무작위 기저 선택
        b_a = int(np.random.choice(basis_opts_a))
        b_b = int(np.random.choice(basis_opts_b))
        
        qc = QuantumCircuit(2, 2)
        
        # Bell state
        qc.h(0)
        qc.cx(0, 1)
        
        # Rotate to measurement bases
        qc.ry(-2 * np.radians(b_a), 0)
        qc.ry(-2 * np.radians(b_b), 1)
        
        # Measure
        qc.measure(0, 0)  # Alice
        qc.measure(1, 1)  # Bob
        
        # 1회 샷 실행
        job = simulator.run(transpile(qc, simulator), shots=1)
        res = list(job.result().get_counts().keys())[0]
        
        # Qiskit order: res[1] = qubit 0 (Alice), res[0] = qubit 1 (Bob)
        bit_a = int(res[1])
        bit_b = int(res[0])
        
        alice_bases.append(b_a)
        bob_bases.append(b_b)
        raw_bits_a.append(bit_a)
        raw_bits_b.append(bit_b)
    
    return {
        "alice_bases": alice_bases,
        "bob_bases": bob_bases,
        "raw_bits_a": raw_bits_a,
        "raw_bits_b": raw_bits_b
    }

# --- Phase 3: 도청자(Eve) 개입 (FIXED) ---
@app.post("/api/phase3/attack")
async def run_eve_attack(req: EveRequest):
    """
    도청자 Eve가 중간에 개입할 때 S-value 붕괴 시뮬레이션
    
    FIX: Eve가 없을 때도 정상 작동하도록 수정
    """
    pairs = [(0, 22.5), (0, 67.5), (45, 22.5), (45, 67.5)]
    correlations = []
    
    for theta_a, theta_b in pairs:
        # FIX: 조건부로 회로 생성
        if np.random.random() < req.intercept_prob:
            # ===== EVE INTERCEPTS =====
            # Eve가 측정하면 얽힘이 붕괴됨
            # 간단한 모델: Eve 측정 후 고전 상태로 전환
            
            qc = QuantumCircuit(2, 2)
            
            # 초기 얽힘 생성
            qc.h(0)
            qc.cx(0, 1)
            
            # Eve의 측정 (무작위 기저)
            eve_angle = np.random.choice([0, 45, 90])
            qc.ry(-2 * np.radians(eve_angle), 0)
            qc.ry(-2 * np.radians(eve_angle), 1)
            
            # Eve가 측정 (얽힘 붕괴!)
            qc.measure(0, 0)
            qc.measure(1, 1)
            
            # 중간 측정 결과 확인
            temp_job = simulator.run(transpile(qc, simulator), shots=1)
            eve_result = list(temp_job.result().get_counts().keys())[0]
            
            # 붕괴된 상태로 새 회로 생성
            qc = QuantumCircuit(2, 2)
            
            # Eve가 재전송: 측정 결과를 다시 준비
            if eve_result[1] == '1':  # Alice's qubit
                qc.x(0)
            if eve_result[0] == '1':  # Bob's qubit
                qc.x(1)
            
            # 이제 Alice와 Bob이 측정
            qc.ry(-2 * np.radians(theta_a), 0)
            qc.ry(-2 * np.radians(theta_b), 1)
            qc.measure(0, 0)
            qc.measure(1, 1)
            
        else:
            # ===== NO EVE (NORMAL OPERATION) =====
            # FIX: Eve가 없을 때는 정상 Bell state 사용
            qc = QuantumCircuit(2, 2)
            
            # 얽힘 생성 (붕괴 없음)
            qc.h(0)
            qc.cx(0, 1)
            
            # Alice와 Bob 측정
            qc.ry(-2 * np.radians(theta_a), 0)
            qc.ry(-2 * np.radians(theta_b), 1)
            qc.measure(0, 0)
            qc.measure(1, 1)
        
        # 시뮬레이션 실행
        job = simulator.run(transpile(qc, simulator), shots=req.shots)
        counts = job.result().get_counts()
        
        # 상관계수 계산
        n_same = counts.get('00', 0) + counts.get('11', 0)
        n_diff = counts.get('01', 0) + counts.get('10', 0)
        corr = (n_same - n_diff) / req.shots
        correlations.append(corr)
    
    # S-value 계산
    s_value = abs(correlations[0] - correlations[1] + correlations[2] + correlations[3])
    
    print(f"DEBUG Phase3: Eve_prob={req.intercept_prob}, S={s_value}, Corr={correlations}")
    
    return {
        "s_value": round(s_value, 4),
        "correlations": correlations,
        "is_secure": s_value > 2.0,
        "eve_active": req.intercept_prob > 0
    }

# Static files
app.mount("/", StaticFiles(directory=".", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)