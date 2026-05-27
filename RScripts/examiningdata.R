library(tidyverse)
citi <- read_csv("~/citibike/data_clean/01_citibike.csv")

zero <- citi %>%
  filter(trip_count == 0)

# around 1.5 million only have a count of 0

# citibike demand histogram
ggplot(data = citi) +
  geom_histogram(aes(x = trip_count))


full_data <- read_csv("~/citibike/data_clean/main_spec/11_sharp_window_station_hour_panel.csv")

full_data_clean <- full_data %>%
  group_by(city, station_hour) %>%
  mutate(city_station_hour_ebike_rides = sum(ebike_trip_count),
         city_station_hour_classic_rides = sum(classic_trip_count)) %>%
  ungroup() %>%
  group_by(treated_city, station_hour) %>%
  mutate(treated_station_hour_ebike_rides = sum(ebike_trip_count),
         treated_station_hour_classic_rides = sum(classic_trip_count)) %>%
  ungroup() %>%
  group_by(treated_city, date) %>%
  mutate(treated_station_day_ebike_rides = sum(ebike_trip_count),
         treated_station_day_classic_rides = sum(classic_trip_count))
  

# plot with citywide hourly demand across windows
city_hourly <- full_data_clean %>%
  ungroup() %>%
  distinct(city, station_hour, .keep_all = TRUE)

ggplot(city_hourly) +
  geom_line(aes(x = station_hour, 
                y = city_station_hour_ebike_rides, 
                color = city))

# plot with treatment/control hourly demand across windows
treat_hourly <- full_data_clean %>%
  ungroup() %>%
  distinct(treated_city, station_hour, .keep_all = TRUE) %>%
  mutate(treated = as.character(treated_city))

ggplot(treat_hourly) +
  geom_line(aes(x = station_hour, 
                y = treated_station_hour_ebike_rides, 
                color = treated))

ggplot(treat_hourly) +
  geom_line(aes(x = date, 
                y = treated_station_day_ebike_rides,
                color = treated)) +
  geom_smooth(aes(x = date, 
                  y = treated_station_day_ebike_rides,
                  color = treated), method = "loess")


#nyc
citi_treat_hourly <- treat_hourly %>%
  filter(city == "nyc")

ggplot(citi_treat_hourly) +
  geom_line(aes(x = date, 
                y = treated_station_day_ebike_rides),
                color = "grey") +
  geom_line(aes(x = date, 
                y = treated_station_day_classic_rides),
                color = "blue")





