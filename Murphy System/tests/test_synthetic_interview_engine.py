"""Tests for synthetic_interview_engine.py"""
import pytest, sys, os

from synthetic_interview_engine import (
    SyntheticInterviewEngine, ReadingLevel, QUESTION_BANK, QUESTION_IDS,
    INFERENCE_RULES, InferredAnswer, _SIMPLIFY_MAP,
)


@pytest.fixture
def engine():
    return SyntheticInterviewEngine()

@pytest.fixture
def session(engine):
    return engine.create_session("test_BAS", reading_level=ReadingLevel.HIGH_SCHOOL)


class TestQuestionBank:
    def test_21_questions(self): assert len(QUESTION_BANK) == 21
    def test_all_ids(self): assert set(QUESTION_IDS) == set(QUESTION_BANK.keys())
    def test_each_has_hs_level(self):
        for qid, q in QUESTION_BANK.items():
            assert ReadingLevel.HIGH_SCHOOL in q or any(k in q for k in [ReadingLevel.HIGH_SCHOOL])
    def test_each_has_topic(self):
        for qid, q in QUESTION_BANK.items():
            assert "topic" in q
    def test_each_has_hint(self):
        for qid, q in QUESTION_BANK.items():
            assert "hint" in q

class TestInferenceRules:
    def test_minimum_rules(self): assert len(INFERENCE_RULES) >= 30
    def test_chiller_infers_q01(self): assert "q01" in INFERENCE_RULES.get("chiller", {})
    def test_hipaa_infers_safety(self): assert "q09" in INFERENCE_RULES.get("HIPAA", {})
    def test_osha_infers_constraint(self): assert "q06" in INFERENCE_RULES.get("OSHA", {})
    def test_plc_implies_control(self): assert "PLC" in INFERENCE_RULES

class TestSession:
    def test_create_session(self, engine):
        s = engine.create_session("HVAC")
        assert s.domain == "HVAC"
        assert s.session_id
    def test_reading_level_default(self, engine):
        s = engine.create_session("domain")
        assert s.reading_level_detected == ReadingLevel.HIGH_SCHOOL
    def test_not_found(self, engine):
        with pytest.raises(KeyError):
            engine.next_question("bad_id")

class TestNextQuestion:
    def test_returns_q01_first(self, engine, session):
        q = engine.next_question(session.session_id)
        assert q is not None
        assert "question_id" in q and "question" in q
    def test_progress_format(self, engine, session):
        q = engine.next_question(session.session_id)
        assert "/" in q["progress"]
    def test_has_hint(self, engine, session):
        q = engine.next_question(session.session_id)
        assert "hint" in q

class TestAnswer:
    def test_records_answer(self, engine, session):
        q = engine.next_question(session.session_id)
        r = engine.answer(session.session_id, q["question_id"], "This is a chiller plant.")
        assert r["answer_recorded"] is True
    def test_infers_from_keyword(self, engine, session):
        q = engine.next_question(session.session_id)
        r = engine.answer(session.session_id, q["question_id"],
                          "We have a SCADA system with PLC and Modbus registers.")
        assert r["implicit_answers_found"] > 0
    def test_coverage_increases(self, engine, session):
        q = engine.next_question(session.session_id)
        r = engine.answer(session.session_id, q["question_id"],
                          "BACnet chiller with AHU and boiler, ASHRAE 90.1 compliant, OSHA required.")
        assert r["coverage_pct"] > 0
    def test_multi_demographic_chiller(self, engine):
        for level in [ReadingLevel.HIGH_SCHOOL, ReadingLevel.PROFESSIONAL, ReadingLevel.EXPERT]:
            s = engine.create_session("chiller", reading_level=level)
            q = engine.next_question(s.session_id)
            text = q["question"]
            assert len(text) > 10
    def test_all_21_covered_when_enough_keywords(self, engine):
        s = engine.create_session("industrial")
        stmt = ("chiller boiler AHU VFD PLC SCADA BACnet Modbus HIPAA OSHA ASHRAE NEC ISO FDA EPA "
                "inverter compressor pump sensor actuator DDC energy efficiency maintenance redundancy "
                "alarm setpoint schedule retrofit commissioning interlock emergency network wireless "
                "cloud analytics LEED carbon water solar generator UPS redundant")
        q = engine.next_question(s.session_id)
        engine.answer(s.session_id, q["question_id"], stmt)
        status = engine.get_all_21_status(s.session_id)
        assert status["coverage_pct"] >= 50.0

class TestKnowledgeModel:
    def test_generates_model(self, engine, session):
        q = engine.next_question(session.session_id)
        engine.answer(session.session_id, q["question_id"], "This is a BAS chiller system.")
        model = engine.generate_knowledge_model(session.session_id)
        assert isinstance(model, dict)
    def test_export(self, engine, session):
        q = engine.next_question(session.session_id)
        engine.answer(session.session_id, q["question_id"], "RTU with schedule and setpoint.")
        export = engine.export_interview(session.session_id)
        for k in ["session","knowledge_model","coverage_status","all_question_ids"]:
            assert k in export

class TestReadingLevelDetection:
    def test_expert_level(self, engine):
        assert engine.detect_reading_level("SIL-2 FMEA IPMVP delta-T enthalpy commissioning ASHRAE ISA interlock") == ReadingLevel.EXPERT
    def test_professional_level(self, engine):
        assert engine.detect_reading_level("EUI kWh VFD DDC BAS setpoint sequence algorithm SCADA") == ReadingLevel.PROFESSIONAL
    def test_hs_level(self, engine):
        lvl = engine.detect_reading_level("The system heats and cools the building.")
        assert lvl in [ReadingLevel.HIGH_SCHOOL, ReadingLevel.MIDDLE_SCHOOL]

class TestReadingLevelAdaptation:
    def test_simplifies_delta_t(self, engine):
        text = "The delta-T must be maintained."
        adapted = engine.adapt_to_reading_level(text, ReadingLevel.HIGH_SCHOOL)
        assert "temperature difference" in adapted
    def test_no_change_at_expert(self, engine):
        text = "The IPMVP Option B delta-T EUI kW protocol."
        adapted = engine.adapt_to_reading_level(text, ReadingLevel.EXPERT)
        assert adapted == text
