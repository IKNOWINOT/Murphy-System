"""
PRESET-030 through PRESET-034 — Financial Services Presets
Copyright 2024 Inoni LLC – BSL-1.1
"""
from __future__ import annotations
import logging
from typing import List
from .base import AgentPersona, ComplianceRule, IndustryPreset, IntegrationMapping, KPIDefinition, WorkflowTemplate
logger = logging.getLogger(__name__)

BANK = IndustryPreset(
    preset_id="PRESET-030", name="Bank", industry="Financial Services", sub_industry="Commercial Banking",
    description="Core banking, KYC/AML, loan processing, and regulatory reporting.",
    version="1.0.0", tags=["banking","KYC","AML","BSA","Basel-III","FDIC","loans"],
    compatible_with=["PRESET-034","PRESET-031"],
    workflow_templates=[
        WorkflowTemplate(template_id="WF-BANK-001", name="KYC / Customer Onboarding", description="New customer identity verification, risk scoring, and account opening.",
            steps=[
                {"step_name":"Identity Verification","step_type":"automated_check","agent_persona":"BSA/AML Compliance Officer","integrations":["NICE Actimize","Wolters Kluwer"],"compliance_gates":["BSA-CIP","FinCEN-KYC"],"kpis":["KYC_completion_time"]},
                {"step_name":"Risk Scoring & EDD","step_type":"human_review","agent_persona":"BSA/AML Compliance Officer","integrations":["NICE Actimize"],"compliance_gates":["BSA-EDD-requirements"],"kpis":["AML_alert_false_positive_rate"]},
                {"step_name":"Account Opening","step_type":"integration_action","agent_persona":"Retail Banking Agent","integrations":["Temenos","FIS"],"compliance_gates":["Reg-CC","ECOA"],"kpis":["account_open_time"]},
            ], triggers=["new_customer_application"], outputs=["open_account","KYC_record","risk_score"]),
        WorkflowTemplate(template_id="WF-BANK-002", name="Loan Origination", description="Loan application through underwriting, approval, and funding.",
            steps=[
                {"step_name":"Application & Document Collection","step_type":"data_collection","agent_persona":"Loan Operations Agent","integrations":["FIS","Wolters Kluwer"],"compliance_gates":["TILA","ECOA","HMDA"],"kpis":["application_to_decision_time"]},
                {"step_name":"Underwriting & Credit Decision","step_type":"human_review","agent_persona":"Loan Operations Agent","integrations":["FIS"],"compliance_gates":["fair-lending","ECOA"],"kpis":["loan_approval_rate"]},
                {"step_name":"Loan Closing & Funding","step_type":"processing","agent_persona":"Loan Operations Agent","integrations":["FIS","Wolters Kluwer"],"compliance_gates":["RESPA","TILA-closing-disclosure"],"kpis":["cycle_time"]},
            ], triggers=["loan_application_received"], outputs=["funded_loan","closing_docs","core_system_update"]),
    ],
    agent_personas=[
        AgentPersona(persona_id="AP-BANK-001", name="BSA/AML Compliance Officer", role="Compliance", domain="Banking",
            capabilities=["SAR_filing","KYC_review","transaction_monitoring","regulatory_reporting"], tools=["NICE Actimize","Wolters Kluwer"], personality_traits=["regulatory-expert","meticulous","risk-aware"]),
        AgentPersona(persona_id="AP-BANK-002", name="Retail Banking Agent", role="Retail Operations", domain="Banking",
            capabilities=["account_opening","customer_service","product_cross_sell","digital_onboarding"], tools=["Temenos","FIS"], personality_traits=["customer-focused","compliant","helpful"]),
        AgentPersona(persona_id="AP-BANK-003", name="Loan Operations Agent", role="Loan Officer", domain="Banking",
            capabilities=["application_processing","underwriting_support","closing_coordination","pipeline_management"], tools=["FIS","Wolters Kluwer"], personality_traits=["detail-oriented","deadline-driven","fair"]),
    ],
    integration_mappings=[
        IntegrationMapping(connector_name="Temenos", connector_type="core_banking", required=True, config_template={"api_url":"","api_key":""}, purpose="Core banking platform for accounts and transactions."),
        IntegrationMapping(connector_name="FIS", connector_type="core_banking", required=False, config_template={"api_key":""}, purpose="Alternative core banking and loan origination."),
        IntegrationMapping(connector_name="NICE Actimize", connector_type="AML", required=True, config_template={"server_url":"","username":""}, purpose="Transaction monitoring and AML/BSA compliance."),
        IntegrationMapping(connector_name="Wolters Kluwer", connector_type="regulatory_compliance", required=True, config_template={"api_key":""}, purpose="Regulatory document generation and compliance management."),
    ],
    compliance_rules=[
        ComplianceRule(rule_id="CR-BANK-001", standard="BSA/AML", description="Bank Secrecy Act requires SAR and CTR filing, CIP, and ongoing transaction monitoring.", required_approvals=2, penalty_severity="critical", automated_check=True),
        ComplianceRule(rule_id="CR-BANK-002", standard="Basel III", description="Capital adequacy ratios and liquidity coverage requirements per Basel III.", required_approvals=2, penalty_severity="critical", automated_check=True),
        ComplianceRule(rule_id="CR-BANK-003", standard="FDIC / FFIEC", description="Safety and soundness examination standards and IT security guidelines.", required_approvals=2, penalty_severity="critical", automated_check=False),
    ],
    kpi_definitions=[
        KPIDefinition(kpi_id="KPI-BANK-001", name="Net Interest Margin (NIM)", description="Net interest income as % of average earning assets.", unit="%", target_value=3.5, warning_threshold=2.5, critical_threshold=1.5, measurement_method="net_interest_income/avg_earning_assets*100"),
        KPIDefinition(kpi_id="KPI-BANK-002", name="Loan Delinquency Rate", description="% of loans 30+ days past due.", unit="%", target_value=1.5, warning_threshold=3.0, critical_threshold=5.0, measurement_method="delinquent_loans/total_loans*100"),
        KPIDefinition(kpi_id="KPI-BANK-003", name="AML Alert False Positive Rate", description="% of AML transaction monitoring alerts that are false positives.", unit="%", target_value=85.0, warning_threshold=92.0, critical_threshold=97.0, measurement_method="false_positive_alerts/total_alerts*100"),
    ],
)

INSURANCE = IndustryPreset(
    preset_id="PRESET-031", name="Insurance Company", industry="Financial Services", sub_industry="Insurance",
    description="Underwriting, claims processing, policy management, and actuarial reporting.",
    version="1.0.0", tags=["insurance","underwriting","claims","NAIC","Solvency-II","loss-ratio"],
    compatible_with=["PRESET-030","PRESET-032"],
    workflow_templates=[
        WorkflowTemplate(template_id="WF-INS-001", name="Policy Underwriting", description="Risk assessment, quote generation, and policy issuance.",
            steps=[
                {"step_name":"Application & Risk Data Collection","step_type":"data_collection","agent_persona":"Underwriting Agent","integrations":["Guidewire","Duck Creek"],"compliance_gates":["state-filing-requirements"],"kpis":["quote_turnaround_time"]},
                {"step_name":"Risk Assessment & Pricing","step_type":"human_review","agent_persona":"Underwriting Agent","integrations":["Guidewire"],"compliance_gates":["actuarial-filing","rate-manual-compliance"],"kpis":["loss_ratio"]},
                {"step_name":"Policy Issuance","step_type":"integration_action","agent_persona":"Policy Administration Agent","integrations":["Guidewire","Duck Creek"],"compliance_gates":["state-policy-form-approval"],"kpis":["policy_issue_time"]},
            ], triggers=["application_received"], outputs=["issued_policy","premium_record"]),
        WorkflowTemplate(template_id="WF-INS-002", name="Claims Processing", description="First notice of loss through settlement and closure.",
            steps=[
                {"step_name":"FNOL & Coverage Verification","step_type":"data_collection","agent_persona":"Claims Operations Agent","integrations":["Guidewire","Majesco"],"compliance_gates":["prompt-payment-laws"],"kpis":["claims_cycle_time"]},
                {"step_name":"Investigation & Reserve Setting","step_type":"human_review","agent_persona":"Claims Operations Agent","integrations":["Guidewire"],"compliance_gates":["bad-faith-avoidance"],"kpis":["reserve_adequacy"]},
                {"step_name":"Settlement & Closure","step_type":"processing","agent_persona":"Claims Operations Agent","integrations":["Guidewire"],"compliance_gates":["state-settlement-requirements"],"kpis":["claims_cycle_time","combined_ratio"]},
            ], triggers=["loss_reported"], outputs=["closed_claim","payment","subrogation_referral"]),
    ],
    agent_personas=[
        AgentPersona(persona_id="AP-INS-001", name="Underwriting Agent", role="Underwriter", domain="Insurance",
            capabilities=["risk_assessment","pricing","portfolio_management","reinsurance_coordination"], tools=["Guidewire","Duck Creek"], personality_traits=["analytical","risk-aware","decisive"]),
        AgentPersona(persona_id="AP-INS-002", name="Claims Operations Agent", role="Claims Adjuster", domain="Insurance",
            capabilities=["FNOL_intake","investigation","reserve_management","litigation_coordination"], tools=["Guidewire","Majesco"], personality_traits=["empathetic","thorough","fair"]),
        AgentPersona(persona_id="AP-INS-003", name="Policy Administration Agent", role="Policy Admin", domain="Insurance",
            capabilities=["policy_issuance","endorsements","renewals","billing_management"], tools=["Guidewire","Duck Creek"], personality_traits=["accurate","process-driven","responsive"]),
    ],
    integration_mappings=[
        IntegrationMapping(connector_name="Guidewire", connector_type="insurance_core", required=True, config_template={"server_url":"","api_key":""}, purpose="Core insurance platform: policy, billing, and claims."),
        IntegrationMapping(connector_name="Duck Creek", connector_type="insurance_core", required=False, config_template={"api_key":""}, purpose="Alternative insurance core system."),
        IntegrationMapping(connector_name="Majesco", connector_type="insurance_core", required=False, config_template={"api_key":""}, purpose="Cloud-native insurance platform."),
    ],
    compliance_rules=[
        ComplianceRule(rule_id="CR-INS-001", standard="NAIC Model Laws", description="State insurance regulations based on NAIC model acts govern rates, forms, and market conduct.", required_approvals=2, penalty_severity="critical", automated_check=True),
        ComplianceRule(rule_id="CR-INS-002", standard="Solvency II (EU)", description="EU solvency capital requirements and governance standards.", required_approvals=2, penalty_severity="critical", automated_check=True),
        ComplianceRule(rule_id="CR-INS-003", standard="State Prompt Payment Laws", description="Claims must be acknowledged, investigated, and paid within state-mandated timeframes.", required_approvals=1, penalty_severity="high", automated_check=True),
    ],
    kpi_definitions=[
        KPIDefinition(kpi_id="KPI-INS-001", name="Loss Ratio", description="Incurred losses as % of earned premiums.", unit="%", target_value=65.0, warning_threshold=75.0, critical_threshold=85.0, measurement_method="incurred_losses/earned_premiums*100"),
        KPIDefinition(kpi_id="KPI-INS-002", name="Combined Ratio", description="Loss ratio plus expense ratio; below 100% is profitable.", unit="%", target_value=95.0, warning_threshold=100.0, critical_threshold=108.0, measurement_method="loss_ratio+expense_ratio"),
        KPIDefinition(kpi_id="KPI-INS-003", name="Claims Cycle Time", description="Average days from FNOL to claim closure.", unit="days", target_value=15.0, warning_threshold=25.0, critical_threshold=40.0, measurement_method="avg(closure_date-FNOL_date)"),
    ],
)

INVESTMENT_FIRM = IndustryPreset(
    preset_id="PRESET-032", name="Investment Firm", industry="Financial Services", sub_industry="Investment Management",
    description="Portfolio management, trade execution, compliance monitoring, and investor reporting.",
    version="1.0.0", tags=["investment","portfolio","SEC","FINRA","MiFID-II","GIPS","alpha"],
    compatible_with=["PRESET-030","PRESET-033"],
    workflow_templates=[
        WorkflowTemplate(template_id="WF-INV-001", name="Trade Order Management", description="Generate orders, pre-trade compliance checks, execution, and post-trade allocation.",
            steps=[
                {"step_name":"Portfolio Rebalance & Order Generation","step_type":"processing","agent_persona":"Portfolio Analytics Agent","integrations":["Bloomberg","FactSet"],"compliance_gates":["investment-policy-statement"],"kpis":["tracking_error"]},
                {"step_name":"Pre-trade Compliance Check","step_type":"automated_check","agent_persona":"Investment Compliance Officer","integrations":["Charles River","SS&C"],"compliance_gates":["SEC-17a-3","FINRA-best-execution","MiFID-II"],"kpis":["compliance_exceptions"]},
                {"step_name":"Trade Execution & Allocation","step_type":"integration_action","agent_persona":"Portfolio Analytics Agent","integrations":["Charles River"],"compliance_gates":["trade-allocation-fairness"],"kpis":["execution_cost"]},
            ], triggers=["rebalance_trigger","client_cashflow"], outputs=["executed_trades","allocation_record","compliance_report"]),
        WorkflowTemplate(template_id="WF-INV-002", name="Client Performance Reporting", description="Calculate returns, generate GIPS-compliant composites, and distribute reports.",
            steps=[
                {"step_name":"Performance Calculation","step_type":"processing","agent_persona":"Portfolio Analytics Agent","integrations":["SS&C","Bloomberg"],"compliance_gates":["GIPS-composite-construction"],"kpis":["alpha_generation","Sharpe_ratio"]},
                {"step_name":"Report Generation & Distribution","step_type":"document_generation","agent_persona":"Client Reporting Agent","integrations":["SS&C"],"compliance_gates":["ADV-disclosure"],"kpis":["report_delivery_timeliness"]},
            ], triggers=["quarter_end"], outputs=["client_report","composite_performance","GIPS_report"]),
    ],
    agent_personas=[
        AgentPersona(persona_id="AP-INV-001", name="Portfolio Analytics Agent", role="Portfolio Analyst", domain="Investment Management",
            capabilities=["portfolio_construction","risk_analytics","performance_attribution","rebalancing"], tools=["Bloomberg","FactSet","SS&C"], personality_traits=["quantitative","risk-aware","precise"]),
        AgentPersona(persona_id="AP-INV-002", name="Investment Compliance Officer", role="Compliance", domain="Investment Management",
            capabilities=["pre_trade_compliance","regulatory_reporting","marketing_review","code_of_ethics_monitoring"], tools=["Charles River","SS&C"], personality_traits=["regulatory-expert","vigilant","independent"]),
        AgentPersona(persona_id="AP-INV-003", name="Client Reporting Agent", role="Client Services", domain="Investment Management",
            capabilities=["performance_reporting","client_communication","onboarding","RFP_responses"], tools=["SS&C","Bloomberg"], personality_traits=["client-focused","accurate","communicative"]),
    ],
    integration_mappings=[
        IntegrationMapping(connector_name="Bloomberg", connector_type="market_data", required=True, config_template={"api_key":""}, purpose="Market data, analytics, and trade execution."),
        IntegrationMapping(connector_name="Charles River", connector_type="OMS", required=True, config_template={"server_url":"","api_key":""}, purpose="Order management and pre-trade compliance."),
        IntegrationMapping(connector_name="SS&C", connector_type="accounting", required=True, config_template={"api_key":""}, purpose="Portfolio accounting, performance, and reporting."),
        IntegrationMapping(connector_name="FactSet", connector_type="analytics", required=False, config_template={"api_key":""}, purpose="Fundamental data and portfolio analytics."),
    ],
    compliance_rules=[
        ComplianceRule(rule_id="CR-INV-001", standard="SEC Investment Advisers Act", description="Registered advisers must maintain fiduciary duty, ADV disclosure, and books/records.", required_approvals=2, penalty_severity="critical", automated_check=True),
        ComplianceRule(rule_id="CR-INV-002", standard="GIPS", description="Global Investment Performance Standards for fair and comparable performance reporting.", required_approvals=2, penalty_severity="high", automated_check=True),
        ComplianceRule(rule_id="CR-INV-003", standard="MiFID II", description="EU markets regulation requiring best execution, trade reporting, and investor protection.", required_approvals=2, penalty_severity="critical", automated_check=True),
    ],
    kpi_definitions=[
        KPIDefinition(kpi_id="KPI-INV-001", name="Alpha Generation", description="Portfolio return above benchmark on annualized basis.", unit="%", target_value=1.5, warning_threshold=0.0, critical_threshold=-2.0, measurement_method="portfolio_return - benchmark_return"),
        KPIDefinition(kpi_id="KPI-INV-002", name="Sharpe Ratio", description="Risk-adjusted return relative to risk-free rate.", unit="ratio", target_value=1.2, warning_threshold=0.7, critical_threshold=0.3, measurement_method="(portfolio_return-risk_free_rate)/portfolio_stdev"),
        KPIDefinition(kpi_id="KPI-INV-003", name="Compliance Exceptions", description="Number of pre/post-trade compliance exceptions per quarter.", unit="count", target_value=0.0, warning_threshold=2.0, critical_threshold=5.0, measurement_method="count(compliance_exceptions_per_quarter)"),
    ],
)

FINTECH = IndustryPreset(
    preset_id="PRESET-033", name="FinTech Company", industry="Financial Services", sub_industry="FinTech",
    description="Payment processing, digital lending, regulatory compliance, and fraud management.",
    version="1.0.0", tags=["fintech","payments","lending","PCI-DSS","FinCEN","CFPB","fraud"],
    compatible_with=["PRESET-030","PRESET-025"],
    workflow_templates=[
        WorkflowTemplate(template_id="WF-FINTECH-001", name="Payment Processing", description="Payment initiation, fraud screening, authorization, and settlement.",
            steps=[
                {"step_name":"Payment Initiation & Fraud Screening","step_type":"automated_check","agent_persona":"Payment Operations Agent","integrations":["Stripe","Plaid"],"compliance_gates":["PCI-DSS","NACHA-rules"],"kpis":["fraud_rate","payment_success_rate"]},
                {"step_name":"Authorization & Routing","step_type":"processing","agent_persona":"Payment Operations Agent","integrations":["Stripe","Dwolla"],"compliance_gates":["Regulation-E"],"kpis":["authorization_rate"]},
                {"step_name":"Settlement & Reconciliation","step_type":"automated_check","agent_persona":"Payment Operations Agent","integrations":["Stripe"],"compliance_gates":["FDIC-pass-through-requirements"],"kpis":["settlement_accuracy"]},
            ], triggers=["payment_initiated"], outputs=["settled_payment","transaction_record"]),
        WorkflowTemplate(template_id="WF-FINTECH-002", name="Digital Lending Origination", description="Application, credit decision, disclosures, and funding.",
            steps=[
                {"step_name":"Application & Credit Pull","step_type":"data_collection","agent_persona":"Lending Compliance Agent","integrations":["Plaid","Unit"],"compliance_gates":["FCRA","ECOA","TILA"],"kpis":["application_to_decision_time"]},
                {"step_name":"Underwriting & Offer","step_type":"automated_check","agent_persona":"Lending Compliance Agent","integrations":["Plaid"],"compliance_gates":["fair-lending","state-usury-laws"],"kpis":["approval_rate"]},
                {"step_name":"Disclosure & Funding","step_type":"integration_action","agent_persona":"Lending Compliance Agent","integrations":["Unit","Dwolla"],"compliance_gates":["TILA-Reg-Z","state-MTL"],"kpis":["funding_time"]},
            ], triggers=["loan_application"], outputs=["funded_loan","disclosure_record"]),
    ],
    agent_personas=[
        AgentPersona(persona_id="AP-FINTECH-001", name="Payment Operations Agent", role="Payments Specialist", domain="FinTech",
            capabilities=["payment_routing","fraud_monitoring","dispute_management","settlement_reconciliation"], tools=["Stripe","Dwolla","Plaid"], personality_traits=["fast","precise","fraud-aware"]),
        AgentPersona(persona_id="AP-FINTECH-002", name="Lending Compliance Agent", role="Compliance Officer", domain="FinTech",
            capabilities=["fair_lending","TILA_disclosures","state_licensing","regulatory_reporting"], tools=["Plaid","Unit"], personality_traits=["regulatory-expert","thorough","risk-conscious"]),
    ],
    integration_mappings=[
        IntegrationMapping(connector_name="Stripe", connector_type="payments", required=True, config_template={"secret_key":"","webhook_secret":""}, purpose="Payment processing and subscription billing."),
        IntegrationMapping(connector_name="Plaid", connector_type="bank_data", required=True, config_template={"client_id":"","secret":""}, purpose="Bank account verification and financial data."),
        IntegrationMapping(connector_name="Dwolla", connector_type="ACH", required=False, config_template={"key":"","secret":""}, purpose="ACH payment origination and management."),
        IntegrationMapping(connector_name="Unit", connector_type="banking_as_service", required=False, config_template={"api_key":""}, purpose="Embedded banking and ledger services."),
    ],
    compliance_rules=[
        ComplianceRule(rule_id="CR-FINTECH-001", standard="PCI DSS", description="Cardholder data environment must be PCI compliant.", required_approvals=2, penalty_severity="critical", automated_check=True),
        ComplianceRule(rule_id="CR-FINTECH-002", standard="FinCEN / BSA", description="Money services business registration and AML program required.", required_approvals=2, penalty_severity="critical", automated_check=True),
        ComplianceRule(rule_id="CR-FINTECH-003", standard="State MTL", description="Money Transmitter Licenses required in each state of operation.", required_approvals=2, penalty_severity="critical", automated_check=True),
    ],
    kpi_definitions=[
        KPIDefinition(kpi_id="KPI-FINTECH-001", name="Payment Success Rate", description="% of payment attempts that succeed.", unit="%", target_value=98.5, warning_threshold=96.0, critical_threshold=93.0, measurement_method="successful_payments/attempted_payments*100"),
        KPIDefinition(kpi_id="KPI-FINTECH-002", name="Fraud Rate", description="% of transaction volume flagged as fraudulent.", unit="%", target_value=0.05, warning_threshold=0.15, critical_threshold=0.30, measurement_method="fraud_value/total_volume*100"),
        KPIDefinition(kpi_id="KPI-FINTECH-003", name="Customer Acquisition Cost", description="Total S&M spend divided by new paying customers.", unit="USD", target_value=50.0, warning_threshold=100.0, critical_threshold=200.0, measurement_method="SM_spend/new_customers"),
    ],
)

CREDIT_UNION = IndustryPreset(
    preset_id="PRESET-034", name="Credit Union", industry="Financial Services", sub_industry="Credit Union",
    description="Member services, loan origination, deposit management, and NCUA regulatory compliance.",
    version="1.0.0", tags=["credit-union","NCUA","members","loans","BSA","TILA","ECOA"],
    compatible_with=["PRESET-030"],
    workflow_templates=[
        WorkflowTemplate(template_id="WF-CU-001", name="Member Loan Origination", description="Application intake through funding for consumer and auto loans.",
            steps=[
                {"step_name":"Loan Application & Decisioning","step_type":"automated_check","agent_persona":"Credit Union Loan Officer","integrations":["Symitar","CU*BASE"],"compliance_gates":["TILA","ECOA","FCRA"],"kpis":["application_to_decision_time"]},
                {"step_name":"Adverse Action or Approval","step_type":"human_review","agent_persona":"Credit Union Loan Officer","integrations":["Symitar"],"compliance_gates":["ECOA-notice-requirements","fair-lending"],"kpis":["loan_to_share_ratio"]},
                {"step_name":"Closing & Disbursement","step_type":"integration_action","agent_persona":"Credit Union Loan Officer","integrations":["Symitar","OnBase"],"compliance_gates":["TILA-Reg-Z-disclosures"],"kpis":["funding_time"]},
            ], triggers=["loan_application_received"], outputs=["funded_loan","adverse_action_notice","member_account_update"]),
        WorkflowTemplate(template_id="WF-CU-002", name="New Member Onboarding", description="Membership eligibility, account opening, and cross-sell.",
            steps=[
                {"step_name":"Field of Membership Verification","step_type":"automated_check","agent_persona":"Member Services Agent","integrations":["CU*BASE"],"compliance_gates":["NCUA-FOM-requirements"],"kpis":["member_growth"]},
                {"step_name":"Account Opening & KYC","step_type":"processing","agent_persona":"Member Services Agent","integrations":["Symitar","DNA"],"compliance_gates":["BSA-CIP","Reg-CC"],"kpis":["onboarding_completion_time"]},
            ], triggers=["membership_application"], outputs=["open_accounts","member_record","debit_card"]),
    ],
    agent_personas=[
        AgentPersona(persona_id="AP-CU-001", name="Credit Union Loan Officer", role="Loan Officer", domain="Credit Union",
            capabilities=["loan_underwriting","member_counseling","rate_negotiation","pipeline_management"], tools=["Symitar","CU*BASE","DNA"], personality_traits=["member-focused","fair","knowledgeable"]),
        AgentPersona(persona_id="AP-CU-002", name="Member Services Agent", role="Member Services", domain="Credit Union",
            capabilities=["account_management","cross_sell","dispute_resolution","financial_education"], tools=["Symitar","OnBase"], personality_traits=["helpful","member-centric","compliant"]),
    ],
    integration_mappings=[
        IntegrationMapping(connector_name="Symitar", connector_type="core_banking", required=True, config_template={"host":"","port":8089,"username":""}, purpose="Core credit union processing system."),
        IntegrationMapping(connector_name="CU*BASE", connector_type="core_banking", required=False, config_template={"api_key":""}, purpose="Alternative credit union core platform."),
        IntegrationMapping(connector_name="OnBase", connector_type="document_management", required=False, config_template={"server_url":"","username":""}, purpose="Document management and workflow automation."),
        IntegrationMapping(connector_name="DNA", connector_type="core_banking", required=False, config_template={"api_key":""}, purpose="FIS DNA core banking alternative."),
    ],
    compliance_rules=[
        ComplianceRule(rule_id="CR-CU-001", standard="NCUA Regulations", description="Credit unions must comply with NCUA charter, field of membership, and examination requirements.", required_approvals=2, penalty_severity="critical", automated_check=False),
        ComplianceRule(rule_id="CR-CU-002", standard="BSA/AML", description="Credit unions must maintain AML program, file SARs and CTRs, and conduct CIP.", required_approvals=2, penalty_severity="critical", automated_check=True),
        ComplianceRule(rule_id="CR-CU-003", standard="TILA / ECOA", description="Truth in Lending and Equal Credit Opportunity Act requirements for all consumer loans.", required_approvals=1, penalty_severity="high", automated_check=True),
    ],
    kpi_definitions=[
        KPIDefinition(kpi_id="KPI-CU-001", name="Member Growth Rate", description="Net new members as % of prior year membership.", unit="%", target_value=5.0, warning_threshold=2.0, critical_threshold=0.0, measurement_method="net_new_members/prior_members*100"),
        KPIDefinition(kpi_id="KPI-CU-002", name="Loan-to-Share Ratio", description="Total loans as % of total deposits (shares).", unit="%", target_value=75.0, warning_threshold=85.0, critical_threshold=95.0, measurement_method="total_loans/total_shares*100"),
        KPIDefinition(kpi_id="KPI-CU-003", name="Net Promoter Score", description="Member NPS from satisfaction surveys.", unit="score", target_value=60.0, warning_threshold=40.0, critical_threshold=20.0, measurement_method="promoters_pct-detractors_pct"),
    ],
)

ALL_FINANCIAL_PRESETS: List[IndustryPreset] = [BANK, INSURANCE, INVESTMENT_FIRM, FINTECH, CREDIT_UNION]
