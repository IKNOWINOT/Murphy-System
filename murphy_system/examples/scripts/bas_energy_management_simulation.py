#!/usr/bin/env python3
"""
BAS/Energy Management System Simulation
========================================
Demonstrates: equipment ingestion -> virtual controller -> wiring verification
-> energy audit -> ECM recommendations -> as-built generation.
Industry: Building Automation / Energy Management
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

def run():
    from bas_equipment_ingestion import EquipmentDataIngestion, EquipmentCategory, EquipmentProtocol
    from virtual_controller import VirtualController, WiringVerificationEngine
    from energy_efficiency_framework import EnergyEfficiencyFramework, MSSEnergyRubric
    from climate_resilience_engine import ClimateResilienceEngine
    from as_built_generator import AsBuiltGenerator, DrawingDatabase
    from pro_con_decision_engine import ProConDecisionEngine

    print("=" * 60)
    print("BAS/Energy Management System Simulation")
    print("=" * 60)

    # 1. Ingest AHU equipment data
    ingestor = EquipmentDataIngestion()
    csv_data = """point_name,point_type,description,units
SAT,AI,Supply Air Temp,degF
RAT,AI,Return Air Temp,degF
CC-POS,AO,Cooling Coil Valve,pct
SF-SPD,AO,Supply Fan Speed,pct
OA-DMP,AO,OA Damper,pct
SF-RUN,DO,Supply Fan Enable,binary
FILTER-DP,AI,Filter Differential Pressure,inwg"""
    spec_01 = ingestor.ingest_csv(csv_data, "AHU-01", "BACnet")
    spec_02 = ingestor.ingest_csv(csv_data, "AHU-02", "BACnet")
    result = [spec_01, spec_02]
    print(f"\n[1] Ingested {len(result)} equipment specs")
    for spec in result:
        print(f"    - {spec.equipment_name} ({spec.protocol.value})")

    # 2. Create virtual controller and populate
    vc = VirtualController(spec=spec_01)
    print(f"\n[2] Virtual Controller for '{spec_01.equipment_name}' — {len(vc.points)} points loaded")

    # 3. Wiring verification
    verifier = WiringVerificationEngine()
    report = verifier.verify(spec_01)
    print(f"\n[3] Wiring Verification: {'PASSED' if report.passed else 'WARNINGS PRESENT'}")
    print(f"    Points: {report.point_count_summary} | Errors: {report.error_count} | Warnings: {report.warning_count}")

    # 4. Climate zone lookup
    climate = ClimateResilienceEngine()
    zone = climate.lookup_climate_zone("Chicago, IL")
    recs = climate.get_design_recommendations("Chicago, IL", "AHU")
    print(f"\n[4] Climate Zone for Chicago: {zone.zone_id if zone else 'N/A'}")
    print(f"    Top design recommendation: {recs[0] if recs else 'N/A'}")

    # 5. Energy audit
    eef = EnergyEfficiencyFramework()
    utility_data = {
        "site_name": "Office Building - Chicago",
        "electricity_kwh": 1_200_000,
        "natural_gas_therms": 8_000,
        "facility_sqft": 50_000,
        "electricity_cost": 144_000,
        "natural_gas_cost": 9_600,
        "demand_charges": 18_000,
        "peak_demand_kw": 280,
    }
    analysis = eef.analyze_utility_data(utility_data)
    print(f"\n[5] Energy Audit: EUI = {analysis.eui_kbtu_sqft_yr:.1f} kBtu/sqft/yr")
    ecms = eef.recommend_ecms(analysis, "office", "5A")
    print(f"    Top 3 ECM recommendations:")
    for ecm in ecms[:3]:
        print(f"      - {ecm.name} (saves {ecm.typical_savings_pct}%, payback {ecm.typical_payback_years} yrs)")

    # 6. MSS rubric
    rubric = MSSEnergyRubric()
    simple = rubric.simplify(utility_data)
    print(f"\n[6] Simplify (quick wins):")
    for win in simple["top_3_quick_wins"]:
        print(f"    - {win['name']}: {win['savings_pct']}% savings")

    # 7. As-built generation
    gen = AsBuiltGenerator()
    diagram = gen.from_equipment_spec(spec_01, "AHU-01")
    schematic = gen.generate_schematic_description(diagram)
    print(f"\n[7] As-Built: {len(diagram.point_schedule)} points, {len(diagram.elements)} elements")
    print(f"    {diagram.summary()}")

    # 8. Pro/con decision: strategy selection
    engine = ProConDecisionEngine()
    decision = engine.evaluate_strategies([
        {"name": "CAV Standard", "description": "Constant air volume",
         "scores": {"performance":7,"energy_efficiency":4,"complexity":2,"reliability":9,"scalability":4,"cost":8,"safety_interlocks":1,"code_compliance":1}},
        {"name": "VAV High-Performance", "description": "Variable air volume with Guideline 36",
         "scores": {"performance":9,"energy_efficiency":9,"complexity":7,"reliability":8,"scalability":9,"cost":5,"safety_interlocks":1,"code_compliance":1}},
    ], system_type="AHU")
    print(f"\n[8] Strategy Decision: Winner = '{decision.winner.name if decision.winner else 'None'}'")
    print(f"    Reason: {decision.reasoning[:100]}...")
    print("\n[SIMULATION COMPLETE] BAS/Energy Management\n")

if __name__ == "__main__":
    run()
