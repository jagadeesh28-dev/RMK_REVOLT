"""
Phase 12: Economic Tornado & Sensitivity Analysis
Project: RMK-REVOLT / SECONDShift Platform

Computes parameter swing deltas for Tornado plot:
Varies 6 key parameters across +/- 40%:
1. Grid electricity tariff (₹6 - ₹14/kWh)
2. Usable second-life cycles (800 - 1600 cycles)
3. Failure liability penalty (₹3,000 - ₹12,000)
4. Black mass scrap buyback tariff (₹800 - ₹1600/kWh)
5. Mean qualified capacity SOH (0.75 - 0.90)
6. Equipment amortized test cost (₹5 - ₹35/cell)

Saves figure to secondshift/docs/figures/fig_tornado_economic.png
"""

import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import json

FIGURES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "figures")
os.makedirs(FIGURES_DIR, exist_ok=True)

# Baseline Nominal Parameters (10-cell 0.64 kWh Module)
BASE_PARAMS = {
    "tariff": 10.0,          # INR / kWh
    "cycles": 1200,          # Usable full cycles
    "penalty": 6000.0,       # INR per field hazard incident
    "salvage": 1200.0,       # INR / kWh scrap
    "soh": 0.82,             # Mean qualified SOH
    "test_cost": 12.5,       # INR per cell test cost
    "kwh_nom": 0.064,        # 64 Wh per cell
    "n_cells": 10,           # 10 cells in series (0.64 kWh)
    "p_safe": 5/12,
    "p_unsafe": 7/12,
    "qar": 0.80,
    "far": 0.00
}

def compute_module_net_value(p):
    kwh = p["kwh_nom"] * p["n_cells"]
    gross_rev = p["soh"] * kwh * p["cycles"] * p["tariff"]
    salvage = kwh * p["salvage"]
    
    p_safe_qual = p["p_safe"] * p["qar"]
    p_retired = (p["p_safe"] * (1 - p["qar"])) + (p["p_unsafe"] * (1 - p["far"]))
    p_hazard = p["p_unsafe"] * p["far"]
    
    exp_rev = (p_safe_qual * gross_rev) + (p_retired * salvage)
    exp_pen = p_hazard * p["penalty"]
    testing = p["test_cost"] * p["n_cells"]
    
    return exp_rev - exp_pen - testing

def generate_tornado():
    base_val = compute_module_net_value(BASE_PARAMS)
    
    parameters = [
        ("Electricity Tariff (₹6 to ₹14/kWh)", "tariff", 6.0, 14.0),
        ("Second-Life Usable Cycles (800 to 1600)", "cycles", 800, 1600),
        ("Scrap Buyback Tariff (₹800 to ₹1600/kWh)", "salvage", 800.0, 1600.0),
        ("Mean Qualified SOH (0.75 to 0.90)", "soh", 0.75, 0.90),
        ("Testing Bench Amortization (₹5 to ₹35/cell)", "test_cost", 35.0, 5.0), # Note: high cost lowers value
        ("Failure Penalty Liability (₹12k to ₹3k)", "penalty", 12000.0, 3000.0)
    ]
    
    deltas = []
    
    for label, param_key, low_val, high_val in parameters:
        p_low = dict(BASE_PARAMS)
        p_low[param_key] = low_val
        val_low = compute_module_net_value(p_low)
        
        p_high = dict(BASE_PARAMS)
        p_high[param_key] = high_val
        val_high = compute_module_net_value(p_high)
        
        deltas.append({
            "label": label,
            "low": val_low,
            "high": val_high,
            "spread": abs(val_high - val_low)
        })
        
    # Sort by spread (descending)
    deltas.sort(key=lambda x: x["spread"], reverse=True)
    
    # Plot Tornado
    y_pos = np.arange(len(deltas))
    fig, ax = plt.subplots(figsize=(8, 4.5))
    
    for i, d in enumerate(deltas):
        left_val = min(d["low"], d["high"])
        right_val = max(d["low"], d["high"])
        
        ax.barh(i, right_val - base_val, left=base_val, color="#2ca02c", alpha=0.85, height=0.55)
        ax.barh(i, left_val - base_val, left=base_val, color="#d62728", alpha=0.85, height=0.55)
        
    ax.axvline(base_val, color="black", lw=1.5, ls="--", label=f"Nominal Baseline: ₹{base_val:,.0f}/module")
    ax.set_yticks(y_pos)
    ax.set_yticklabels([d["label"] for d in deltas])
    ax.invert_yaxis() # Highest spread on top
    ax.set_xlabel("Net Economic Value per 0.64 kWh Module (INR)")
    ax.set_title("FIG-TORNADO: Sensitivity of Net Economic Arbitrage to Commercial Assumptions")
    
    # Evidence tag
    ax.text(
        0.98, 0.05, "[THEORETICAL SENSITIVITY]",
        transform=ax.transAxes,
        fontsize=9, fontweight="bold", color="white",
        verticalalignment="bottom", horizontalalignment="right",
        bbox=dict(boxstyle="round,pad=0.35", facecolor="#4a148c", alpha=0.85, edgecolor="none")
    )
    ax.legend(loc="upper right")
    plt.tight_layout()
    
    out_fig = os.path.join(FIGURES_DIR, "fig_tornado_economic.png")
    plt.savefig(out_fig, dpi=200)
    plt.close()
    
    print(f"Tornado figure saved to {out_fig}")
    print(f"Nominal Net Value: ₹{base_val:.2f} / module")
    for d in deltas:
        print(f"  {d['label']:45s} | Range: [₹{d['low']:8.2f}, ₹{d['high']:8.2f}] | Spread: ₹{d['spread']:8.2f}")

if __name__ == "__main__":
    generate_tornado()
