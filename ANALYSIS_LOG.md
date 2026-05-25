# Analysis Log

This file records implementation decisions and data-quality checks made while
building the bike-share panels and AIPTW sensitivity analyses. It is intended to
make the analysis auditable without modifying the Human Notes section in
`PROJECT.md`.

## Station Identity

- Station identity is `city:start_station_id`.
- `start_station_name` is metadata only.
- Reason: station names can change over time for the same station ID. Using
  station names as panel keys can duplicate a station-hour and break the
  one-to-one paired design.
- Implemented in `build/panel_utils.py`.

## Station Retention Rule

- Retained stations must have at least one observed trip in each exact analysis
  window, not merely somewhere in each requested month.
- For the main specification, this means a station must appear in both:
  - `2025-09-01 00:00:00` through `2025-09-21 23:00:00`
  - `2025-11-03 00:00:00` through `2025-11-23 23:00:00`
- For placebo windows, the same first-three-full-week rule is applied to the
  corresponding months.
- After this change, every retained station contributes exactly 504 paired rows
  in each paired analysis dataset.

## Main Specification After Exact-Window Filtering

- Main cleaned weather panel: `data_clean/07_station_hour_panel_weather.csv`
- Main paired sample:
  - Rows: `2,501,352`
  - Stations: `4,963`
  - Rows per station: `504`
  - Missing main-spec features: none
- Stations by city:
  - NYC: `2,104`
  - Chicago: `1,191`
  - Philadelphia: `283`
  - Boston: `575`
  - Washington DC: `810`
- Updated main AIPTW result:
  - ATT: `-0.547561`
  - Standard error: `0.003156`
  - 95% CI: `[-0.553746, -0.541376]`
  - Hypothetical trimming if dropping clipped propensity rows: `21,866` rows,
    or `0.8742%`
- Row-weighted and station-weighted estimates are currently identical because
  every retained station has the same number of paired rows.

## Atomic CSV Writes

- Large build outputs are written through `.part` files and then atomically
  moved into place.
- Reason: interrupted writes previously left valid-looking but truncated CSVs.
- This applies to main panel builds, weather merges, geography aggregation, and
  sensitivity panel builds.

## Weather Missingness And Alternate-Station Fill

- The main specification has complete non-snow weather covariates in the paired
  analysis windows.
- Placebo windows had missing weather in the raw Meteostat city-hour files.
- Missing city-hours become many missing station-hour rows because each
  city-hour weather value is repeated across all retained stations in that city.
- Snow is not filled from alternate stations; the analysis code keeps the
  existing rule that missing snow is treated as zero.

### 20 km Fill Experiment

- Script: `build/00_fill_meteostat_weather_gaps.py`
- Filled weather directory: `data_raw/weather_filled_20km/`
- Merged sensitivity outputs:
  - `data_clean/sensitivities/2024_sep_nov_station_hour_panel_weather_filled20.csv`
  - `data_clean/sensitivities/2025_aug_sep_station_hour_panel_weather_filled20.csv`
- Result in paired analysis features:
  - `2025_aug_sep`: missing `delta_precip_mm` fell from `62,077` rows to
    `5,901` rows.
  - `2024_sep_nov`: missing temp, humidity, and wind were eliminated; missing
    `delta_precip_mm` fell from `245,947` rows to `12,103` rows.
- Main fill sources included:
  - NYC: LaGuardia, about 7.2 km away.
  - Chicago: Wood Oaks Glen and Schaumburg, about 15-16 km away.
  - Boston: Blue Hill Observatory, about 18.8 km away.
  - Washington DC: Andrews AFB and College Park, about 17 km away.
- Philadelphia precipitation did not improve under a 20 km cap.

### 50 km Fill Experiment

- Filled weather directory: `data_raw/weather_filled_50km/`
- City-hour result:
  - All missing temperature, relative humidity, precipitation, and wind-speed
    values were filled within 50 km.
  - Six weather-condition-code hours remain missing in NYC, Chicago,
    Philadelphia, and Washington DC.
- The 50 km filled sensitivity weather panels are being generated as:
  - `data_clean/sensitivities/2024_sep_nov_station_hour_panel_weather_filled50.csv`
  - `data_clean/sensitivities/2025_aug_sep_station_hour_panel_weather_filled50.csv`
- Paired analysis result:
  - `2025_aug_sep`: no missing AIPTW feature values.
  - `2024_sep_nov`: no missing AIPTW feature values.
- Recommendation: use the `_filled50.csv` sensitivity weather panels for the
  August-September 2025 and September-November 2024 placebo analyses.

## Sensitivity Execution Policy

- Run sensitivities one at a time.
- Report each result before moving to the next sensitivity.
- Recommended order:
  1. August-September 2025 placebo.
  2. September-November 2024 placebo.
  3. One-control-city-at-a-time.
  4. Leave-one-control-city-out.
  5. Control-city placebo treatments.
  6. Classic-rides robustness.
  7. Main-spec bootstrap confidence intervals.

## Sensitivity Runs

### One-Control-City ATT

- Script: `analysis/04_one_control_city.py`
- Status: complete.
- Purpose: estimate the NYC ATT separately using each control city as the only
  control group.
- Inputs:
  - Main weather panel: `data_clean/07_station_hour_panel_weather.csv`
  - Outcome: `ebike_trip_count`
  - Windows:
    - t0: `2025-09-01 00:00:00` through `2025-09-21 23:00:00`
    - t1: `2025-11-03 00:00:00` through `2025-11-23 23:00:00`
- Comparisons:
  - NYC vs Chicago
  - NYC vs Boston
  - NYC vs Philadelphia
  - NYC vs Washington DC
- Output summary: `results/sensitivities/one_control_city_summary.csv`
- Result table:

| Control city | ATT | SE | 95% CI | Rows | NYC stations | Control stations | Hypothetical trimmed rows |
|---|---:|---:|---:|---:|---:|---:|---:|
| Chicago | `-0.519291` | `0.003213` | `[-0.525589, -0.512993]` | `1,660,680` | `2,104` | `1,191` | `14,174` |
| Boston | `-0.571557` | `0.003318` | `[-0.578061, -0.565054]` | `1,350,216` | `2,104` | `575` | `20,482` |
| Philadelphia | `-0.535598` | `0.003874` | `[-0.543191, -0.528006]` | `1,203,048` | `2,104` | `283` | `37,026` |
| Washington DC | `-0.551007` | `0.003354` | `[-0.557581, -0.544433]` | `1,468,656` | `2,104` | `810` | `14,635` |

- Row-weighted and station-weighted estimates are identical for this run
  because every retained station contributes exactly 504 paired rows.
- Interpretation note: all one-control-city estimates are negative and fairly
  close to the pooled main estimate (`-0.547561`), but Philadelphia has the
  highest hypothetical trimming share (`3.0777%`) and the smallest control
  station count.

### Leave-One-Control-City-Out ATT

- Script: `analysis/03_leave_one_control_out.py`
- Status: complete.
- Purpose: re-estimate the NYC ATT after excluding each control city one at a
  time from the pooled control group.
- Input:
  - Main weather panel: `data_clean/07_station_hour_panel_weather.csv`
  - Outcome: `ebike_trip_count`
  - Windows:
    - t0: `2025-09-01 00:00:00` through `2025-09-21 23:00:00`
    - t1: `2025-11-03 00:00:00` through `2025-11-23 23:00:00`
- Output summary: `results/sensitivities/leave_one_control_out_summary.csv`
- Result table:

| Omitted control city | ATT | SE | 95% CI | Rows | Control stations | Hypothetical trimmed rows |
|---|---:|---:|---:|---:|---:|---:|
| Chicago | `-0.556077` | `0.003213` | `[-0.562375, -0.549779]` | `1,901,088` | `1,668` | `21,389` |
| Boston | `-0.541437` | `0.003187` | `[-0.547685, -0.535190]` | `2,211,552` | `2,284` | `7,214` |
| Philadelphia | `-0.546308` | `0.003164` | `[-0.552510, -0.540107]` | `2,358,720` | `2,576` | `10,005` |
| Washington DC | `-0.543506` | `0.003184` | `[-0.549746, -0.537267]` | `2,093,112` | `2,049` | `16,737` |

- Row-weighted and station-weighted estimates are identical because every
  retained station contributes exactly 504 paired rows.
- Interpretation note: estimates are stable around the pooled main estimate
  (`-0.547561`). Excluding Chicago makes the estimate somewhat more negative;
  excluding Boston makes it somewhat less negative.

### August-September 2025 Placebo

- Script: `analysis/06_aug_sep_2025_placebo.py`
- Status: complete.
- Purpose: pre-treatment placebo comparing NYC to controls before the October
  2025 e-bike speed-cap treatment.
- Input:
  - `data_clean/sensitivities/2025_aug_sep_station_hour_panel_weather_filled50.csv`
  - The 50 km filled weather panel is used because it has no missing AIPTW
    feature values for this placebo.
- Outcome: `ebike_trip_count`
- Windows:
  - t0: `2025-08-04 00:00:00` through `2025-08-24 23:00:00`
  - t1: `2025-09-01 00:00:00` through `2025-09-21 23:00:00`
- Output summary: `results/sensitivities/aug_sep_2025_placebo_summary.csv`
- Result:
  - ATT: `0.143201`
  - Standard error: `0.003038`
  - 95% CI: `[0.137246, 0.149155]`
  - Rows: `2,528,064`
  - Treated NYC stations: `2,121`
  - Control stations: `2,895`
  - Hypothetical trimmed rows: `26,243` (`1.0381%`)
  - Row-weighted and station-weighted estimates are identical because every
    retained station contributes exactly 504 paired rows.
- City mean paired changes:
  - NYC: `0.156723`
  - Chicago: `-0.011298`
  - Boston: `0.000887`
  - Philadelphia: `0.064544`
  - Washington DC: `0.045311`
- Interpretation note: this placebo is positive and statistically distinguishable
  from zero, which is evidence of pre-treatment differential movement between
  NYC and the control cities from August to September 2025. This should be
  treated as a meaningful parallel-trends warning rather than a pass.

### August-September 2025 Placebo Bootstrap

- Script: `analysis/11_bootstrap_aug_sep_2025_placebo.py`
- Status: complete.
- Purpose: rerun the August-September 2025 placebo and compare the analytic
  influence-function standard error to station-level bootstrap uncertainty.
- Bootstrap design:
  - Resample `station_uid` clusters.
  - Use fixed cross-fitted nuisance predictions.
  - Do not refit XGBoost inside each bootstrap draw.
  - Default draws: `500`.
- Input:
  - `data_clean/sensitivities/2025_aug_sep_station_hour_panel_weather_filled50.csv`
- Output summary:
  - `results/sensitivities/aug_sep_2025_placebo_bootstrap_summary.csv`
- Result:

| Target | ATT | Analytic SE | Analytic 95% CI | Bootstrap SE | Bootstrap 95% CI | Bootstrap draws | Station clusters |
|---|---:|---:|---:|---:|---:|---:|---:|
| Row-weighted | `0.143201` | `0.003038` | `[0.137246, 0.149155]` | `0.012063` | `[0.119797, 0.166315]` | `500` | `5,016` |
| Station-weighted | `0.143201` | `0.003038` | `[0.137246, 0.149155]` | `0.012063` | `[0.119797, 0.166315]` | `500` | `5,016` |

- Interpretation note: the fixed-nuisance station bootstrap standard error is
  about four times the analytic row-level standard error. The placebo remains
  positive with the bootstrap CI, but this strongly suggests the analytic
  closed-form SE is optimistic for station-clustered uncertainty.

### September-November 2024 Placebo

- Script: `analysis/07_sep_nov_2024_placebo.py`
- Status: complete.
- Purpose: prior-year placebo comparing the same fall seasonal windows one year
  before the October 2025 e-bike speed-cap treatment.
- Input:
  - `data_clean/sensitivities/2024_sep_nov_station_hour_panel_weather_filled50.csv`
  - The 50 km filled weather panel is used because it has no missing AIPTW
    feature values for this placebo.
- Outcome: `ebike_trip_count`
- Windows:
  - t0: `2024-09-02 00:00:00` through `2024-09-22 23:00:00`
  - t1: `2024-11-04 00:00:00` through `2024-11-24 23:00:00`
- Output summary: `results/sensitivities/sep_nov_2024_placebo_summary.csv`
- Result:
  - ATT: `-0.373430`
  - Standard error: `0.002743`
  - 95% CI: `[-0.378806, -0.368053]`
  - Rows: `2,431,800`
  - Treated NYC stations: `2,204`
  - Control stations: `2,621`
  - Hypothetical trimmed rows: `23,142` (`0.9516%`)
  - Row-weighted and station-weighted estimates are identical because every
    retained station contributes exactly 504 paired rows.
- City mean paired changes:
  - NYC: `-0.511174`
  - Chicago: `-0.225998`
  - Boston: `-0.074149`
  - Philadelphia: `-0.094483`
  - Washington DC: `-0.070997`
- Interpretation note: this prior-year placebo is large and negative. It is a
  serious warning that NYC's fall seasonal e-bike change differed from the
  control cities even in 2024, before the speed-cap treatment.

### Main ATT With Time-Slot Controls

- Script: `analysis/12_aiptw_att_time_controls.py`
- Status: complete.
- Purpose: rerun the main paired AIPTW specification with a richer nuisance
  covariate set.
- Motivation: placebo failures suggest weather-only `X` may not be sufficient.
  Exact pairing handles station/time-slot comparisons in the outcome, but
  untreated paired changes may still differ by hour, day of week, or week index
  across cities.
- Input:
  - `data_clean/07_station_hour_panel_weather.csv`
- Outcome: `ebike_trip_count`
- Windows:
  - t0: `2025-09-01 00:00:00` through `2025-09-21 23:00:00`
  - t1: `2025-11-03 00:00:00` through `2025-11-23 23:00:00`
- Covariates:
  - Main weather controls.
  - Categorical indicators for `hour`, `day_of_week`, and `week_index`.
- Output summary: `results/sensitivities/main_time_controls_summary.csv`
- Result:
  - ATT: `-0.547247`
  - Standard error: `0.003135`
  - 95% CI: `[-0.553392, -0.541102]`
  - Rows: `2,501,352`
  - Treated NYC stations: `2,104`
  - Control stations: `2,859`
  - Hypothetical trimmed rows: `25,788` (`1.0310%`)
  - Row-weighted and station-weighted estimates are identical because every
    retained station contributes exactly 504 paired rows.
- Comparison to weather-only main spec:
  - Weather-only ATT: `-0.547561`
  - Time-controls ATT: `-0.547247`
  - Difference: `0.000314`
- Interpretation note: adding hour/day/week indicators to `X` barely changes
  the main ATT. This does not resolve the placebo concern by itself; the next
  useful check is whether the same time-control specification changes the
  placebo estimates.

### Placebos With Time-Slot Controls

- Scripts:
  - `analysis/13_aug_sep_2025_placebo_time_controls.py`
  - `analysis/14_sep_nov_2024_placebo_time_controls.py`
- Status: complete.
- Purpose: check whether adding categorical `hour`, `day_of_week`, and
  `week_index` indicators to `X` attenuates the placebo failures.
- Inputs:
  - `data_clean/sensitivities/2025_aug_sep_station_hour_panel_weather_filled50.csv`
  - `data_clean/sensitivities/2024_sep_nov_station_hour_panel_weather_filled50.csv`
- Data gap note: fleet size and fleet composition remain important candidate
  controls. We do not currently have comparable city-hour measures of active
  bikes, e-bike availability, or e-bike share across systems. The project owner
  has looked for these data and has not found a comparable source yet.
- Results:

| Placebo | Weather-only ATT | Time-controls ATT | Time-controls SE | Time-controls 95% CI |
|---|---:|---:|---:|---:|
| August-September 2025 | `0.143201` | `0.134630` | `0.003005` | `[0.128739, 0.140521]` |
| September-November 2024 | `-0.373430` | `-0.394778` | `0.002744` | `[-0.400156, -0.389401]` |

- Output summaries:
  - `results/sensitivities/aug_sep_2025_placebo_time_controls_summary.csv`
  - `results/sensitivities/sep_nov_2024_placebo_time_controls_summary.csv`
- Interpretation note: adding time-slot indicators does not resolve the placebo
  failures. The August-September 2025 placebo shrinks slightly but remains
  positive. The September-November 2024 placebo becomes somewhat more negative.

### Classic-Rides Diagnostic Outcome

- Script: `analysis/08_classic_rides_robustness.py`
- Status: complete.
- Purpose: rerun the main September-November 2025 paired design with
  `classic_trip_count` as the outcome.
- Interpretation:
  - This is a diagnostic outcome, not a control variable in the e-bike model.
  - Classic rides may be affected by treatment through substitution from
    e-bikes to classic bikes, so they are not a clean unaffected placebo
    outcome.
  - If classic rides rise or stay flat while e-bike rides fall, that is
    consistent with substitution or e-bike-specific effects.
  - If classic rides also fall, that suggests broader Citi Bike demand changes.
- Input:
  - `data_clean/07_station_hour_panel_weather.csv`
- Windows:
  - t0: `2025-09-01 00:00:00` through `2025-09-21 23:00:00`
  - t1: `2025-11-03 00:00:00` through `2025-11-23 23:00:00`
- Output summary: `results/sensitivities/classic_rides_robustness_summary.csv`
- Result:
  - ATT: `-0.152042`
  - Standard error: `0.002080`
  - 95% CI: `[-0.156120, -0.147964]`
  - Rows: `2,501,352`
  - Treated NYC stations: `2,104`
  - Control stations: `2,859`
  - Hypothetical trimmed rows: `21,866` (`0.8742%`)
  - Row-weighted and station-weighted estimates are identical because every
    retained station contributes exactly 504 paired rows.
- City mean paired classic-ride changes:
  - NYC: `-0.347690`
  - Chicago: `-0.122028`
  - Boston: `-0.465231`
  - Philadelphia: `-0.115353`
  - Washington DC: `-0.116387`
- Interpretation note: classic rides fall in NYC rather than rising or staying
  flat. This is not consistent with a simple substitution story from e-bikes to
  classic bikes. It points toward broader Citi Bike demand changes, though
  Boston also has a large classic-ride decline in this window.
