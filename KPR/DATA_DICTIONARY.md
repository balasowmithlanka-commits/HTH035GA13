# DATA DICTIONARY
## Chennai Flood Emergency Response — Multi-Agent Disaster Response Coordinator

> **Classification**: This document covers both SOURCE (historical/public) data and SIMULATION (generated) data.  
> SOURCE data is read-only and never modified by the application.  
> SIMULATION data is generated at runtime from the disaster scenario engine.

---

## SOURCE DATA FILES (Files 01–04)

### 01_chennai_rainfall_source.csv
| Column | Type | Description |
|--------|------|-------------|
| Date | date (YYYY-MM-DD) | Calendar date |
| Rainfall_mm_day | float | Daily rainfall in mm |
- **Rows**: 9,362 | **Range**: 2000-01-01 to present
- **Provenance**: Original uploaded Chennai rainfall dataset
- **Use**: Historical baseline. Simulation scales recent average × flood scenario multiplier.

### 02_chennai_roads_source.csv
| Column | Type | Description |
|--------|------|-------------|
| (various) | mixed | Original road records filtered to Chennai city |
- **Provenance**: Source-filtered from uploaded road dataset
- **Use**: Base for road network; characteristics inherited by 06_chennai_1500_road_links.csv

### 03_healthcare_source.csv
| Column | Type | Description |
|--------|------|-------------|
| (various) | mixed | Healthcare facility records for Chennai |
- **Provenance**: Original uploaded healthcare data
- **Use**: Distribution ratios for patient severity estimation

### 04_chennai_census_source.csv
| Column | Type | Description |
|--------|------|-------------|
| District code | int | Census district identifier |
| State Name | str | Tamil Nadu |
| District name | str | Chennai |
| Population | int | Total population (4,646,732) |
| Male / Female | int | Gender breakdown |
| Age_Group_0_29 / 30_49 / 50 | int | Age distribution |
| Urban_Households | int | Urban household count |
| … (100+ columns) | mixed | Economic, education, infrastructure indicators |
- **Rows**: 1 (single district record) | **Provenance**: Source census record
- **Use**: Population baseline. Zone populations allocated proportionally.

---

## DERIVED + SCENARIO FILES (Files 05–14)

### 05_chennai_500_zone_cells.csv
| Column | Type | Description |
|--------|------|-------------|
| cell_id | str | Unique cell identifier (Z01-001 … Z05-100) |
| zone_id | str | Parent zone (Z01–Z05) |
| zone_name | str | Zone name (North Chennai, etc.) |
| latitude | float | Cell centroid latitude |
| longitude | float | Cell centroid longitude |
| population | int | Population in cell (derived from census) |
| rainfall_mm_day | float | Rainfall for this cell (derived from source) |
| flood_index | float | Flood severity index 0–3.5 (scenario) |
| flood_severity | str | Severe / Moderate / Minor (scenario) |
| affected_rate | float | Fraction of population affected (scenario) |
| affected_population | int | Estimated affected persons (derived) |
| evacuation_priority | str | 1-Critical / 2-High / 3-Medium / 4-Low (scenario) |
- **Rows**: 500 | **Classification**: Derived + Scenario

### 06_chennai_1500_road_links.csv
| Column | Type | Description |
|--------|------|-------------|
| road_id | str | Unique road segment ID (R0001…) |
| from_zone / to_zone | str | Zone IDs at segment endpoints |
| from_lat / from_lon | float | Start coordinates |
| to_lat / to_lon | float | End coordinates |
| distance_km | float | Segment length |
| lanes | int | Number of lanes |
| traffic_density | str | low / medium / high |
| source_risk_score | float | Risk factor 0–1 |
| road_status | str | Open / Blocked / Flooded |
| water_depth_m | float | Current water depth in metres |
| travel_time_min | float | Estimated travel time |
- **Rows**: 1,500 | **Classification**: Derived + Scenario

### 07_chennai_150_shelters.csv
| Column | Type | Description |
|--------|------|-------------|
| shelter_id | str | Unique identifier (S001…S150) |
| zone_id | str | Host zone |
| zone_name | str | Zone name |
| latitude / longitude | float | Shelter location |
| capacity | int | Maximum occupancy |
| occupancy | int | Current occupancy |
| available_slots | int | Remaining capacity |
| food_packets | int | Current food stock |
| water_litres | int | Current water stock |
| medical_support | str | Yes / No |
- **Rows**: 150 | **Classification**: Scenario

### 08_chennai_200_ambulances.csv
| Column | Type | Description |
|--------|------|-------------|
| ambulance_id | str | Unit identifier (A001…A200) |
| zone_id / zone_name | str | Base zone |
| latitude / longitude | float | Current position |
| status | str | Available / Standby / Dispatched |
| patient_capacity | int | Patients per trip |
| type | str | Advanced / Basic |
- **Rows**: 200 | **Classification**: Scenario

### 09_chennai_120_rescue_vehicles.csv
| Column | Type | Description |
|--------|------|-------------|
| rescue_vehicle_id | str | Unit identifier (RV001…) |
| zone_id / zone_name | str | Base zone |
| latitude / longitude | float | Position |
| status | str | Available / Standby / Dispatched |
| vehicle_type | str | Boat / Rescue Van / etc. |
- **Rows**: 120 | **Classification**: Scenario

### 10_chennai_150_medical_teams.csv
| Column | Type | Description |
|--------|------|-------------|
| medical_team_id | str | Team identifier (MT001…) |
| zone_id / zone_name | str | Assignment |
| doctors | int | Number of doctors |
| nurses | int | Number of nurses |
| status | str | Available / Deployed |
| specialization | str | General / Emergency / etc. |
- **Rows**: 150 | **Classification**: Scenario

### 11_chennai_500_resources.csv
| Column | Type | Description |
|--------|------|-------------|
| resource_id | str | Item identifier |
| zone_id / zone_name | str | Zone |
| resource_type | str | Blankets / Medicine / Food / etc. |
| unit | str | units / kits / litres |
| quantity | int | Stock level |
| status | str | Available / In Transit / Depleted |
- **Rows**: 500 | **Classification**: Scenario

### 12_chennai_10000_patients.csv
| Column | Type | Description |
|--------|------|-------------|
| patient_id | str | Patient identifier (P00001…) |
| zone_id / zone_name | str | Zone |
| latitude / longitude | float | Location |
| severity | str | Critical / Moderate / Minor |
| medical_condition | str | Condition type |
| arrival_mode | str | Ambulance / Rescue Vehicle / Self |
| response_status | str | Assigned / Unassigned |
- **Rows**: 10,000 | **Classification**: Derived + Scenario (synthetic triage demand)
- **Critical patients by zone**: Z01=64, Z02=53, Z03=75, Z04=78, Z05=64

### 13_chennai_3000_incidents.csv
| Column | Type | Description |
|--------|------|-------------|
| incident_id | str | Incident identifier (I00001…) |
| zone_id / zone_name | str | Zone |
| latitude / longitude | float | Location |
| incident_type | str | Flooded Road / Medical Emergency / Rescue / etc. |
| severity | str | Critical / Moderate / Minor |
| timestamp | datetime | Incident time |
- **Rows**: 3,000 | **Classification**: Scenario

### 14_chennai_20000_event_stream.csv
| Column | Type | Description |
|--------|------|-------------|
| event_id | str | Event identifier |
| cell_id | str | Spatial cell |
| zone_id / zone_name | str | Zone |
| rainfall_mm_day | float | Rainfall at time of event |
| flood_index | float | Flood index |
| response_stage | str | Stage label |
| hour / minute | int | Simulation time |
- **Rows**: 20,000 | **Classification**: Derived + Scenario

---

## SERVICE LAYER FILES (Files 16–29)
> Operational capacities, coordinates, stocks — **SCENARIO VALUES** (not live government inventory)

| File | Rows | Key Fields |
|------|------|-----------|
| 16_helicopters_air_rescue.csv | 6 | helicopter_id, base, capacity, rescue_capability, availability |
| 17_police_stations.csv | 52 | station_name, officers, vehicles, availability |
| 18_fire_rescue_stations.csv | 30 | station_name, water_tenders, rescue_tenders, personnel |
| 19_hospitals.csv | 24 | hospital_name, beds, icu_beds, emergency_capacity, specialty |
| 20_safe_places_shelters.csv | 100 | name, capacity, occupancy, facility_type |
| 21_food_distribution_centers.csv | 50 | food_packets_stock, daily_capacity |
| 22_water_points.csv | 60 | storage_capacity_litres, current_stock_litres |
| 23_medical_supply_centers.csv | 60 | item_type, stock_quantity |
| 24_evacuation_vehicles.csv | 250 | vehicle_type, passenger_capacity, capability |
| 25_helipads.csv | 6 | location_name, slots, helicopter_class |
| 26_fuel_stations.csv | 100 | storage_capacity_litres, current_stock_litres |
| 27_communication_towers.csv | 150 | network_type, status, coverage_radius_km |
| 28_power_stations.csv | 50 | capacity_mw, status, outage_risk |
| 29_schools_public_buildings.csv | 500+ | building_type, capacity, temporary_shelter_eligible |

---

## SIMULATION-GENERATED FIELDS

These fields **do not exist in source data** and are computed at runtime:

| Field | Formula | Agent Using It |
|-------|---------|----------------|
| `flood_level` (metres) | flood_index × 0.6 | All agents |
| `population_at_risk` | population × affected_rate | Medical, Rescue |
| `critical_patients` (scenario) | pop_at_risk × crit_ratio × flood_boost | Medical Agent |
| `ambulance_requirement` | ceil(critical_patients / 5) | Medical Agent |
| `rescue_vehicle_requirement` | ceil(pop_at_risk / 800) | Rescue Agent |
| `shelter_demand` | pop_at_risk × 0.35 | Logistics Agent |
| `food_requirement` | shelter_demand × 3 | Logistics Agent |
| `water_requirement` | shelter_demand × 15 | Logistics Agent |
| `priority` | derived from flood_level + critical_patients | Coordinator |
| `evacuation_routes` | graph traversal on road_status | Routing Agent |
| `what_changed` | diff(Plan V1, Plan V2) | Coordinator |
