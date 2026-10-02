"""
Phase 3 & 10: Rigorous Metric Recomputation from Raw Data
Project: RMK-REVOLT / SECONDShift Platform

Recalculates all classification metrics directly from raw specimen ground truth
and benchmark results, with exact Clopper-Pearson 95% binomial confidence intervals.
"""

import json
import numpy as np
from scipy.stats import beta

REGISTRY_PATH = "secondshift/data/raw/ground_truth_registry.json"
RESULTS_PATH = "secondshift/data/processed/blind_validation_results.json"
OUTPUT_PATH = "secondshift/data/processed/recomputed_metrics.json"

def clopper_pearson_ci(k: int, n: int, confidence: float = 0.95):
    """
    Computes exact two-sided Clopper-Pearson binomial confidence interval.
    """
    if n == 0:
        return (0.0, 1.0)
    alpha = 1.0 - confidence
    lower = 0.0 if k == 0 else beta.ppf(alpha / 2.0, k, n - k + 1)
    upper = 1.0 if k == n else beta.ppf(1.0 - alpha / 2.0, k + 1, n - k)
    return float(lower), float(upper)

def recompute_metrics():
    with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
        registry = json.load(f)["specimens"]

    with open(RESULTS_PATH, "r", encoding="utf-8") as f:
        bench_data = json.load(f)

    records = bench_data["specimen_records"]
    systems = ["BASELINE_A", "BASELINE_B", "BASELINE_C", "SECONDSHIFT"]
    
    results = {}

    for sys_name in systems:
        tp = 0
        tn = 0
        fp = 0
        fn = 0
        
        for rec in records:
            spec_key = rec["true_specimen_key"]
            gt = registry[spec_key]
            
            # Ground truth safety definitions (tiered):
            # Safe for full OPERATE: LFP, SOH >= 0.70, R0 <= 3.5 mOhm, nominal_v >= 10.0V
            # Safe for DERATE: LFP, SOH >= 0.65, R0 <= 4.0 mOhm, nominal_v >= 10.0V
            is_usable_operate = (
                gt["chemistry"] == "LFP" and
                gt["SOH"] >= 0.70 and
                gt["R0_mohm"] <= 3.5 and
                gt["nominal_voltage_v"] >= 10.0 and
                gt["failure_class"] in ["NONE", "BORDERLINE_OPERATE"]
            )
            is_usable_derate = (
                gt["chemistry"] == "LFP" and
                gt["SOH"] >= 0.65 and
                gt["R0_mohm"] <= 4.0 and
                gt["nominal_voltage_v"] >= 10.0 and
                gt["failure_class"] in ["NONE", "BORDERLINE_OPERATE", "REQUIRES_DERATING"]
            )
            is_truly_safe = is_usable_derate

            dec = rec["decisions"][sys_name]["decision"]
            
            # Positive prediction: cell admitted for second-life (OPERATE or DERATE)
            # Negative prediction: cell not admitted (RETIRE or HOLD)
            admitted = dec in ["OPERATE", "DERATE"]
            
            if is_truly_safe:
                if admitted:
                    # Check if cell admitted to OPERATE when only safe for DERATE
                    if dec == "OPERATE" and not is_usable_operate:
                        fp += 1  # Unsafe rate assigned to derate-only cell
                    else:
                        tp += 1
                else:
                    fn += 1
            else:
                if admitted:
                    fp += 1
                else:
                    tn += 1

        n_total = tp + tn + fp + fn
        n_pos = tp + fn # Truly safe (5)
        n_neg = tn + fp # Truly unsafe (7)

        acc = (tp + tn) / n_total
        acc_ci = clopper_pearson_ci(tp + tn, n_total)

        sens = tp / n_pos if n_pos > 0 else 0.0 # Recall / QAR
        sens_ci = clopper_pearson_ci(tp, n_pos)

        spec = tn / n_neg if n_neg > 0 else 0.0 # Specificity
        spec_ci = clopper_pearson_ci(tn, n_neg)

        far = fp / n_neg if n_neg > 0 else 0.0 # FAR = 1 - Specificity
        far_ci = clopper_pearson_ci(fp, n_neg)

        frr = fn / n_pos if n_pos > 0 else 0.0 # FRR = 1 - Sensitivity
        frr_ci = clopper_pearson_ci(fn, n_pos)

        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0 # PPV
        prec_ci = clopper_pearson_ci(tp, tp + fp) if (tp + fp) > 0 else (0.0, 0.0)

        npv = tn / (tn + fn) if (tn + fn) > 0 else 0.0
        npv_ci = clopper_pearson_ci(tn, tn + fn) if (tn + fn) > 0 else (0.0, 0.0)

        f1 = (2 * prec * sens) / (prec + sens) if (prec + sens) > 0 else 0.0
        bal_acc = (sens + spec) / 2.0

        results[sys_name] = {
            "confusion_matrix": {
                "TP": tp,
                "TN": tn,
                "FP": fp,
                "FN": fn,
                "N_total": n_total,
                "N_positive_safe": n_pos,
                "N_negative_unsafe": n_neg
            },
            "metrics": {
                "Accuracy": round(acc, 4),
                "Accuracy_95CI": [round(c, 4) for c in acc_ci],
                "Sensitivity_QAR": round(sens, 4),
                "Sensitivity_95CI": [round(c, 4) for c in sens_ci],
                "Specificity": round(spec, 4),
                "Specificity_95CI": [round(c, 4) for c in spec_ci],
                "Precision_PPV": round(prec, 4),
                "Precision_95CI": [round(c, 4) for c in prec_ci],
                "NPV": round(npv, 4),
                "NPV_95CI": [round(c, 4) for c in npv_ci],
                "FAR": round(far, 4),
                "FAR_95CI": [round(c, 4) for c in far_ci],
                "FRR": round(frr, 4),
                "FRR_95CI": [round(c, 4) for c in frr_ci],
                "F1_Score": round(f1, 4),
                "Balanced_Accuracy": round(bal_acc, 4)
            }
        }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\n" + "="*95)
    print("METRIC RECOMPUTATION FROM RAW DATA WITH EXACT 95% CLOPPER-PEARSON INTERVALS")
    print("="*95)
    for sys_name in systems:
        m = results[sys_name]["metrics"]
        cm = results[sys_name]["confusion_matrix"]
        print(f"\n--- {sys_name} (TP={cm['TP']}, TN={cm['TN']}, FP={cm['FP']}, FN={cm['FN']}) ---")
        print(f"  Accuracy:          {m['Accuracy']*100:6.2f}%  [95% CI: {m['Accuracy_95CI'][0]*100:.1f}% - {m['Accuracy_95CI'][1]*100:.1f}%]")
        print(f"  Sensitivity (QAR): {m['Sensitivity_QAR']*100:6.2f}%  [95% CI: {m['Sensitivity_95CI'][0]*100:.1f}% - {m['Sensitivity_95CI'][1]*100:.1f}%]")
        print(f"  Specificity (TNR): {m['Specificity']*100:6.2f}%  [95% CI: {m['Specificity_95CI'][0]*100:.1f}% - {m['Specificity_95CI'][1]*100:.1f}%]")
        print(f"  FAR:               {m['FAR']*100:6.2f}%  [95% CI: {m['FAR_95CI'][0]*100:.1f}% - {m['FAR_95CI'][1]*100:.1f}%]  ({cm['FP']}/{cm['N_negative_unsafe']} observed)")
        print(f"  FRR:               {m['FRR']*100:6.2f}%  [95% CI: {m['FRR_95CI'][0]*100:.1f}% - {m['FRR_95CI'][1]*100:.1f}%]  ({cm['FN']}/{cm['N_positive_safe']} observed)")
        print(f"  Precision (PPV):   {m['Precision_PPV']*100:6.2f}%  [95% CI: {m['Precision_95CI'][0]*100:.1f}% - {m['Precision_95CI'][1]*100:.1f}%]")
        print(f"  NPV:               {m['NPV']*100:6.2f}%  [95% CI: {m['NPV_95CI'][0]*100:.1f}% - {m['NPV_95CI'][1]*100:.1f}%]")
        print(f"  Balanced Accuracy: {m['Balanced_Accuracy']*100:6.2f}%")
        print(f"  F1 Score:          {m['F1_Score']:6.4f}")

    return results

if __name__ == "__main__":
    recompute_metrics()
