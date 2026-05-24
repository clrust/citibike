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