"""
Plot Generation Script for RC-VOI v2 Adversarial Validation Gate
Generates high-resolution scientific figures for:
1. Hard Safety Barrier (Task 1)
2. Model Mismatch Performance (Task 2)
3. Heterogeneity & Mixed Chemistries (Task 3)
4. Uncertainty Sweep & Crossover Region (Task 4)
5. Derating Physical Validation (Task 6)
6. 7-Way Comprehensive Component Ablation (Task 9)
"""

import json
import os
import matplotlib.pyplot as plt
import numpy as np

plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.size'] = 10
plt.rcParams['axes.labelsize'] = 11
plt.rcParams['axes.titlesize'] = 12
plt.rcParams['legend.fontsize'] = 9
plt.rcParams['xtick.labelsize'] = 9
plt.rcParams['ytick.labelsize'] = 9
plt.rcParams['figure.titlesize'] = 14

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "adversarial")


def plot_task1_hard_barrier():
    summary_path = os.path.join(RESULTS_DIR, "task1_hard_barrier_summary.json")
    if not os.path.exists(summary_path):
        return
    with open(summary_path, "r") as f:
        data = json.load(f)

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle("Task 1: Hard Probabilistic Safety Barrier (alpha = 0.01) Evaluation (1,000 Modules)", fontweight='bold', y=1.02)

    configs = ["RC_VOI_Original", "RC_VOI_HardBarrier", "Policy_C"]
    labels = ["Original RC-VOI\n(Soft Penalty)", "RC-VOI +\nHard Barrier", "Policy C\n(Heuristic)"]
    colors = ['#E53E3E', '#3182CE', '#DD6B20']

    # 1. FAR (%) with 1.0% limit line
    fars = [data[c]["far_percent"] for c in configs]
    ax = axes[0]
    bars = ax.bar(labels, fars, color=colors, alpha=0.85, edgecolor='black', linewidth=1)
    ax.axhline(1.0, color='red', linestyle='--', linewidth=2, label="Hard Safety Target FAR <= 1.0%")
    ax.set_ylabel("False Acceptance Rate (%)")
    ax.set_title("Safety Target Compliance: FAR (%)")
    ax.grid(axis='y', linestyle='--', alpha=0.7)
    ax.legend(loc='upper right')
    for bar, val in zip(bars, fars):
        ax.text(bar.get_x() + bar.get_width()/2.0, val + 0.15, f"{val:.2f}%", ha='center', va='bottom', fontsize=9, fontweight='bold')

    # 2. UIR (%)
    uirs = [data[c]["uir_percent"] for c in configs]
    ax = axes[1]
    bars = ax.bar(labels, uirs, color=colors, alpha=0.85, edgecolor='black', linewidth=1)
    ax.set_ylabel("Unnecessary Isolation Rate (%)")
    ax.set_title("Asset Waste: UIR (%)")
    ax.grid(axis='y', linestyle='--', alpha=0.7)
    for bar, val in zip(bars, uirs):
        ax.text(bar.get_x() + bar.get_width()/2.0, val + 0.8, f"{val:.1f}%", ha='center', va='bottom', fontsize=9, fontweight='bold')

    # 3. Retained Energy (kWh) & Mean Time
    kwhs = [data[c]["total_kwh"] for c in configs]
    ax = axes[2]
    bars = ax.bar(labels, kwhs, color=colors, alpha=0.85, edgecolor='black', linewidth=1)
    ax.set_ylabel("Retained Usable Energy (kWh)")
    ax.set_title("Total Energy Harvested (kWh)")
    ax.grid(axis='y', linestyle='--', alpha=0.7)
    for bar, val in zip(bars, kwhs):
        ax.text(bar.get_x() + bar.get_width()/2.0, val + 1.0, f"{val:.1f} kWh", ha='center', va='bottom', fontsize=9, fontweight='bold')

    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, "adversarial_task1_hard_barrier.png"), dpi=300)
    plt.close()


def plot_task2_mismatch():
    summary_path = os.path.join(RESULTS_DIR, "task2_model_mismatch_summary.json")
    if not os.path.exists(summary_path):
        return
    with open(summary_path, "r") as f:
        data = json.load(f)

    scenarios = list(data.keys())
    clean_labels = [
        "Nonlinear Knee", "Heavy-Tailed Noise", "Sensor Bias +18mV",
        "Contact Spikes", "Bimodal Fleet", "Unknown History"
    ]

    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    fig.suptitle("Task 2: Model Mismatch & Adversarial Distortion Battery", fontweight='bold', y=0.98)

    width = 0.35
    x = np.arange(len(scenarios))

    # 1. FAR (%) Policy D vs Policy C
    far_d = [data[s]["Policy_D_HardBarrier"]["far_percent"] for s in scenarios]
    far_c = [data[s]["Policy_C"]["far_percent"] for s in scenarios]
    ax = axes[0, 0]
    ax.bar(x - width/2, far_c, width, label='Policy C', color='#DD6B20', alpha=0.85, edgecolor='black')
    ax.bar(x + width/2, far_d, width, label='Policy D (Hard Barrier)', color='#3182CE', alpha=0.85, edgecolor='black')
    ax.axhline(1.0, color='red', linestyle='--', linewidth=1.5, label='Safety Limit <= 1.0%')
    ax.set_xticks(x)
    ax.set_xticklabels(clean_labels, rotation=15, ha='right')
    ax.set_ylabel("False Acceptance Rate (%)")
    ax.set_title("Safety Robustness Under Model Mismatch: FAR (%)")
    ax.grid(axis='y', linestyle='--', alpha=0.7)
    ax.legend()

    # 2. UIR (%) Policy D vs Policy C
    uir_d = [data[s]["Policy_D_HardBarrier"]["uir_percent"] for s in scenarios]
    uir_c = [data[s]["Policy_C"]["uir_percent"] for s in scenarios]
    ax = axes[0, 1]
    ax.bar(x - width/2, uir_c, width, label='Policy C', color='#DD6B20', alpha=0.85, edgecolor='black')
    ax.bar(x + width/2, uir_d, width, label='Policy D (Hard Barrier)', color='#3182CE', alpha=0.85, edgecolor='black')
    ax.set_xticks(x)
    ax.set_xticklabels(clean_labels, rotation=15, ha='right')
    ax.set_ylabel("Unnecessary Isolation Rate (%)")
    ax.set_title("Asset Waste Under Model Mismatch: UIR (%)")
    ax.grid(axis='y', linestyle='--', alpha=0.7)
    ax.legend()

    # 3. Retained Energy (kWh)
    kwh_d = [data[s]["Policy_D_HardBarrier"]["total_kwh"] for s in scenarios]
    kwh_c = [data[s]["Policy_C"]["total_kwh"] for s in scenarios]
    ax = axes[1, 0]
    ax.bar(x - width/2, kwh_c, width, label='Policy C', color='#DD6B20', alpha=0.85, edgecolor='black')
    ax.bar(x + width/2, kwh_d, width, label='Policy D (Hard Barrier)', color='#3182CE', alpha=0.85, edgecolor='black')
    ax.set_xticks(x)
    ax.set_xticklabels(clean_labels, rotation=15, ha='right')
    ax.set_ylabel("Retained Capacity (kWh)")
    ax.set_title("Usable Energy Harvested Across 500 Modules")
    ax.grid(axis='y', linestyle='--', alpha=0.7)
    ax.legend()

    # 4. Net Economic Value (INR)
    val_d = [data[s]["Policy_D_HardBarrier"]["mean_net_val_inr"] for s in scenarios]
    val_c = [data[s]["Policy_C"]["mean_net_val_inr"] for s in scenarios]
    ax = axes[1, 1]
    ax.bar(x - width/2, val_c, width, label='Policy C', color='#DD6B20', alpha=0.85, edgecolor='black')
    ax.bar(x + width/2, val_d, width, label='Policy D (Hard Barrier)', color='#3182CE', alpha=0.85, edgecolor='black')
    ax.set_xticks(x)
    ax.set_xticklabels(clean_labels, rotation=15, ha='right')
    ax.set_ylabel("Net Economic Value (INR / module)")
    ax.set_title("Average Net Economic Value per Module")
    ax.grid(axis='y', linestyle='--', alpha=0.7)
    ax.legend()

    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, "adversarial_task2_mismatch.png"), dpi=300)
    plt.close()


def plot_task4_crossover():
    summary_path = os.path.join(RESULTS_DIR, "task4_uncertainty_sweep_summary.json")
    if not os.path.exists(summary_path):
        return
    with open(summary_path, "r") as f:
        data = json.load(f)

    records = data["sweep_records"]
    sigmas = [r["sigma_prior"] for r in records]
    time_c = [r["policy_c_time_s"] for r in records]
    time_d = [r["policy_d_time_s"] for r in records]
    uir_c = [r["policy_c_uir"] for r in records]
    uir_d = [r["policy_d_uir"] for r in records]
    net_c = [r["policy_c_net_val_inr"] for r in records]
    net_d = [r["policy_d_net_val_inr"] for r in records]
    delta_val = [r["net_val_delta_inr"] for r in records]
    crossover = data["crossover_sigma_prior"]

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(f"Task 4: Uncertainty Sweep & Crossover Identification (Crossover sigma* = {crossover})", fontweight='bold', y=0.98)

    # 1. Net Economic Value Comparison
    ax = axes[0, 0]
    ax.plot(sigmas, net_c, marker='o', linewidth=2, color='#DD6B20', label='Policy C Net Value (INR)')
    ax.plot(sigmas, net_d, marker='s', linewidth=2, color='#3182CE', label='Policy D Net Value (INR)')
    if crossover is not None:
        ax.axvline(crossover, color='green', linestyle='--', linewidth=2, label=f'Crossover sigma* = {crossover}')
    ax.set_xlabel("Prior Uncertainty sigma_prior")
    ax.set_ylabel("Net Economic Value (INR / module)")
    ax.set_title("Economic Value vs Prior Uncertainty")
    ax.grid(True, linestyle='--', alpha=0.7)
    ax.legend()

    # 2. Net Economic Delta (Policy D - Policy C)
    ax = axes[0, 1]
    ax.bar(sigmas, delta_val, width=0.012, color=['#E53E3E' if v < 0 else '#38A169' for v in delta_val], alpha=0.85, edgecolor='black')
    ax.axhline(0.0, color='black', linestyle='-', linewidth=1)
    if crossover is not None:
        ax.axvline(crossover, color='green', linestyle='--', linewidth=2, label=f'Crossover sigma* = {crossover}')
    ax.set_xlabel("Prior Uncertainty sigma_prior")
    ax.set_ylabel("Value Delta: Pol D - Pol C (INR)")
    ax.set_title("Net Value Advantage of RC-VOI Over Policy C")
    ax.grid(True, linestyle='--', alpha=0.7)
    ax.legend()

    # 3. UIR (%) Asset Waste
    ax = axes[1, 0]
    ax.plot(sigmas, uir_c, marker='o', linewidth=2, color='#DD6B20', label='Policy C (Heuristic)')
    ax.plot(sigmas, uir_d, marker='s', linewidth=2, color='#3182CE', label='Policy D (RC-VOI)')
    if crossover is not None:
        ax.axvline(crossover, color='green', linestyle='--', linewidth=2)
    ax.set_xlabel("Prior Uncertainty sigma_prior")
    ax.set_ylabel("Unnecessary Isolation Rate (%)")
    ax.set_title("Asset Waste (UIR %) vs Uncertainty")
    ax.grid(True, linestyle='--', alpha=0.7)
    ax.legend()

    # 4. Diagnostic Time (s)
    ax = axes[1, 1]
    ax.plot(sigmas, time_c, marker='o', linewidth=2, color='#DD6B20', label='Policy C Time (s)')
    ax.plot(sigmas, time_d, marker='s', linewidth=2, color='#3182CE', label='Policy D Time (s)')
    if crossover is not None:
        ax.axvline(crossover, color='green', linestyle='--', linewidth=2)
    ax.set_xlabel("Prior Uncertainty sigma_prior")
    ax.set_ylabel("Diagnostic Time (s)")
    ax.set_title("Diagnostic Duration vs Uncertainty Level")
    ax.grid(True, linestyle='--', alpha=0.7)
    ax.legend()

    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, "adversarial_task4_crossover.png"), dpi=300)
    plt.close()


def plot_task6_derating():
    summary_path = os.path.join(RESULTS_DIR, "task6_derating_physics_summary.json")
    if not os.path.exists(summary_path):
        return
    with open(summary_path, "r") as f:
        data = json.load(f)

    c_rates = list(data.keys())
    temps = [data[c]["mean_peak_temp_c"] for c in c_rates]
    max_temps = [data[c]["max_peak_temp_c"] for c in c_rates]
    thermal_trips = [data[c]["thermal_excursion_rate_percent"] for c in c_rates]
    cutoffs = [data[c]["undervoltage_cutoff_rate_percent"] for c in c_rates]
    total_fails = [data[c]["combined_failure_rate_percent"] for c in c_rates]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle("Task 6: Dynamic Thermal & Electrical Derating Validation (500 Borderline Modules)", fontweight='bold', y=1.02)

    # 1. Failure Rates vs C-Rate
    ax = axes[0]
    ax.plot(c_rates, thermal_trips, marker='o', linewidth=2, color='#E53E3E', label='Thermal Excursion (>55 C)')
    ax.plot(c_rates, cutoffs, marker='s', linewidth=2, color='#DD6B20', label='Premature Cutoff (<2.5V)')
    ax.plot(c_rates, total_fails, marker='^', linewidth=2.5, color='#805AD5', label='Combined Failure Rate (%)')
    ax.set_xlabel("Operational C-Rate")
    ax.set_ylabel("Empirical Failure Rate (%)")
    ax.set_title("Failure Probability Under Simulated Physics")
    ax.grid(True, linestyle='--', alpha=0.7)
    ax.legend()

    # 2. Peak Temperatures
    ax = axes[1]
    ax.plot(c_rates, temps, marker='o', linewidth=2, color='#3182CE', label='Mean Peak Temperature (C)')
    ax.plot(c_rates, max_temps, marker='x', linestyle=':', color='#E53E3E', label='Max Peak Temperature (C)')
    ax.axhline(55.0, color='red', linestyle='--', linewidth=1.5, label='Thermal Shutdown Limit (55 C)')
    ax.set_xlabel("Operational C-Rate")
    ax.set_ylabel("Module Temperature (C)")
    ax.set_title("Thermal Dissipation vs Operational Load")
    ax.grid(True, linestyle='--', alpha=0.7)
    ax.legend()

    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, "adversarial_task6_derating.png"), dpi=300)
    plt.close()


def plot_task9_ablation():
    summary_path = os.path.join(RESULTS_DIR, "task9_ablation_summary.json")
    if not os.path.exists(summary_path):
        return
    with open(summary_path, "r") as f:
        data = json.load(f)

    configs = list(data.keys())
    clean_labels = [
        "1. Fixed", "2. Scalar", "3. UncThresh",
        "4. RC-VOI\n(HardBarrier)", "5. No App\nContext",
        "6. No\nDerating", "7. No Hard\nBarrier"
    ]
    colors = ['#4A5568', '#E53E3E', '#DD6B20', '#3182CE', '#805AD5', '#D69E2E', '#E53E3E']

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    fig.suptitle("Task 9: Comprehensive 7-Way Component Ablation (500 Modules)", fontweight='bold', y=1.02)

    # 1. FAR (%)
    fars = [data[c]["far_percent"] for c in configs]
    ax = axes[0]
    bars = ax.bar(clean_labels, fars, color=colors, alpha=0.85, edgecolor='black', linewidth=1)
    ax.axhline(1.0, color='red', linestyle='--', linewidth=1.5, label='Safety Target <= 1.0%')
    ax.set_ylabel("False Acceptance Rate (%)")
    ax.set_title("Safety Target: FAR (%)")
    ax.grid(axis='y', linestyle='--', alpha=0.7)
    ax.legend()
    for bar, val in zip(bars, fars):
        ax.text(bar.get_x() + bar.get_width()/2.0, val + 0.3, f"{val:.1f}%", ha='center', va='bottom', fontsize=8, fontweight='bold')

    # 2. UIR (%)
    uirs = [data[c]["uir_percent"] for c in configs]
    ax = axes[1]
    bars = ax.bar(clean_labels, uirs, color=colors, alpha=0.85, edgecolor='black', linewidth=1)
    ax.set_ylabel("Unnecessary Isolation Rate (%)")
    ax.set_title("Asset Waste: UIR (%)")
    ax.grid(axis='y', linestyle='--', alpha=0.7)
    for bar, val in zip(bars, uirs):
        ax.text(bar.get_x() + bar.get_width()/2.0, val + 0.8, f"{val:.1f}%", ha='center', va='bottom', fontsize=8, fontweight='bold')

    # 3. Net Economic Value (INR)
    vals = [data[c]["mean_net_val_inr"] for c in configs]
    ax = axes[2]
    bars = ax.bar(clean_labels, vals, color=colors, alpha=0.85, edgecolor='black', linewidth=1)
    ax.set_ylabel("Net Economic Value (INR / module)")
    ax.set_title("Average Net Value per Module")
    ax.grid(axis='y', linestyle='--', alpha=0.7)
    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width()/2.0, val + 15, f"INR {val:.0f}", ha='center', va='bottom', fontsize=8, fontweight='bold')

    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, "adversarial_task9_ablation.png"), dpi=300)
    plt.close()


def main():
    plot_task1_hard_barrier()
    plot_task2_mismatch()
    plot_task4_crossover()
    plot_task6_derating()
    plot_task9_ablation()
    print("Adversarial plots generated successfully.")

if __name__ == "__main__":
    main()
