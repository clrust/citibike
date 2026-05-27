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
- For the original September-November specification, this means a station must
  appear in both:
  - `2025-09-01 00:00:00` through `2025-09-21 23:00:00`
  - `2025-11-03 00:00:00` through `2025-11-23 23:00:00`
- For placebo windows, the same first-three-full-week rule is applied to the
  corresponding months.
- After this change, every retained station contributes exactly 504 paired rows
  in each paired analysis dataset.

## Original September-November Specification After Exact-Window Filtering

- Original cleaned weather panel:
  `data_clean/og_main_spec_sept_nov/07_station_hour_panel_weather.csv`
- Original paired sample:
  - Rows: `2,501,352`
  - Stations: `4,963`
  - Rows per station: `504`
  - Missing original-spec features: none
- Stations by city:
  - NYC: `2,104`
  - Chicago: `1,191`
  - Philadelphia: `283`
  - Boston: `575`
  - Washington DC: `810`
- Updated original September-November AIPTW result:
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

- The original September-November specification has complete non-snow weather
  covariates in the paired analysis windows.
- Placebo windows had missing weather in the raw Meteostat city-hour files.
- Missing city-hours become many missing station-hour rows because each
  city-hour weather value is repeated across all retained stations in that city.
- Snow is not filled from alternate stations; the analysis code keeps the
  existing rule that missing snow is treated as zero.

### 20 km Fill Experiment

- Script: `build/00_fill_meteostat_weather_gaps.py`
- Filled weather directory: `data_raw/weather_filled_20km/`
- Merged sensitivity outputs:
  - `data_clean/sensitivities/og_placebo_2024_sep_nov/09_2024_sep_nov_station_hour_panel_weather_filled20.csv`
  - `data_clean/sensitivities/og_placebo_2025_aug_sep/09_2025_aug_sep_station_hour_panel_weather_filled20.csv`
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
  - `data_clean/sensitivities/og_placebo_2024_sep_nov/09_2024_sep_nov_station_hour_panel_weather_filled50.csv`
  - `data_clean/sensitivities/og_placebo_2025_aug_sep/09_2025_aug_sep_station_hour_panel_weather_filled50.csv`
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
  - Main weather panel:
    `data_clean/og_main_spec_sept_nov/07_station_hour_panel_weather.csv`
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
  - Main weather panel:
    `data_clean/og_main_spec_sept_nov/07_station_hour_panel_weather.csv`
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
  - `data_clean/sensitivities/og_placebo_2025_aug_sep/09_2025_aug_sep_station_hour_panel_weather_filled50.csv`
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
  - `data_clean/sensitivities/og_placebo_2025_aug_sep/09_2025_aug_sep_station_hour_panel_weather_filled50.csv`
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
  - `data_clean/sensitivities/og_placebo_2024_sep_nov/09_2024_sep_nov_station_hour_panel_weather_filled50.csv`
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

### Original September-November ATT With Time-Slot Controls

- Script: `analysis/12_aiptw_att_time_controls.py`
- Status: complete.
- Purpose: rerun the original September-November paired AIPTW specification
  with a richer nuisance covariate set.
- Motivation: placebo failures suggest weather-only `X` may not be sufficient.
  Exact pairing handles station/time-slot comparisons in the outcome, but
  untreated paired changes may still differ by hour, day of week, or week index
  across cities.
- Input:
  - `data_clean/og_main_spec_sept_nov/07_station_hour_panel_weather.csv`
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
- Comparison to original weather-only spec:
  - Weather-only ATT: `-0.547561`
  - Time-controls ATT: `-0.547247`
  - Difference: `0.000314`
- Interpretation note: adding hour/day/week indicators to `X` barely changes
  the original September-November ATT. This does not resolve the placebo
  concern by itself; the next useful check is whether the same time-control
  specification changes the placebo estimates.

### Placebos With Time-Slot Controls

- Scripts:
  - `analysis/13_aug_sep_2025_placebo_time_controls.py`
  - `analysis/14_sep_nov_2024_placebo_time_controls.py`
- Status: complete.
- Purpose: check whether adding categorical `hour`, `day_of_week`, and
  `week_index` indicators to `X` attenuates the placebo failures.
- Inputs:
  - `data_clean/sensitivities/og_placebo_2025_aug_sep/09_2025_aug_sep_station_hour_panel_weather_filled50.csv`
  - `data_clean/sensitivities/og_placebo_2024_sep_nov/09_2024_sep_nov_station_hour_panel_weather_filled50.csv`
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
  - `data_clean/og_main_spec_sept_nov/07_station_hour_panel_weather.csv`
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

### Original September-November ATT With Daylight Controls

- Script: `analysis/15_aiptw_att_daylight_controls.py`
- Status: complete.
- Purpose: rerun the main September-November 2025 paired design with
  `delta_daylight` in `X`.
- Interpretation of daylight variables:
  - `daylight_t0 = 1` if the midpoint of the pre-period local hour is between
    sunrise and sunset for that city.
  - `daylight_t1 = 1` if the midpoint of the post-period local hour is between
    sunrise and sunset for that city.
  - `delta_daylight = daylight_t1 - daylight_t0`.
  - Only `delta_daylight` is included as a nuisance-model covariate.
- Input:
  - `data_clean/og_main_spec_sept_nov/07_station_hour_panel_weather.csv`
- Outcome: `ebike_trip_count`
- Windows:
  - t0: `2025-09-01 00:00:00` through `2025-09-21 23:00:00`
  - t1: `2025-11-03 00:00:00` through `2025-11-23 23:00:00`
- Output summary: `results/sensitivities/main_daylight_controls_summary.csv`
- Result:
  - ATT: `-0.549361`
  - Standard error: `0.003156`
  - 95% CI: `[-0.555546, -0.543176]`
  - Rows: `2,501,352`
  - Treated NYC stations: `2,104`
  - Control stations: `2,859`
  - Hypothetical trimmed rows: `21,942` (`0.8772%`)
  - Row-weighted and station-weighted estimates are identical because every
    retained station contributes exactly 504 paired rows.
- Comparison to original weather-only spec:
  - Weather-only ATT: `-0.547561`
  - Delta-daylight ATT: `-0.549361`
  - Difference: `-0.001800`
- Interpretation note: adding `delta_daylight` changes the original
  September-November ATT very little. It does not appear to explain a
  meaningful share of that estimate.

### Adjacent-Window E-Bike Trips With Time Controls

- Scripts prepared:
  - `build/10_build_adjacent_window_panel.py`
  - `analysis/16_adjacent_window_time_controls.py`
- Status: complete.
- Purpose: compare the nearest clean three-week windows around the October 24,
  2025 speed cap while excluding the treatment week itself.
- Windows:
  - t0: `2025-09-29 00:00:00` through `2025-10-19 23:00:00`
  - t1: `2025-10-27 00:00:00` through `2025-11-16 23:00:00`
- Outcome: `ebike_trip_count`.
- Treated city: NYC.
- Control cities: Chicago, Boston, Philadelphia, Washington DC.
- Station retention: stations must be present in both exact adjacent analysis
  windows.
- Covariates in `X`: continuous weather differences, pre/post broad weather
  condition indicators, and categorical `hour`, `day_of_week`, and
  `week_index` indicators. Daylight controls are not included in this version.
- Planned outputs:
  - `data_clean/sensitivities/10_adjacent_window_station_hour_panel.csv`
  - `data_clean/sensitivities/10_adjacent_window_station_hour_panel_weather.csv`
  - `data_clean/sensitivities/10_adjacent_window_station_hour_panel_weather_filled50.csv`
  - `results/sensitivities/adjacent_window_time_controls_summary.csv`
- Weather note:
  - The base weather merge had missing precipitation for 52 city-hours around
    October 10-11, affecting `delta_precip_mm` for 39,330 paired rows.
  - The 50 km filled-weather files were refreshed and the analysis was run on
    `10_adjacent_window_station_hour_panel_weather_filled50.csv`.
  - The final paired analysis feature matrix had no missing covariates.
- Build result:
  - Station-hour rows: `5,084,352`
  - Paired rows: `2,542,176`
  - NYC stations: `2,137`
  - Control stations: `2,907`
  - Every retained station contributes exactly `504` paired observations.
- AIPTW result:
  - ATT: `-0.225187`
  - Standard error: `0.002908`
  - 95% CI: `[-0.230887, -0.219488]`
  - Hypothetical trimmed rows under dropping rather than clipping: `131,233`
    (`5.1622%`)
  - Row-weighted and station-weighted estimates are identical because every
    retained station contributes exactly 504 paired rows.
- City mean paired e-bike changes:
  - NYC: `-0.311328`
  - Chicago: `-0.118660`
  - Boston: `-0.040945`
  - Philadelphia: `-0.079545`
  - Washington DC: `-0.070726`
- Interpretation note: the adjacent-window estimate remains negative but is
  substantially smaller in magnitude than the original September-November main
  estimate (`-0.547561`). This suggests part of the original main estimate is
  sensitive to the wider calendar comparison window, while the adjacent-window
  design still shows a meaningful NYC-specific e-bike decline.

### Sharp Immediate-Post E-Bike Trips With Time Controls

- Scripts:
  - `build/11_build_sharp_window_panel.py`
  - `analysis/17_sharp_window_time_controls.py`
- Status: complete.
- Current role: preferred main October-policy specification as of
  May 27, 2026. Earlier September-November estimates are retained as
  sensitivities rather than overwritten.
- Purpose: treat the October 24, 2025 policy date as active beginning at
  midnight and compare the nearest possible four-week windows.
- Windows:
  - t0: `2025-09-26 00:00:00` through `2025-10-23 23:00:00`
  - t1: `2025-10-24 00:00:00` through `2025-11-20 23:00:00`
- Outcome: `ebike_trip_count`.
- Treated city: NYC.
- Control cities: Chicago, Boston, Philadelphia, Washington DC.
- Station retention: stations must be present in both exact sharp analysis
  windows.
- Covariates in `X`: continuous weather differences, pre/post broad weather
  condition indicators, and categorical `hour`, `day_of_week`, and
  `week_index` indicators.
- Weather source: 50 km filled-weather files.
- Build result:
  - Station-hour rows: `6,863,808`
  - Paired rows: `3,431,904`
  - NYC stations: `2,145`
  - Control stations: `2,962`
  - Every retained station contributes exactly `672` paired observations.
  - The final paired analysis feature matrix had no missing covariates.
- AIPTW result:
  - ATT: `-0.269000`
  - Standard error: `0.002496`
  - 95% CI: `[-0.273892, -0.264108]`
  - Hypothetical trimmed rows under dropping rather than clipping: `76,994`
    (`2.2435%`)
  - Row-weighted and station-weighted estimates are identical because every
    retained station contributes exactly 672 paired rows.
- City mean paired e-bike changes:
  - NYC: `-0.345244`
  - Chicago: `-0.108899`
  - Boston: `-0.039435`
  - Philadelphia: `-0.085565`
  - Washington DC: `-0.069146`
- Interpretation note: the sharp four-week estimate is more negative than the
  skipped-treatment-week adjacent-window estimate (`-0.225187`) but still much
  smaller in magnitude than the original September-November main estimate
  (`-0.547561`).

### 2024 Sharp-Window Placebo With Time Controls

- Scripts:
  - `build/12_build_sharp_2024_placebo_panel.py`
  - `analysis/18_sharp_2024_placebo_time_controls.py`
- Status: complete.
- Purpose: repeat the preferred four-week October-policy design one year
  earlier, when no NYC October 24 e-bike speed-cap policy event occurred.
- Windows:
  - t0: `2024-09-26 00:00:00` through `2024-10-23 23:00:00`
  - t1: `2024-10-24 00:00:00` through `2024-11-20 23:00:00`
- Outcome: `ebike_trip_count`.
- Treated city: NYC.
- Control cities: Chicago, Boston, Philadelphia, Washington DC.
- Station retention: stations must be present in both exact placebo windows.
- Covariates in `X`: continuous weather differences, pre/post broad weather
  condition indicators, and categorical `hour`, `day_of_week`, and
  `week_index` indicators.
- Weather source: 50 km filled-weather files, refreshed to include
  `2024-10`.
- Build result:
  - Station-hour rows: `6,632,640`
  - Paired rows: `3,316,320`
  - NYC stations: `2,214`
  - Control stations: `2,721`
  - Every retained station contributes exactly `672` paired observations.
  - The final paired analysis feature matrix had no missing covariates.
- AIPTW result:
  - ATT: `-0.084448`
  - Standard error: `0.002167`
  - 95% CI: `[-0.088695, -0.080201]`
  - Hypothetical trimmed rows under dropping rather than clipping: `142,597`
    (`4.2999%`)
  - Row-weighted and station-weighted estimates are identical because every
    retained station contributes exactly 672 paired rows.
- City mean paired e-bike changes:
  - NYC: `-0.107018`
  - Chicago: `-0.085938`
  - Boston: `-0.023327`
  - Philadelphia: `-0.036900`
  - Washington DC: `-0.020040`
- Interpretation note: this same-calendar 2024 placebo is negative and
  statistically different from zero, but much smaller than the preferred 2025
  sharp-window estimate (`-0.269000`). This weakens but does not eliminate the
  concern that NYC has differential late-October/November demand movement
  relative to the control cities.

### Sharp-Window Control-City Sensitivities

- Scripts:
  - `analysis/19_sharp_one_control_city.py`
  - `analysis/20_sharp_leave_one_control_out.py`
- Status: complete.
- Purpose: repeat the preferred four-week October 2025 specification while
  varying only the control group.
- Windows:
  - t0: `2025-09-26 00:00:00` through `2025-10-23 23:00:00`
  - t1: `2025-10-24 00:00:00` through `2025-11-20 23:00:00`
- Outcome: `ebike_trip_count`.
- Covariates in `X`: continuous weather differences, pre/post broad weather
  condition indicators, and categorical `hour`, `day_of_week`, and
  `week_index` indicators.
- Input: `data_clean/main_spec/11_sharp_window_station_hour_panel_weather.csv`.
- One-control-city results:

| Control city | ATT | SE | 95% CI | NYC stations | Control stations | Hypothetical trim share |
|---|---:|---:|---:|---:|---:|---:|
| Chicago | `-0.242481` | `0.002480` | `[-0.247342, -0.237619]` | `2,145` | `1,277` | `5.3662%` |
| Boston | `-0.294496` | `0.002608` | `[-0.299607, -0.289385]` | `2,145` | `588` | `0.2706%` |
| Philadelphia | `-0.262333` | `0.003294` | `[-0.268788, -0.255877]` | `2,145` | `286` | `0.2625%` |
| Washington DC | `-0.259931` | `0.002755` | `[-0.265330, -0.254531]` | `2,145` | `811` | `0.4749%` |

- One-control-city interpretation note: all single-control estimates are
  negative and fairly close to the preferred pooled-control estimate
  (`-0.269000`). Boston gives the most negative estimate and Chicago the least
  negative estimate.
- Leave-one-control-out results:

| Omitted city | ATT | SE | 95% CI | NYC stations | Control stations | Hypothetical trim share |
|---|---:|---:|---:|---:|---:|---:|
| Chicago | `-0.277591` | `0.002563` | `[-0.282614, -0.272567]` | `2,145` | `1,685` | `0.2797%` |
| Boston | `-0.258436` | `0.002532` | `[-0.263398, -0.253473]` | `2,145` | `2,374` | `3.1054%` |
| Philadelphia | `-0.265486` | `0.002497` | `[-0.270380, -0.260591]` | `2,145` | `2,676` | `2.6718%` |
| Washington DC | `-0.268858` | `0.002522` | `[-0.273801, -0.263915]` | `2,145` | `2,151` | `2.9627%` |

- Leave-one-out interpretation note: the estimate is stable to omitting any
  one control city. The range is `-0.277591` to `-0.258436`, bracketing the
  preferred pooled-control estimate (`-0.269000`).

### Sharp-Window City-Hour E-Bike Share Outcome

- Script: `analysis/21_sharp_ebike_share_city_hour_aiptw.py`
- Build input: `data_clean/sensitivities/13_sharp_ebike_share_city_hour.csv`,
  produced by `build/13_build_sharp_ebike_share_city_hour.py`.
- Status: complete.
- Purpose: repeat the preferred four-week October 2025 design with an outcome
  that measures the share of all system rides taken on e-bikes.
- Outcome: `ebike_trip_count / (ebike_trip_count + classic_trip_count)`.
- Unit: paired city-hour.
  - NYC contributes one treated row for each paired hour.
  - Chicago, Boston, Philadelphia, and Washington DC each contribute one
    control row for each paired hour.
- Windows:
  - t0: `2025-09-26 00:00:00` through `2025-10-23 23:00:00`
  - t1: `2025-10-24 00:00:00` through `2025-11-20 23:00:00`
- Estimator: AIPTW ATT for NYC city-hours.
- Nuisance models: conservative XGBoost classifier for `g(X)` and XGBoost
  squared-error regressor for `Q(A, X)`.
- Covariates in `X`: continuous weather differences, pre/post broad weather
  condition indicators, and categorical `hour`, `day_of_week`, and
  `week_index` indicators.
- Geography note: neighborhood-hour ratios are feasible in principle, but not
  run here. They would require comparable neighborhood definitions across all
  cities and would reintroduce small-denominator ratio noise.
- Cross-fitting note:
  - The final script uses paired time-slot folds: each fold holds out all cities
    for a subset of matched `week_index`/`day_of_week`/`hour` slots.
  - City-level folds are not appropriate for this sensitivity because there is
    only one treated city.
- Result:
  - ATT: `-0.001650`
  - Standard error: `0.002010`
  - 95% CI: `[-0.005590, 0.002290]`
  - Rows: `3,360`
  - Treated rows: `672`
  - Control rows: `2,688`
  - Treated cities: `1`
  - Control cities: `4`
- Propensity score diagnostics:
  - No propensity scores were outside the `[0.01, 0.99]` clipping range.
  - Hypothetical trimmed rows if dropping outside-range observations: `0`
    (`0.0000%`).
  - Raw propensity minimum: `0.034028`
  - Raw propensity maximum: `0.357084`
  - NYC raw propensity median: `0.243327`
  - Control raw propensity median: `0.199254`
  - `g` model AUC: `0.673202`
  - `g` model log loss: `0.471804`
- City mean e-bike share changes:
  - NYC: `0.020101`
  - Chicago: `0.003438`
  - Boston: `0.021843`
  - Philadelphia: `0.030332`
  - Washington DC: `0.028009`
- Interpretation note: the near-zero city-hour e-bike-share ATT creates tension
  with a clean story that the speed cap reduced e-bike demand relative to
  classic bikes. A composition outcome should be more robust to broad shifts in
  total bike-share demand if classic and e-bike rides move together. However,
  this specification is much more aggregated than the station-hour main design
  and does not condition on station or neighborhood, so it is not a decisive
  falsification of the station-hour count result.

### Sharp-Window Classic-Rides Diagnostic Outcome

- Script: `analysis/22_sharp_classic_rides_robustness.py`
- Status: complete.
- Purpose: repeat the preferred four-week October 2025 station-hour AIPTW
  specification, changing only the outcome from `ebike_trip_count` to
  `classic_trip_count`.
- Interpretation:
  - This is a robustness/diagnostic outcome for the station-hour count design,
    not a clean unaffected placebo.
  - If the speed cap specifically reduced e-bike demand, classic-bike rides
    would ideally be roughly unchanged or higher.
  - A negative classic-bike ATT therefore weakens a simple treatment-specific
    e-bike-demand interpretation, while the smaller magnitude matters for
    assessing how much broader demand movement could explain.
- Windows:
  - t0: `2025-09-26 00:00:00` through `2025-10-23 23:00:00`
  - t1: `2025-10-24 00:00:00` through `2025-11-20 23:00:00`
- Covariates in `X`: continuous weather differences, pre/post broad weather
  condition indicators, and categorical `hour`, `day_of_week`, and
  `week_index` indicators.
- Result:
  - ATT: `-0.095219`
  - Standard error: `0.001644`
  - 95% CI: `[-0.098440, -0.091998]`
  - Rows: `3,431,904`
  - Treated NYC stations: `2,145`
  - Control stations: `2,962`
  - Hypothetical trimmed rows under dropping rather than clipping: `76,994`
    (`2.2435%`)
  - Row-weighted and station-weighted estimates are identical because every
    retained station contributes exactly 672 paired rows.
- City mean paired classic-ride changes:
  - NYC: `-0.220134`
  - Chicago: `-0.090145`
  - Boston: `-0.243137`
  - Philadelphia: `-0.071543`
  - Washington DC: `-0.077931`
- Interpretation note: this is best read as a robustness/diagnostic outcome for
  the station-hour count specification, not primarily as a substitution test.
  In a clean treatment-specific e-bike-demand story, classic-bike ATT would
  ideally be around zero or positive. The observed classic-bike ATT is also
  negative, which weakens a simple causal interpretation of the e-bike count
  ATT. That said, its magnitude (`-0.095219`) is much smaller than the e-bike
  count ATT (`-0.269000`), so it does not mechanically explain away the full
  e-bike decline.

### June 20 Sharp-Window E-Bike Count Analysis

- Build script: `build/june_20/01_build_june_20_panel.py`
- Analysis script: `analysis/june_20/01_june_20_sharp_window_time_controls.py`
- Status: complete.
- Purpose: test the earlier Citi Bike operational e-bike speed reduction date,
  separately from the October 24 policy implementation date.
- Treatment date: `2025-06-20`, treated as active beginning at midnight.
- Clean data:
  - `data_clean/june_20/01_june_20_station_hour_panel.csv`
  - `data_clean/june_20/01_june_20_station_hour_panel_weather.csv`
- Weather handling:
  - Initial June 20 weather merge had missing precipitation in control cities.
  - The provisional analysis from that unfilled weather merge was deleted and
    should not be interpreted.
  - Final analysis uses 50 km alternate-station filled weather from
    `data_raw/weather_june_20_filled_50km/`.
  - Filled precipitation hours:
    - Chicago: `130`
    - Philadelphia: `186`
    - Boston: `154`
    - Washington DC: `218`
    - NYC: `0`
  - After the 50 km fill, all non-snow AIPTW weather features have zero
    missingness in the merged analysis panel.
  - `weather_snow_mm` is fully missing in this period and is handled by the
    analysis code as zero, consistent with prior specifications.
- Windows:
  - t0: `2025-05-23 00:00:00` through `2025-06-19 23:00:00`
  - t1: `2025-06-20 00:00:00` through `2025-07-17 23:00:00`
- Outcome: `ebike_trip_count` at the paired station-hour level.
- Treated city: NYC.
- Control cities: Chicago, Boston, Philadelphia, and Washington DC.
- Covariates in `X`: continuous weather differences, pre/post broad weather
  condition indicators, and categorical `hour`, `day_of_week`, and
  `week_index` indicators.
- Result:
  - ATT: `0.090379`
  - Standard error: `0.002519`
  - 95% CI: `[0.085441, 0.095316]`
  - Rows: `3,343,872`
  - Treated rows: `1,442,112`
  - Control rows: `1,901,760`
  - Treated NYC stations: `2,146`
  - Control stations: `2,830`
  - Row-weighted and station-weighted estimates are identical because every
    retained station contributes exactly 672 paired rows.
- Propensity score diagnostics:
  - `g_hat` minimum after clipping: `0.010000`
  - `g_hat` maximum after clipping: `0.973363`
  - Hypothetical trimmed rows under dropping rather than clipping: `7,692`
    (`0.2300%`)
  - All outside-range observations are control rows; no treated rows would be
    trimmed.
  - `g` model AUC: `0.995357`
  - `g` model log loss: `0.238225`
  - `Q` model RMSE: `2.090898`
- City mean paired e-bike changes:
  - NYC: `0.147774`
  - Chicago: `0.154955`
  - Boston: `0.030972`
  - Philadelphia: `0.008879`
  - Washington DC: `0.013161`
- Interpretation note: this estimate is positive rather than negative. It is a
  different estimand from the October 24 policy-date analysis because it targets
  Citi Bike's operational June 20 speed change, not the later public policy
  implementation date.

### June 20 Fixed-Nuisance Station Bootstrap

- Script: `analysis/june_20/02_bootstrap_june_20_sharp_window.py`
- Status: complete.
- Purpose: compute station-cluster bootstrap confidence intervals for the June
  20 sharp-window AIPTW estimate.
- Bootstrap method:
  - Fit the cross-fitted nuisance models once.
  - Hold `g_hat`, `Q0_hat`, and `Q1_hat` fixed.
  - Resample `station_uid` clusters with replacement.
  - Recompute the row-weighted AIPTW ATT for each draw.
  - XGBoost nuisance functions are not refit inside bootstrap draws.
- Draws: `500`
- Station clusters: `4,976`
- Output: `results/june_20/june_20_sharp_window_bootstrap_summary.csv`
- Result:
  - ATT: `0.090379`
  - Analytic standard error: `0.002519`
  - Analytic 95% CI: `[0.085441, 0.095316]`
  - Bootstrap standard error: `0.009467`
  - Bootstrap percentile 95% CI: `[0.072855, 0.108151]`
- Weighting note: only the row-weighted bootstrap is reported because the
  retained June 20 station panel is balanced. Every retained station contributes
  exactly 672 paired station-hours, so station-weighted and row-weighted ATTs
  are identical by construction for this specification.

### Sharp-Window Main Spec Fixed-Nuisance Station Bootstrap

- Script: `analysis/23_bootstrap_sharp_window.py`
- Status: complete.
- Purpose: compute station-cluster bootstrap confidence intervals for the
  preferred October 24 sharp-window AIPTW estimate.
- Windows:
  - t0: `2025-09-26 00:00:00` through `2025-10-23 23:00:00`
  - t1: `2025-10-24 00:00:00` through `2025-11-20 23:00:00`
- Outcome: `ebike_trip_count` at the paired station-hour level.
- Covariates in `X`: continuous weather differences, pre/post broad weather
  condition indicators, and categorical `hour`, `day_of_week`, and
  `week_index` indicators.
- Bootstrap method:
  - Fit the cross-fitted nuisance models once.
  - Hold `g_hat`, `Q0_hat`, and `Q1_hat` fixed.
  - Resample `station_uid` clusters with replacement.
  - Recompute the row-weighted AIPTW ATT for each draw.
  - XGBoost nuisance functions are not refit inside bootstrap draws.
- Draws: `500`
- Station clusters: `5,107`
- Output: `results/main_spec/sharp_window_bootstrap_summary.csv`
- Result:
  - ATT: `-0.269000`
  - Analytic standard error: `0.002496`
  - Analytic 95% CI: `[-0.273892, -0.264108]`
  - Bootstrap standard error: `0.013013`
  - Bootstrap percentile 95% CI: `[-0.291827, -0.242106]`
  - Hypothetical trimmed rows under dropping rather than clipping: `76,994`
    (`2.2435%`)
- Weighting note: only the row-weighted bootstrap is reported because the
  retained sharp-window station panel is balanced. Every retained station
  contributes exactly 672 paired station-hours, so station-weighted and
  row-weighted ATTs are identical by construction for this specification.

### Rolling Assumed-Treatment-Date ATT Plot

- Build script: `build/rolling_att/01_build_rolling_panel.py`
- Analysis script: `analysis/rolling_att/01_run_rolling_att.py`
- Plot script: `analysis/rolling_att/02_plot_rolling_att.py`
- Status: complete.
- Purpose: create an event-study-like diagnostic by re-estimating the same
  four-week sharp-window AIPTW design under different assumed treatment dates.
- Clean data:
  - `data_clean/rolling_att/01_rolling_station_hour_panel.csv`
  - `data_clean/rolling_att/01_rolling_station_hour_panel_weather.csv`
- Broad panel range: `2025-08-15 00:00:00` through
  `2025-11-27 23:00:00`.
- Weather source: `data_raw/weather_filled_50km/`.
- Weather missingness check:
  - All non-snow AIPTW weather features have zero missingness in the broad
    rolling panel.
  - `weather_snow_mm` is handled as zero by the analysis code, as in the other
    station-hour specifications.
- Date-specific retention:
  - The first rolling run used the broad panel without applying the agreed
    exact-window station-retention rule. Those provisional outputs were moved
    to `results/rolling_att/obsolete_no_window_retention/` and should not be
    interpreted.
  - The final rolling estimates retain stations separately for each assumed
    treatment date only if the station has at least one observed trip in both
    that date's exact four-week pre window and exact four-week post window.
- Outcome: `ebike_trip_count` at the paired station-hour level.
- Treated city: NYC.
- Control cities: Chicago, Boston, Philadelphia, and Washington DC.
- Covariates in `X`: continuous weather differences, pre/post broad weather
  condition indicators, and categorical `hour`, `day_of_week`, and
  `week_index` indicators.
- Outputs:
  - `results/rolling_att/rolling_att_summary.csv`
  - `results/rolling_att/rolling_att_plot.png`
  - `results/rolling_att/rolling_att_plot.pdf`
- Results:

| Assumed date | ATT | SE | 95% CI | Treated stations | Control stations | Hypothetical trim share |
|---|---:|---:|---:|---:|---:|---:|
| 2025-09-12 | `0.167738` | `0.002620` | `[0.162603, 0.172874]` | `2,125` | `2,970` | `0.4298%` |
| 2025-09-19 | `-0.057345` | `0.002666` | `[-0.062570, -0.052120]` | `2,122` | `2,968` | `0.2331%` |
| 2025-09-26 | `-0.141515` | `0.002653` | `[-0.146715, -0.136315]` | `2,125` | `2,972` | `0.2061%` |
| 2025-10-03 | `-0.302691` | `0.002613` | `[-0.307813, -0.297569]` | `2,136` | `2,982` | `0.2019%` |
| 2025-10-10 | `-0.357263` | `0.002649` | `[-0.362455, -0.352070]` | `2,139` | `2,971` | `1.3277%` |
| 2025-10-17 | `-0.203357` | `0.002530` | `[-0.208316, -0.198399]` | `2,143` | `2,961` | `3.0318%` |
| 2025-10-24 | `-0.269000` | `0.002496` | `[-0.273892, -0.264108]` | `2,145` | `2,962` | `2.2435%` |
| 2025-10-31 | `-0.273980` | `0.002438` | `[-0.278758, -0.269201]` | `2,144` | `2,948` | `2.4690%` |

- Interpretation note: the October 24 point matches the preferred sharp-window
  main estimate. The rolling curve is not a formal regression event study; it
  is a placebo/sensitivity curve over assumed treatment dates. Negative
  estimates appear before October 24, especially around October 3 and October
  10, so the plot should be read as evidence that the sharp-window estimate is
  sensitive to broader timing/seasonality patterns, not as isolated visual
  confirmation of the October 24 policy date.
