#!/usr/bin/env python3
"""System Configuration Engine Simulation"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

def run():
    from system_configuration_engine import SystemConfigurationEngine, SystemType, STRATEGY_TEMPLATES
    from as_built_generator import AsBuiltGenerator, DrawingDatabase, ControlDiagram, DrawingElement, DrawingElementType

    print("=" * 60)
    print("System Configuration + As-Built Simulation")
    print("=" * 60)

    engine = SystemConfigurationEngine()
    descriptions = [
        "air handling unit with variable frequency drive and CO2 sensor",
        "chiller plant with two centrifugal chillers and cooling tower",
        "SCADA system with OPC-UA and historian",
    ]
    for desc in descriptions:
        st = engine.detect_system_type(desc)
        strategy = engine.recommend_strategy(st, {"energy_priority": True})
        config = engine.configure(st, strategy.strategy_id, {"system_name": st.value})
        mag = engine.magnify(config)
        print(f"\n  System: {st.value}")
        print(f"  Strategy: {strategy.name} ({strategy.energy_efficiency_rating})")
        print(f"  Pros: {', '.join(strategy.pros[:2])}")
        print(f"  Setpoints: {list(config.setpoints.items())[:2]}")
        print(f"  Standards: {strategy.applicable_standards[:2]}")

    # As-built with drawing database
    db = DrawingDatabase()
    ref_diagram = ControlDiagram(title="Reference AHU", system_name="AHU-REF")
    ref_diagram.elements.append(DrawingElement(
        element_type=DrawingElementType.SENSOR, tag="SAT",
        description="Supply Air Temperature Sensor",
        manufacturer="Dwyer", model="RSBT-A",
        cutsheet_reference="DWY-RSBT-A.pdf",
        specifications={"range": "-40 to 250F", "accuracy": "0.5F"},
    ))
    db.ingest_drawing(ref_diagram)
    print(f"\n[4] Drawing Database: {len(db)} elements from reference drawings")
    print(f"    Best SAT sensor: {db.get_best_element(DrawingElementType.SENSOR, 'SAT')}")
    cat = db.export_catalog()
    print(f"    Catalog entries: {len(cat)}")
    print("\n[SIMULATION COMPLETE] System Configuration\n")

if __name__ == "__main__":
    run()
