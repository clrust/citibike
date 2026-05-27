# Future Methods Notes

## Cluster-Robust Influence-Function Standard Errors

Potential next step: add station-cluster robust standard errors for the AIPTW
ATT estimator.

The current analytic standard error uses row-level influence values. A
station-cluster version would aggregate those influence values within
`station_uid` and then compute a sandwich-style variance using station-level
influence sums.

Conceptual mapping to parametric sandwich estimators:

| Regression sandwich | AIPTW ATT setting |
|---|---|
| Parameter `beta` | Parameter `ATT` |
| Row score `x_i u_i` | Row influence value `psi_i` |
| Cluster score `sum_i x_i u_i` | Station influence sum `sum_i psi_i` |
| Meat `sum_s score_s score_s'` | Meat `sum_s Psi_s^2` |
| Bread `(X'X)^(-1)` | Already embedded in the estimated influence function |

This should be much faster than a station bootstrap and should better respect
within-station dependence than the current row-level analytic SE. It would still
not fully solve city-level treatment assignment uncertainty because there is one
treated city and four control cities.

Relevant references to revisit:

- Liang and Zeger (1986), generalized estimating equations / sandwich variance.
- Arellano (1987), robust standard errors for panel within estimators.
- Cameron and Miller (2015), cluster-robust inference in applied econometrics.
- Chernozhukov et al. (2018), double/debiased machine learning.
- Chiang, Kato, Ma, and Sasaki, multiway cluster robust DML.

