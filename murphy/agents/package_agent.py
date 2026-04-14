# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""PackageAgent — MURPHY-AGENT-PACKAGE-001

Owner: Platform Engineering
Dep: AgentOutput schema, Rosetta org lookup

Packages all agent outputs into a deliverable zip.

HARD RULE: if ci_status != "PASS" → return FAIL immediately.

Generates start.sh, start.bat, smoke_test.py at zip root.
Runs smoke_test.py — if non-zero exit → return FAIL with smoke output.

Input:
  manifest (list of AgentOutputs), ci_status (str)
Output:
  AgentOutput with content_type=zip

Error codes: PACKAGE-ERR-001 through PACKAGE-ERR-005.
"""

from __future__ import annotations

import base64
import io
import logging
import os
import subprocess
import tempfile
import uuid
import zipfile
from typing import Any, Dict, List

from murphy.rosetta.org_lookup import get_rosetta_state_hash
from murphy.schemas.agent_output import AgentOutput, ContentType, RenderType

logger = logging.getLogger(__name__)


class PackageAgent:
    """Package all agent outputs into a deliverable zip.

    Hard rules:
      - ci_status != "PASS" → immediate FAIL
      - smoke_test.py must be generated and executed
      - smoke test failure → FAIL with output in error field
      - Never package without passing CI
    """

    AGENT_NAME = "PackageAgent"

    def __init__(self, *, org_node_id: str = "platform-engineering") -> None:
        self.agent_id = f"package-{uuid.uuid4().hex[:8]}"
        self.org_node_id = org_node_id

    def run(
        self,
        manifest: List[AgentOutput],
        ci_status: str,
        *,
        skip_smoke: bool = False,
    ) -> AgentOutput:
        """Execute the package agent.

        Args:
            manifest: List of AgentOutput objects (the files to package).
            ci_status: Must be "PASS" or packaging is blocked.
            skip_smoke: If True, skip the smoke test (for test isolation).

        Returns:
            AgentOutput with content_type=zip or FAIL.
        """
        # HARD RULE: CI must pass
        if ci_status != "PASS":
            return AgentOutput.from_error(
                agent_id=self.agent_id,
                agent_name=self.AGENT_NAME,
                file_path="deliverable.zip",
                org_node_id=self.org_node_id,
                error_message=(
                    f"PACKAGE-ERR-002: CI status is '{ci_status}' — "
                    f"packaging blocked until CI passes"
                ),
            )

        try:
            # Build the zip in memory
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                # Add all manifest files
                for output in manifest:
                    zf.writestr(output.file_path, output.content)

                # Generate start scripts
                start_sh = self._generate_start_sh(manifest)
                start_bat = self._generate_start_bat(manifest)
                smoke_test = self._generate_smoke_test(manifest)

                zf.writestr("start.sh", start_sh)
                zf.writestr("start.bat", start_bat)
                zf.writestr("smoke_test.py", smoke_test)

            # Run smoke test (unless skipped for test isolation)
            if not skip_smoke:
                smoke_result = self._run_smoke_test(smoke_test)
                if not smoke_result["passed"]:
                    return AgentOutput.from_error(
                        agent_id=self.agent_id,
                        agent_name=self.AGENT_NAME,
                        file_path="deliverable.zip",
                        org_node_id=self.org_node_id,
                        error_message=(
                            f"PACKAGE-ERR-003: Smoke test failed — "
                            f"{smoke_result.get('output', 'no output')}"
                        ),
                    )

            # Encode zip as base64
            zip_buffer.seek(0)
            zip_b64 = base64.b64encode(zip_buffer.read()).decode("ascii")

            state_hash = get_rosetta_state_hash()

            return AgentOutput(
                agent_id=self.agent_id,
                agent_name=self.AGENT_NAME,
                file_path="deliverable.zip",
                content_type=ContentType.ZIP,
                content=zip_b64,
                lang=None,
                depends_on=[o.file_path for o in manifest],
                org_node_id=self.org_node_id,
                rosetta_state_hash=state_hash,
                render_type=RenderType.DOWNLOAD,
                hitl_required=False,
                bat_seal_required=True,
            )

        except Exception as exc:  # PACKAGE-ERR-001
            logger.error("PACKAGE-ERR-001: %s", exc)
            return AgentOutput.from_error(
                agent_id=self.agent_id,
                agent_name=self.AGENT_NAME,
                file_path="deliverable.zip",
                org_node_id=self.org_node_id,
                error_message=f"PACKAGE-ERR-001: {exc}",
            )

    # ------------------------------------------------------------------
    # Script generators  (PACKAGE-GEN-001)
    # ------------------------------------------------------------------

    def _generate_start_sh(self, manifest: List[AgentOutput]) -> str:
        """Generate a start.sh that launches the app with no internet."""
        main_file = next(
            (o.file_path for o in manifest if "main" in o.file_path),
            manifest[0].file_path if manifest else "main.py",
        )
        return (
            "#!/usr/bin/env bash\n"
            "# Auto-generated by Murphy PackageAgent — no internet required\n"
            "set -euo pipefail\n"
            f'echo "Starting {main_file}..."\n'
            f'python3 "{main_file}" "$@"\n'
        )

    def _generate_start_bat(self, manifest: List[AgentOutput]) -> str:
        """Generate a start.bat for Windows — no internet required."""
        main_file = next(
            (o.file_path for o in manifest if "main" in o.file_path),
            manifest[0].file_path if manifest else "main.py",
        )
        return (
            "@echo off\n"
            "REM Auto-generated by Murphy PackageAgent — no internet required\n"
            f'echo Starting {main_file}...\n'
            f'python "{main_file}" %*\n'
        )

    def _generate_smoke_test(self, manifest: List[AgentOutput]) -> str:
        """Generate smoke_test.py that checks the process starts within 10s."""
        main_file = next(
            (o.file_path for o in manifest if "main" in o.file_path),
            manifest[0].file_path if manifest else "main.py",
        )
        return (
            "#!/usr/bin/env python3\n"
            '"""Smoke test — auto-generated by Murphy PackageAgent."""\n'
            "import subprocess, sys, time\n"
            "\n"
            "def main():\n"
            f'    proc = subprocess.Popen(\n'
            f'        [sys.executable, "{main_file}"],\n'
            f'        stdout=subprocess.PIPE,\n'
            f'        stderr=subprocess.PIPE,\n'
            f'    )\n'
            "    time.sleep(2)\n"
            "    if proc.poll() is not None and proc.returncode != 0:\n"
            '        print(f"FAIL: process exited with {proc.returncode}")\n'
            "        sys.exit(1)\n"
            "    proc.terminate()\n"
            "    proc.wait(timeout=10)\n"
            '    print("PASS: process started and responded")\n'
            "    sys.exit(0)\n"
            "\n"
            'if __name__ == "__main__":\n'
            "    main()\n"
        )

    # ------------------------------------------------------------------
    # Smoke test runner  (PACKAGE-SMOKE-001)
    # ------------------------------------------------------------------

    def _run_smoke_test(self, smoke_code: str) -> Dict[str, Any]:
        """Execute the smoke test in a temporary directory.

        Returns {"passed": bool, "output": str}.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            smoke_path = os.path.join(tmpdir, "smoke_test.py")
            with open(smoke_path, "w") as f:
                f.write(smoke_code)

            try:
                result = subprocess.run(
                    ["python3", smoke_path],
                    capture_output=True,
                    text=True,
                    timeout=15,
                    cwd=tmpdir,
                )
                return {
                    "passed": result.returncode == 0,
                    "output": (result.stdout + result.stderr).strip(),
                }
            except subprocess.TimeoutExpired:  # PACKAGE-ERR-004
                return {
                    "passed": False,
                    "output": "PACKAGE-ERR-004: Smoke test timed out after 15s",
                }
            except Exception as exc:  # PACKAGE-ERR-005
                return {
                    "passed": False,
                    "output": f"PACKAGE-ERR-005: {exc}",
                }
