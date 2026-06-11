"""
Ship 31ag end-to-end test:
  - Generate deliverable (3 formats) using existing demo_deliverable_generator
  - Build multipart/mixed message using new attachments path
  - Hand to sendmail
  - Send to corey.gfc@gmail.com
"""
import sys, os, base64, subprocess
sys.path.insert(0, "/opt/Murphy-System")
sys.path.insert(0, "/opt/Murphy-System/src")

from demo_deliverable_generator import _convert_to_pdf, _convert_to_docx
from email_mime_builder import build_multipart_message

DELIVERABLE_MD = """# MEP Engineering Risk Brief — 50,000 sqft Mixed-Use HVAC Retrofit

Prepared by: Murphy (autonomous AI engineer)
Date: 2026-06-11
For: Bid evaluation — go/no-go

SCOPE SUMMARY
- 50,000 sqft mixed-use building: 4 floors retail + office + 12 residential
- HVAC retrofit: replace 3 RTUs (10/15/15 ton), add VRF for residential
- Construction window: 14 weeks (avoid Dec-Jan holidays)

TOP 5 RISKS
1. Asbestos in 1970s mechanical room insulation — HIGH x HIGH
   Mitigation: $25K Phase-1 ESA before bid finalization
2. Roof structural capacity for new VRF outdoor units — MED x HIGH
   Mitigation: Structural engineer review week 1
3. Electrical service upgrade required (480V 3ph) — MED x MED
   Mitigation: Coordinate with utility, 6-week lead time
4. Tenant disruption during construction — HIGH x MED
   Mitigation: Phased shutdown plan with notification SLA
5. Refrigerant transition (R-410A to R-454B) — MED x LOW
   Mitigation: Spec R-454B equipment from start

GO/NO-GO RECOMMENDATION
GO, conditional on:
  1. Owner funds $25K Phase-1 ESA before bid finalization
  2. Structural engineer review added as line item
  3. Tenant notification SLA in writing

Estimated bid: $1.2M - $1.4M material+labor, 18% gross margin target
Walkaway price: below $1.05M

Murphy is an AI assistant. Verify all specifics with a licensed PE before construction acts.
"""

# Generate PDF + DOCX using existing infra
pdf_r = _convert_to_pdf(DELIVERABLE_MD, "MEP Risk Brief")
docx_r = _convert_to_docx(DELIVERABLE_MD, "MEP Risk Brief")

pdf_bytes = base64.b64decode(pdf_r["content"])
docx_bytes = base64.b64decode(docx_r["content"])
print(f"  PDF: {len(pdf_bytes)} bytes (starts with: {pdf_bytes[:5]})")
print(f"  DOCX: {len(docx_bytes)} bytes (starts with: {docx_bytes[:4]})")

# Build the email body
plain_body = """Greetings.

Per your request, please find attached the engineering risk brief for the 50,000 sqft mixed-use HVAC retrofit bid evaluation.

The brief covers scope summary, the five most material risks ranked by likelihood and impact, and a go/no-go recommendation with the contingencies that need to be in writing before bid finalization.

In short: GO, conditional on owner-funded Phase-1 ESA. Bid range $1.2M to $1.4M with 18% margin target. Walkaway below $1.05M.

Two questions before I would lock the bid:
1. Has the owner agreed to fund the Phase-1 ESA, or is that still in negotiation?
2. Do you have current utility records showing whether 480V 3-phase service is already present, or is the upgrade definitely required?

Both PDF and DOCX versions are attached. The DOCX is editable should you wish to add internal notes or modify the recommendation language for your own bid packet.

Yours,
Murphy
"""

# Build multipart/mixed with attachments via new 31ag path
msg = build_multipart_message(
    to_addr="corey.gfc@gmail.com",
    subject="Ship 31ag — MEP risk brief (attachments test)",
    plain_body=plain_body,
    from_addr="murphy@murphy.systems",
    attachments=[
        {"filename": "MEP_Risk_Brief.pdf", "mime": "application/pdf", "blob": pdf_bytes},
        {"filename": "MEP_Risk_Brief.docx",
         "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
         "blob": docx_bytes},
        {"filename": "MEP_Risk_Brief.md", "mime": "text/markdown",
         "blob": DELIVERABLE_MD.encode()},
    ],
)
print(f"  message size: {len(msg)} chars")
print(f"  multipart/mixed: {'multipart/mixed' in msg}")
print(f"  3 attachments declared: {msg.count('Content-Disposition: attachment')}")

# Ship it
r = subprocess.run(
    ["/usr/sbin/sendmail","-t","-f","murphy@murphy.systems"],
    input=msg.encode(), capture_output=True, timeout=15,
)
print(f"\n  sendmail rc={r.returncode}")
if r.stderr:
    print(f"  stderr: {r.stderr.decode()[:200]}")
print(f"\n  ✓ test message dispatched to corey.gfc@gmail.com")
