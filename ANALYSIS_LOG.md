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

### Sharp-Window Main Spec With Propensity Trimming

- Script: `analysis/26_sharp_window_trimmed.py`
- Status: complete.
- Purpose: rerun the preferred October 24 sharp-window AIPTW specification
  dropping rows whose raw propensity score falls outside `[0.01, 0.99]`,
  instead of retaining all rows with clipped propensity scores.
- Input: `data_clean/main_spec/11_sharp_window_station_hour_panel_weather.csv`
- Output:
  - `results/sensitivities/sharp_window_trimmed_summary.csv`
  - `results/sensitivities/sharp_window_trimmed_city_diagnostics.csv`
- Windows:
  - t0: `2025-09-26 00:00:00` through `2025-10-23 23:00:00`
  - t1: `2025-10-24 00:00:00` through `2025-11-20 23:00:00`
- Outcome: `ebike_trip_count` at the paired station-hour level.
- Covariates in `X`: continuous weather differences, pre/post broad weather
  condition indicators, and categorical `hour`, `day_of_week`, and
  `week_index` indicators.
- Estimate reported: row-weighted only.
- Trim rule: drop rows with raw `g_hat < 0.01` or raw `g_hat > 0.99`.
- Rows:
  - Before trim: `3,431,904`
  - After trim: `3,354,910`
  - Dropped: `76,994` (`2.2435%`)
  - Treated rows dropped: `0`
  - Control rows dropped: `76,994` (`3.8681%` of control rows)
- Stations:
  - Treated stations before/after trim: `2,145` / `2,145`
  - Control stations before/after trim: `2,962` / `2,962`
- Result:
  - Trimmed ATT: `-0.268995`
  - Standard error: `0.002496`
  - 95% CI: `[-0.273887, -0.264103]`
- Comparison to clipped main spec:
  - Clipped main ATT: `-0.269000`
  - Difference: `0.000005`
  - Interpretation note: trimming the outside-range propensity rows instead of
    clipping them leaves the main estimate essentially unchanged.

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
- Broad panel range: `2025-07-18 00:00:00` through
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
  - A later shorter-range corrected run covering September 12-October 31 was
    moved to `results/rolling_att/obsolete_shorter_date_range/` after the
    rolling window was extended four weeks earlier. The date-level corrected
    estimates from that run were reused rather than refit.
  - The final rolling estimates retain stations separately for each assumed
    treatment date only if the station has at least one observed trip in both
    that date's exact four-week pre window and exact four-week post window.
- Plot note:
  - The x-axis labels every assumed treatment date.
  - A vertical marker at `2025-10-03` indicates the first assumed treatment date
    whose four-week post window includes actual post-October 24 treatment time.
  - A second vertical marker identifies the actual October 24 policy date.
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
| 2025-08-15 | `-0.091040` | `0.002511` | `[-0.095961, -0.086118]` | `2,134` | `2,927` | `2.6131%` |
| 2025-08-22 | `0.036557` | `0.002554` | `[0.031550, 0.041563]` | `2,130` | `2,931` | `0.9915%` |
| 2025-08-29 | `0.067841` | `0.002601` | `[0.062743, 0.072939]` | `2,126` | `2,945` | `0.5553%` |
| 2025-09-05 | `0.157263` | `0.002619` | `[0.152129, 0.162396]` | `2,124` | `2,962` | `0.4848%` |
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
  is a placebo/sensitivity curve over assumed treatment dates. Dates through
  September 26 are clean pre-treatment placebo windows with no actual
  post-October 24 exposure. The first large negative estimates occur once the
  assumed post window begins to include actual post-treatment days, starting at
  October 3. The August-September estimates also move substantially over time,
  so the plot is best read as a timing sensitivity diagnostic rather than as
  isolated visual confirmation of the October 24 policy date.

### Sharp Window Baseline-Demand and Log-Scale Sensitivities

- Date run: `2026-05-28`.
- Purpose: address the concern that NYC has substantially more e-bike rides per
  station-hour than the control cities, so a common proportional demand shock
  could appear larger in raw trip counts for NYC.
- Shared design:
  - Window: `2025-09-26 00:00:00` through `2025-10-23 23:00:00` versus
    `2025-10-24 00:00:00` through `2025-11-20 23:00:00`.
  - Treated city: NYC.
  - Control cities: Chicago, Boston, Philadelphia, and Washington DC.
  - Five-fold station-level cross-fitting.
  - Propensity clipping at `[0.01, 0.99]`.
  - Weather controls and categorical `hour`, `day_of_week`, and `week_index`
    controls match the preferred sharp-window main specification.
- Baseline-demand diagnostic:
  - Candidate baseline definitions were inspected before fitting. The preferred
    `station_uid x day_of_week x hour` baseline had only four observations per
    cell and was judged too noisy: 45.5% of cells had zero total pre-period
    e-bike trips, and early-versus-late pre-period Spearman correlation was
    0.680.
  - The chosen covariate was leave-one-out average pre-treatment
    `ebike_trip_count` by `station_uid x hour`.
  - This baseline has 28 pre-period observations per station-hour cell before
    leave-one-out, 122,568 groups, median `0.259259`, p90 `3.074074`, p95
    `5.703704`, and 21.8% zero values.
- Baseline-demand sensitivity:
  - Script: `analysis/27_sharp_window_baseline_demand_controls.py`.
  - Outputs:
    - `results/sensitivities/sharp_window_baseline_demand_controls_summary.csv`
    - `results/sensitivities/sharp_window_baseline_demand_controls_row_weighted.csv`
    - `results/sensitivities/sharp_window_baseline_demand_controls_station_weighted.csv`
    - `results/sensitivities/sharp_window_baseline_demand_controls_baseline_diagnostics.csv`
  - Outcome: raw `ebike_trip_count` change.
  - Extra covariate in `X`: `baseline_station_hour_ebike_pre_loo`.
  - Row-weighted ATT: `0.028009`.
  - Standard error: `0.004420`.
  - 95% CI: `[0.019347, 0.036672]`.
  - Hypothetical trim share from raw propensities outside `[0.01, 0.99]`:
    `2.0605%`.
  - Interpretation note: conditioning on station-hour baseline e-bike demand
    reverses the raw-count ATT from negative to slightly positive. This is a
    major sensitivity and suggests that baseline demand scale is highly
    consequential for the raw-count specification.
- Log1p outcome sensitivity:
  - Script: `analysis/28_sharp_window_log1p_outcome.py`.
  - Outputs:
    - `results/sensitivities/sharp_window_log1p_outcome_summary.csv`
    - `results/sensitivities/sharp_window_log1p_outcome_row_weighted.csv`
    - `results/sensitivities/sharp_window_log1p_outcome_station_weighted.csv`
  - Outcome: `log1p(y1_ebike_trip_count) - log1p(y0_ebike_trip_count)`.
  - Row-weighted ATT: `-0.044984`.
  - Standard error: `0.000601`.
  - 95% CI: `[-0.046161, -0.043807]`.
  - Hypothetical trim share from raw propensities outside `[0.01, 0.99]`:
    `2.2435%`.
  - Interpretation note: on a log-like scale, NYC still has a negative
    relative change, but the estimand is proportional/log-change rather than
    lost station-hour trips. This result is more directly responsive to the
    baseline-scale concern than the raw-count ATT.

### June 20 Baseline-Demand Sensitivity

- Date run: `2026-05-28`.
- Script: `analysis/june_20/03_june_20_baseline_demand_controls.py`.
- Run mode: caffeinated with `caffeinate -i`; command exited normally.
- Purpose: rerun the June 20 sharp-window analysis while controlling for
  baseline e-bike demand, analogous to the October 24 baseline-demand
  sensitivity.
- Window:
  - Pre-treatment: `2025-05-23 00:00:00` through `2025-06-19 23:00:00`.
  - Post-treatment: `2025-06-20 00:00:00` through `2025-07-17 23:00:00`.
- Station inclusion:
  - The built June 20 panel uses the exact-window station-retention rule:
    stations must appear with at least one observed trip in both the pre and
    post windows.
- Outcome: raw `ebike_trip_count` change at the paired station-hour level.
- Added covariate in `X`: leave-one-out pre-treatment mean
  `ebike_trip_count` by `station_uid x hour`
  (`baseline_station_hour_ebike_pre_loo`).
- Other covariates: same as the June 20 time-control specification:
  continuous-weather differences, pre/post broad weather-condition indicators,
  and categorical `hour`, `day_of_week`, and `week_index` indicators.
- Outputs:
  - `results/june_20/june_20_baseline_demand_controls_summary.csv`
  - `results/june_20/june_20_baseline_demand_controls_row_weighted.csv`
  - `results/june_20/june_20_baseline_demand_controls_station_weighted.csv`
  - `results/june_20/june_20_baseline_demand_controls_baseline_diagnostics.csv`
- Baseline covariate diagnostics:
  - Rows: `3,343,872`.
  - Groups: `119,424`.
  - Mean: `1.046759`.
  - Median: `0.222222`.
  - p90: `2.851852`.
  - p95: `5.259259`.
  - p99: `11.444444`.
  - Share zero: `23.4946%`.
- Result:
  - Row-weighted ATT: `-0.293970`.
  - Standard error: `0.003012`.
  - 95% CI: `[-0.299874, -0.288067]`.
  - Station-weighted ATT is identical because the retained panel is balanced by
    station-hour.
  - Hypothetical trim share from raw propensities outside `[0.01, 0.99]`:
    `2.1360%`.
- Comparison:
  - Prior June 20 sharp-window ATT without baseline-demand covariate:
    `0.090379`.
  - Adding baseline station-hour demand reverses the June 20 estimate from
    positive to substantially negative. This mirrors the October 24 exercise in
    showing that baseline e-bike demand scale is highly consequential, though
    the direction of the reversal differs across the two dates.

### Baseline-Demand Control-Group Sensitivities

- Date run: `2026-05-28`.
- Run mode: caffeinated with `caffeinate -i`; both scripts exited normally.
- Shared added covariate: leave-one-out pre-treatment mean
  `ebike_trip_count` by `station_uid x hour`
  (`baseline_station_hour_ebike_pre_loo`).
- Other covariates: weather controls and categorical `hour`, `day_of_week`,
  and `week_index` controls.
- Note on interruption: the workstation lost Wi-Fi during the June 20 run, but
  the analysis was local-only and continued running. Outputs were written
  normally.

#### October 24 Baseline-Demand Control-Group Sensitivities

- Script: `analysis/29_sharp_window_baseline_demand_control_groups.py`.
- Outputs:
  - `results/sensitivities/sharp_window_baseline_demand_one_control_city_summary.csv`
  - `results/sensitivities/sharp_window_baseline_demand_leave_one_control_out_summary.csv`
- Window: `2025-09-26 00:00:00` through `2025-10-23 23:00:00` versus
  `2025-10-24 00:00:00` through `2025-11-20 23:00:00`.
- Pooled baseline-demand estimate for comparison:
  - ATT: `0.028009`.
  - SE: `0.004420`.
  - 95% CI: `[0.019347, 0.036672]`.
- Individual-control estimates:

| Control city | ATT | SE | 95% CI | Hypothetical trim share |
|---|---:|---:|---:|---:|
| Chicago | `0.168874` | `0.005111` | `[0.158856, 0.178892]` | `6.8603%` |
| Boston | `-0.042680` | `0.004312` | `[-0.051132, -0.034229]` | `13.1929%` |
| Philadelphia | `-0.017351` | `0.005641` | `[-0.028408, -0.006295]` | `14.4159%` |
| Washington DC | `-0.041638` | `0.004415` | `[-0.050292, -0.032984]` | `1.7748%` |

- Leave-one-control-out estimates:

| Omitted control city | ATT | SE | 95% CI | Hypothetical trim share |
|---|---:|---:|---:|---:|
| Chicago | `-0.049784` | `0.004591` | `[-0.058783, -0.040786]` | `0.4667%` |
| Boston | `0.029210` | `0.004703` | `[0.019991, 0.038428]` | `2.4209%` |
| Philadelphia | `0.029107` | `0.004499` | `[0.020290, 0.037925]` | `2.1785%` |
| Washington DC | `0.092551` | `0.004962` | `[0.082826, 0.102277]` | `2.5779%` |

- Interpretation note: with baseline-demand controls, the October 24 pooled
  estimate is small and positive, but the individual-control estimates vary in
  sign. Chicago alone implies a positive estimate, while Boston, Philadelphia,
  and Washington DC alone imply negative estimates. The leave-one-out checks
  show that omitting Chicago makes the estimate negative, while omitting
  Washington DC makes it more positive.

#### June 20 Baseline-Demand Control-Group Sensitivities

- Script: `analysis/june_20/04_june_20_baseline_demand_control_groups.py`.
- Outputs:
  - `results/june_20/june_20_baseline_demand_one_control_city_summary.csv`
  - `results/june_20/june_20_baseline_demand_leave_one_control_out_summary.csv`
- Window: `2025-05-23 00:00:00` through `2025-06-19 23:00:00` versus
  `2025-06-20 00:00:00` through `2025-07-17 23:00:00`.
- Pooled baseline-demand estimate for comparison:
  - ATT: `-0.293970`.
  - SE: `0.003012`.
  - 95% CI: `[-0.299874, -0.288067]`.
- Individual-control estimates:

| Control city | ATT | SE | 95% CI | Hypothetical trim share |
|---|---:|---:|---:|---:|
| Chicago | `-0.922870` | `0.003314` | `[-0.929365, -0.916375]` | `10.7162%` |
| Boston | `0.008032` | `0.002843` | `[0.002460, 0.013604]` | `16.2486%` |
| Philadelphia | `0.035781` | `0.002681` | `[0.030525, 0.041036]` | `23.3264%` |
| Washington DC | `0.020762` | `0.002774` | `[0.015325, 0.026199]` | `7.1012%` |

- Leave-one-control-out estimates:

| Omitted control city | ATT | SE | 95% CI | Hypothetical trim share |
|---|---:|---:|---:|---:|
| Chicago | `0.034768` | `0.002726` | `[0.029425, 0.040111]` | `3.2937%` |
| Boston | `-0.325408` | `0.002989` | `[-0.331267, -0.319550]` | `2.9191%` |
| Philadelphia | `-0.325851` | `0.003061` | `[-0.331850, -0.319852]` | `2.4162%` |
| Washington DC | `-0.582479` | `0.003595` | `[-0.589524, -0.575433]` | `3.7663%` |

- Interpretation note: the June 20 baseline-demand estimate is extremely
  sensitive to Chicago. Chicago alone implies a very large negative estimate,
  while Boston, Philadelphia, and Washington DC alone imply small positive
  estimates. Omitting Chicago from the pooled controls also makes the estimate
  small and positive. This suggests the June 20 baseline-demand result is
  driven heavily by Chicago's control trajectory rather than being stable
  across control groups.

### Baseline-Demand Fixed-Nuisance Station Bootstraps

- Date run: `2026-05-28`.
- Run mode: caffeinated with `caffeinate -i`; both scripts exited normally.
- Bootstrap method:
  - Fit the five-fold cross-fitted XGBoost nuisance models once.
  - Collapse row-level AIPTW numerator and denominator contributions to
    `station_uid` clusters.
  - Resample station clusters with replacement.
  - Recompute the normalized row-weighted ATT for each bootstrap draw.
  - Number of draws: `500`.
  - Nuisance functions are fixed across bootstrap draws.
- Shared added covariate: leave-one-out pre-treatment mean
  `ebike_trip_count` by `station_uid x hour`
  (`baseline_station_hour_ebike_pre_loo`).

#### October 24 Baseline-Demand Bootstrap

- Script: `analysis/30_bootstrap_sharp_window_baseline_demand.py`.
- Output: `results/main_spec/sharp_window_baseline_demand_bootstrap_summary.csv`.
- Station clusters: `5,107`.
- Point estimate: `0.028009`.
- Analytic SE: `0.004420`.
- Analytic 95% CI: `[0.019347, 0.036672]`.
- Bootstrap SE: `0.014044`.
- Bootstrap 95% CI: `[0.000971, 0.054942]`.
- Interpretation note: the fixed-nuisance station bootstrap interval is much
  wider than the analytic interval, but remains barely above zero in this
  500-draw run.

#### June 20 Baseline-Demand Bootstrap

- Script: `analysis/june_20/05_bootstrap_june_20_baseline_demand.py`.
- Output: `results/june_20/june_20_baseline_demand_bootstrap_summary.csv`.
- Station clusters: `4,976`.
- Point estimate: `-0.293970`.
- Analytic SE: `0.003012`.
- Analytic 95% CI: `[-0.299874, -0.288067]`.
- Bootstrap SE: `0.015133`.
- Bootstrap 95% CI: `[-0.323228, -0.264520]`.
- Interpretation note: the bootstrap interval is much wider than the analytic
  interval, but the June 20 pooled baseline-demand estimate remains clearly
  negative under this fixed-nuisance station bootstrap.

### Baseline-Demand Propensity Trimming Sensitivities

- Date run: `2026-05-28`.
- Run mode: caffeinated with `caffeinate -i`; both scripts exited normally.
- Purpose: rerun the pooled baseline-demand specifications with propensity
  trimming instead of clipping.
- Trim rule: drop rows with raw `g_hat` outside `[0.01, 0.99]`.
- Shared covariates: weather controls, categorical `hour`, `day_of_week`, and
  `week_index` controls, and leave-one-out pre-treatment mean
  `ebike_trip_count` by `station_uid x hour`.

#### October 24 Baseline-Demand Trimming

- Script: `analysis/31_sharp_window_baseline_demand_trimmed.py`.
- Outputs:
  - `results/sensitivities/sharp_window_baseline_demand_trimmed_summary.csv`
  - `results/sensitivities/sharp_window_baseline_demand_trimmed_city_diagnostics.csv`
- Clipped pooled baseline-demand estimate for comparison:
  - ATT: `0.028009`.
  - SE: `0.004420`.
  - 95% CI: `[0.019347, 0.036672]`.
- Trimmed result:
  - ATT: `0.028043`.
  - SE: `0.004423`.
  - 95% CI: `[0.019375, 0.036711]`.
- Trimming diagnostics:
  - Rows before trim: `3,431,904`.
  - Rows after trim: `3,361,189`.
  - Rows dropped: `70,715` (`2.0605%`).
  - Treated rows dropped: `2,706`.
  - Control rows dropped: `68,009`.
  - Treated stations before/after: `2,145` / `2,145`.
  - Control stations before/after: `2,962` / `2,962`.
- Interpretation note: trimming instead of clipping has essentially no effect
  on the October 24 pooled baseline-demand estimate.

#### June 20 Baseline-Demand Trimming

- Script: `analysis/june_20/07_june_20_baseline_demand_trimmed.py`.
- Outputs:
  - `results/june_20/june_20_baseline_demand_trimmed_summary.csv`
  - `results/june_20/june_20_baseline_demand_trimmed_city_diagnostics.csv`
- Clipped pooled baseline-demand estimate for comparison:
  - ATT: `-0.293970`.
  - SE: `0.003012`.
  - 95% CI: `[-0.299874, -0.288067]`.
- Trimmed result:
  - ATT: `-0.257476`.
  - SE: `0.002951`.
  - 95% CI: `[-0.263260, -0.251692]`.
- Trimming diagnostics:
  - Rows before trim: `3,343,872`.
  - Rows after trim: `3,272,448`.
  - Rows dropped: `71,424` (`2.1360%`).
  - Treated rows dropped: `41,865`.
  - Control rows dropped: `29,559`.
  - Treated stations before/after: `2,146` / `2,146`.
  - Control stations before/after: `2,830` / `2,830`.
- Interpretation note: trimming makes the June 20 pooled baseline-demand
  estimate less negative by about `0.0365`, but it remains clearly negative.

### June 20 No-Baseline Control-Group Sensitivities

- Date run: `2026-05-28`.
- Script: `analysis/june_20/06_june_20_control_groups.py`.
- Run mode: caffeinated with `caffeinate -i`; script exited normally.
- Purpose: create the June 20 analog of the October 24 no-baseline
  control-group sensitivity table.
- Window:
  - Pre-treatment: `2025-05-23 00:00:00` through `2025-06-19 23:00:00`.
  - Post-treatment: `2025-06-20 00:00:00` through `2025-07-17 23:00:00`.
- Outcome: raw `ebike_trip_count` change at the paired station-hour level.
- Covariates: continuous-weather differences, pre/post broad weather-condition
  indicators, and categorical `hour`, `day_of_week`, and `week_index`
  indicators. No baseline-demand covariate.
- Outputs:
  - `results/june_20/june_20_one_control_city_summary.csv`
  - `results/june_20/june_20_leave_one_control_out_summary.csv`
- Pooled no-baseline estimate for comparison:
  - ATT: `0.090379`.
  - Analytic SE: `0.002519`.
  - Analytic 95% CI: `[0.085441, 0.095316]`.
  - Bootstrap 95% CI: `[0.072855, 0.108151]`.
- Individual-control estimates:

| Control city | ATT | SE | 95% CI | Hypothetical trim share |
|---|---:|---:|---:|---:|
| Chicago | `-0.004647` | `0.002492` | `[-0.009532, 0.000238]` | `2.3931%` |
| Boston | `0.109071` | `0.002513` | `[0.104146, 0.113996]` | `0.3261%` |
| Philadelphia | `0.118403` | `0.002542` | `[0.113420, 0.123385]` | `6.0293%` |
| Washington DC | `0.091171` | `0.002516` | `[0.086239, 0.096103]` | `2.0300%` |

- Leave-one-control-out estimates:

| Omitted control city | ATT | SE | 95% CI | Hypothetical trim share |
|---|---:|---:|---:|---:|
| Chicago | `0.119968` | `0.002521` | `[0.115027, 0.124908]` | `0.1201%` |
| Boston | `0.081060` | `0.002520` | `[0.076122, 0.085999]` | `0.2241%` |
| Philadelphia | `0.079435` | `0.002513` | `[0.074509, 0.084360]` | `0.1777%` |
| Washington DC | `0.073302` | `0.002519` | `[0.068366, 0.078239]` | `0.1992%` |

- Table output:
  - `figures/tables/table_8_june20_no_baseline_controls/`.
- Interpretation note: without baseline-demand controls, the June 20 pooled
  estimate is positive and fairly stable across leave-one-out checks. Chicago
  alone is the exception among individual controls, giving an estimate close
  to zero.

### June 20 Citi Bike E-Bike Speed Analysis

- Date run: `2026-05-28`.
- Build script: `build/speed/02_build_june20_speed_panel.py`.
- Analysis script: `analysis/speed/01_june20_speed_aiptw.py`.
- Run mode: caffeinated with `caffeinate -i`; both scripts exited normally.
- Purpose: test whether the June 20, 2025 Citi Bike operational e-bike speed
  reduction changed average speed among Citi e-bike rides.
- Treatment/control:
  - Treated: Citi Bike `electric_bike` rides.
  - Control: Citi Bike `classic_bike` rides.
- Window:
  - Pre-treatment: `2025-05-23` through `2025-06-19`.
  - Post-treatment: `2025-06-20` through `2025-07-17`.
- Unit of analysis:
  - `OD pair x ride type x week_index x day_of_week`.
  - Each row has a matched pre and post average speed for the same OD pair,
    ride type, week-within-window, and day of week.
- Outcome:
  - `avg_speed_mph_post - avg_speed_mph_pre`.
  - Speed uses straight-line origin-destination distance divided by trip
    duration; this is not route distance.
- Retention rule:
  - OD pairs must have both classic-bike and e-bike rides in both pre and post
    windows.
  - OD pairs must have at least `50` total classic rides and at least `50`
    total e-bike rides across the full 56-day window.
- Ride-level speed filters:
  - Duration between `1` and `180` minutes.
  - Straight-line OD distance at least `0.05` miles.
  - Average straight-line speed between `0.5` and `30` mph.
- Outputs:
  - `data_clean/speed/02_june20_speed_paired_panel_threshold50.csv`.
  - `data_clean/speed/02_june20_speed_panel_diagnostics.csv`.
  - `results/speed/01_june20_speed_aiptw_threshold50.csv`.
  - `results/speed/01_june20_speed_aiptw_threshold50_ride_type_diagnostics.csv`.
  - `results/speed/01_june20_speed_aiptw_threshold50_predictions.csv`.
- Build diagnostics:
  - Earlier coverage-only threshold-50 diagnostic implied `148,479` paired
    rows.
  - After applying speed-validity filters before pairing, the analysis panel
    contains `133,234` paired rows.
  - Retained OD pairs: `4,175`.
  - Classic-bike paired rows: `60,927`.
  - E-bike paired rows: `72,307`.
  - Median pre/post rides per paired cell: `2` / `2`.
  - Missing weather rows: `0`.
- Unadjusted paired speed changes:
  - Classic bikes: mean pre speed `5.9849` mph, mean post speed `5.9097` mph,
    mean change `-0.0752` mph.
  - E-bikes: mean pre speed `7.6761` mph, mean post speed `7.4312` mph, mean
    change `-0.2449` mph.
- AIPTW result:
  - ATT: `-0.166926` mph.
  - Analytic SE: `0.011404`.
  - 95% CI: `[-0.189278, -0.144574]`.
  - Rows: `133,234`.
  - Treated rows: `72,307`.
  - Control rows: `60,927`.
- Propensity-score diagnostics:
  - Clipping range: `[0.01, 0.99]`.
  - Raw propensity range: `[0.516018, 0.580750]`.
  - Mean clipped propensity: `0.542716`.
  - Rows clipped: `0`.
  - Hypothetical rows lost under trimming: `0` (`0.0000%`).
  - G-model AUC: `0.515568`.
  - G-model log loss: `0.689098`.
  - Q-model RMSE: `2.105338`.
- Interpretation note: under this OD-day cell design, e-bike average
  straight-line speed fell by about `0.167` mph more than classic-bike speed
  after June 20. The propensity scores are extremely non-extreme here, so
  clipping/trimming is not driving the result.

### June 20 Citi Bike E-Bike Speed Threshold Sensitivities

- Date run: `2026-05-28`.
- Scripts:
  - `build/speed/02_build_june20_speed_panel.py`.
  - `analysis/speed/01_june20_speed_aiptw.py`.
- Run mode: caffeinated with `caffeinate -i`; all scripts exited normally.
- Purpose: test whether the speed ATT depends on the minimum total ride-count
  threshold used to retain OD pairs.
- Design held fixed across thresholds:
  - Window: `2025-05-23` through `2025-06-19` versus `2025-06-20` through
    `2025-07-17`.
  - Treatment/control: Citi Bike e-bikes versus Citi Bike classic bikes.
  - Outcome: post-minus-pre change in average straight-line speed at the
    `OD pair x ride type x week_index x day_of_week` level.
  - Covariates: paired daily weather differences, pre/post broad weather
    condition indicators, and categorical `day_of_week` and `week_index`
    indicators.
  - Speed filters: duration `1`-`180` minutes, straight-line OD distance at
    least `0.05` miles, and straight-line speed `0.5`-`30` mph.
  - Propensity clipping range: `[0.01, 0.99]`.
- Summary output:
  - `results/speed/01_june20_speed_threshold_sensitivity_summary.csv`.

| Min rides per OD/type | OD pairs | Rows | E-bike rows | Classic rows | ATT mph | SE | 95% CI | Trim share |
|---:|---:|---:|---:|---:|---:|---:|---|---:|
| `30` | `11,247` | `256,416` | `145,761` | `110,655` | `-0.174274` | `0.008507` | `[-0.190947, -0.157600]` | `0.0000%` |
| `50` | `4,175` | `133,234` | `72,307` | `60,927` | `-0.166926` | `0.011404` | `[-0.189278, -0.144574]` | `0.0000%` |
| `75` | `1,664` | `65,667` | `34,602` | `31,065` | `-0.182522` | `0.015397` | `[-0.212701, -0.152343]` | `0.0000%` |
| `100` | `788` | `34,866` | `18,067` | `16,799` | `-0.201293` | `0.019976` | `[-0.240446, -0.162140]` | `0.0000%` |

- Propensity diagnostics:
  - No threshold had any propensity scores outside `[0.01, 0.99]`.
  - Raw propensity ranges were mild:
    - threshold `30`: `[0.538948, 0.616769]`.
    - threshold `50`: `[0.516018, 0.580750]`.
    - threshold `75`: `[0.506626, 0.563155]`.
    - threshold `100`: `[0.498411, 0.543851]`.
- Interpretation note: the estimated e-bike speed decline is stable across
  OD-pair ride-count thresholds and becomes somewhat more negative under the
  strictest threshold. This supports the conclusion that the June 20 speed
  reduction lowered realized straight-line e-bike speed relative to classic
  bikes, though the estimand remains an OD-day-cell average rather than a
  ride-weighted average.

### June 20 No-Chicago Reruns

- Date run: `2026-05-28`.
- Reason: the June 20 descriptive plot revealed false Chicago zeros from
  `2025-05-23` through `2025-05-30`. Raw Divvy has normal rides on those dates,
  but Divvy station IDs appear to change around `2025-06-01`, from numeric-like
  IDs to `CHI...` IDs. Because the station-hour panel retains stations by
  `start_station_id` presence in both exact windows, the June-style Chicago
  stations have no observations in the first eight pre-window days and are
  filled as zeros.
- Decision: rerun June 20 count analyses excluding Chicago rather than
  introducing a fuzzy Divvy station crosswalk.
- Control cities retained:
  - Boston.
  - Philadelphia.
  - Washington DC.
- Scripts:
  - `analysis/june_20/08_june_20_no_chicago_control_groups.py`.
  - `analysis/june_20/09_bootstrap_june_20_no_chicago.py`.
  - `analysis/june_20/10_june_20_baseline_demand_no_chicago_control_groups.py`.
  - `analysis/june_20/11_bootstrap_june_20_baseline_demand_no_chicago.py`.
- Run mode: caffeinated with `caffeinate -i`; all scripts exited normally.
- Outputs:
  - `results/june_20_no_chicago/june_20_no_chicago_pooled_summary.csv`.
  - `results/june_20_no_chicago/june_20_no_chicago_one_control_city_summary.csv`.
  - `results/june_20_no_chicago/june_20_no_chicago_leave_one_control_out_summary.csv`.
  - `results/june_20_no_chicago/june_20_no_chicago_bootstrap_summary.csv`.
  - `results/june_20_no_chicago/june_20_baseline_demand_no_chicago_pooled_summary.csv`.
  - `results/june_20_no_chicago/june_20_baseline_demand_no_chicago_one_control_city_summary.csv`.
  - `results/june_20_no_chicago/june_20_baseline_demand_no_chicago_leave_one_control_out_summary.csv`.
  - `results/june_20_no_chicago/june_20_baseline_demand_no_chicago_bootstrap_summary.csv`.
- Rebuilt paper tables:
  - `figures/tables/table_7_june20_baseline_demand_controls/`.
  - `figures/tables/table_8_june20_no_baseline_controls/`.
  - Table notes now state that Chicago is excluded because of the Divvy station
    ID break.

#### No-Baseline No-Chicago Results

- Pooled ATT excluding Chicago:
  - ATT: `0.119968`.
  - Analytic SE: `0.002521`.
  - Analytic 95% CI: `[0.115027, 0.124908]`.
  - Bootstrap SE: `0.009365`.
  - Bootstrap 95% CI: `[0.100771, 0.139498]`.
  - Rows: `2,534,784`.
  - Hypothetical trim share: `0.1201%`.
- Cross-check:
  - New no-Chicago pooled estimate exactly matches the prior
    `june_20_leave_one_out_excluding_chicago_row_weighted.csv` estimate.
- Individual-control estimates:
  - Boston: ATT `0.109071`, 95% CI `[0.104146, 0.113996]`.
  - Philadelphia: ATT `0.118403`, 95% CI `[0.113420, 0.123385]`.
  - Washington DC: ATT `0.091171`, 95% CI `[0.086239, 0.096103]`.
- Leave-one-out among retained controls:
  - Excluding Boston: ATT `0.117818`, 95% CI `[0.112823, 0.122814]`.
  - Excluding Philadelphia: ATT `0.111115`, 95% CI `[0.106165, 0.116064]`.
  - Excluding Washington DC: ATT `0.117606`, 95% CI `[0.112632, 0.122580]`.

#### Baseline-Demand No-Chicago Results

- Pooled ATT excluding Chicago:
  - ATT: `0.034768`.
  - Analytic SE: `0.002726`.
  - Analytic 95% CI: `[0.029425, 0.040111]`.
  - Bootstrap SE: `0.009492`.
  - Bootstrap 95% CI: `[0.014459, 0.054588]`.
  - Rows: `2,534,784`.
  - Hypothetical trim share: `3.2937%`.
- Cross-check:
  - New no-Chicago pooled estimate exactly matches the prior
    `june_20_baseline_demand_leave_one_out_excluding_chicago_row_weighted.csv`
    estimate.
- Individual-control estimates:
  - Boston: ATT `0.007979`, 95% CI `[0.002126, 0.013831]`.
  - Philadelphia: ATT `0.036035`, 95% CI `[0.030647, 0.041423]`.
  - Washington DC: ATT `0.020550`, 95% CI `[0.015048, 0.026052]`.
- Leave-one-out among retained controls:
  - Excluding Boston: ATT `0.034629`, 95% CI `[0.029216, 0.040041]`.
  - Excluding Philadelphia: ATT `0.026094`, 95% CI `[0.020702, 0.031486]`.
  - Excluding Washington DC: ATT `0.027467`, 95% CI `[0.022077, 0.032856]`.

### June 20 Speed Threshold Bootstrap CIs

- Date run: `2026-05-28`.
- Script: `analysis/speed/02_bootstrap_june20_speed_thresholds.py`.
- Run mode: caffeinated with `caffeinate -i`; script exited normally.
- Bootstrap method:
  - Fit the cross-fitted XGBoost nuisance models once for each threshold.
  - Resample `station_uid` clusters, where `station_uid` is the OD-pair ID in
    this speed panel.
  - Recompute the normalized AIPTW ATT for each bootstrap draw.
  - Do not refit XGBoost inside bootstrap draws.
- Number of bootstrap draws: `500`.
- Outputs:
  - `results/speed/02_june20_speed_threshold_bootstrap_summary.csv`.
  - `results/speed/02_june20_speed_threshold_bootstrap_draws.csv`.

| Min rides per OD/type | ATT mph | Analytic SE | Analytic 95% CI | Bootstrap SE | Bootstrap 95% CI | OD clusters |
|---:|---:|---:|---|---:|---|---:|
| `30` | `-0.174274` | `0.008507` | `[-0.190947, -0.157600]` | `0.008950` | `[-0.189343, -0.154522]` | `11,247` |
| `50` | `-0.166926` | `0.011404` | `[-0.189278, -0.144574]` | `0.011989` | `[-0.191733, -0.144486]` | `4,175` |
| `75` | `-0.182522` | `0.015397` | `[-0.212701, -0.152343]` | `0.015813` | `[-0.211603, -0.150221]` | `1,664` |
| `100` | `-0.201293` | `0.019976` | `[-0.240446, -0.162140]` | `0.019909` | `[-0.238678, -0.159773]` | `788` |

- Interpretation note: fixed-nuisance OD-pair bootstrap uncertainty is very
  close to the analytic uncertainty for all four speed thresholds. This is
  reassuring for the speed analysis because the bootstrap CIs do not materially
  weaken the conclusion that e-bike average straight-line speed fell relative
  to classic bikes after June 20.
