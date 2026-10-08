"""Producer admission checks; shared service upgrades belong to its own project."""


def require_capabilities(client, workflow, validator=None):
    capabilities = client.call('capabilities')
    if (capabilities.get('protocol_version') != 1 or
            workflow not in capabilities.get('workflows', []) or
            (validator and validator not in capabilities.get('validators', []))):
        raise RuntimeError(
            'Standalone Chromecast coordinator upgrade required; use the reviewed '
            'release in /home/will/chromecast-coordinator. App installers do not '
            'deploy shared service code.')
    return capabilities
