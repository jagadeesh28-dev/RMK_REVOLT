"""
RMK-REVOLT TRIAGE Engine
Deterministic Physical Safety and Eligibility Gate.
Enforces hard thermodynamic, electrochemical, and mechanical criteria.
Guarantees NO AI halluncinations can override safety cutoffs.
"""

from typing import Dict, Any, Tuple
from models.battery_model import BatteryModule
from models.belief_state import ModuleBelief

class TriageEngine:
    """
    Deterministic safety classifier for retired battery screening.
    Decisions:
    - ACCEPT: Cleared for safe automated characterization
    - HOLD: Ambiguous physical indicators; requires manual inspection / slow rest study
    - REJECT: Hard physical safety failure; routed directly to recycling / hazard bin
    """
    def __init__(
        self,
        v_min_reject: float = 2.00,       # Copper dissolution threshold in LFP
        v_min_hold: float = 2.50,         # Deep depletion zone
        v_max_reject: float = 3.75,       # Overcharge / electrolyte oxidation threshold
        t_max_reject_c: float = 45.0,     # Ambient rest overtemperature limit
        delta_t_max_c: float = 4.0,       # Self-heating anomaly at rest
        max_leakage_mv_hr: float = 15.0   # Self-discharge threshold for internal micro-short
    ):
        self.v_min_reject = v_min_reject
        self.v_min_hold = v_min_hold
        self.v_max_reject = v_max_reject
        self.t_max_reject_c = t_max_reject_c
        self.delta_t_max_c = delta_t_max_c
        self.max_leakage_mv_hr = max_leakage_mv_hr

    def evaluate(
        self,
        module: BatteryModule,
        belief: ModuleBelief,
        visual_bulge: bool = False,
        terminal_damage: bool = False,
        resting_duration_s: float = 60.0
    ) -> Tuple[str, str]:
        """
        Evaluate module through deterministic cascaded physical gates.
        Returns: (status, reason_string)
        where status is in {"ACCEPT", "HOLD", "REJECT"}.
        """
        # Read raw sensors (simulated ADC with noise)
        meas_0 = module.measure(0.0)
        v_rest_start = meas_0["v_meas"]
        t_rest = meas_0["t_meas"]
        
        # GATE 1: Physical / Mechanical Integrity
        if visual_bulge:
            belief.triage_status = "REJECT"
            belief.triage_cleared = False
            return "REJECT", "Physical defect: Pouch/case bulging indicates internal gas evolution"
        if terminal_damage:
            belief.triage_status = "HOLD"
            belief.triage_cleared = False
            return "HOLD", "Mechanical warning: Terminal corrosion or structural thread damage"

        # GATE 2: Severe Overcharge / Deep Overdischarge
        if v_rest_start < self.v_min_reject:
            belief.triage_status = "REJECT"
            belief.triage_cleared = False
            return "REJECT", f"Electrochemical hazard: Voc = {v_rest_start:.3f}V < {self.v_min_reject}V (Copper dendrite risk)"
        
        if v_rest_start > self.v_max_reject:
            belief.triage_status = "REJECT"
            belief.triage_cleared = False
            return "REJECT", f"Overcharge hazard: Voc = {v_rest_start:.3f}V > {self.v_max_reject}V (Electrolyte breakdown risk)"

        # GATE 3: Thermal Resting Anomaly
        if t_rest > self.t_max_reject_c:
            belief.triage_status = "REJECT"
            belief.triage_cleared = False
            return "REJECT", f"Thermal anomaly: Resting temp = {t_rest:.1f}C exceeds safety cutoff {self.t_max_reject_c}C"
            
        if (t_rest - module.ambient_temp_c) > self.delta_t_max_c:
            belief.triage_status = "REJECT"
            belief.triage_cleared = False
            return "REJECT", f"Internal exothermic reaction: Module temp is {t_rest - module.ambient_temp_c:.1f}C above ambient at rest"

        # GATE 4: Short Rest Leakage Observation (Observation of self-discharge dV/dt)
        module.rest(duration_s=resting_duration_s, dt_s=1.0)
        meas_1 = module.measure(0.0)
        v_rest_end = meas_1["v_meas"]
        
        # Calculate leakage rate (mV/hour)
        delta_v_mv = (v_rest_start - v_rest_end) * 1000.0
        elapsed_hours = resting_duration_s / 3600.0
        leakage_rate_mv_hr = max(0.0, delta_v_mv / elapsed_hours)
        belief.leakage_mv_hr = float(leakage_rate_mv_hr)
        belief.temp_c = float(meas_1["t_meas"])
        
        if leakage_rate_mv_hr > self.max_leakage_mv_hr:
            belief.triage_status = "REJECT"
            belief.triage_cleared = False
            return "REJECT", f"Internal micro-short: Self-discharge rate {leakage_rate_mv_hr:.1f} mV/hr > {self.max_leakage_mv_hr} mV/hr"
        elif leakage_rate_mv_hr > (self.max_leakage_mv_hr * 0.5):
            belief.triage_status = "HOLD"
            belief.triage_cleared = False
            return "HOLD", f"Suspicious relaxation rate: {leakage_rate_mv_hr:.1f} mV/hr indicates possible high self-discharge"

        # GATE 5: Deep Depletion Ambiguity
        if v_rest_end < self.v_min_hold:
            belief.triage_status = "HOLD"
            belief.triage_cleared = False
            return "HOLD", f"Depleted state: Voc = {v_rest_end:.3f}V is below normal operating cutoff {self.v_min_hold}V; needs trickle test"

        # Cleared all deterministic gates
        belief.triage_status = "ACCEPT"
        belief.triage_cleared = True
        return "ACCEPT", "Deterministic safety screening passed; eligible for SECONDShift characterization"
