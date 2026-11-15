"""Step 4: how far the target climate of the farm is from the observed climate of a place, in
"sigmas" (Fitzpatrick & Dunn 2019).

The gap between the mean indicators is judged against the normal year-to-year variations of the
place, taking into account that the 5 indicators vary together (Mahalanobis distance). That
distance in 5 dimensions becomes a percentile of the chi distribution with 5 degrees of freedom,
then the distance with the same percentile in one dimension.
0 = identical, below 2 = good twin, above 2 = no real twin.

The percentile is read on the upper tail (`sf` then `isf`), which equals the reference
(`ppf(cdf(d))`) wherever that one is finite and stays finite, and ordered, for very far places.
"""

from __future__ import annotations

import numpy as np
from scipy.stats import chi

from field_shift.algorithm.config.climate import COVARIANCE_RIDGE_SHARE


def _ridge_singular(covariance: np.ndarray) -> np.ndarray:
    """Covariances of a place whose indicator never changes (no hot day in 14 years) are singular:
    the reference stops there. A tiny ridge on the diagonal makes such a place simply very far."""
    size = covariance.shape[-1]
    singular = np.linalg.matrix_rank(covariance) < size
    if not singular.any():
        return covariance
    mean_variance = np.trace(covariance, axis1=-2, axis2=-1) / size
    ridge = np.where(singular, COVARIANCE_RIDGE_SHARE * np.maximum(mean_variance, 1.0), 0.0)
    return covariance + ridge[..., None, None] * np.eye(size)


def sigma_dissimilarities(target_rows: np.ndarray, observed: np.ndarray) -> np.ndarray:
    """One sigma per place.

    target_rows  (years, 5): yearly indicators of the target climate;
    observed     (years, places, 5): yearly indicators observed at each place.
    """
    dimensions = target_rows.shape[1]
    observed_mean = observed.mean(axis=0)
    gap = target_rows.mean(axis=0) - observed_mean
    anomalies = observed - observed_mean
    covariance = np.einsum("tci,tcj->cij", anomalies, anomalies) / (observed.shape[0] - 1)
    weighted_gap = np.linalg.solve(_ridge_singular(covariance), gap[..., None])[..., 0]
    squared_distance = np.einsum("ci,ci->c", gap, weighted_gap)
    distance = np.sqrt(np.clip(squared_distance, 0.0, None))
    return chi(1).isf(chi(dimensions).sf(distance))


def sigma_dissimilarity(target_rows: np.ndarray, place_rows: np.ndarray) -> float:
    """Sigma of one place (rows = years)."""
    return float(sigma_dissimilarities(target_rows, place_rows[:, None, :])[0])
