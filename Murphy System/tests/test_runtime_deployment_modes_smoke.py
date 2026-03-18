from src.murphy_core.runtime_deployment_modes import RuntimeDeploymentModes


def test_runtime_deployment_modes_has_direct_and_shell():
    modes = RuntimeDeploymentModes()
    payload = modes.to_dict()
    assert payload['preferred_direct']['name'] == 'direct_core_runtime_correct'
    assert payload['compat_shell']['name'] == 'legacy_compat_shell'
    assert len(payload['modes']) >= 2


def test_runtime_deployment_modes_categories():
    modes = RuntimeDeploymentModes()
    assert modes.preferred_direct().category == 'canonical'
    assert modes.compat_shell().category == 'transitional'
