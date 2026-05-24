# To do (Agent Tasks)

## Main Spec

### Data Structure
Unit: number of rides in a station-hour
Treatment group: NYC Citi Bike
Control groups: Chicago Divvy, Boston BlueBike, Philadelphia Indego, Washington DC Capitalbike

### Estimand
- Average Treatment Effect on the Treated

### Estimation Strategy
- Window at t0: First three full weeks of September 2025
- Window at t1: First three full weeks of November 2025
- Define y_tilde as y_1 - y_0
    - y_0 is the number of e-bike rides taken from a station at a certain hour on a certain day in the t0 
    window (i.e. the Monday of the first full week in September)
    - y_1 is the number of e-bike rides taken from a station at a certain hour on a certain day in the t1 window (i.e. the Monday of the first week in November)
- Use AIPTW esimator for the ATT with y_tilde as the outcome

### Covariates
- difference in temperature in celcius
- difference in precipitation in millimeters 
- difference in snow in millimeters
- difference in relative humidity
- difference in wind speed in kph
- weather condition code indicator

### Machine Learning Nuisance Models
For nonparametric DiD:
- Use XGBoost for nuisance functions
- Cross-fitting required

### Naming Conventions
- refer to the propensity score model that predicts treatment A from covariates X as g
- refer to the conditional expectation model that predicts outcome Y from treatment A and covariates X as Q

### Substantive Decisions / Analysis Log
- Main paired windows:
    - t0: September 1, 2025 through September 21, 2025
    - t1: November 3, 2025 through November 23, 2025
    - These are the first three full Monday-Sunday weeks in each month.
    - Thanksgiving week is excluded because holiday travel is likely too influential for the short-window main design.
- Pairing:
    - Pair observations exactly by station_uid, week_index, day_of_week, and hour.
    - y_tilde is the matched change in e-bike rides: y_1 - y_0.
- Treatment:
    - A = 1 for NYC Citi Bike.
    - A = 0 for all control cities in the pooled main specification.
- Main identifying covariates X:
    - Use weather differences for continuous weather variables:
        - temperature in Celsius
        - precipitation in millimeters
        - snow in millimeters
        - relative humidity
        - wind speed in kph
    - Use coarse weather condition indicators for t0 and t1.
    - Do not include city/system in X because treatment is deterministic by city and this would destroy overlap.
    - Do not include rider type in X because it is trip-level and potentially post-treatment / outcome-composition related.
    - Do not include station baseline demand, hour, day_of_week, or week_index in X for the main paired design because station and time-slot comparisons are handled by exact pairing.
    - Do not include federal holiday indicators in the main spec because the short windows contain too few holiday observations for this to be useful.
- Nuisance models:
    - g is an XGBoost binary classifier estimating P(A = 1 | X).
    - Q is an XGBoost regressor with squared-error loss estimating E[y_tilde | A, X].
    - Cross-fitting splits by station_uid so the same station never appears in both train and test folds.
    - Folds are stratified by treatment status at the station level.
- Propensity scores:
    - Main estimates clip predicted propensity scores to [0.01, 0.99].
    - Clipping does not drop observations; it caps extreme predicted probabilities for numerical stability.
    - Report the number/share of observations that would be lost if we trimmed rather than clipped.
- Target populations:
    - Row-weighted ATT: ATT for the average treated NYC station-hour.
    - Station-weighted ATT: ATT for the average treated NYC station, averaging station-level effects equally.
- Uncertainty:
    - Use the AIPTW influence-function / closed-form row-level variance for first-pass standard errors.
    - Treat these standard errors cautiously because treatment is assigned at the city level; robustness checks are required.

## Sensitivity / Robustness Plan
- Leave-one-control-city-out:
    - Re-estimate NYC ATT excluding one control city at a time.
    - Control cities: Chicago, Boston, Philadelphia, Washington DC.
- One-control-city-at-a-time:
    - Re-estimate NYC ATT separately against each control city individually.
    - Comparisons: NYC vs Chicago, NYC vs Boston, NYC vs Philadelphia, NYC vs Washington DC.
    - This checks whether the pooled estimate masks heterogeneity across control cities.
- Control-city placebo treatments:
    - Use the September-November 2025 main window.
    - Pretend each control city is treated, excluding NYC, and use the remaining control cities as controls.
    - This checks whether the estimator finds large placebo effects where no speed cap occurred.
- August-September 2025 placebo:
    - t0: first three full weeks of August 2025.
    - t1: first three full weeks of September 2025.
    - Treatment remains NYC vs control cities.
    - This checks short-run pre-treatment differential changes in the same year.
- September-November 2024 placebo:
    - t0: first three full weeks of September 2024.
    - t1: first three full weeks of November 2024.
    - Treatment remains NYC vs control cities.
    - This checks whether NYC usually has a different fall seasonal change than controls.
- Classic-rides robustness:
    - Repeat the main specification with classic ride counts as the outcome instead of e-bike ride counts.
    - This checks whether the estimated effect is specific to the treated e-bike margin or reflects broader bike-share demand changes.
- Future e-bike share outcome:
    - Repeat the paired design with e-bike ride share as the outcome.
    - Define an explicit rule for station-hours with zero total rides before implementing this outcome.
- Bootstrap uncertainty for the main specification:
    - Compute bootstrap confidence intervals for the main row-weighted and station-weighted specifications if compute allows.
    - Bootstrap should resample at the station_uid level, not the row level, to preserve within-station dependence.
- Additional future sensitivity:
    - Pedestrian/bike count or traffic controls may be considered in a separate model specification if comparable city-level data can be constructed.


# Human Notes / Backlog

These are notes for the project owner and are NOT active coding tasks.

## Future Ideas
Other specs to run
    - instead of using station hour, do by neighborhood hour (many station hours have low counts, 46% for NYC are 0)
    - If we do by neighborhood, also allows the potential possibility of doing OD (origin destination) neighborhood pairs
    - Change window to include two months instead of only one month
        - Why we aren't doing this already: because fleet composition is not necessarily fixed. Shorter time window less likely to have changed
    - Outcome as proprition of rides that are ebike/classic
    - Triple DiD
- Sensitivities: test for parallel trends etc.
- Estimate ATT for citibike to each of the control cities individually
- Have to consider Thanksgiving too, and election day
- Pedestrian/Bike Counts will be a covariate in another model spec, as well as traffic potentially
