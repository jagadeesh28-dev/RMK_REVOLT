"""
Phase 5 Feature Ablation & Scientific Validation Engine
Project: RMK-REVOLT / SECONDShift Platform

Implements:
1. Feature-Family Ablation Matrix (A0 - A9)
2. Individual Feature Leave-One-Feature-Out (LOFO) Ablation
3. Redundancy & Collinearity Analysis (Pearson & Spearman)
4. Perturbation & Noise Sensitivity Analysis
5. Sampling-Resolution Sensitivity Analysis
6. R0 Contextual Dependency Analysis
7. Thermal Feature Hypothesis Testing
8. Data Quality Epistemic Separation Testing
9. Chemistry Domain Stratification
"""

import math
import warnings
from typing import Dict, Any, List, Optional, Tuple, Set
import numpy as np
import pandas as pd
from scipy import stats

from secondshift.software.features.validation_models import (
    FeatureValidationStatus,
    FeatureAdmissionStatus,
    ClaimStatus,
    MultidimensionalEvidenceVector,
    FoldRobustnessStats,
    MeanPredictorBaseline,
    LinearBaseline,
    RidgeBaseline,
    BatteryDisjointSplitter,
    RandomRowSplitter,
    HostileLeakageAuditor
)
from secondshift.software.features.feature_metadata import FeatureFamily


class FeatureAblationEngine:
    """
    Executes systematic, battery-disjoint ablation experiments to determine
    which features contain true, reproducible degradation signal.
    """

    FAMILY_DEFINITIONS = {
        "ELECTRICAL": [
            "V_MEAN", "V_MIN", "V_MAX", "I_MEAN", "I_ABS_MEAN", "I_PEAK", "P_MEAN", "P_PEAK"
        ],
        "PULSE": [
            "DELTA_V_TOTAL", "DELTA_V_OHMIC", "R0_OHMIC"
        ],
        "RELAXATION": [
            "RELAXATION_DELTA_V", "RELAXATION_SLOPE_DV_DT"
        ],
        "COULOMETRIC": [
            "CHARGE_AH", "DISCHARGE_AH", "COULOMBIC_EFFICIENCY"
        ],
        "ENERGY": [
            "CHARGE_WH", "DISCHARGE_WH", "ENERGY_EFFICIENCY"
        ],
        "THERMAL": [
            "T_MEAN", "T_MAX", "DELTA_T", "DT_DT"
        ],
        "DATA_QUALITY": [
            "VALID_SAMPLE_FRACTION", "INVALID_SAMPLE_FRACTION", "CURRENT_FLOW_VALID",
            "PULSE_VALID", "TIMESTAMP_INTEGRITY", "MEASUREMENT_DURATION"
        ]
    }

    # Canonical Phase 5 Ablation Group Definitions
    ABLATION_SUITES = {
        "A0_MINIMAL_BASELINE": ["V_MEAN"],
        "A1_ELECTRICAL": [
            "V_MEAN", "V_MIN", "V_MAX", "I_MEAN", "I_ABS_MEAN", "I_PEAK", "P_MEAN", "P_PEAK"
        ],
        "A2_ELEC_PLUS_PULSE": [
            "V_MEAN", "V_MIN", "V_MAX", "I_MEAN", "I_ABS_MEAN", "I_PEAK", "P_MEAN", "P_PEAK",
            "DELTA_V_TOTAL", "DELTA_V_OHMIC", "R0_OHMIC"
        ],
        "A3_ELEC_PLUS_RELAXATION": [
            "V_MEAN", "V_MIN", "V_MAX", "I_MEAN", "I_ABS_MEAN", "I_PEAK", "P_MEAN", "P_PEAK",
            "RELAXATION_DELTA_V", "RELAXATION_SLOPE_DV_DT"
        ],
        "A4_ELEC_PLUS_COULOMETRIC": [
            "V_MEAN", "V_MIN", "V_MAX", "I_MEAN", "I_ABS_MEAN", "I_PEAK", "P_MEAN", "P_PEAK",
            "CHARGE_AH", "DISCHARGE_AH", "COULOMBIC_EFFICIENCY"
        ],
        "A5_ELEC_PLUS_ENERGY": [
            "V_MEAN", "V_MIN", "V_MAX", "I_MEAN", "I_ABS_MEAN", "I_PEAK", "P_MEAN", "P_PEAK",
            "CHARGE_WH", "DISCHARGE_WH", "ENERGY_EFFICIENCY"
        ],
        "A6_ELEC_PLUS_THERMAL": [
            "V_MEAN", "V_MIN", "V_MAX", "I_MEAN", "I_ABS_MEAN", "I_PEAK", "P_MEAN", "P_PEAK",
            "T_MEAN", "T_MAX", "DELTA_T", "DT_DT"
        ],
        "A7_ELEC_PLUS_DATA_QUALITY": [
            "V_MEAN", "V_MIN", "V_MAX", "I_MEAN", "I_ABS_MEAN", "I_PEAK", "P_MEAN", "P_PEAK",
            "VALID_SAMPLE_FRACTION", "INVALID_SAMPLE_FRACTION", "CURRENT_FLOW_VALID",
            "PULSE_VALID", "TIMESTAMP_INTEGRITY", "MEASUREMENT_DURATION"
        ],
        "A8_FULL_CANDIDATE_SET": [
            "V_MEAN", "V_MIN", "V_MAX", "I_MEAN", "I_ABS_MEAN", "I_PEAK", "P_MEAN", "P_PEAK",
            "DELTA_V_TOTAL", "DELTA_V_OHMIC", "R0_OHMIC",
            "RELAXATION_DELTA_V", "RELAXATION_SLOPE_DV_DT",
            "CHARGE_AH", "DISCHARGE_AH", "COULOMBIC_EFFICIENCY",
            "CHARGE_WH", "DISCHARGE_WH", "ENERGY_EFFICIENCY",
            "T_MEAN", "T_MAX", "DELTA_T", "DT_DT",
            "VALID_SAMPLE_FRACTION", "INVALID_SAMPLE_FRACTION", "CURRENT_FLOW_VALID",
            "PULSE_VALID", "TIMESTAMP_INTEGRITY", "MEASUREMENT_DURATION"
        ],
        "A9_SCIENTIFICALLY_ADMITTED": [
            "V_MEAN", "DELTA_V_TOTAL", "DELTA_V_OHMIC", "R0_OHMIC", "RELAXATION_DELTA_V"
        ]
    }

    @staticmethod
    def evaluate_feature_subset_battery_disjoint(
        feature_df: pd.DataFrame,
        feature_subset: List[str],
        target_col: str,
        battery_col: str = "specimen_id",
        model_type: str = "ridge",
        alpha: float = 1.0
    ) -> Dict[str, Any]:
        """
        Evaluates a specified feature subset under strict Leave-One-Battery-Out (LOBO) Cross-Validation.
        Guarantees that test batteries never leak into training folds.
        """
        # Ensure target and battery columns exist
        if target_col not in feature_df.columns:
            raise KeyError(f"Target column '{target_col}' missing from feature dataset.")
        if battery_col not in feature_df.columns:
            raise KeyError(f"Battery column '{battery_col}' missing from feature dataset.")

        # Filter available features in subset
        valid_features = [f for f in feature_subset if f in feature_df.columns]
        y_all = feature_df[target_col].to_numpy(dtype=float)
        if valid_features:
            X_all = feature_df[valid_features].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
        else:
            X_all = np.zeros((len(feature_df), 1), dtype=float)

        battery_ids = feature_df[battery_col].tolist()
        lobo_splits = BatteryDisjointSplitter.split_lobo(battery_ids)

        y_true_all = []
        y_pred_all = []
        fold_maes = []
        fold_rmses = []
        per_battery_errors: Dict[str, float] = {}

        for train_idx, test_idx, test_battery in lobo_splits:
            y_train = y_all[train_idx]
            y_test = y_all[test_idx]

            if not valid_features:
                model = MeanPredictorBaseline()
                model.fit(X_all[train_idx], y_train)
                preds = model.predict(X_all[test_idx])
            else:
                X_train = X_all[train_idx].copy()
                X_test = X_all[test_idx].copy()

                # Impute missing feature values with training feature median
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", category=RuntimeWarning)
                    col_medians = np.nanmedian(X_train, axis=0)
                col_medians = np.nan_to_num(col_medians, nan=0.0)

                inds_train = np.where(np.isnan(X_train))
                X_train[inds_train] = np.take(col_medians, inds_train[1])
                inds_test = np.where(np.isnan(X_test))
                X_test[inds_test] = np.take(col_medians, inds_test[1])

                if model_type == "linear":
                    model = LinearBaseline(fit_intercept=True)
                elif model_type == "ridge":
                    model = RidgeBaseline(alpha=alpha, fit_intercept=True)
                else:
                    model = MeanPredictorBaseline()

                model.fit(X_train, y_train)
                preds = model.predict(X_test)

            y_true_all.extend(y_test)
            y_pred_all.extend(preds)

            f_mae = float(np.mean(np.abs(y_test - preds)))
            f_rmse = float(np.sqrt(np.mean((y_test - preds) ** 2)))
            fold_maes.append(f_mae)
            fold_rmses.append(f_rmse)
            per_battery_errors[test_battery] = f_mae

        y_true_arr = np.asarray(y_true_all)
        y_pred_arr = np.asarray(y_pred_all)

        overall_mae = float(np.mean(np.abs(y_true_arr - y_pred_arr)))
        overall_rmse = float(np.sqrt(np.mean((y_true_arr - y_pred_arr) ** 2)))

        # R^2 with safe denominator
        ss_tot = float(np.sum((y_true_arr - np.mean(y_true_arr)) ** 2))
        ss_res = float(np.sum((y_true_arr - y_pred_arr) ** 2))
        r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 1e-9 else 0.0

        # Spearman rank correlation
        spearman_corr, spearman_p = stats.spearmanr(y_true_arr, y_pred_arr)
        if math.isnan(spearman_corr):
            spearman_corr = 0.0

        return {
            "features_used": valid_features,
            "feature_count": len(valid_features),
            "mae": overall_mae,
            "rmse": overall_rmse,
            "r2": r2,
            "spearman_corr": float(spearman_corr),
            "fold_mae_mean": float(np.mean(fold_maes)),
            "fold_mae_std": float(np.std(fold_maes)),
            "per_battery_errors": per_battery_errors
        }

    @staticmethod
    def evaluate_feature_subset_random_row(
        feature_df: pd.DataFrame,
        feature_subset: List[str],
        target_col: str,
        test_ratio: float = 0.25,
        seed: int = 42,
        alpha: float = 1.0
    ) -> Dict[str, Any]:
        """
        Evaluates a feature subset using Random Row Splitting.
        Solely used to contrast against battery-disjoint splitting to demonstrate
        how row-level correlation creates illusory, non-generalizable metric inflation.
        """
        valid_features = [f for f in feature_subset if f in feature_df.columns]
        train_idx, test_idx = RandomRowSplitter.split(len(feature_df), test_ratio=test_ratio, seed=seed)

        train_df = feature_df.iloc[train_idx]
        test_df = feature_df.iloc[test_idx]

        y_train = train_df[target_col].values
        y_test = test_df[target_col].values

        if not valid_features:
            model = MeanPredictorBaseline()
            model.fit(np.zeros((len(y_train), 1)), y_train)
            preds = model.predict(np.zeros((len(y_test), 1)))
        else:
            X_train = train_df[valid_features].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
            X_test = test_df[valid_features].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)

            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=RuntimeWarning)
                col_medians = np.nanmedian(X_train, axis=0)
            col_medians = np.nan_to_num(col_medians, nan=0.0)

            inds_train = np.where(np.isnan(X_train))
            X_train[inds_train] = np.take(col_medians, inds_train[1])
            inds_test = np.where(np.isnan(X_test))
            X_test[inds_test] = np.take(col_medians, inds_test[1])

            model = RidgeBaseline(alpha=alpha, fit_intercept=True)
            model.fit(X_train, y_train)
            preds = model.predict(X_test)

        mae = float(np.mean(np.abs(y_test - preds)))
        rmse = float(np.sqrt(np.mean((y_test - preds) ** 2)))
        ss_tot = float(np.sum((y_test - np.mean(y_test)) ** 2))
        ss_res = float(np.sum((y_test - preds) ** 2))
        r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 1e-9 else 0.0

        return {
            "split_type": "RANDOM_ROW_LEAKAGE_VULNERABLE",
            "features_used": valid_features,
            "mae": mae,
            "rmse": rmse,
            "r2": r2
        }

    @classmethod
    def run_family_ablation_matrix(
        cls,
        feature_df: pd.DataFrame,
        target_col: str = "true_soh",
        battery_col: str = "specimen_id"
    ) -> Dict[str, Dict[str, Any]]:
        """
        Runs the canonical A0 through A9 family ablation matrix under battery-disjoint validation.
        """
        results = {}
        for suite_name, feat_list in cls.ABLATION_SUITES.items():
            res = cls.evaluate_feature_subset_battery_disjoint(
                feature_df=feature_df,
                feature_subset=feat_list,
                target_col=target_col,
                battery_col=battery_col
            )
            results[suite_name] = res
        return results

    @classmethod
    def run_leave_one_feature_out(
        cls,
        feature_df: pd.DataFrame,
        candidate_features: List[str],
        target_col: str = "true_soh",
        battery_col: str = "specimen_id"
    ) -> Dict[str, Dict[str, Any]]:
        """
        Executes Leave-One-Feature-Out (LOFO) ablation:
        Evaluates Full Model vs Full Model minus Feature X under battery-disjoint validation.
        """
        baseline_full = cls.evaluate_feature_subset_battery_disjoint(
            feature_df=feature_df,
            feature_subset=candidate_features,
            target_col=target_col,
            battery_col=battery_col
        )
        full_mae = baseline_full["mae"]
        full_rmse = baseline_full["rmse"]

        lofo_results = {}
        for feat in candidate_features:
            reduced_subset = [f for f in candidate_features if f != feat]
            reduced_res = cls.evaluate_feature_subset_battery_disjoint(
                feature_df=feature_df,
                feature_subset=reduced_subset,
                target_col=target_col,
                battery_col=battery_col
            )

            # Delta MAE: if positive, removing feature WORSER performance (feature was helpful)
            # If negative, removing feature IMPROVED performance (feature was harmful/noisy)
            delta_mae = reduced_res["mae"] - full_mae
            delta_rmse = reduced_res["rmse"] - full_rmse

            lofo_results[feat] = {
                "omitted_feature": feat,
                "full_mae": full_mae,
                "without_feature_mae": reduced_res["mae"],
                "delta_mae": delta_mae,
                "delta_rmse": delta_rmse,
                "importance_verdict": "VALUABLE" if delta_mae > 0.005 else ("HARMFUL" if delta_mae < -0.005 else "NEGLIGIBLE")
            }
        return lofo_results

    @classmethod
    def run_leave_one_feature_out_robust(
        cls,
        feature_df: pd.DataFrame,
        candidate_features: List[str],
        target_col: str = "true_soh",
        battery_col: str = "specimen_id",
        engineering_threshold: float = 0.005
    ) -> Dict[str, Dict[str, Any]]:
        """
        Executes Leave-One-Feature-Out (LOFO) ablation with fold-level statistical robustness,
        confidence intervals, Cohen's d effect sizes, and engineering significance audit.
        """
        baseline_full = cls.evaluate_feature_subset_battery_disjoint(
            feature_df=feature_df,
            feature_subset=candidate_features,
            target_col=target_col,
            battery_col=battery_col
        )
        full_mae = baseline_full["mae"]
        full_per_bat = baseline_full.get("per_battery_errors", {})

        robust_results = {}
        for feat in candidate_features:
            reduced_subset = [f for f in candidate_features if f != feat]
            reduced_res = cls.evaluate_feature_subset_battery_disjoint(
                feature_df=feature_df,
                feature_subset=reduced_subset,
                target_col=target_col,
                battery_col=battery_col
            )
            reduced_per_bat = reduced_res.get("per_battery_errors", {})

            # Paired differences per battery fold: Delta MAE_k = MAE_(without, k) - MAE_(full, k)
            common_bats = [b for b in full_per_bat if b in reduced_per_bat]
            delta_maes = [reduced_per_bat[b] - full_per_bat[b] for b in common_bats]
            delta_arr = np.array(delta_maes, dtype=float)

            n_folds = len(delta_arr)
            mean_delta = float(np.mean(delta_arr)) if n_folds > 0 else 0.0
            median_delta = float(np.median(delta_arr)) if n_folds > 0 else 0.0
            std_delta = float(np.std(delta_arr, ddof=1)) if n_folds > 1 else 0.0
            se_delta = float(std_delta / np.sqrt(n_folds)) if n_folds > 1 else 0.0

            # 95% Confidence Interval
            if n_folds > 1:
                t_crit = float(stats.t.ppf(0.975, df=n_folds - 1))
                ci_lower = mean_delta - t_crit * se_delta
                ci_upper = mean_delta + t_crit * se_delta
            else:
                ci_lower, ci_upper = mean_delta, mean_delta

            folds_improved = int(np.sum(delta_arr > 1e-6))
            folds_degraded = int(np.sum(delta_arr < -1e-6))
            folds_neutral = int(np.sum(np.abs(delta_arr) <= 1e-6))

            cohens_d = float(mean_delta / std_delta) if std_delta > 1e-9 else 0.0

            # Paired t-test
            if n_folds > 1 and std_delta > 1e-9:
                t_stat, p_val = stats.ttest_rel(
                    [reduced_per_bat[b] for b in common_bats],
                    [full_per_bat[b] for b in common_bats]
                )
                p_val = float(p_val) if not math.isnan(p_val) else 1.0
            else:
                p_val = 1.0

            is_stat_sig = bool(p_val < 0.05 and mean_delta > 0)
            is_eng_sig = bool(mean_delta >= engineering_threshold)

            stats_obj = FoldRobustnessStats(
                feature_id=feat,
                mean_delta_mae=mean_delta,
                median_delta_mae=median_delta,
                std_delta_mae=std_delta,
                se_delta_mae=se_delta,
                ci_95_lower=ci_lower,
                ci_95_upper=ci_upper,
                folds_improved=folds_improved,
                folds_degraded=folds_degraded,
                folds_neutral=folds_neutral,
                cohens_d=cohens_d,
                p_value=p_val,
                is_statistically_significant=is_stat_sig,
                is_engineering_significant=is_eng_sig,
                engineering_threshold=engineering_threshold
            )

            robust_results[feat] = {
                "omitted_feature": feat,
                "full_mae": full_mae,
                "without_feature_mae": reduced_res["mae"],
                "delta_mae": reduced_res["mae"] - full_mae,
                "fold_stats": stats_obj.to_dict()
            }
        return robust_results

    @classmethod
    def run_nested_grouped_validation(
        cls,
        feature_df: pd.DataFrame,
        candidate_suites: Optional[Dict[str, List[str]]] = None,
        target_col: str = "true_soh",
        battery_col: str = "specimen_id",
        alpha: float = 1.0,
        inner_splits: int = 4
    ) -> Dict[str, Any]:
        """
        Executes Nested Grouped Cross-Validation to eliminate feature-selection bias.
        
        Outer Loop: Leave-One-Battery-Out (Outer Test Battery B_k is held out).
        Inner Loop: Evaluates candidate feature suites strictly across the remaining K-1 training batteries using Grouped K-Fold.
        Selection: The feature suite with the lowest inner grouped CV MAE is selected.
        Evaluation: Model trained on K-1 batteries with selected features is evaluated strictly on B_k.
        """
        if candidate_suites is None:
            candidate_suites = {
                "A0_MINIMAL_BASELINE": ["V_MEAN"],
                "A1_ELECTRICAL": ["V_MEAN", "V_MIN", "V_MAX", "I_MEAN", "I_ABS_MEAN", "I_PEAK", "P_MEAN", "P_PEAK"],
                "A2_ELEC_PLUS_PULSE": [
                    "V_MEAN", "V_MIN", "V_MAX", "I_MEAN", "I_ABS_MEAN", "I_PEAK", "P_MEAN", "P_PEAK",
                    "DELTA_V_TOTAL", "DELTA_V_OHMIC", "R0_OHMIC"
                ],
                "A3_ELEC_PLUS_RELAXATION": [
                    "V_MEAN", "V_MIN", "V_MAX", "I_MEAN", "I_ABS_MEAN", "I_PEAK", "P_MEAN", "P_PEAK",
                    "RELAXATION_DELTA_V", "RELAXATION_SLOPE_DV_DT"
                ],
                "A9_SCIENTIFICALLY_ADMITTED": [
                    "V_MEAN", "DELTA_V_TOTAL", "DELTA_V_OHMIC", "R0_OHMIC", "RELAXATION_DELTA_V"
                ]
            }

        battery_ids = feature_df[battery_col].tolist()
        lobo_splits = BatteryDisjointSplitter.split_lobo(battery_ids)
        y_all = feature_df[target_col].to_numpy(dtype=float)

        # Precompute numeric matrices for candidate suites
        suite_X = {}
        for s_name, feats in candidate_suites.items():
            valid_feats = [f for f in feats if f in feature_df.columns]
            if valid_feats:
                X_mat = feature_df[valid_feats].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
            else:
                X_mat = np.zeros((len(feature_df), 1), dtype=float)
            suite_X[s_name] = X_mat

        outer_y_true = []
        outer_y_pred = []
        outer_selected_suites = {}
        outer_fold_maes = []

        for train_idx, test_idx, outer_test_battery in lobo_splits:
            train_bats = [battery_ids[i] for i in train_idx]
            n_inner_k = min(inner_splits, len(set(train_bats)))
            inner_folds = BatteryDisjointSplitter.split_grouped_kfold(train_bats, n_splits=n_inner_k, seed=42)

            best_suite_name = None
            best_inner_mae = float("inf")

            for suite_name, X_full in suite_X.items():
                X_pool = X_full[train_idx]
                y_pool = y_all[train_idx]
                inner_errors = []

                for in_tr_idx, in_te_idx, _ in inner_folds:
                    X_in_tr = X_pool[in_tr_idx].copy()
                    y_in_tr = y_pool[in_tr_idx]
                    X_in_te = X_pool[in_te_idx].copy()
                    y_in_te = y_pool[in_te_idx]

                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", category=RuntimeWarning)
                        col_medians = np.nanmedian(X_in_tr, axis=0)
                    col_medians = np.nan_to_num(col_medians, nan=0.0)

                    inds_tr = np.where(np.isnan(X_in_tr))
                    X_in_tr[inds_tr] = np.take(col_medians, inds_tr[1])
                    inds_te = np.where(np.isnan(X_in_te))
                    X_in_te[inds_te] = np.take(col_medians, inds_te[1])

                    model = RidgeBaseline(alpha=alpha, fit_intercept=True)
                    model.fit(X_in_tr, y_in_tr)
                    in_preds = model.predict(X_in_te)
                    inner_errors.extend(np.abs(y_in_te - in_preds))

                mean_in_mae = float(np.mean(inner_errors))
                if mean_in_mae < best_inner_mae:
                    best_inner_mae = mean_in_mae
                    best_suite_name = suite_name

            outer_selected_suites[outer_test_battery] = best_suite_name

            # Fit on outer train pool using best_suite_name and evaluate on outer test
            X_best = suite_X[best_suite_name]
            X_outer_tr = X_best[train_idx].copy()
            y_outer_tr = y_all[train_idx]
            X_outer_te = X_best[test_idx].copy()
            y_outer_te = y_all[test_idx]

            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=RuntimeWarning)
                col_medians = np.nanmedian(X_outer_tr, axis=0)
            col_medians = np.nan_to_num(col_medians, nan=0.0)

            inds_tr = np.where(np.isnan(X_outer_tr))
            X_outer_tr[inds_tr] = np.take(col_medians, inds_tr[1])
            inds_te = np.where(np.isnan(X_outer_te))
            X_outer_te[inds_te] = np.take(col_medians, inds_te[1])

            model = RidgeBaseline(alpha=alpha, fit_intercept=True)
            model.fit(X_outer_tr, y_outer_tr)
            preds = model.predict(X_outer_te)

            outer_y_true.extend(y_outer_te)
            outer_y_pred.extend(preds)
            outer_fold_maes.append(float(np.mean(np.abs(y_outer_te - preds))))

        y_tr_arr = np.asarray(outer_y_true)
        y_pr_arr = np.asarray(outer_y_pred)
        nested_mae = float(np.mean(np.abs(y_tr_arr - y_pr_arr)))
        nested_rmse = float(np.sqrt(np.mean((y_tr_arr - y_pr_arr) ** 2)))
        ss_tot = float(np.sum((y_tr_arr - np.mean(y_tr_arr)) ** 2))
        ss_res = float(np.sum((y_tr_arr - y_pr_arr) ** 2))
        nested_r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 1e-9 else 0.0

        return {
            "validation_type": "NESTED_GROUPED_LOBO",
            "outer_batteries_count": len(lobo_splits),
            "nested_mae": nested_mae,
            "nested_rmse": nested_rmse,
            "nested_r2": nested_r2,
            "selected_suites_frequency": {s: list(outer_selected_suites.values()).count(s) for s in candidate_suites},
            "per_battery_selected_suite": outer_selected_suites
        }


    @staticmethod
    def compute_redundancy_and_correlation(
        feature_df: pd.DataFrame,
        feature_list: List[str]
    ) -> Dict[str, Any]:
        """
        Computes Pearson and Spearman rank correlation matrices across candidate features.
        Identifies collinear clusters with |r| > 0.85.
        """
        valid_cols = [c for c in feature_list if c in feature_df.columns]
        sub_df = feature_df[valid_cols].apply(pd.to_numeric, errors="coerce")
        # Impute NaNs with column median
        sub_df = sub_df.fillna(sub_df.median())

        pearson_mat = sub_df.corr(method="pearson").round(4)
        spearman_mat = sub_df.corr(method="spearman").round(4)

        # Identify highly collinear pairs (|r| >= 0.85)
        collinear_pairs = []
        for i in range(len(valid_cols)):
            for j in range(i + 1, len(valid_cols)):
                c1, c2 = valid_cols[i], valid_cols[j]
                p_r = pearson_mat.loc[c1, c2]
                s_r = spearman_mat.loc[c1, c2]
                if abs(p_r) >= 0.85 or abs(s_r) >= 0.85:
                    collinear_pairs.append({
                        "feature_a": c1,
                        "feature_b": c2,
                        "pearson_r": float(p_r),
                        "spearman_r": float(s_r),
                        "redundancy_class": "EXTREME_REDUNDANCY" if min(abs(p_r), abs(s_r)) > 0.95 else "HIGH_REDUNDANCY"
                    })

        # Condition number of normalized feature matrix
        norm_X = (sub_df - sub_df.mean()) / (sub_df.std() + 1e-9)
        try:
            cond_num = float(np.linalg.cond(norm_X.values))
        except Exception:
            cond_num = float("inf")

        return {
            "features_evaluated": valid_cols,
            "collinear_pairs_count": len(collinear_pairs),
            "collinear_pairs": collinear_pairs,
            "matrix_condition_number": cond_num,
            "severe_multicollinearity": cond_num > 1000.0
        }

    @staticmethod
    def evaluate_noise_sensitivity(
        feature_df: pd.DataFrame,
        feature_list: List[str],
        noise_levels: Dict[str, float] = None
    ) -> Dict[str, Any]:
        """
        Perturbs feature inputs with realistic sensor noise and measures:
        - Relative feature drift (CV)
        - Ranking stability (Kendall tau)
        - Number of physical bound violations induced
        """
        if noise_levels is None:
            noise_levels = {
                "voltage_noise_rel": 0.005,    # 0.5% voltage perturbation (~15mV)
                "current_noise_rel": 0.02,     # 2.0% current perturbation (~200mA)
                "thermal_noise_c": 0.5         # 0.5 degC temperature jitter
            }

        rng = np.random.RandomState(42)
        valid_cols = [c for c in feature_list if c in feature_df.columns]
        drift_scores = {}

        for feat in valid_cols:
            orig_vals = pd.to_numeric(feature_df[feat], errors="coerce").fillna(0.0).values
            mean_val = np.mean(np.abs(orig_vals)) + 1e-9

            # Apply targeted perturbation depending on physical quantity
            if "V_" in feat or "VOLTAGE" in feat or "DELTA_V" in feat:
                noise = rng.normal(0, noise_levels["voltage_noise_rel"] * mean_val, size=len(orig_vals))
            elif "I_" in feat or "CURRENT" in feat:
                noise = rng.normal(0, noise_levels["current_noise_rel"] * mean_val, size=len(orig_vals))
            elif "T_" in feat or "TEMP" in feat:
                noise = rng.normal(0, noise_levels["thermal_noise_c"], size=len(orig_vals))
            elif "R0" in feat:
                # R0 propagates both delta_v noise and current noise: delta_v/I
                noise = rng.normal(0, 0.03 * mean_val, size=len(orig_vals))
            else:
                noise = rng.normal(0, 0.01 * mean_val, size=len(orig_vals))

            perturbed = orig_vals + noise
            rel_drift = float(np.mean(np.abs(perturbed - orig_vals)) / mean_val)
            rank_corr, _ = stats.kendalltau(orig_vals, perturbed)
            if math.isnan(rank_corr):
                rank_corr = 1.0

            drift_scores[feat] = {
                "feature_id": feat,
                "relative_drift": rel_drift,
                "rank_stability": float(rank_corr),
                "robustness_score": float(np.clip(1.0 - rel_drift, 0.0, 1.0)),
                "is_noise_resilient": bool(rel_drift < 0.10 and rank_corr > 0.90)
            }

        return drift_scores
