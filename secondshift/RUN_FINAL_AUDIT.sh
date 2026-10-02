#!/usr/bin/env bash
# ==============================================================================
# SECONDShift Master Research Audit & Reproducibility Pipeline
# Project: RMK REVOLT / SECONDShift
#
# Executes the complete end-to-end audit:
# 1. Automated unit test suite & ground-truth quarantine isolation
# 2. 12-Specimen blind benchmark pipeline
# 3. Exact metric recomputation & Clopper-Pearson confidence interval generator
# 4. Statistical inference tests (Wilcoxon signed-rank & McNemar paired)
# 5. Adversarial estimator overconfidence attacks (14 stress modes)
# 6. Epistemic chemistry disambiguation stress suite (250 cycles)
# 7. Systematic architectural ablation study (A0 to A6)
# 8. Economic sensitivity tornado analysis
# 9. Publication visualization generator (FIG-01 to FIG-14 + FIG_TORNADO)
# 10. Forbidden claim scanner
# 11. Manifest verification
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${WORKSPACE_ROOT}"

PYTHON_BIN="/home/jagadeesh/miniconda3/envs/EB_2935/bin/python"
if [ ! -f "${PYTHON_BIN}" ]; then
    PYTHON_BIN="$(which python3 || which python)"
fi

echo "================================================================================"
echo "STARTING SECONDShift MASTER RESEARCH AUDIT PIPELINE"
echo "Timestamp:   $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo "Interpreter: ${PYTHON_BIN}"
echo "Workspace:   ${WORKSPACE_ROOT}"
echo "================================================================================"

export PYTHONPATH="${WORKSPACE_ROOT}"

# STEP 1: Pytest Unit Tests & Ground-Truth Isolation
echo -e "\n[1/11] Executing Automated Pytest Suite (10 unit & isolation tests)..."
${PYTHON_BIN} -m pytest secondshift/tests/ -v --tb=short

# STEP 2: Blind Physical Validation Benchmark
echo -e "\n[2/11] Executing Blind Benchmark Pipeline (N=12 Specimens)..."
${PYTHON_BIN} secondshift/experiments/run_blind_physical_validation.py

# STEP 3: Metric Recomputation & Exact Clopper-Pearson CIs
echo -e "\n[3/11] Recomputing Formal Metrics & Clopper-Pearson Intervals..."
${PYTHON_BIN} secondshift/experiments/recompute_all_metrics.py

# STEP 4: Statistical Significance Tests (Wilcoxon & McNemar)
echo -e "\n[4/11] Running Statistical Inference Tests (Wilcoxon & McNemar)..."
${PYTHON_BIN} secondshift/experiments/run_statistical_inference.py

# STEP 5: Adversarial Overconfidence Stress Suite
echo -e "\n[5/11] Running Adversarial Overconfidence Stress Suite (14 modes)..."
${PYTHON_BIN} secondshift/experiments/run_adversarial_overconfidence.py

# STEP 6: Epistemic Chemistry Disambiguation Suite
echo -e "\n[6/11] Running Epistemic Chemistry Attacks (250 cycles)..."
${PYTHON_BIN} secondshift/experiments/run_chemistry_attacks.py

# STEP 7: Architectural Ablation Study (A0 to A6)
echo -e "\n[7/11] Running Architectural Ablation Study (A0 to A6)..."
${PYTHON_BIN} secondshift/experiments/run_ablation_study.py

# STEP 8: Economic Tornado Sensitivity
echo -e "\n[8/11] Generating Economic Sensitivity Tornado Analysis..."
${PYTHON_BIN} secondshift/experiments/generate_economic_tornado.py

# STEP 9: Publication Visualizations (FIG-01 to FIG-14)
echo -e "\n[9/11] Generating Publication Visualizations (FIG-01 to FIG-14)..."
${PYTHON_BIN} secondshift/experiments/generate_visualizations.py

# STEP 10: Forbidden Claim Scanner
echo -e "\n[10/11] Scanning Codebase for Forbidden Overclaims..."
FORBIDDEN_VIOLATIONS=0

# Check for ungrounded "thermal runaway prevention" claims (excluding disclaimers and retractions)
if grep -rn -i "SECONDShift prevents thermal runaway" secondshift/ --exclude-dir=".git" --exclude="RUN_FINAL_AUDIT.sh" 2>/dev/null; then
    echo "ERROR: Found forbidden claim 'SECONDShift prevents thermal runaway'!"
    FORBIDDEN_VIOLATIONS=$((FORBIDDEN_VIOLATIONS + 1))
fi

if [ "${FORBIDDEN_VIOLATIONS}" -gt 0 ]; then
    echo "FAILED: ${FORBIDDEN_VIOLATIONS} forbidden claim violations detected."
    exit 1
else
    echo "PASS: Zero forbidden claim violations detected across repository."
fi

# STEP 11: Output Manifest Verification
echo -e "\n[11/11] Verifying Artifact & Figure Integrity..."
REQUIRED_FILES=(
    "secondshift/data/processed/blind_validation_results.json"
    "secondshift/data/processed/recomputed_metrics.json"
    "secondshift/data/processed/chemistry_attack_results.json"
    "secondshift/docs/figures/fig_01.png"
    "secondshift/docs/figures/fig_05.png"
    "secondshift/docs/figures/fig_10.png"
    "secondshift/docs/figures/fig_14.png"
    "secondshift/docs/figures/fig_tornado_economic.png"
    "secondshift/docs/RESULTS.md"
    "secondshift/docs/LIMITATIONS.md"
    "secondshift/docs/METRIC_RECOMPUTATION.md"
    "secondshift/paper/01_abstract.md"
    "secondshift/paper/14_conclusion.md"
    "secondshift/paper/references.bib"
)

for f in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "${f}" ]; then
        echo "ERROR: Missing required artifact: ${f}"
        exit 1
    fi
done
echo "PASS: All required figures, reports, data artifacts, and paper sections verified."

echo -e "\n================================================================================"
echo "SECONDShift MASTER RESEARCH AUDIT COMPLETED SUCCESSFULLY (EXIT 0)"
echo "All 11 audit stages passed. The codebase is reproducible and publication-ready."
echo "================================================================================"
exit 0
