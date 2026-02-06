"""
Documentation & UI Asset Tests

Validates key documentation files and UI variant entry points exist.
"""

from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.resolve()
DOCS_DIR = BASE_DIR / 'documentation'

UI_VARIANTS = [
    'murphy_ui_integrated.html',
    'murphy_ui_integrated_terminal.html',
    'terminal_architect.html',
    'terminal_integrated.html',
    'terminal_worker.html',
    'terminal_enhanced.html',
]

BLUEPRINT_PATH = DOCS_DIR / 'architecture' / 'BACKEND_ARCHITECTURE_BLUEPRINT.md'
DOC_ASSETS = [
    BLUEPRINT_PATH,
    DOCS_DIR / 'enterprise' / 'SALES_AUTOMATION_RESPONSE_FLOWS.md',
    DOCS_DIR / 'enterprise' / 'ML_AUTOMATION_ROADMAP.md',
]

REQUIRED_BLUEPRINT_HEADINGS = [
    '[CLARIFYING QUESTIONS]',
    '[ARCHITECTURE BLUEPRINT]',
    '[MATHEMATICAL FRAMEWORK]',
    '[IMPLEMENTATION ROADMAP]',
    '[KEY DECISIONS SUMMARY]'
]


def validate_ui_variants_exist() -> bool:
    missing = [
        filename
        for filename in UI_VARIANTS
        if not (BASE_DIR / filename).exists()
    ]
    if missing:
        print(f"✗ Missing UI variants: {', '.join(missing)}")
        return False
    print("✓ All UI variants found")
    return True


def validate_documentation_assets_exist() -> bool:
    missing = [path for path in DOC_ASSETS if not path.exists()]
    if missing:
        print("✗ Missing documentation assets:")
        for path in missing:
            print(f"  - {path}")
        return False
    print("✓ All documentation assets found")
    return True


def validate_blueprint_headings_exist() -> bool:
    try:
        content = BLUEPRINT_PATH.read_text(encoding='utf-8')
    except (FileNotFoundError, OSError) as exc:
        print(f"✗ Blueprint could not be read: {exc}")
        return False

    missing = [heading for heading in REQUIRED_BLUEPRINT_HEADINGS if heading not in content]
    if missing:
        print(f"✗ Blueprint missing headings: {', '.join(missing)}")
        return False
    print("✓ Blueprint headings present")
    return True


def main() -> int:
    print("=" * 60)
    print("Murphy System - Documentation Asset Tests")
    print("=" * 60)

    tests = [
        validate_ui_variants_exist,
        validate_documentation_assets_exist,
        validate_blueprint_headings_exist,
    ]

    results = []
    for test in tests:
        print(f"\nTesting: {test.__name__}")
        try:
            results.append(test())
        except Exception as exc:
            print(f"✗ {test.__name__} raised an exception: {exc}")
            results.append(False)

    print("\n" + "=" * 60)
    print(f"Results: {sum(results)}/{len(results)} tests passed")
    print("=" * 60)

    if all(results):
        print("\n✓ All documentation asset tests passed!")
        return 0

    print("\n✗ Some documentation asset tests failed.")
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
