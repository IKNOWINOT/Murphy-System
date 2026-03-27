"""
Test Suite — Librarian Controls for Drawing Modules

Validates that the SystemLibrarian has knowledge entries, module functions,
and capabilities registered for all drawing-related modules.
"""

import os
import unittest


from system_librarian import SystemLibrarian


class TestLibrarianDrawingKnowledge(unittest.TestCase):
    """Verify the librarian knowledge base contains drawing module entries."""

    def setUp(self):
        self.librarian = SystemLibrarian()

    def test_drawing_engine_knowledge_exists(self):
        """SystemLibrarian must have a knowledge entry for murphy_drawing_engine."""
        results = self.librarian.search_knowledge("drawing engine")
        topics = [r.topic for r in results]
        self.assertTrue(
            any("Drawing Engine" in t for t in topics),
            f"Expected 'Drawing Engine' knowledge entry, found: {topics}",
        )

    def test_engineering_toolbox_knowledge_exists(self):
        """SystemLibrarian must have a knowledge entry for murphy_engineering_toolbox."""
        results = self.librarian.search_knowledge("engineering toolbox")
        topics = [r.topic for r in results]
        self.assertTrue(
            any("Engineering Toolbox" in t for t in topics),
            f"Expected 'Engineering Toolbox' knowledge entry, found: {topics}",
        )

    def test_drawing_knowledge_references_export_formats(self):
        """Drawing engine knowledge should reference SVG/DXF export capabilities."""
        results = self.librarian.search_knowledge("drawing")
        descriptions = " ".join(r.description for r in results)
        self.assertIn("SVG", descriptions)
        self.assertIn("DXF", descriptions)

    def test_drawing_knowledge_references_bom(self):
        """Drawing engine knowledge should reference BOM extraction."""
        results = self.librarian.search_knowledge("drawing")
        descriptions = " ".join(r.description for r in results)
        self.assertIn("BOM", descriptions)


class TestLibrarianDrawingFunctions(unittest.TestCase):
    """Verify the librarian has function registrations for drawing modules."""

    def setUp(self):
        self.librarian = SystemLibrarian()

    def test_drawing_engine_in_module_functions(self):
        """murphy_drawing_engine must be registered in module_functions."""
        self.assertIn("murphy_drawing_engine", self.librarian.module_functions)

    def test_engineering_toolbox_in_module_functions(self):
        """murphy_engineering_toolbox must be registered in module_functions."""
        self.assertIn("murphy_engineering_toolbox", self.librarian.module_functions)

    def test_drawing_engine_has_export_svg(self):
        """Drawing engine must register export_svg function."""
        funcs = self.librarian.module_functions.get("murphy_drawing_engine", {})
        self.assertIn("export_svg", funcs)

    def test_drawing_engine_has_export_dxf(self):
        """Drawing engine must register export_dxf function."""
        funcs = self.librarian.module_functions.get("murphy_drawing_engine", {})
        self.assertIn("export_dxf", funcs)

    def test_drawing_engine_has_extract_bom(self):
        """Drawing engine must register extract_bom function."""
        funcs = self.librarian.module_functions.get("murphy_drawing_engine", {})
        self.assertIn("extract_bom", funcs)

    def test_drawing_engine_has_execute_command(self):
        """Drawing engine must register execute_command (agentic assistant)."""
        funcs = self.librarian.module_functions.get("murphy_drawing_engine", {})
        self.assertIn("execute_command", funcs)

    def test_drawing_engine_has_create_project(self):
        """Drawing engine must register create_project function."""
        funcs = self.librarian.module_functions.get("murphy_drawing_engine", {})
        self.assertIn("create_project", funcs)


class TestLibrarianDrawingCapabilities(unittest.TestCase):
    """Verify the librarian has capability registrations for drawing modules."""

    def setUp(self):
        self.librarian = SystemLibrarian()

    def test_drawing_engine_in_capabilities(self):
        """murphy_drawing_engine must be in module_capabilities."""
        self.assertIn("murphy_drawing_engine", self.librarian.module_capabilities)

    def test_engineering_toolbox_in_capabilities(self):
        """murphy_engineering_toolbox must be in module_capabilities."""
        self.assertIn("murphy_engineering_toolbox", self.librarian.module_capabilities)

    def test_drawing_capabilities_include_svg(self):
        """Drawing engine capabilities must include SVG export."""
        caps = self.librarian.module_capabilities.get("murphy_drawing_engine", [])
        self.assertTrue(
            any("SVG" in c for c in caps),
            f"Expected SVG capability, found: {caps}",
        )

    def test_drawing_capabilities_include_dxf(self):
        """Drawing engine capabilities must include DXF export."""
        caps = self.librarian.module_capabilities.get("murphy_drawing_engine", [])
        self.assertTrue(
            any("DXF" in c for c in caps),
            f"Expected DXF capability, found: {caps}",
        )

    def test_drawing_capabilities_include_bom(self):
        """Drawing engine capabilities must include BOM extraction."""
        caps = self.librarian.module_capabilities.get("murphy_drawing_engine", [])
        self.assertTrue(
            any("bill of materials" in c.lower() for c in caps),
            f"Expected BOM capability, found: {caps}",
        )

    def test_drawing_capabilities_include_agentic_commands(self):
        """Drawing engine capabilities must include NL command execution."""
        caps = self.librarian.module_capabilities.get("murphy_drawing_engine", [])
        self.assertTrue(
            any("natural-language" in c.lower() or "command" in c.lower() for c in caps),
            f"Expected agentic command capability, found: {caps}",
        )


class TestLibrarianDrawingOverview(unittest.TestCase):
    """Verify drawing modules appear in system overview."""

    def setUp(self):
        self.librarian = SystemLibrarian()

    def test_drawing_engine_in_system_overview(self):
        """System overview must list murphy_drawing_engine."""
        overview = self.librarian.get_system_overview()
        self.assertIn("murphy_drawing_engine", overview["modules"])

    def test_engineering_toolbox_in_system_overview(self):
        """System overview must list murphy_engineering_toolbox."""
        overview = self.librarian.get_system_overview()
        self.assertIn("murphy_engineering_toolbox", overview["modules"])

    def test_module_documentation_available(self):
        """Module documentation must be retrievable for drawing engine."""
        doc = self.librarian.get_module_documentation("murphy_drawing_engine")
        self.assertIn("functions", doc)
        self.assertIn("capabilities", doc)


if __name__ == "__main__":
    unittest.main()
