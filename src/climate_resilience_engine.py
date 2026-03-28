"""
Climate Resilience Engine

ASHRAE 169-2021 climate zone system + resilience design matrix +
location-based recommendations for building systems.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ClimateZone:
    """ASHRAE 169-2021 climate zone"""
    zone_id: str
    zone_number: int
    zone_letter: str
    description: str
    heating_degree_days: int
    cooling_degree_days: int
    dominant_load: str
    humidity_class: str
    representative_cities: List[str]


@dataclass
class ResilienceFactors:
    """Location-specific resilience factors"""
    location: str
    climate_zone: ClimateZone
    seismic_zone: str
    hurricane_risk: str
    flood_zone: str
    extreme_heat_risk: bool
    freeze_thaw_cycles: int
    wildfire_risk: str
    permafrost: bool
    design_temp_heating: float
    design_temp_cooling: float
    design_humidity: float
    wind_speed_design: int
    snowload_psf: float


@dataclass
class EnergyTarget:
    """Energy performance targets for climate zone and building type"""
    climate_zone: str
    building_type: str
    ashrae_901_eui: float
    energy_star_score_target: int
    recommended_ecms: List[str]
    heating_system_recommendation: str
    cooling_system_recommendation: str
    envelope_r_value_roof: float
    envelope_r_value_walls: float
    window_u_value: float
    lighting_lpdw: float


# ---------------------------------------------------------------------------
# Climate Zone Database
# ---------------------------------------------------------------------------

CLIMATE_ZONE_DATABASE = {
    "1A": ClimateZone(
        zone_id="1A",
        zone_number=1,
        zone_letter="A",
        description="Very Hot-Humid",
        heating_degree_days=500,
        cooling_degree_days=6000,
        dominant_load="cooling",
        humidity_class="moist",
        representative_cities=["Miami, FL", "Key West, FL", "Honolulu, HI"]
    ),
    "2A": ClimateZone(
        zone_id="2A",
        zone_number=2,
        zone_letter="A",
        description="Hot-Humid",
        heating_degree_days=1500,
        cooling_degree_days=4500,
        dominant_load="cooling",
        humidity_class="moist",
        representative_cities=["Houston, TX", "New Orleans, LA", "Orlando, FL"]
    ),
    "2B": ClimateZone(
        zone_id="2B",
        zone_number=2,
        zone_letter="B",
        description="Hot-Dry",
        heating_degree_days=1400,
        cooling_degree_days=4500,
        dominant_load="cooling",
        humidity_class="dry",
        representative_cities=["Phoenix, AZ", "Tucson, AZ", "El Paso, TX"]
    ),
    "3A": ClimateZone(
        zone_id="3A",
        zone_number=3,
        zone_letter="A",
        description="Warm-Humid",
        heating_degree_days=2500,
        cooling_degree_days=3500,
        dominant_load="balanced",
        humidity_class="moist",
        representative_cities=["Atlanta, GA", "Birmingham, AL", "Memphis, TN"]
    ),
    "3B": ClimateZone(
        zone_id="3B",
        zone_number=3,
        zone_letter="B",
        description="Warm-Dry",
        heating_degree_days=2000,
        cooling_degree_days=3500,
        dominant_load="cooling",
        humidity_class="dry",
        representative_cities=["Las Vegas, NV", "Riverside, CA", "Fresno, CA"]
    ),
    "3C": ClimateZone(
        zone_id="3C",
        zone_number=3,
        zone_letter="C",
        description="Warm-Marine",
        heating_degree_days=2500,
        cooling_degree_days=1500,
        dominant_load="heating",
        humidity_class="marine",
        representative_cities=["San Francisco, CA", "San Diego, CA", "Los Angeles, CA"]
    ),
    "4A": ClimateZone(
        zone_id="4A",
        zone_number=4,
        zone_letter="A",
        description="Mixed-Humid",
        heating_degree_days=4500,
        cooling_degree_days=2500,
        dominant_load="heating",
        humidity_class="moist",
        representative_cities=["Baltimore, MD", "New York, NY", "Louisville, KY"]
    ),
    "4B": ClimateZone(
        zone_id="4B",
        zone_number=4,
        zone_letter="B",
        description="Mixed-Dry",
        heating_degree_days=4000,
        cooling_degree_days=2500,
        dominant_load="heating",
        humidity_class="dry",
        representative_cities=["Albuquerque, NM", "Salt Lake City, UT", "Reno, NV"]
    ),
    "4C": ClimateZone(
        zone_id="4C",
        zone_number=4,
        zone_letter="C",
        description="Mixed-Marine",
        heating_degree_days=4500,
        cooling_degree_days=500,
        dominant_load="heating",
        humidity_class="marine",
        representative_cities=["Seattle, WA", "Portland, OR", "Salem, OR"]
    ),
    "5A": ClimateZone(
        zone_id="5A",
        zone_number=5,
        zone_letter="A",
        description="Cool-Humid",
        heating_degree_days=6000,
        cooling_degree_days=1500,
        dominant_load="heating",
        humidity_class="moist",
        representative_cities=["Chicago, IL", "Boston, MA", "Detroit, MI"]
    ),
    "5B": ClimateZone(
        zone_id="5B",
        zone_number=5,
        zone_letter="B",
        description="Cool-Dry",
        heating_degree_days=5500,
        cooling_degree_days=1500,
        dominant_load="heating",
        humidity_class="dry",
        representative_cities=["Denver, CO", "Boise, ID", "Colorado Springs, CO"]
    ),
    "6A": ClimateZone(
        zone_id="6A",
        zone_number=6,
        zone_letter="A",
        description="Cold-Humid",
        heating_degree_days=7500,
        cooling_degree_days=1000,
        dominant_load="heating",
        humidity_class="moist",
        representative_cities=["Minneapolis, MN", "Burlington, VT", "Rochester, NY"]
    ),
    "6B": ClimateZone(
        zone_id="6B",
        zone_number=6,
        zone_letter="B",
        description="Cold-Dry",
        heating_degree_days=7000,
        cooling_degree_days=1000,
        dominant_load="heating",
        humidity_class="dry",
        representative_cities=["Helena, MT", "Great Falls, MT", "Cheyenne, WY"]
    ),
    "7": ClimateZone(
        zone_id="7",
        zone_number=7,
        zone_letter="",
        description="Very Cold",
        heating_degree_days=9500,
        cooling_degree_days=500,
        dominant_load="heating",
        humidity_class="moist",
        representative_cities=["Duluth, MN", "Fargo, ND", "International Falls, MN"]
    ),
    "8": ClimateZone(
        zone_id="8",
        zone_number=8,
        zone_letter="",
        description="Subarctic",
        heating_degree_days=14000,
        cooling_degree_days=100,
        dominant_load="heating",
        humidity_class="dry",
        representative_cities=["Fairbanks, AK", "Barrow, AK", "Nome, AK"]
    ),
}


# ---------------------------------------------------------------------------
# Resilience Database
# ---------------------------------------------------------------------------

RESILIENCE_DATABASE = {
    "Miami, FL": {
        "climate_zone": "1A",
        "seismic_zone": "low",
        "hurricane_risk": "high",
        "flood_zone": "coastal",
        "extreme_heat_risk": True,
        "freeze_thaw_cycles": 0,
        "wildfire_risk": "none",
        "permafrost": False,
        "design_temp_heating": 47.0,
        "design_temp_cooling": 91.0,
        "design_humidity": 78.0,
        "wind_speed_design": 160,
        "snowload_psf": 0.0
    },
    "Houston, TX": {
        "climate_zone": "2A",
        "seismic_zone": "low",
        "hurricane_risk": "high",
        "flood_zone": "high",
        "extreme_heat_risk": True,
        "freeze_thaw_cycles": 5,
        "wildfire_risk": "low",
        "permafrost": False,
        "design_temp_heating": 29.0,
        "design_temp_cooling": 95.0,
        "design_humidity": 75.0,
        "wind_speed_design": 130,
        "snowload_psf": 0.0
    },
    "Phoenix, AZ": {
        "climate_zone": "2B",
        "seismic_zone": "low",
        "hurricane_risk": "none",
        "flood_zone": "minimal",
        "extreme_heat_risk": True,
        "freeze_thaw_cycles": 10,
        "wildfire_risk": "moderate",
        "permafrost": False,
        "design_temp_heating": 34.0,
        "design_temp_cooling": 108.0,
        "design_humidity": 25.0,
        "wind_speed_design": 90,
        "snowload_psf": 0.0
    },
    "Atlanta, GA": {
        "climate_zone": "3A",
        "seismic_zone": "low",
        "hurricane_risk": "low",
        "flood_zone": "moderate",
        "extreme_heat_risk": False,
        "freeze_thaw_cycles": 30,
        "wildfire_risk": "low",
        "permafrost": False,
        "design_temp_heating": 22.0,
        "design_temp_cooling": 92.0,
        "design_humidity": 74.0,
        "wind_speed_design": 90,
        "snowload_psf": 5.0
    },
    "Las Vegas, NV": {
        "climate_zone": "3B",
        "seismic_zone": "moderate",
        "hurricane_risk": "none",
        "flood_zone": "minimal",
        "extreme_heat_risk": True,
        "freeze_thaw_cycles": 15,
        "wildfire_risk": "moderate",
        "permafrost": False,
        "design_temp_heating": 28.0,
        "design_temp_cooling": 106.0,
        "design_humidity": 18.0,
        "wind_speed_design": 85,
        "snowload_psf": 5.0
    },
    "San Francisco, CA": {
        "climate_zone": "3C",
        "seismic_zone": "very_high",
        "hurricane_risk": "none",
        "flood_zone": "moderate",
        "extreme_heat_risk": False,
        "freeze_thaw_cycles": 0,
        "wildfire_risk": "high",
        "permafrost": False,
        "design_temp_heating": 42.0,
        "design_temp_cooling": 77.0,
        "design_humidity": 72.0,
        "wind_speed_design": 85,
        "snowload_psf": 0.0
    },
    "Baltimore, MD": {
        "climate_zone": "4A",
        "seismic_zone": "low",
        "hurricane_risk": "moderate",
        "flood_zone": "moderate",
        "extreme_heat_risk": False,
        "freeze_thaw_cycles": 50,
        "wildfire_risk": "none",
        "permafrost": False,
        "design_temp_heating": 13.0,
        "design_temp_cooling": 91.0,
        "design_humidity": 73.0,
        "wind_speed_design": 90,
        "snowload_psf": 25.0
    },
    "New York, NY": {
        "climate_zone": "4A",
        "seismic_zone": "low",
        "hurricane_risk": "moderate",
        "flood_zone": "coastal",
        "extreme_heat_risk": False,
        "freeze_thaw_cycles": 60,
        "wildfire_risk": "none",
        "permafrost": False,
        "design_temp_heating": 15.0,
        "design_temp_cooling": 90.0,
        "design_humidity": 72.0,
        "wind_speed_design": 110,
        "snowload_psf": 30.0
    },
    "Albuquerque, NM": {
        "climate_zone": "4B",
        "seismic_zone": "moderate",
        "hurricane_risk": "none",
        "flood_zone": "minimal",
        "extreme_heat_risk": False,
        "freeze_thaw_cycles": 80,
        "wildfire_risk": "high",
        "permafrost": False,
        "design_temp_heating": 14.0,
        "design_temp_cooling": 95.0,
        "design_humidity": 25.0,
        "wind_speed_design": 80,
        "snowload_psf": 20.0
    },
    "Seattle, WA": {
        "climate_zone": "4C",
        "seismic_zone": "high",
        "hurricane_risk": "none",
        "flood_zone": "moderate",
        "extreme_heat_risk": False,
        "freeze_thaw_cycles": 20,
        "wildfire_risk": "moderate",
        "permafrost": False,
        "design_temp_heating": 27.0,
        "design_temp_cooling": 84.0,
        "design_humidity": 65.0,
        "wind_speed_design": 85,
        "snowload_psf": 25.0
    },
    "Chicago, IL": {
        "climate_zone": "5A",
        "seismic_zone": "low",
        "hurricane_risk": "none",
        "flood_zone": "moderate",
        "extreme_heat_risk": False,
        "freeze_thaw_cycles": 100,
        "wildfire_risk": "none",
        "permafrost": False,
        "design_temp_heating": -4.0,
        "design_temp_cooling": 91.0,
        "design_humidity": 74.0,
        "wind_speed_design": 90,
        "snowload_psf": 25.0
    },
    "Boston, MA": {
        "climate_zone": "5A",
        "seismic_zone": "low",
        "hurricane_risk": "moderate",
        "flood_zone": "coastal",
        "extreme_heat_risk": False,
        "freeze_thaw_cycles": 90,
        "wildfire_risk": "none",
        "permafrost": False,
        "design_temp_heating": 6.0,
        "design_temp_cooling": 88.0,
        "design_humidity": 72.0,
        "wind_speed_design": 100,
        "snowload_psf": 40.0
    },
    "Denver, CO": {
        "climate_zone": "5B",
        "seismic_zone": "low",
        "hurricane_risk": "none",
        "flood_zone": "minimal",
        "extreme_heat_risk": False,
        "freeze_thaw_cycles": 120,
        "wildfire_risk": "high",
        "permafrost": False,
        "design_temp_heating": -2.0,
        "design_temp_cooling": 91.0,
        "design_humidity": 30.0,
        "wind_speed_design": 90,
        "snowload_psf": 30.0
    },
    "Minneapolis, MN": {
        "climate_zone": "6A",
        "seismic_zone": "low",
        "hurricane_risk": "none",
        "flood_zone": "moderate",
        "extreme_heat_risk": False,
        "freeze_thaw_cycles": 140,
        "wildfire_risk": "none",
        "permafrost": False,
        "design_temp_heating": -16.0,
        "design_temp_cooling": 89.0,
        "design_humidity": 75.0,
        "wind_speed_design": 90,
        "snowload_psf": 50.0
    },
    "Helena, MT": {
        "climate_zone": "6B",
        "seismic_zone": "moderate",
        "hurricane_risk": "none",
        "flood_zone": "minimal",
        "extreme_heat_risk": False,
        "freeze_thaw_cycles": 150,
        "wildfire_risk": "high",
        "permafrost": False,
        "design_temp_heating": -15.0,
        "design_temp_cooling": 88.0,
        "design_humidity": 35.0,
        "wind_speed_design": 80,
        "snowload_psf": 40.0
    },
    "Duluth, MN": {
        "climate_zone": "7",
        "seismic_zone": "low",
        "hurricane_risk": "none",
        "flood_zone": "minimal",
        "extreme_heat_risk": False,
        "freeze_thaw_cycles": 160,
        "wildfire_risk": "none",
        "permafrost": False,
        "design_temp_heating": -20.0,
        "design_temp_cooling": 83.0,
        "design_humidity": 73.0,
        "wind_speed_design": 90,
        "snowload_psf": 70.0
    },
    "Fairbanks, AK": {
        "climate_zone": "8",
        "seismic_zone": "high",
        "hurricane_risk": "none",
        "flood_zone": "minimal",
        "extreme_heat_risk": False,
        "freeze_thaw_cycles": 20,
        "wildfire_risk": "moderate",
        "permafrost": True,
        "design_temp_heating": -47.0,
        "design_temp_cooling": 78.0,
        "design_humidity": 65.0,
        "wind_speed_design": 70,
        "snowload_psf": 60.0
    },
    "Los Angeles, CA": {
        "climate_zone": "3C",
        "seismic_zone": "very_high",
        "hurricane_risk": "none",
        "flood_zone": "moderate",
        "extreme_heat_risk": False,
        "freeze_thaw_cycles": 0,
        "wildfire_risk": "high",
        "permafrost": False,
        "design_temp_heating": 41.0,
        "design_temp_cooling": 83.0,
        "design_humidity": 68.0,
        "wind_speed_design": 85,
        "snowload_psf": 0.0
    },
    "Portland, OR": {
        "climate_zone": "4C",
        "seismic_zone": "high",
        "hurricane_risk": "none",
        "flood_zone": "moderate",
        "extreme_heat_risk": False,
        "freeze_thaw_cycles": 25,
        "wildfire_risk": "moderate",
        "permafrost": False,
        "design_temp_heating": 23.0,
        "design_temp_cooling": 88.0,
        "design_humidity": 60.0,
        "wind_speed_design": 80,
        "snowload_psf": 25.0
    },
    "Detroit, MI": {
        "climate_zone": "5A",
        "seismic_zone": "low",
        "hurricane_risk": "none",
        "flood_zone": "moderate",
        "extreme_heat_risk": False,
        "freeze_thaw_cycles": 110,
        "wildfire_risk": "none",
        "permafrost": False,
        "design_temp_heating": 1.0,
        "design_temp_cooling": 89.0,
        "design_humidity": 73.0,
        "wind_speed_design": 90,
        "snowload_psf": 30.0
    },
    "Salt Lake City, UT": {
        "climate_zone": "4B",
        "seismic_zone": "moderate",
        "hurricane_risk": "none",
        "flood_zone": "minimal",
        "extreme_heat_risk": False,
        "freeze_thaw_cycles": 100,
        "wildfire_risk": "moderate",
        "permafrost": False,
        "design_temp_heating": 8.0,
        "design_temp_cooling": 95.0,
        "design_humidity": 28.0,
        "wind_speed_design": 85,
        "snowload_psf": 25.0
    },
}


# ---------------------------------------------------------------------------
# Climate Resilience Engine
# ---------------------------------------------------------------------------

class ClimateResilienceEngine:
    """Engine for climate zone lookup and resilience recommendations"""

    def __init__(self):
        """Initialize the climate resilience engine"""
        self.climate_zones = CLIMATE_ZONE_DATABASE
        self.resilience_data = RESILIENCE_DATABASE

    def lookup_climate_zone(self, location: str) -> Optional[ClimateZone]:
        """Lookup climate zone by location"""
        location_lower = location.lower().strip()

        for zone_id, zone in self.climate_zones.items():
            for city in zone.representative_cities:
                if location_lower in city.lower():
                    return zone

        for city_key in self.resilience_data.keys():
            if location_lower in city_key.lower():
                zone_id = self.resilience_data[city_key]["climate_zone"]
                return self.climate_zones.get(zone_id)

        logger.warning(f"Location '{location}' not found, returning default zone 4A")
        return self.climate_zones.get("4A")

    def get_resilience_factors(self, location: str) -> ResilienceFactors:
        """Get resilience factors for location"""
        location_key = None
        location_lower = location.lower().strip()

        for key in self.resilience_data.keys():
            if location_lower in key.lower():
                location_key = key
                break

        if not location_key:
            logger.warning(f"Location '{location}' not found in resilience database")
            climate_zone = self.lookup_climate_zone(location)
            if climate_zone:
                return ResilienceFactors(
                    location=location,
                    climate_zone=climate_zone,
                    seismic_zone="low",
                    hurricane_risk="none",
                    flood_zone="minimal",
                    extreme_heat_risk=False,
                    freeze_thaw_cycles=50,
                    wildfire_risk="none",
                    permafrost=False,
                    design_temp_heating=20.0,
                    design_temp_cooling=90.0,
                    design_humidity=60.0,
                    wind_speed_design=90,
                    snowload_psf=20.0
                )

        data = self.resilience_data[location_key]
        climate_zone = self.climate_zones[data["climate_zone"]]

        return ResilienceFactors(
            location=location_key,
            climate_zone=climate_zone,
            seismic_zone=data["seismic_zone"],
            hurricane_risk=data["hurricane_risk"],
            flood_zone=data["flood_zone"],
            extreme_heat_risk=data["extreme_heat_risk"],
            freeze_thaw_cycles=data["freeze_thaw_cycles"],
            wildfire_risk=data["wildfire_risk"],
            permafrost=data["permafrost"],
            design_temp_heating=data["design_temp_heating"],
            design_temp_cooling=data["design_temp_cooling"],
            design_humidity=data["design_humidity"],
            wind_speed_design=data["wind_speed_design"],
            snowload_psf=data["snowload_psf"]
        )

    def get_design_recommendations(self, location: str, equipment_type: str) -> List[str]:
        """Get design recommendations for location and equipment"""
        factors = self.get_resilience_factors(location)
        recommendations = []
        zone = factors.climate_zone
        equipment_lower = equipment_type.lower()

        if zone.zone_number in [1, 2]:
            recommendations.append("Specify corrosion-resistant materials for coastal/humid environments")
            recommendations.append("Design for high cooling loads with efficient chillers (>0.6 kW/ton)")
            if factors.hurricane_risk in ["moderate", "high"]:
                recommendations.append("Hurricane strapping and wind-rated equipment per ASCE 7")
                recommendations.append("Elevate equipment above base flood elevation plus 2 feet")
            if factors.extreme_heat_risk:
                recommendations.append("Oversized cooling capacity by 15% for extreme heat events")

        if zone.zone_number in [3, 4]:
            recommendations.append("Implement economizer controls for free cooling (ASHRAE 90.1)")
            recommendations.append("Energy recovery ventilator (ERV) for balanced loads")
            recommendations.append("Variable speed drives on all fans and pumps >5 HP")
            if factors.freeze_thaw_cycles > 40:
                recommendations.append("Freeze protection on outdoor equipment and piping")

        if zone.zone_number in [5, 6]:
            recommendations.append("Condensing boilers for high heating efficiency (>90% AFUE)")
            recommendations.append("Heat trace on outdoor piping and drain lines")
            recommendations.append("Glycol loops for freeze protection in critical systems")
            recommendations.append("Snow melt controls for outdoor equipment pads")
            if factors.freeze_thaw_cycles > 100:
                recommendations.append("Insulated equipment enclosures with trace heating")

        if zone.zone_number in [7, 8]:
            recommendations.append("Permafrost foundation design with thermosyphons")
            recommendations.append("Extreme cold startup procedures (-40°F rated equipment)")
            recommendations.append("Triple-pane windows (U-factor < 0.20)")
            recommendations.append("Heat recovery mandatory on all exhaust systems")
            recommendations.append("Vestibule entries with air curtains at all doors")

        if factors.seismic_zone in ["high", "very_high"]:
            recommendations.append("Seismic bracing per ASCE 7 and local amendments")
            recommendations.append("Flexible connections on all piping and ductwork")
            recommendations.append("Seismic shutoff valves on gas lines")

        if factors.wildfire_risk in ["moderate", "high"]:
            recommendations.append("Fire-rated exterior equipment enclosures")
            recommendations.append("Automatic dampers to prevent smoke infiltration")
            recommendations.append("Backup power for critical life safety systems")

        if "chiller" in equipment_lower:
            recommendations.append(f"Design chiller for {factors.design_temp_cooling}°F entering condenser water")
            if zone.zone_number <= 3:
                recommendations.append("Water-cooled chiller recommended for high cooling hours")

        if "boiler" in equipment_lower:
            recommendations.append(f"Design heating for {factors.design_temp_heating}°F outdoor air")
            if zone.zone_number >= 5:
                recommendations.append("Condensing boiler technology for high efficiency")

        if "roof" in equipment_lower or "rtu" in equipment_lower:
            recommendations.append(f"Roof equipment rated for {factors.wind_speed_design} mph wind")
            recommendations.append(f"Structural support designed for {factors.snowload_psf} PSF snow load")

        return recommendations

    def get_energy_targets(self, location: str, building_type: str) -> EnergyTarget:
        """Get energy performance targets"""
        climate_zone = self.lookup_climate_zone(location)
        zone_id = climate_zone.zone_id if climate_zone else "4A"

        eui_targets = {
            "office": {
                "1A": 65.0, "2A": 60.0, "2B": 58.0, "3A": 55.0, "3B": 53.0, "3C": 48.0,
                "4A": 52.0, "4B": 50.0, "4C": 47.0, "5A": 58.0, "5B": 55.0,
                "6A": 65.0, "6B": 62.0, "7": 72.0, "8": 85.0
            },
            "school": {
                "1A": 70.0, "2A": 65.0, "2B": 63.0, "3A": 58.0, "3B": 56.0, "3C": 52.0,
                "4A": 60.0, "4B": 58.0, "4C": 54.0, "5A": 67.0, "5B": 64.0,
                "6A": 75.0, "6B": 72.0, "7": 82.0, "8": 95.0
            },
            "hospital": {
                "1A": 230.0, "2A": 220.0, "2B": 215.0, "3A": 210.0, "3B": 205.0, "3C": 200.0,
                "4A": 215.0, "4B": 210.0, "4C": 205.0, "5A": 225.0, "5B": 220.0,
                "6A": 240.0, "6B": 235.0, "7": 250.0, "8": 270.0
            },
            "retail": {
                "1A": 95.0, "2A": 90.0, "2B": 88.0, "3A": 82.0, "3B": 80.0, "3C": 75.0,
                "4A": 85.0, "4B": 83.0, "4C": 78.0, "5A": 92.0, "5B": 88.0,
                "6A": 100.0, "6B": 97.0, "7": 110.0, "8": 125.0
            }
        }

        building_lower = building_type.lower()
        if "office" in building_lower:
            eui = eui_targets["office"].get(zone_id, 55.0)
            btype = "office"
        elif "school" in building_lower:
            eui = eui_targets["school"].get(zone_id, 60.0)
            btype = "school"
        elif "hospital" in building_lower or "healthcare" in building_lower:
            eui = eui_targets["hospital"].get(zone_id, 215.0)
            btype = "hospital"
        elif "retail" in building_lower:
            eui = eui_targets["retail"].get(zone_id, 85.0)
            btype = "retail"
        else:
            eui = 65.0
            btype = "general"

        ecms = ["LED lighting upgrade", "economizer controls", "demand controlled ventilation"]
        if climate_zone and climate_zone.zone_number >= 5:
            heating_rec = "Condensing boiler with outdoor air reset"
            ecms.append("heat recovery from exhaust")
        else:
            heating_rec = "High efficiency boiler or heat pump"

        if climate_zone and climate_zone.zone_number <= 3:
            cooling_rec = "High efficiency chiller (>0.6 kW/ton) or VRF"
            ecms.append("chilled water temperature reset")
        else:
            cooling_rec = "High efficiency RTU with economizer"

        envelope_r_roof = 30.0 if climate_zone and climate_zone.zone_number <= 3 else 40.0
        envelope_r_walls = 15.0 if climate_zone and climate_zone.zone_number <= 3 else 20.0
        window_u = 0.45 if climate_zone and climate_zone.zone_number <= 3 else 0.35

        return EnergyTarget(
            climate_zone=zone_id,
            building_type=btype,
            ashrae_901_eui=eui,
            energy_star_score_target=75,
            recommended_ecms=ecms,
            heating_system_recommendation=heating_rec,
            cooling_system_recommendation=cooling_rec,
            envelope_r_value_roof=envelope_r_roof,
            envelope_r_value_walls=envelope_r_walls,
            window_u_value=window_u,
            lighting_lpdw=0.9
        )

    def get_equipment_sizing_factors(self, location: str) -> Dict[str, float]:
        """Get equipment sizing factors for location"""
        factors = self.get_resilience_factors(location)
        sizing = {
            "heating_oversizing_factor": 1.0,
            "cooling_oversizing_factor": 1.0,
            "backup_power_factor": 1.0
        }

        if factors.design_temp_heating < 0:
            sizing["heating_oversizing_factor"] = 1.15
        elif factors.design_temp_heating < 15:
            sizing["heating_oversizing_factor"] = 1.10

        if factors.extreme_heat_risk:
            sizing["cooling_oversizing_factor"] = 1.15
        elif factors.design_temp_cooling > 95:
            sizing["cooling_oversizing_factor"] = 1.10

        if factors.hurricane_risk in ["moderate", "high"]:
            sizing["backup_power_factor"] = 1.5
        elif factors.wildfire_risk == "high":
            sizing["backup_power_factor"] = 1.3

        return sizing

    def assess_resilience(self, location: str, systems: List[str]) -> Dict[str, any]:
        """Assess resilience and provide mitigation recommendations"""
        factors = self.get_resilience_factors(location)
        assessment = {
            "location": location,
            "climate_zone": factors.climate_zone.zone_id,
            "risk_summary": {},
            "system_risks": {},
            "mitigation_recommendations": []
        }

        risks = []
        if factors.hurricane_risk in ["moderate", "high"]:
            risks.append(f"Hurricane risk: {factors.hurricane_risk}")
        if factors.seismic_zone in ["high", "very_high"]:
            risks.append(f"Seismic risk: {factors.seismic_zone}")
        if factors.flood_zone in ["high", "coastal"]:
            risks.append(f"Flood risk: {factors.flood_zone}")
        if factors.wildfire_risk in ["moderate", "high"]:
            risks.append(f"Wildfire risk: {factors.wildfire_risk}")
        if factors.extreme_heat_risk:
            risks.append("Extreme heat events likely")
        if factors.freeze_thaw_cycles > 100:
            risks.append(f"High freeze/thaw cycles: {factors.freeze_thaw_cycles}")
        if factors.permafrost:
            risks.append("Permafrost foundation considerations")

        assessment["risk_summary"] = risks

        for system in systems:
            system_lower = system.lower()
            system_risks = []

            if "hvac" in system_lower or "cooling" in system_lower:
                if factors.extreme_heat_risk:
                    system_risks.append("Cooling capacity inadequate during heat waves")
                if factors.hurricane_risk == "high":
                    system_risks.append("Wind damage to outdoor equipment")

            if "electrical" in system_lower or "power" in system_lower:
                if factors.hurricane_risk in ["moderate", "high"]:
                    system_risks.append("Grid outage from storms")
                if factors.wildfire_risk in ["moderate", "high"]:
                    system_risks.append("Power interruption from wildfires")

            if system_lower in ["plumbing", "water"]:
                if factors.freeze_thaw_cycles > 50:
                    system_risks.append("Pipe freezing risk")

            assessment["system_risks"][system] = system_risks

        if factors.hurricane_risk in ["moderate", "high"]:
            assessment["mitigation_recommendations"].append("Install backup generator with 7-day fuel supply")
            assessment["mitigation_recommendations"].append("Elevate critical equipment above flood plain")

        if factors.seismic_zone in ["high", "very_high"]:
            assessment["mitigation_recommendations"].append("Retrofit equipment with seismic restraints")
            assessment["mitigation_recommendations"].append("Install flexible utility connections")

        if factors.wildfire_risk in ["moderate", "high"]:
            assessment["mitigation_recommendations"].append("Create defensible space around equipment")
            assessment["mitigation_recommendations"].append("Install ember-resistant louvers")

        if factors.freeze_thaw_cycles > 80:
            assessment["mitigation_recommendations"].append("Implement comprehensive freeze protection program")

        return assessment
