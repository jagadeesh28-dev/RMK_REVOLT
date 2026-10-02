"""
Plot Generation Script for RC-VOI Simulation v1
Generates publication-quality charts from the 5,000-module population,
Monte Carlo seeds, parameter sweeps, and component ablation studies.
"""

import json
import os
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.size'] = 10
plt.rcParams['axes.labelsize'] = 11
plt.rcParams['axes.titlesize'] = 12
plt.rcParams['legend.fontsize'] = 9
plt.rcParams['xtick.labelsize'] = 9
plt.rcParams['ytick.labelsize'] = 9
plt.rcParams['figure.titlesize'] = 14

RESULTS_DIR = os.path.dirname(os.path.abspath(__file__))

def load_data():
    with open(os.path.join(RESULTS_DIR, "rc_voi_5000_summary.json"), "r") as f:
        summary_5000 = json.load(f)
    with open(os.path.join(RESULTS_DIR, "monte_carlo_seeds_summary.json"), "r") as f:
        summary_mc = json.load(f)
    with open(os.path.join(RESULTS_DIR, "sensitivity_sweeps_summary.json"), "r") as f:
        summary_sens = json.load(f)
    with open(os.path.join(RESULTS_DIR, "rc_voi_ablation_summary.json"), "r") as f:
        summary_abl = json.load(f)
    raw_5000 = pd.read_csv(os.path.join(RESULTS_DIR, "rc_voi_5000_raw_records.csv"))
    return summary_5000, summary_mc, summary_sens, summary_abl, raw_5000


def plot_policy_comparison(summary_5000, raw_5000):
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("RC-VOI Simulation v1: 5,000-Module Policy Benchmark", fontweight='bold', y=0.98)

    policies = ["A_Fixed", "B_Scalar", "C_UncertaintyThresh", "D_RC_VOI"]
    labels = ["A: Fixed\n(Industrial)", "B: Scalar SOH\n(Standard BMS)", "C: Uncertainty\nThreshold", "D: RC-VOI\n(Proposed)"]
    colors = ['#4A5568', '#E53E3E', '#DD6B20', '#3182CE']

    # 1. Mean Diagnostic Time with 95% CI
    means_t = [summary_5000[p]["time_distribution_s"]["mean"] for p in policies]
    err_t_low = [means_t[i] - summary_5000[p]["time_distribution_s"]["ci_95_low"] for i, p in enumerate(policies)]
    err_t_high = [summary_5000[p]["time_distribution_s"]["ci_95_high"] - means_t[i] for i, p in enumerate(policies)]

    ax = axes[0, 0]
    bars = ax.bar(labels, means_t, yerr=[err_t_low, err_t_high], capsize=5, color=colors, alpha=0.85, edgecolor='black', linewidth=1)
    ax.set_ylabel("Diagnostic Time (s)")
    ax.set_title("Mean Diagnostic Duration per Module (95% CI)")
    ax.grid(axis='y', linestyle='--', alpha=0.7)
    for bar, val in zip(bars, means_t):
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2.0, yval + 15, f"{val:.1f}s", ha='center', va='bottom', fontsize=9, fontweight='bold')

    # 2. FAR vs Safety Threshold (1%)
    fars = [summary_5000[p]["far_percent"] for p in policies]
    ax = axes[0, 1]
    bars = ax.bar(labels, fars, color=colors, alpha=0.85, edgecolor='black', linewidth=1)
    ax.axhline(1.0, color='red', linestyle='--', linewidth=2, label="Safety Limit FAR <= 1.0%")
    ax.set_ylabel("False Acceptance Rate (%)")
    ax.set_title("Safety Compliance: False Acceptance Rate (%)")
    ax.set_yscale('log')
    ax.set_ylim(0.5, 30.0)
    ax.grid(axis='y', linestyle='--', alpha=0.7)
    ax.legend(loc='upper right')
    for bar, val in zip(bars, fars):
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2.0, yval * 1.1, f"{val:.2f}%", ha='center', va='bottom', fontsize=9, fontweight='bold')

    # 3. Unnecessary Isolation Rate (UIR %) & Retained kWh
    uirs = [summary_5000[p]["uir_percent"] for p in policies]
    kwhs = [summary_5000[p]["total_kwh_retained"] for p in policies]
    ax = axes[1, 0]
    width = 0.35
    x = np.arange(len(labels))
    bars1 = ax.bar(x - width/2, uirs, width, label='Unnecessary Isolation (%)', color='#E53E3E', alpha=0.8, edgecolor='black')
    ax2 = ax.twinx()
    bars2 = ax2.bar(x + width/2, kwhs, width, label='Retained Usable (kWh)', color='#38A169', alpha=0.8, edgecolor='black')
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Unnecessary Isolation Rate (%)", color='#E53E3E')
    ax2.set_ylabel("Total Retained Energy (kWh)", color='#38A169')
    ax.set_title("Asset Waste vs Usable Capacity Recovered")
    ax.grid(axis='y', linestyle='--', alpha=0.5)

    # 4. Total Cost per Module (INR)
    costs = [summary_5000[p]["cost_distribution_inr"]["mean"] for p in policies]
    ax = axes[1, 1]
    bars = ax.bar(labels, costs, color=colors, alpha=0.85, edgecolor='black', linewidth=1)
    ax.set_ylabel("Mean Testing Cost (INR)")
    ax.set_title("Total Qualification Cost per Module (Labor + Electricity)")
    ax.grid(axis='y', linestyle='--', alpha=0.7)
    for bar, val in zip(bars, costs):
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2.0, yval + 3, f"INR {val:.1f}", ha='center', va='bottom', fontsize=9, fontweight='bold')

    plt.tight_layout()
    plot_path = os.path.join(RESULTS_DIR, "rc_voi_policy_comparison.png")
    plt.savefig(plot_path, dpi=300)
    plt.close()
    print(f"Saved: {plot_path}")


def plot_rc_voi_vs_policy_c(summary_sens):
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Policy D (RC-VOI) vs Policy C (Uncertainty Threshold): Boundary Conditions", fontweight='bold', y=0.98)

    # 1. Uncertainty Scale Sweep vs Time
    unc_data = summary_sens["uncertainty_scale_sweep"]
    sigmas = [d["prior_sigma_soh"] for d in unc_data]
    time_c = [d["time_c_s"] for d in unc_data]
    time_d = [d["time_rc_voi_s"] for d in unc_data]

    ax = axes[0, 0]
    ax.plot(sigmas, time_c, marker='o', linewidth=2, color='#DD6B20', label='Policy C (Heuristic Threshold)')
    ax.plot(sigmas, time_d, marker='s', linewidth=2, color='#3182CE', label='Policy D (RC-VOI Quadrature)')
    ax.set_xlabel("Prior Estimator Standard Deviation (sigma_soh)")
    ax.set_ylabel("Diagnostic Time (s)")
    ax.set_title("Diagnostic Duration vs Uncertainty Level")
    ax.grid(True, linestyle='--', alpha=0.7)
    ax.legend()

    # 2. Uncertainty Scale Sweep vs UIR (Waste Avoidance)
    uir_c = [d["uir_c_percent"] for d in unc_data]
    uir_d = [d["uir_rc_voi_percent"] for d in unc_data]

    ax = axes[0, 1]
    ax.plot(sigmas, uir_c, marker='o', linewidth=2, color='#DD6B20', label='Policy C (Heuristic Threshold)')
    ax.plot(sigmas, uir_d, marker='s', linewidth=2, color='#3182CE', label='Policy D (RC-VOI Quadrature)')
    ax.set_xlabel("Prior Estimator Standard Deviation (sigma_soh)")
    ax.set_ylabel("Unnecessary Isolation Rate (%)")
    ax.set_title("Asset Waste (UIR %) under Increasing Uncertainty")
    ax.grid(True, linestyle='--', alpha=0.7)
    ax.legend()

    # 3. Labor Cost Sensitivity vs Testing Cost
    labor_data = summary_sens["labor_rate_sweep"]
    rates = [d["labor_rate_hr"] for d in labor_data]
    cost_c = [d["cost_c_inr"] for d in labor_data]
    cost_d = [d["cost_rc_voi_inr"] for d in labor_data]

    ax = axes[1, 0]
    ax.plot(rates, cost_c, marker='o', linewidth=2, color='#DD6B20', label='Policy C Cost (INR)')
    ax.plot(rates, cost_d, marker='s', linewidth=2, color='#3182CE', label='Policy D Cost (INR)')
    ax.set_xlabel("Labor Rate (INR / hour)")
    ax.set_ylabel("Diagnostic Cost (INR)")
    ax.set_title("Qualification Cost vs Technician Labor Rate")
    ax.grid(True, linestyle='--', alpha=0.7)
    ax.legend()

    # 4. Failure Penalty vs Policy D Time
    pen_data = summary_sens["penalty_sweep"]
    penalties = [d["safety_penalty_inr"] for d in pen_data]
    time_pen = [d["time_rc_voi_s"] for d in pen_data]
    far_pen = [d["far_rc_voi_percent"] for d in pen_data]

    ax = axes[1, 1]
    ax.plot(penalties, time_pen, marker='^', linewidth=2, color='#805AD5', label='Diagnostic Time (s)')
    ax.set_xlabel("Catastrophic Failure Penalty C_fail (INR)")
    ax.set_ylabel("Policy D Time (s)", color='#805AD5')
    ax.set_title("Risk-Adaptive Escalation: Duration vs Failure Penalty")
    ax.grid(True, linestyle='--', alpha=0.7)

    ax2 = ax.twinx()
    ax2.plot(penalties, far_pen, marker='x', linestyle=':', color='#E53E3E', label='FAR (%)')
    ax2.set_ylabel("False Acceptance Rate (%)", color='#E53E3E')

    plt.tight_layout()
    plot_path = os.path.join(RESULTS_DIR, "rc_voi_vs_policy_c.png")
    plt.savefig(plot_path, dpi=300)
    plt.close()
    print(f"Saved: {plot_path}")


def plot_ablation(summary_abl):
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    fig.suptitle("RC-VOI Component Ablation Analysis (500 Modules)", fontweight='bold', y=1.02)

    configs = ["FULL_RC_VOI", "NO_UNCERTAINTY", "NO_TEST_COST", "NO_APP_CONTEXT", "NO_DERATING"]
    labels = ["Full RC-VOI", "No Uncertainty\n(Blind)", "No Test Cost\n(Greedy)", "No App Context\n(Static)", "No Derating\n(Binary)"]
    colors = ['#3182CE', '#E53E3E', '#DD6B20', '#805AD5', '#D69E2E']

    # 1. Unnecessary Isolation Rate (%)
    uirs = [summary_abl[c]["uir_percent"] for c in configs]
    ax = axes[0]
    bars = ax.bar(labels, uirs, color=colors, alpha=0.85, edgecolor='black', linewidth=1)
    ax.set_ylabel("Unnecessary Isolation Rate (%)")
    ax.set_title("Asset Waste: UIR (%)")
    ax.grid(axis='y', linestyle='--', alpha=0.7)
    for bar, val in zip(bars, uirs):
        ax.text(bar.get_x() + bar.get_width()/2.0, val + 0.5, f"{val:.1f}%", ha='center', va='bottom', fontsize=8, fontweight='bold')

    # 2. Retained Usable Energy (kWh)
    kwhs = [summary_abl[c]["total_kwh"] for c in configs]
    ax = axes[1]
    bars = ax.bar(labels, kwhs, color=colors, alpha=0.85, edgecolor='black', linewidth=1)
    ax.set_ylabel("Retained Capacity (kWh)")
    ax.set_title("Usable Second-Life Energy Harvested")
    ax.grid(axis='y', linestyle='--', alpha=0.7)
    for bar, val in zip(bars, kwhs):
        ax.text(bar.get_x() + bar.get_width()/2.0, val + 0.5, f"{val:.1f}", ha='center', va='bottom', fontsize=8, fontweight='bold')

    # 3. Diagnostic Duration (s)
    times = [summary_abl[c]["mean_time_s"] for c in configs]
    ax = axes[2]
    bars = ax.bar(labels, times, color=colors, alpha=0.85, edgecolor='black', linewidth=1)
    ax.set_ylabel("Mean Diagnostic Time (s)")
    ax.set_title("Diagnostic Burden per Module")
    ax.grid(axis='y', linestyle='--', alpha=0.7)
    for bar, val in zip(bars, times):
        ax.text(bar.get_x() + bar.get_width()/2.0, val + 5, f"{val:.0f}s", ha='center', va='bottom', fontsize=8, fontweight='bold')

    plt.tight_layout()
    plot_path = os.path.join(RESULTS_DIR, "rc_voi_ablation_study.png")
    plt.savefig(plot_path, dpi=300)
    plt.close()
    print(f"Saved: {plot_path}")


def main():
    summary_5000, summary_mc, summary_sens, summary_abl, raw_5000 = load_data()
    plot_policy_comparison(summary_5000, raw_5000)
    plot_rc_voi_vs_policy_c(summary_sens)
    plot_ablation(summary_abl)
    print("All RC-VOI plots generated successfully.")

if __name__ == "__main__":
    main()
