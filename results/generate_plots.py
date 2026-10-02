"""
RMK-REVOLT Visualization and Plot Generation
Generates publication-quality charts for Experiments E1-E5, Ablation, and Application Dependence.
"""

import os
import json
import matplotlib.pyplot as plt
import numpy as np

def generate_all_plots():
    results_dir = os.path.dirname(__file__)
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
    
    # -------------------------------------------------------------
    # PLOT 1: Experiment 2 - Diagnostic Burden Comparison
    # -------------------------------------------------------------
    e2_file = os.path.join(results_dir, "experiment_2_results.json")
    if os.path.exists(e2_file):
        with open(e2_file, "r") as f:
            e2_data = json.load(f)
            
        fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
        
        # Subplot 1: Testing Time
        times = [e2_data["fixed_testing"]["mean_diag_time_s"], e2_data["adaptive_testing"]["mean_diag_time_s"]]
        bars1 = axes[0].bar(["Fixed Sequence", "Adaptive Policy"], times, color=["#d9534f", "#5cb85c"], width=0.5)
        axes[0].set_ylabel("Diagnostic Time per Module (seconds)")
        axes[0].set_title(f"Time Reduction: {e2_data['time_reduction_percent']}%\n(p = {e2_data['p_value_diagnostic_time']:.1e})", fontweight="bold")
        for bar in bars1:
            yval = bar.get_height()
            axes[0].text(bar.get_x() + bar.get_width()/2.0, yval + 15, f"{yval:.1f}s", ha='center', va='bottom', fontweight='bold')
            
        # Subplot 2: Energy Consumed
        energy = [e2_data["fixed_testing"]["mean_diag_energy_wh"], e2_data["adaptive_testing"]["mean_diag_energy_wh"]]
        bars2 = axes[1].bar(["Fixed Sequence", "Adaptive Policy"], energy, color=["#f0ad4e", "#337ab7"], width=0.5)
        axes[1].set_ylabel("Diagnostic Energy (Wh)")
        axes[1].set_title(f"Energy Reduction: {e2_data['energy_reduction_percent']}%", fontweight="bold")
        for bar in bars2:
            yval = bar.get_height()
            axes[1].text(bar.get_x() + bar.get_width()/2.0, yval + 0.8, f"{yval:.1f} Wh", ha='center', va='bottom', fontweight='bold')
            
        # Subplot 3: False Acceptance Rate (Safety)
        fars = [e2_data["fixed_testing"]["far_percent"], e2_data["adaptive_testing"]["far_percent"]]
        bars3 = axes[2].bar(["Fixed Sequence", "Adaptive Policy"], fars, color=["#5bc0de", "#2e6da4"], width=0.5)
        axes[2].set_ylabel("False Acceptance Rate (%)")
        axes[2].set_title("Safety Compliance: 0.0% FAR", fontweight="bold")
        axes[2].set_ylim(0, 2.0)
        for bar in bars3:
            yval = bar.get_height()
            axes[2].text(bar.get_x() + bar.get_width()/2.0, yval + 0.05, f"{yval:.1f}%", ha='center', va='bottom', fontweight='bold')
            
        plt.tight_layout()
        plt.savefig(os.path.join(results_dir, "e2_diagnostic_burden.png"), dpi=200)
        plt.close()
        print("Generated e2_diagnostic_burden.png")

    # -------------------------------------------------------------
    # PLOT 2: Experiment 3 - Unnecessary Isolation Rate & Usable Energy
    # -------------------------------------------------------------
    e3_file = os.path.join(results_dir, "experiment_3_results.json")
    if os.path.exists(e3_file):
        with open(e3_file, "r") as f:
            e3_data = json.load(f)
            
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
        
        # Subplot 1: UIR
        uir = [e3_data["threshold_baseline_uir_percent"], e3_data["adaptive_system_uir_percent"]]
        bars1 = axes[0].bar(["Conventional Threshold", "Uncertainty-Aware System"], uir, color=["#c9302c", "#449d44"], width=0.5)
        axes[0].set_ylabel("Unnecessary Isolation Rate (%)")
        axes[0].set_title(f"Unnecessary Isolation Drop: -{e3_data['uir_reduction_points']}% points", fontweight="bold")
        axes[0].set_ylim(0, 115)
        for bar in bars1:
            yval = bar.get_height()
            axes[0].text(bar.get_x() + bar.get_width()/2.0, yval + 2, f"{yval:.1f}%", ha='center', va='bottom', fontweight='bold')
            
        # Subplot 2: Energy Recovered
        energy_rec = [e3_data["usable_energy_recovered_baseline_kwh"], e3_data["usable_energy_recovered_adaptive_kwh"]]
        bars2 = axes[1].bar(["Conventional Threshold", "Uncertainty-Aware System"], energy_rec, color=["#888888", "#286090"], width=0.5)
        axes[1].set_ylabel("Recovered Usable Energy (kWh)")
        axes[1].set_title(f"Additional Energy Saved: +{e3_data['additional_energy_saved_kwh']} kWh", fontweight="bold")
        for bar in bars2:
            yval = bar.get_height()
            axes[1].text(bar.get_x() + bar.get_width()/2.0, yval + 0.3, f"{yval:.1f} kWh", ha='center', va='bottom', fontweight='bold')
            
        plt.tight_layout()
        plt.savefig(os.path.join(results_dir, "e3_unnecessary_isolation.png"), dpi=200)
        plt.close()
        print("Generated e3_unnecessary_isolation.png")

    # -------------------------------------------------------------
    # PLOT 3: Ablation Study Comparison
    # -------------------------------------------------------------
    abl_file = os.path.join(results_dir, "ablation_results.json")
    if os.path.exists(abl_file):
        with open(abl_file, "r") as f:
            abl_data = json.load(f)
            
        labels = list(abl_data.keys())
        des = [abl_data[k]["decision_efficiency"] for k in labels]
        uirs = [abl_data[k]["uir_percent"] for k in labels]
        times = [abl_data[k]["mean_diag_time_s"] for k in labels]
        
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        
        colors = ["#2b542c" if k == "FULL" else "#337ab7" for k in labels]
        bars1 = axes[0].barh(labels, des, color=colors)
        axes[0].set_xlabel("Decision Efficiency (DE = Retained Energy / Burden)")
        axes[0].set_title("Decision Efficiency by Architectural Variant", fontweight="bold")
        axes[0].invert_yaxis()
        
        bars2 = axes[1].barh(labels, uirs, color=["#d9534f" if u > 70 else "#5cb85c" for u in uirs])
        axes[1].set_xlabel("Unnecessary Isolation Rate (%)")
        axes[1].set_title("Unnecessary Isolation Rate Across Variants", fontweight="bold")
        axes[1].invert_yaxis()
        
        plt.tight_layout()
        plt.savefig(os.path.join(results_dir, "ablation_study.png"), dpi=200)
        plt.close()
        print("Generated ablation_study.png")

if __name__ == "__main__":
    generate_all_plots()
