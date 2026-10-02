"""
RMK-REVOLT Statistical Calculator
Computes rigorous distribution metrics: Mean, Median, 95% Confidence Intervals,
Cohen's d effect sizes, and worst-case bounds. Avoids p-value reliance.
"""

import numpy as np
from typing import List, Dict, Any, Tuple

def bootstrap_ci(data: np.ndarray, num_resamples: int = 1000, ci: float = 0.95) -> Tuple[float, float]:
    """Calculate non-parametric bootstrap confidence interval."""
    if len(data) == 0:
        return (0.0, 0.0)
    boot_means = []
    n = len(data)
    rng = np.random.RandomState(42)
    for _ in range(num_resamples):
        sample = rng.choice(data, size=n, replace=True)
        boot_means.append(np.mean(sample))
    alpha = (1.0 - ci) / 2.0
    low = np.percentile(boot_means, alpha * 100.0)
    high = np.percentile(boot_means, (1.0 - alpha) * 100.0)
    return float(low), float(high)

def cohens_d(group1: np.ndarray, group2: np.ndarray) -> float:
    """Calculate Cohen's d effect size between two cohorts."""
    n1, n2 = len(group1), len(group2)
    if n1 < 2 or n2 < 2:
        return 0.0
    s1, s2 = np.var(group1, ddof=1), np.var(group2, ddof=1)
    s_pooled = np.sqrt(((n1 - 1) * s1 + (n2 - 1) * s2) / (n1 + n2 - 2))
    if s_pooled < 1e-9:
        return 0.0
    return float((np.mean(group1) - np.mean(group2)) / s_pooled)

def compute_distribution_metrics(values: List[float]) -> Dict[str, float]:
    """Compute comprehensive distribution summary."""
    arr = np.array(values, dtype=float)
    if len(arr) == 0:
        return {}
    mean_val = float(np.mean(arr))
    median_val = float(np.median(arr))
    std_val = float(np.std(arr, ddof=1))
    ci_low, ci_high = bootstrap_ci(arr)
    return {
        "mean": round(mean_val, 3),
        "median": round(median_val, 3),
        "std": round(std_val, 3),
        "ci_95_low": round(ci_low, 3),
        "ci_95_high": round(ci_high, 3),
        "p5": round(float(np.percentile(arr, 5)), 3),
        "p25": round(float(np.percentile(arr, 25)), 3),
        "p75": round(float(np.percentile(arr, 75)), 3),
        "p95": round(float(np.percentile(arr, 95)), 3),
        "min": round(float(np.min(arr)), 3),
        "max": round(float(np.max(arr)), 3)
    }
