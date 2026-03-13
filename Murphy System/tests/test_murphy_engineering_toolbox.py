"""
Tests for Murphy Engineering Toolbox (Subsystem 7).
Murphy System - Copyright 2024-2026 Corey Post, Inoni LLC - License: BSL 1.1
"""

import math
import pytest

from src.murphy_engineering_toolbox import (
    CPMActivity,
    CostEstimation,
    ElectricalCalcs,
    HVACCalcs,
    PlumbingCalcs,
    ProjectManagement,
    ReferenceData,
    StructuralCalcs,
    UnitConverter,
)


# ---------------------------------------------------------------------------
# Unit Converter
# ---------------------------------------------------------------------------

class TestUnitConverter:

    def test_length_m_to_ft(self):
        uc = UnitConverter()
        result = uc.convert(1.0, "m", "ft")
        assert abs(result - 3.28084) < 0.001

    def test_length_ft_to_m(self):
        uc = UnitConverter()
        result = uc.convert(1.0, "ft", "m")
        assert abs(result - 0.3048) < 1e-6

    def test_length_in_to_mm(self):
        uc = UnitConverter()
        result = uc.convert(1.0, "in", "mm")
        assert abs(result - 25.4) < 0.001

    def test_pressure_psi_to_kpa(self):
        uc = UnitConverter()
        result = uc.convert(1.0, "psi", "kPa")
        assert abs(result - 6.89476) < 0.001

    def test_temperature_c_to_f(self):
        uc = UnitConverter()
        result = uc.convert(0.0, "C", "F")
        assert abs(result - 32.0) < 0.001

    def test_temperature_f_to_c(self):
        uc = UnitConverter()
        result = uc.convert(212.0, "F", "C")
        assert abs(result - 100.0) < 0.001

    def test_temperature_c_to_k(self):
        uc = UnitConverter()
        result = uc.convert(0.0, "C", "K")
        assert abs(result - 273.15) < 0.001

    def test_energy_kwh_to_j(self):
        uc = UnitConverter()
        result = uc.convert(1.0, "kWh", "J")
        assert abs(result - 3.6e6) < 1.0

    def test_power_hp_to_kw(self):
        uc = UnitConverter()
        result = uc.convert(1.0, "hp", "kW")
        assert abs(result - 0.74570) < 0.001

    def test_mass_lb_to_kg(self):
        uc = UnitConverter()
        result = uc.convert(1.0, "lb", "kg")
        assert abs(result - 0.45359) < 0.001

    def test_incompatible_units_raises(self):
        uc = UnitConverter()
        with pytest.raises(ValueError):
            uc.convert(1.0, "m", "kg")

    def test_unknown_unit_raises(self):
        uc = UnitConverter()
        with pytest.raises(ValueError):
            uc.convert(1.0, "parsec", "m")

    def test_available_units(self):
        uc = UnitConverter()
        units = uc.available_units("length")
        assert "m" in units
        assert "ft" in units

    def test_round_trip(self):
        uc = UnitConverter()
        original = 42.0
        converted = uc.convert(original, "m", "ft")
        back = uc.convert(converted, "ft", "m")
        assert abs(back - original) < 1e-9


# ---------------------------------------------------------------------------
# Structural Calculations
# ---------------------------------------------------------------------------

class TestStructuralCalcs:

    def test_simple_beam_center_load(self):
        sc = StructuralCalcs()
        # Steel W8x31: I ≈ 110 in4 = 4.577e-5 m4, E = 200e9 Pa
        result = sc.simple_beam_deflection(
            load_N=10000,
            span_m=5.0,
            E_Pa=200e9,
            I_m4=4.577e-5,
            load_type="center",
        )
        assert result.max_deflection_m > 0
        assert result.max_moment_Nm > 0
        assert result.max_shear_N > 0

    def test_simple_beam_uniform_load(self):
        sc = StructuralCalcs()
        result = sc.simple_beam_deflection(
            load_N=10000,
            span_m=5.0,
            E_Pa=200e9,
            I_m4=4.577e-5,
            load_type="uniform",
        )
        assert result.max_deflection_m > 0

    def test_cantilever_deflection(self):
        sc = StructuralCalcs()
        result = sc.cantilever_deflection(
            load_N=5000,
            span_m=2.0,
            E_Pa=200e9,
            I_m4=1e-5,
        )
        assert result.max_deflection_m > 0
        assert result.max_moment_Nm == 5000 * 2.0

    def test_moment_of_inertia_rectangle(self):
        sc = StructuralCalcs()
        # 100mm x 200mm: I = (0.1 * 0.2^3) / 12
        I = sc.rectangular_moment_of_inertia(0.1, 0.2)
        expected = (0.1 * 0.2 ** 3) / 12
        assert abs(I - expected) < 1e-12

    def test_section_modulus(self):
        sc = StructuralCalcs()
        S = sc.section_modulus(1e-4, 0.1)
        assert abs(S - 1e-3) < 1e-12

    def test_section_modulus_zero_c(self):
        sc = StructuralCalcs()
        S = sc.section_modulus(1e-4, 0.0)
        assert S == 0.0

    def test_bending_stress(self):
        sc = StructuralCalcs()
        sigma = sc.bending_stress(moment_Nm=1000, I_m4=1e-4, c_m=0.05)
        assert abs(sigma - 500000) < 1.0

    def test_factor_of_safety(self):
        sc = StructuralCalcs()
        fos = sc.factor_of_safety(250e6, 125e6)
        assert abs(fos - 2.0) < 1e-9

    def test_factor_of_safety_zero_actual(self):
        sc = StructuralCalcs()
        fos = sc.factor_of_safety(250e6, 0.0)
        assert fos == float("inf")


# ---------------------------------------------------------------------------
# HVAC Calculations
# ---------------------------------------------------------------------------

class TestHVACCalcs:

    def test_simple_heat_load(self):
        hv = HVACCalcs()
        result = hv.simple_heat_load(area_m2=100, delta_T_K=20, occupants=5)
        assert result.total_load_W > 0
        assert result.total_load_BTU_hr > 0
        assert result.recommended_tonnage > 0

    def test_cfm_from_load(self):
        hv = HVACCalcs()
        cfm = hv.cfm_from_load(5000)  # 5kW sensible load
        assert cfm > 0

    def test_cfm_zero_delta_t(self):
        hv = HVACCalcs()
        cfm = hv.cfm_from_load(5000, delta_T_K=0.0)
        assert cfm == 0.0

    def test_dew_point(self):
        hv = HVACCalcs()
        dp = hv.dew_point(20.0, 50.0)  # 20°C, 50% RH → DP ≈ 9°C
        assert 8 < dp < 11

    def test_enthalpy(self):
        hv = HVACCalcs()
        h = hv.enthalpy(20.0, 0.007)  # 20°C dry bulb, 7g/kg humidity ratio
        assert h > 0  # expect around 37-38 kJ/kg


# ---------------------------------------------------------------------------
# Electrical Calculations
# ---------------------------------------------------------------------------

class TestElectricalCalcs:

    def test_ohms_law_voltage(self):
        ec = ElectricalCalcs()
        result = ec.ohms_law(current_A=2.0, resistance_ohm=10.0)
        assert abs(result["voltage_V"] - 20.0) < 1e-9

    def test_ohms_law_current(self):
        ec = ElectricalCalcs()
        result = ec.ohms_law(voltage_V=120.0, resistance_ohm=60.0)
        assert abs(result["current_A"] - 2.0) < 1e-9

    def test_ohms_law_resistance(self):
        ec = ElectricalCalcs()
        result = ec.ohms_law(voltage_V=12.0, current_A=4.0)
        assert abs(result["resistance_ohm"] - 3.0) < 1e-9

    def test_ohms_law_missing_two_raises(self):
        ec = ElectricalCalcs()
        with pytest.raises(ValueError):
            ec.ohms_law(voltage_V=12.0)

    def test_power_unity_pf(self):
        ec = ElectricalCalcs()
        p = ec.power(120.0, 10.0, 1.0)
        assert abs(p["real_W"] - 1200.0) < 1e-6
        assert p["reactive_VAR"] == 0.0

    def test_power_lagging(self):
        ec = ElectricalCalcs()
        p = ec.power(120.0, 10.0, 0.8)
        assert p["real_W"] < p["apparent_VA"]
        assert p["reactive_VAR"] > 0

    def test_voltage_drop(self):
        ec = ElectricalCalcs()
        vd = ec.voltage_drop(current_A=30, resistance_per_m_ohm=0.005, length_m=50, phases=1)
        # 30 * 0.005 * 50 * 2 = 15V
        assert abs(vd - 15.0) < 1e-9

    def test_motor_fla(self):
        ec = ElectricalCalcs()
        fla = ec.motor_fla(hp=10, voltage_V=480)
        assert fla > 0


# ---------------------------------------------------------------------------
# Plumbing Calculations
# ---------------------------------------------------------------------------

class TestPlumbingCalcs:

    def test_fixture_units(self):
        pc = PlumbingCalcs()
        total = pc.fixture_units({"toilet": 2, "lavatory": 2, "kitchen_sink": 1})
        # 2*4 + 2*1 + 1*2 = 12
        assert total == 12

    def test_demand_gpm_small(self):
        pc = PlumbingCalcs()
        gpm = pc.demand_gpm(10)
        assert gpm > 0

    def test_demand_gpm_large(self):
        pc = PlumbingCalcs()
        gpm = pc.demand_gpm(200)
        assert gpm > pc.demand_gpm(10)

    def test_demand_gpm_zero(self):
        pc = PlumbingCalcs()
        assert pc.demand_gpm(0) == 0.0

    def test_water_heater_sizing(self):
        pc = PlumbingCalcs()
        size = pc.water_heater_sizing_gal(4)
        assert size > 0


# ---------------------------------------------------------------------------
# Project Management
# ---------------------------------------------------------------------------

class TestProjectManagement:

    def test_critical_path_single_chain(self):
        pm = ProjectManagement()
        acts = [
            CPMActivity("A", "Design", 5.0, []),
            CPMActivity("B", "Procurement", 10.0, ["A"]),
            CPMActivity("C", "Construction", 20.0, ["B"]),
        ]
        critical, duration = pm.critical_path(acts)
        assert duration == 35.0
        assert set(critical) == {"A", "B", "C"}

    def test_critical_path_parallel(self):
        pm = ProjectManagement()
        acts = [
            CPMActivity("A", "Design", 10.0, []),
            CPMActivity("B", "Short Task", 3.0, ["A"]),
            CPMActivity("C", "Long Task", 15.0, ["A"]),
            CPMActivity("D", "Finish", 2.0, ["B", "C"]),
        ]
        critical, duration = pm.critical_path(acts)
        assert duration == 27.0
        # A and C should be critical
        assert "A" in critical
        assert "C" in critical

    def test_empty_activities(self):
        pm = ProjectManagement()
        _, duration = pm.critical_path([])
        assert duration == 0.0

    def test_earned_value(self):
        pm = ProjectManagement()
        ev = pm.earned_value(
            budget_at_completion=100000,
            planned_value=60000,
            earned_value_pct=55,
            actual_cost=62000,
        )
        assert ev["CPI"] is not None
        assert ev["SPI"] is not None
        assert ev["EAC"] is not None
        assert ev["CPI"] < 1.0  # Over budget
        assert ev["SPI"] < 1.0  # Behind schedule


# ---------------------------------------------------------------------------
# Cost Estimation
# ---------------------------------------------------------------------------

class TestCostEstimation:

    def test_basic_estimate(self):
        ce = CostEstimation()
        result = ce.estimate({"concrete_m3": 10.0, "rebar_kg": 500.0})
        assert result["subtotal"] > 0
        assert result["total"] > result["subtotal"]

    def test_custom_unit_cost(self):
        ce = CostEstimation()
        ce.set_unit_cost("custom_item", 50.0)
        result = ce.estimate({"custom_item": 10.0})
        assert result["subtotal"] == 500.0

    def test_empty_quantities(self):
        ce = CostEstimation()
        result = ce.estimate({})
        assert result["subtotal"] == 0.0
        assert result["total"] == 0.0

    def test_line_items_count(self):
        ce = CostEstimation()
        result = ce.estimate({"concrete_m3": 5.0, "rebar_kg": 200.0})
        assert len(result["line_items"]) == 2


# ---------------------------------------------------------------------------
# Reference Data
# ---------------------------------------------------------------------------

class TestReferenceData:

    def test_get_material(self):
        mat = ReferenceData.get_material("steel_A36")
        assert mat is not None
        assert "E_GPa" in mat
        assert mat["E_GPa"] == 200

    def test_get_missing_material(self):
        assert ReferenceData.get_material("unobtanium") is None

    def test_list_materials(self):
        materials = ReferenceData.list_materials()
        assert "steel_A36" in materials
        assert "aluminum_6061" in materials
        assert len(materials) >= 5

    def test_standard_pipe_sizes(self):
        assert 0.5 in ReferenceData.STANDARD_PIPE_SIZES_IN
        assert 12.0 in ReferenceData.STANDARD_PIPE_SIZES_IN

    def test_code_references(self):
        assert "structural_steel" in ReferenceData.CODE_REFERENCES
        assert "electrical" in ReferenceData.CODE_REFERENCES


# ---------------------------------------------------------------------------
# Production-readiness tests (30+ new cases)
# ---------------------------------------------------------------------------

class TestUnitConverterProduction:

    def test_length_round_trip_m_ft(self):
        uc = UnitConverter()
        original = 42.5
        result = uc.convert(uc.convert(original, "m", "ft"), "ft", "m")
        assert abs(result - original) < 1e-6

    def test_temperature_c_to_k(self):
        uc = UnitConverter()
        assert abs(uc.convert(0.0, "C", "K") - 273.15) < 1e-6

    def test_temperature_k_to_c(self):
        uc = UnitConverter()
        assert abs(uc.convert(273.15, "K", "C") - 0.0) < 1e-6

    def test_temperature_f_to_k(self):
        uc = UnitConverter()
        assert abs(uc.convert(32.0, "F", "K") - 273.15) < 0.01

    def test_temperature_k_to_f(self):
        uc = UnitConverter()
        assert abs(uc.convert(273.15, "K", "F") - 32.0) < 0.01

    def test_temperature_c_roundtrip(self):
        uc = UnitConverter()
        assert abs(uc.convert(uc.convert(100.0, "C", "F"), "F", "C") - 100.0) < 1e-6

    def test_incompatible_units_raises(self):
        import pytest
        uc = UnitConverter()
        with pytest.raises(ValueError):
            uc.convert(1.0, "m", "kg")

    def test_unknown_unit_raises(self):
        import pytest
        uc = UnitConverter()
        with pytest.raises(ValueError):
            uc.convert(1.0, "furlong", "km")

    def test_mass_kg_to_lb(self):
        uc = UnitConverter()
        assert abs(uc.convert(1.0, "kg", "lb") - 2.20462) < 0.001

    def test_energy_kwh_to_btu(self):
        uc = UnitConverter()
        btu = uc.convert(1.0, "kWh", "BTU")
        assert abs(btu - 3412.14) < 1.0

    def test_power_hp_to_kw(self):
        uc = UnitConverter()
        kw = uc.convert(1.0, "hp", "kW")
        assert abs(kw - 0.74570) < 0.001

    def test_available_units_length(self):
        uc = UnitConverter()
        units = uc.available_units("length")
        assert "m" in units and "ft" in units and "in" in units

    def test_pressure_atm_to_pa(self):
        uc = UnitConverter()
        assert abs(uc.convert(1.0, "atm", "Pa") - 101325.0) < 1.0

    def test_velocity_mph_to_ms(self):
        uc = UnitConverter()
        assert abs(uc.convert(1.0, "mph", "m/s") - 0.44704) < 0.001

    def test_area_sqft_to_sqm(self):
        uc = UnitConverter()
        assert abs(uc.convert(1.0, "ft2", "m2") - 0.0929) < 0.001


class TestStructuralCalcsProduction:

    def test_simple_beam_center_load(self):
        sc = StructuralCalcs()
        result = sc.simple_beam_deflection(
            load_N=10000, span_m=5, E_Pa=200e9, I_m4=1e-5, load_type="center"
        )
        assert result.max_deflection_m > 0
        assert result.max_moment_Nm == pytest.approx(10000 * 5 / 4)

    def test_simple_beam_uniform_load(self):
        sc = StructuralCalcs()
        result = sc.simple_beam_deflection(
            load_N=10000, span_m=5, E_Pa=200e9, I_m4=1e-5, load_type="uniform"
        )
        assert result.max_deflection_m > 0
        assert result.description == "Simple beam, uniform load"

    def test_cantilever_deflection(self):
        sc = StructuralCalcs()
        result = sc.cantilever_deflection(load_N=5000, span_m=3, E_Pa=200e9, I_m4=1e-5)
        assert result.max_deflection_m > 0
        assert result.max_moment_Nm == pytest.approx(5000 * 3)

    def test_cantilever_greater_than_simple_beam(self):
        """Cantilever deflection > simple beam for same load & span."""
        sc = StructuralCalcs()
        cant = sc.cantilever_deflection(load_N=10000, span_m=5, E_Pa=200e9, I_m4=1e-5)
        simple = sc.simple_beam_deflection(load_N=10000, span_m=5, E_Pa=200e9, I_m4=1e-5)
        assert cant.max_deflection_m > simple.max_deflection_m

    def test_rectangular_moi(self):
        sc = StructuralCalcs()
        I = sc.rectangular_moment_of_inertia(0.1, 0.2)
        assert abs(I - (0.1 * 0.2**3) / 12) < 1e-10

    def test_bending_stress(self):
        sc = StructuralCalcs()
        sigma = sc.bending_stress(moment_Nm=1000, I_m4=1e-4, c_m=0.1)
        assert abs(sigma - 1000 * 0.1 / 1e-4) < 1.0

    def test_factor_of_safety(self):
        sc = StructuralCalcs()
        fos = sc.factor_of_safety(allowable_stress_Pa=250e6, actual_stress_Pa=100e6)
        assert abs(fos - 2.5) < 1e-6

    def test_factor_of_safety_zero_actual_stress(self):
        sc = StructuralCalcs()
        fos = sc.factor_of_safety(250e6, 0.0)
        assert fos == float("inf")


class TestHVACCalcsProduction:

    def test_simple_heat_load_returns_positive(self):
        hvac = HVACCalcs()
        result = hvac.simple_heat_load(area_m2=100, delta_T_K=15)
        assert result.total_load_W > 0

    def test_heat_load_with_occupants(self):
        hvac = HVACCalcs()
        result = hvac.simple_heat_load(area_m2=100, delta_T_K=15, occupants=10)
        assert result.sensible_load_W > hvac.simple_heat_load(100, 15, 0).sensible_load_W

    def test_heat_load_btu_conversion(self):
        hvac = HVACCalcs()
        result = hvac.simple_heat_load(area_m2=100, delta_T_K=10)
        assert result.total_load_BTU_hr == pytest.approx(result.total_load_W * 3.41214, abs=1.0)

    def test_cfm_from_load(self):
        hvac = HVACCalcs()
        cfm = hvac.cfm_from_load(load_W=3000, delta_T_K=8.0)
        assert cfm > 0

    def test_dew_point_reasonable(self):
        hvac = HVACCalcs()
        dp = hvac.dew_point(dry_bulb_C=20.0, relative_humidity_pct=50.0)
        assert -5 < dp < 20  # Reasonable dew point

    def test_enthalpy_dry_air(self):
        hvac = HVACCalcs()
        h = hvac.enthalpy(dry_bulb_C=20.0, humidity_ratio=0.0)
        assert abs(h - 1.006 * 20.0) < 0.1


class TestElectricalCalcsProduction:

    def test_ohms_law_v_from_ir(self):
        ec = ElectricalCalcs()
        result = ec.ohms_law(current_A=2.0, resistance_ohm=50.0)
        assert result["voltage_V"] == pytest.approx(100.0)

    def test_ohms_law_i_from_vr(self):
        ec = ElectricalCalcs()
        result = ec.ohms_law(voltage_V=120.0, resistance_ohm=60.0)
        assert result["current_A"] == pytest.approx(2.0)

    def test_ohms_law_r_from_vi(self):
        ec = ElectricalCalcs()
        result = ec.ohms_law(voltage_V=120.0, current_A=2.0)
        assert result["resistance_ohm"] == pytest.approx(60.0)

    def test_ohms_law_raises_with_all_three(self):
        import pytest
        ec = ElectricalCalcs()
        with pytest.raises(ValueError):
            ec.ohms_law(voltage_V=12, current_A=2, resistance_ohm=6)

    def test_power_calculation(self):
        ec = ElectricalCalcs()
        result = ec.power(voltage_V=120.0, current_A=10.0, power_factor=0.9)
        assert result["apparent_VA"] == pytest.approx(1200.0)
        assert result["real_W"] == pytest.approx(1080.0)

    def test_voltage_drop_single_phase(self):
        ec = ElectricalCalcs()
        vd = ec.voltage_drop(current_A=20.0, resistance_per_m_ohm=0.001, length_m=100, phases=1)
        # V = 20 * 0.001 * 100 * 2 = 4.0
        assert abs(vd - 4.0) < 0.001

    def test_motor_fla_positive(self):
        ec = ElectricalCalcs()
        fla = ec.motor_fla(hp=10, voltage_V=480)
        assert fla > 0


class TestPlumbingCalcsProduction:

    def test_fixture_units_toilets(self):
        pc = PlumbingCalcs()
        fu = pc.fixture_units({"toilet": 4})
        assert fu == 16  # 4 toilets × 4 WSFU

    def test_demand_gpm_zero_wsfu(self):
        pc = PlumbingCalcs()
        assert pc.demand_gpm(0) == 0.0

    def test_demand_gpm_small_building(self):
        pc = PlumbingCalcs()
        gpm = pc.demand_gpm(10)
        assert gpm > 0

    def test_demand_gpm_large_building(self):
        pc = PlumbingCalcs()
        gpm_small = pc.demand_gpm(10)
        gpm_large = pc.demand_gpm(200)
        assert gpm_large > gpm_small

    def test_water_heater_sizing(self):
        pc = PlumbingCalcs()
        gal = pc.water_heater_sizing_gal(occupants=4)
        assert gal == pytest.approx(4 * 20.0 * 0.7)


class TestProjectManagementProduction:

    def test_cpm_forward_pass(self):
        pm = ProjectManagement()
        acts = [
            CPMActivity("A", "Activity A", 3, []),
            CPMActivity("B", "Activity B", 5, ["A"]),
            CPMActivity("C", "Activity C", 2, ["A"]),
            CPMActivity("D", "Activity D", 4, ["B", "C"]),
        ]
        critical, total = pm.critical_path(acts)
        assert total == 12.0  # A(3)+B(5)+D(4) = 12
        assert "A" in critical
        assert "B" in critical
        assert "D" in critical

    def test_cpm_backward_pass_critical_path(self):
        pm = ProjectManagement()
        acts = [
            CPMActivity("A", "A", 5, []),
            CPMActivity("B", "B", 3, ["A"]),
        ]
        critical, total = pm.critical_path(acts)
        assert total == 8.0
        assert set(critical) == {"A", "B"}

    def test_cpm_parallel_activities(self):
        pm = ProjectManagement()
        acts = [
            CPMActivity("A", "A", 5, []),
            CPMActivity("B", "B", 8, []),  # longer parallel path
            CPMActivity("C", "C", 2, ["A", "B"]),
        ]
        critical, total = pm.critical_path(acts)
        assert total == 10.0  # B(8)+C(2)
        assert "B" in critical
        assert "A" not in critical

    def test_earned_value_metrics(self):
        pm = ProjectManagement()
        result = pm.earned_value(
            budget_at_completion=100000,
            planned_value=60000,
            earned_value_pct=50,
            actual_cost=55000,
        )
        assert result["EV"] == 50000.0
        assert result["CPI"] == pytest.approx(50000 / 55000, abs=0.001)
        assert result["SPI"] == pytest.approx(50000 / 60000, abs=0.001)

    def test_earned_value_zero_actual_cost(self):
        pm = ProjectManagement()
        result = pm.earned_value(100000, 50000, 50, 0)
        assert result["CPI"] is None  # inf case


class TestCostEstimationProduction:

    def test_estimate_concrete(self):
        ce = CostEstimation()
        result = ce.estimate({"concrete_m3": 10.0})
        assert result["subtotal"] == pytest.approx(10 * 180.0)

    def test_estimate_includes_overhead_and_markup(self):
        ce = CostEstimation()
        result = ce.estimate({"concrete_m3": 10.0})
        assert result["overhead"] > 0
        assert result["profit"] > 0
        assert result["total"] > result["subtotal"]

    def test_estimate_custom_unit_cost(self):
        ce = CostEstimation()
        ce.set_unit_cost("widget", 50.0)
        result = ce.estimate({"widget": 5.0})
        assert result["line_items"][0]["cost"] == 250.0

    def test_estimate_unknown_item_cost_zero(self):
        ce = CostEstimation()
        result = ce.estimate({"nonexistent_item": 10.0})
        assert result["line_items"][0]["unit_cost"] == 0.0

    def test_reference_data_material(self):
        mat = ReferenceData.get_material("steel_A36")
        assert mat is not None
        assert mat["E_GPa"] == 200

    def test_reference_data_list_materials(self):
        materials = ReferenceData.list_materials()
        assert "steel_A36" in materials
        assert "aluminum_6061" in materials

    def test_reference_data_code_references(self):
        assert "AISC" in ReferenceData.CODE_REFERENCES["structural_steel"]

    def test_reference_data_pipe_sizes(self):
        assert 0.5 in ReferenceData.STANDARD_PIPE_SIZES_IN
        assert 12.0 in ReferenceData.STANDARD_PIPE_SIZES_IN


import pytest
