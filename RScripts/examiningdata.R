library(tidyverse)
citi <- read_csv("~/citibike/data_clean/01_citibike.csv")

zero <- citi %>%
  filter(trip_count == 0)

# around 1.5 million only have a count of 1
