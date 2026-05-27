# Future Sensitivities

These are planned or candidate robustness checks that are not being run in the
current step.

## City-Hour E-Bike Share Outcome

- Change the unit of analysis from station-hour to city-hour.
- Outcome:
  - `city_hour_ebike_share = city_hour_ebike_trip_count / city_hour_trip_count`
- Motivation:
  - Avoid noisy station-hour ratios when many station-hours have zero or one
    ride.
  - Diagnose whether the speed cap shifted ride composition away from e-bikes.
- Open decision:
  - How to handle city-hours with zero total rides. This may not matter at
    city-hour aggregation, but should still be checked explicitly.

## Adjacent Treatment Window

- Replace the September-vs-November calendar-month design with windows closer
  to the October 24, 2025 treatment.
- Candidate windows:
  - Pre: Monday September 29, 2025 through Sunday October 19, 2025.
  - Post: Monday October 27, 2025 through Sunday November 16, 2025.
- Motivation:
  - Reduce long-run seasonal drift.
  - Avoid treatment contamination in the pre-period.
  - Avoid Thanksgiving.

## June 20 Citi Bike Speed Change

- Project owner found preliminary evidence that Citi Bike lowered the top speed
  of e-bikes to 15 mph on June 20, 2025, before the October 24 city policy date.
- Future work should treat this as a separate event from the policy effective
  date:
  - June 20 is an operational/fleet speed change that riders may or may not
    have known about immediately.
  - October 24 is the formal policy date, and may affect behavior differently
    through awareness, enforcement, or public salience.
- Candidate future analyses:
  - A June-event DiD using windows around June 20, 2025 if raw data are
    available.
  - A two-event/event-study style design separating June operational changes
    from the October policy date.
  - Sensitivities that exclude the June-to-October period from pre-treatment
    comparisons for October-focused analyses.

## Activity / Mobility Covariates

- Investigate external covariates that proxy for how active or mobile people
  are in each city.
- Candidate sources:
  - Pedestrian counters.
  - Bike counters.
  - Traffic volume or congestion measures.
  - Transit ridership.
- If only one control city has comparable data, run pairwise NYC-vs-that-city
  specifications rather than forcing the full pooled control group.
