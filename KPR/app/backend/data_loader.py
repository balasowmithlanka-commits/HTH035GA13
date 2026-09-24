"""
Data Loader — reads the Chennai source CSV files and builds initial simulation state.
Source data is read-only; this module never modifies the original files.
"""
import os
import pandas as pd
import numpy as np
from typing import Dict, List, Any

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "chennai_disaster_response_COMPLETE")


def _path(filename: str) -> str:
    return os.path.join(DATA_DIR, filename)


# ─── Zone Cells ───────────────────────────────────────────────────────────────

def load_zone_cells() -> pd.DataFrame:
    df = pd.read_csv(_path("05_chennai_500_zone_cells.csv"))
    return df


def get_zone_summary() -> Dict[str, Dict]:
    """Aggregate 500 spatial cells into 5 zones."""
    df = load_zone_cells()
    summary = {}
    for (zone_id, zone_name), grp in df.groupby(["zone_id", "zone_name"]):
        summary[zone_id] = {
            "zone_id": zone_id,
            "zone_name": zone_name,
            "latitude": grp["latitude"].mean(),
            "longitude": grp["longitude"].mean(),
            "total_population": int(grp["population"].sum()),
            "total_affected_population": int(grp["affected_population"].sum()),
            "avg_flood_index": float(grp["flood_index"].mean()),
            "avg_rainfall": float(grp["rainfall_mm_day"].mean()),
            "dominant_flood_severity": grp["flood_severity"].mode()[0],
            "critical_cells": int((grp["evacuation_priority"] == "1-Critical").sum()),
        }
    return summary


# ─── Roads ────────────────────────────────────────────────────────────────────

def load_roads() -> pd.DataFrame:
    df = pd.read_csv(_path("06_chennai_1500_road_links.csv"))
    return df


def get_road_summary() -> Dict[str, Any]:
    df = load_roads()
    return {
        "total_roads": len(df),
        "blocked": int((df["road_status"] == "Blocked").sum()),
        "flooded": int((df["road_status"] == "Flooded").sum()),
        "open": int((df["road_status"] == "Open").sum()),
        "roads": df.to_dict("records"),
    }


# ─── Ambulances ───────────────────────────────────────────────────────────────

def load_ambulances() -> pd.DataFrame:
    return pd.read_csv(_path("08_chennai_200_ambulances.csv"))


def get_ambulance_counts() -> Dict[str, int]:
    df = load_ambulances()
    return {
        "total": len(df),
        "available": int((df["status"] == "Available").sum()),
        "standby": int((df["status"] == "Standby").sum()),
        "dispatched": int((df["status"] == "Dispatched").sum()),
    }


# ─── Rescue Vehicles ──────────────────────────────────────────────────────────

def load_rescue_vehicles() -> pd.DataFrame:
    return pd.read_csv(_path("09_chennai_120_rescue_vehicles.csv"))


def get_rescue_vehicle_counts() -> Dict[str, int]:
    df = load_rescue_vehicles()
    return {
        "total": len(df),
        "available": int((df["status"] == "Available").sum()),
        "standby": int((df["status"] == "Standby").sum()),
        "dispatched": int((df["status"] == "Dispatched").sum()),
    }


# ─── Medical Teams ────────────────────────────────────────────────────────────

def load_medical_teams() -> pd.DataFrame:
    return pd.read_csv(_path("10_chennai_150_medical_teams.csv"))


def get_medical_team_counts() -> Dict[str, int]:
    df = load_medical_teams()
    return {
        "total": len(df),
        "available": int((df["status"] == "Available").sum()),
    }


# ─── Helicopters ──────────────────────────────────────────────────────────────

def load_helicopters() -> pd.DataFrame:
    return pd.read_csv(_path("16_helicopters_air_rescue.csv"))


def get_helicopter_counts() -> Dict[str, int]:
    df = load_helicopters()
    return {
        "total": len(df),
        "available": int((df["availability"] == "Available").sum()),
        "standby": int((df["availability"] == "Standby").sum()),
    }


# ─── Shelters ─────────────────────────────────────────────────────────────────

def load_shelters() -> pd.DataFrame:
    return pd.read_csv(_path("07_chennai_150_shelters.csv"))


def load_safe_places() -> pd.DataFrame:
    return pd.read_csv(_path("20_safe_places_shelters.csv"))


def get_shelter_counts() -> Dict[str, int]:
    df = load_shelters()
    sp = load_safe_places()
    total_cap = int(df["capacity"].sum()) + int(sp["capacity"].sum())
    total_occ = int(df["occupancy"].sum()) + int(sp["occupancy"].sum())
    return {
        "total": total_cap,
        "occupied": total_occ,
        "available": total_cap - total_occ,
    }


# ─── Police ───────────────────────────────────────────────────────────────────

def load_police_stations() -> pd.DataFrame:
    return pd.read_csv(_path("17_police_stations.csv"))


def get_police_counts() -> Dict[str, int]:
    df = load_police_stations()
    return {
        "total_officers": int(df["officers"].sum()),
        "total_vehicles": int(df["vehicles"].sum()),
        "stations": len(df),
        "available": int((df["availability"] == "Available").sum()),
    }


# ─── Hospitals ────────────────────────────────────────────────────────────────

def load_hospitals() -> pd.DataFrame:
    return pd.read_csv(_path("19_hospitals.csv"))


def get_hospital_records() -> List[Dict]:
    return load_hospitals().to_dict("records")


# ─── Food ─────────────────────────────────────────────────────────────────────

def load_food_centers() -> pd.DataFrame:
    return pd.read_csv(_path("21_food_distribution_centers.csv"))


def get_food_total() -> int:
    df = load_food_centers()
    return int(df["food_packets_stock"].sum())


# ─── Water ────────────────────────────────────────────────────────────────────

def load_water_points() -> pd.DataFrame:
    return pd.read_csv(_path("22_water_points.csv"))


def get_water_total() -> int:
    df = load_water_points()
    return int(df["current_stock_litres"].sum())


# ─── Medical Supplies ─────────────────────────────────────────────────────────

def load_medical_supplies() -> pd.DataFrame:
    return pd.read_csv(_path("23_medical_supply_centers.csv"))


def get_medical_supply_total() -> int:
    df = load_medical_supplies()
    return int(df["stock_quantity"].sum())


# ─── Fuel ─────────────────────────────────────────────────────────────────────

def load_fuel_stations() -> pd.DataFrame:
    return pd.read_csv(_path("26_fuel_stations.csv"))


def get_fuel_total() -> int:
    df = load_fuel_stations()
    return int(df["current_stock_litres"].sum())


# ─── Evacuation Vehicles ──────────────────────────────────────────────────────

def load_evacuation_vehicles() -> pd.DataFrame:
    return pd.read_csv(_path("24_evacuation_vehicles.csv"))


def get_evacuation_vehicle_counts() -> Dict[str, int]:
    df = load_evacuation_vehicles()
    return {
        "total": len(df),
        "available": int((df["status"] == "Available").sum()),
    }


# ─── Communication & Power ────────────────────────────────────────────────────

def load_comm_towers() -> pd.DataFrame:
    return pd.read_csv(_path("27_communication_towers.csv"))


def load_power_stations() -> pd.DataFrame:
    return pd.read_csv(_path("28_power_stations.csv"))


def get_comm_status() -> Dict[str, str]:
    df = load_comm_towers()
    result = {}
    for _, row in df.iterrows():
        zone_id = row["zone_id"]
        if zone_id not in result:
            result[zone_id] = row["status"]
    return result


def get_power_status() -> Dict[str, str]:
    df = load_power_stations()
    result = {}
    for _, row in df.iterrows():
        zone_id = row["zone_id"]
        if zone_id not in result:
            result[zone_id] = row["status"]
    return result


# ─── Patients ─────────────────────────────────────────────────────────────────

def load_patients() -> pd.DataFrame:
    return pd.read_csv(_path("12_chennai_10000_patients.csv"))


def get_patient_summary_by_zone() -> Dict[str, Dict[str, int]]:
    df = load_patients()
    result = {}
    for (zone_id, zone_name), grp in df.groupby(["zone_id", "zone_name"]):
        result[zone_id] = {
            "zone_name": zone_name,
            "critical": int((grp["severity"] == "Critical").sum()),
            "moderate": int((grp["severity"] == "Moderate").sum()),
            "minor": int((grp["severity"] == "Minor").sum()),
            "total": len(grp),
        }
    return result


# ─── Incidents ────────────────────────────────────────────────────────────────

def load_incidents() -> pd.DataFrame:
    return pd.read_csv(_path("13_chennai_3000_incidents.csv"))


def get_incident_summary_by_zone() -> Dict[str, int]:
    df = load_incidents()
    return df.groupby("zone_id").size().to_dict()


# ─── Rainfall ─────────────────────────────────────────────────────────────────

def load_rainfall() -> pd.DataFrame:
    return pd.read_csv(_path("01_chennai_rainfall_source.csv"), parse_dates=["Date"])


def get_recent_rainfall_avg(days: int = 30) -> float:
    df = load_rainfall()
    return float(df["Rainfall_mm_day"].tail(days).mean())
