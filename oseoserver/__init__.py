import pkg_resources

__version__ = pkg_resources.require("oseoserver")[0].version
default_app_config = "oseoserver.apps.OseoServerConfig"
