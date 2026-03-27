#!/usr/bin/env python3
"""Climate and Resilience Design Simulation"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

def run():
    from climate_resilience_engine import ClimateResilienceEngine, CLIMATE_ZONE_DATABASE

    print("=" * 60)
    print("Climate Resilience Design Simulation")
    print("=" * 60)

    engine = ClimateResilienceEngine()
    cities = [("Miami, FL","chiller"), ("Chicago, IL","boiler"), ("Seattle, WA","AHU"), ("Phoenix, AZ","chiller"), ("Fairbanks, AK","boiler")]
    print(f"\n{'City':<20} {'Zone':<8} {'Dominant Load':<15} {'Top Recommendation'}")
    print("-" * 90)
    for city, equip in cities:
        zone = engine.lookup_climate_zone(city)
        recs = engine.get_design_recommendations(city, equip)
        zone_id = zone.zone_id if zone else "N/A"
        dom = zone.dominant_load if zone else "N/A"
        rec = recs[0][:50] if recs else "N/A"
        print(f"  {city:<20} {zone_id:<8} {dom:<15} {rec}")

    resilience = engine.get_resilience_factors("Miami, FL")
    print(f"\nMiami Resilience: hurricane={resilience.hurricane_risk}, flood={resilience.flood_zone}")
    print(f"  Design temp cooling: {resilience.design_temp_cooling}F")

    targets = engine.get_energy_targets("Chicago, IL", "office")
    print(f"\nChicago Office Energy Target: {targets.ashrae_901_eui} kBtu/sqft/yr")
    print(f"  Heating system rec: {targets.heating_system_recommendation}")
    print("\n[SIMULATION COMPLETE] Climate/Resilience\n")

if __name__ == "__main__":
    run()
