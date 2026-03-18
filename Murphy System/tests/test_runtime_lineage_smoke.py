from src.murphy_core.runtime_lineage import RuntimeLineage


def test_runtime_lineage_has_preferred_layer():
    lineage = RuntimeLineage()
    preferred = lineage.preferred()
    assert preferred.name == 'murphy_core_v3_runtime_correct'
    assert preferred.status == 'preferred'
    assert preferred.role == 'canonical'


def test_runtime_lineage_dict_contains_layers():
    lineage = RuntimeLineage()
    payload = lineage.to_dict()
    assert 'preferred' in payload
    assert 'layers' in payload
    assert len(payload['layers']) >= 5
