"""
Hard Probabilistic Safety Barrier
Project: RMK-REVOLT / SECONDShift Platform
Enforces: P(Failure | observations) <= alpha (alpha = 0.01)
Decouples safety constraints strictly from economic utility optimization.
RULE: THE OPTIMIZER CANNOT OVERRIDE THIS BARRIER.
"""

from typing import Dict, Any, List, Set

class HardSafetyBarrier:
    def __init__(
        self,
        alpha_safety: float = 0.01,
        known_chem_required: bool = True
    ):
        self.alpha = alpha_safety
        self.known_chem_required = known_chem_required

    def filter_admissible_actions(
        self,
        risk_evaluation_operate: Dict[str, Any],
        risk_evaluation_derate: Dict[str, Any],
        chemistry_confidence_state: str,
        triage_status: str
    ) -> Set[str]:
        """
        Determines the mathematically admissible action set A_safe.
        Actions violating the probabilistic safety barrier or chemistry certainty
        are strictly eliminated (receive utility = -infinity).
        """
        # If deterministic triage rejected, only RETIRE is permitted
        if triage_status == "REJECT":
            return {"RETIRE"}
        elif triage_status == "HOLD":
            return {"HOLD", "TEST", "RETIRE"}

        admissible = {"TEST", "HOLD", "RETIRE"}

        # Check chemistry confidence state
        # If chemistry is not KNOWN, OPERATE is strictly forbidden
        if chemistry_confidence_state == "KNOWN":
            # Check OPERATE risk barrier: P(Failure | y) <= alpha
            if risk_evaluation_operate["p_fail_marginal"] <= self.alpha:
                admissible.add("OPERATE")

            # Check DERATE risk barrier: P(Failure | y) <= alpha
            if risk_evaluation_derate["p_fail_marginal"] <= self.alpha:
                admissible.add("DERATE")

        elif chemistry_confidence_state == "PROBABLE":
            # Direct OPERATE and DERATE are FORBIDDEN under chemistry uncertainty.
            # Permitted actions are TEST and HOLD.
            pass

        elif chemistry_confidence_state == "AMBIGUOUS":
            # Neither OPERATE nor DERATE is permitted. Only TEST, HOLD, RETIRE.
            pass

        return admissible

    def apply_barrier_to_utilities(
        self,
        unconstrained_utilities: Dict[str, float],
        admissible_actions: Set[str]
    ) -> Dict[str, float]:
        """
        Sets utility of non-admissible actions to -1e8 (-infinity).
        """
        constrained = {}
        for action, util in unconstrained_utilities.items():
            if action in admissible_actions:
                constrained[action] = util
            else:
                constrained[action] = -1e8
        return constrained
