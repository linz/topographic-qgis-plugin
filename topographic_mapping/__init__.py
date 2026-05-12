from .plugin import TopographicMappingPlugin


def classFactory(iface):
    return TopographicMappingPlugin(iface)
