# Citi Bike E-Bike Speed Cap Project

This project studies the impact of NYC's October 24, 2025 Citi Bike e-bike speed cap using difference-in-differences methods. Study design is human, but coding relies on codex.

## Research Question

Did the speed cap reduce demand for Citi Bike e-bikes?

## Identification Strategy

Non-parametric difference-in-differences comparing NYC Citi Bike outcomes to Chicago Divvy, Philadelphia Indego, Washginton D.C. CaptialBike, and Boston Bluebike outcomes.

## Estimation Strategy

Estimate the ATT. Use the XGboost package to fit gradient boosted decision tree models for the plugin estimator. (See the causality chapter of the textook in this repo)

## Main Challenges

- Fleet composition changes
- Weather
- Seasonality
- Differential commuting patterns
- E-bike vs classic bike substitution
- citibike fare increase on January 5, 2026
- NYC congestion pricing on January 5, 2025

## Repository Structure

- `build/` : data cleaning scripts
- `analysis/` : data anaysis scripts
- `paper/` : paper files
- `figures/` : exported figures
- `tables/` : regression tables
- `outputs/` : model outputs





