"""
TRIAGE: Deterministic Physical and Safety Admissibility Layer
Project: RMK-REVOLT / SECONDShift Platform
Enforces hard thermodynamic, electrochemical, and mechanical admissibility criteria.
DECISIONS:
- ACCEPT: Cleared for automated diagnostic testing
- HOLD: Ambiguous physical condition; routed to quarantine / manual inspection
- REJECT: Immediate physical failure; routed directly to recycling / hazard bin
"""

from typing import Dict, Any, Tuple

class TriageGate:
    def __init__(
        self,
        v_min_reject: float = 2.00,       # Copper dissolution boundary in LFP
        v_min_hold: float = 2.50,         # Depleted boundary
        v_max_reject: float = 3.75,       # Overcharge boundary
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
        v_rest: float,
        t_rest: float,
        ambient_temp_c: float,
        leakage_rate_mv_hr: float = 0.0,
        visual_bulge: bool = False,
        terminal_damage: bool = False
    ) -> Tuple[str, str]:
        """
        Evaluates physical admissibility across 4 cascaded deterministic gates.
        Returns: (status, reason_string)
        """
        # GATE 1: Mechanical / Physical Enclosure Integrity
        if visual_bulge:
            return "REJECT", "TR-01: Mechanical defect - Casing deformation / internal gas evolution"
        if terminal_damage:
            return "HOLD", "TR-02: Mechanical defect - Terminal thread damage / heavy corrosion"

        # GATE 2: Absolute Electrochemical Voltage Safety Window
        if v_rest < self.v_min_reject:
            return "REJECT", f"TR-03: Electrochemical hazard - Voc={v_rest:.3f}V < {self.v_min_reject}V (Copper dendrite dissolution risk)"
        if v_rest > self.v_max_reject:
            return "REJECT", f"TR-04: Overcharge hazard - Voc={v_rest:.3f}V > {self.v_max_reject}V (Electrolyte oxidation risk)"
        if v_rest < self.v_min_hold:
            return "HOLD", f"TR-05: Deeply depleted cell - Voc={v_rest:.3f}V in [2.00V, 2.50V]; requires manual low-rate recovery"

        # GATE 3: Thermodynamic Rest Anomaly
        if t_rest > self.t_max_reject_c:
            return "REJECT", f"TR-06: Thermal hazard - Resting temp={t_rest:.1f}C exceeds safety cutoff {self.t_max_reject_c}C"
        if (t_rest - ambient_temp_c) > self.delta_t_max_c:
            return "REJECT", f"TR-07: Internal exothermic reaction - Cell temp is {t_rest - ambient_temp_c:.1f}C above ambient at rest"

        # GATE 4: Open-Circuit Relaxation Drift (Self-Discharge Micro-Short Detection)
        if leakage_rate_mv_hr > self.max_leakage_mv_hr:
            return "REJECT", f"TR-08: Micro-short hazard - Self-discharge dV/dt={leakage_rate_mv_hr:.1f} mV/hr > {self.max_leakage_mv_hr} mV/hr"
        if leakage_rate_mv_hr > 5.0:
            return "HOLD", f"TR-09: Suspicious self-discharge - dV/dt={leakage_rate_mv_hr:.1f} mV/hr; requires extended 24-hr rest"

        return "ACCEPT", "All deterministic physical triage gates cleared."
