import os
import logging
import configparser

from regate.const import COMMAND, PLATFORM
from regate.edam import get_data_path

logger = logging.getLogger()


def load_config(options):
    if not os.path.exists(options.config_file):
        raise IOError("{0} doesn't exist".format(options.config_file))
    config = Config(options.config_file, "regate", options)
    logger.debug("Configuration file: %r", config)
    return config


def generate_template(filename="regate.ini"):
    """
    :return:
    """
    if os.path.exists(filename):
        raise FileExistsError("Filename '%s' already exists!" % filename)
    template_config = get_data_path('regate.ini')
    with open(template_config, 'r') as configtemplate:
        with open(filename, 'w') as fp:
            for line in configtemplate:
                fp.write(line)


class Config(object):
    """
    class config to parse and check the config.ini file
    """

    def __init__(self, configfile, script, options):
        self.conf = self.load_configuration(configfile)
        self.galaxy_url_api = self.assign("galaxy_server", "galaxy_url_api", ismandatory=True)
        self.api_key = self.assign("galaxy_server", "api_key", ismandatory=True)
        if script == "regate":
            if options.command != COMMAND.TEMPLATE.value:
                if options.platform == PLATFORM.GALAXY.value or "push" in options:
                    self.galaxy_url = self.assign("galaxy_server", "galaxy_url", ismandatory=True)
                    self.transient_instance = self.assign("galaxy_server", "transient_instance", ismandatory=True, boolean=True)
                    self.tools_default = self.assign("galaxy_server", "tools_default", ismandatory=True)
                    self.contactName = self.assign("galaxy_server", "contactName", ismandatory=True)
                    self.contactUrl = self.assign("galaxy_server", "contactUrl", ismandatory=False)
                    self.contactTel = self.assign("galaxy_server", "contactTel", ismandatory=False)
                    self.contactEmail = self.assign("galaxy_server", "contactEmail", ismandatory=True)
                    self.contactTypeEntity = self.assign("galaxy_server", "contactTypeEntity", ismandatory=True)
                    self.contactTypeRole = self.assign("galaxy_server", "contactTypeRole", ismandatory=True)

                if options.platform == PLATFORM.BIOTOOLS.value or "push" in options:
                    self.login = self.assign("regate_specific_section", "login", ismandatory=True,
                                             message="login option is mandatory to push resources to Elixir")
                    self.bioregistry_host = self.assign("regate_specific_section", "bioregistry_host", ismandatory=True,
                                                        message="bioregistry_host option is mandatory to export "
                                                                "or publish tools and/or workflows to the Elixir registry")
                    self.ssl_verify = self.assign("regate_specific_section", "ssl_verify", ismandatory=True,
                                                  message="ssl_verify option is mandatory to push resources to Elixir", boolean=True)
                    self.accessibility = self.assign("regate_specific_section", "accessibility", ismandatory=True,
                                                     message="accessibility option is mandatory to push resources to Elixir")
                else:
                    self.login = self.assign("regate_specific_section", "login", ismandatory=False)
                    self.bioregistry_host = self.assign("regate_specific_section", "bioregistry_host", ismandatory=False)
                    self.ssl_verify = self.assign("regate_specific_section", "ssl_verify", ismandatory=False, boolean=True)

                self.resourcename = self.assign("galaxy_server", "resourcename", ismandatory=True)
                self.prefix_toolname = self.assign("regate_specific_section", "prefix_toolname", ismandatory=False)
                self.suffix_toolname = self.assign("regate_specific_section", "suffix_toolname", ismandatory=False)
                self.accessibility = self.assign("regate_specific_section", "accessibility", ismandatory=True)
                self.data_uri_prefix = self.assign("regate_specific_section", "data_uri_prefix", ismandatory=True)

            self.tool_dir = self.assign("regate_specific_section", "tool_dir", ismandatory=True)
            self.yaml_file = self.assign("regate_specific_section", "yaml_file", ismandatory=False)
            self.xmltemplate = self.assign("regate_specific_section", "xmltemplate", ismandatory=False)
            self.xsdbiotools = self.assign("regate_specific_section", "xsdbiotools", ismandatory=False)
            self.no_interactive = options.no_interactive

        if script == "remag":
            self.edam_file = self.assign("remag_specific_section", "edam_file", ismandatory=True)
            self.output_yaml = self.assign("remag_specific_section", "output_yaml", ismandatory=True)

    @classmethod
    def load_configuration(cls, configfile):
        """
        :param configfile:
        :return:
        """
        configuration = configparser.ConfigParser()
        configuration.read(configfile)
        return configuration

    def assign(self, section, key, ismandatory=True, message=None, boolean=False):
        """
            return value if key exists in config.ini file or an error or None if not, depending on whether the option
            is mandatory or not
        """
        if ismandatory:
            if self.exist(section, key):
                return self.getvalue(section, key, boolean=boolean)
            else:
                if message:
                    raise KeyError(message)
                else:
                    raise KeyError("{0} option is mandatory".format(key))
        if not ismandatory:
            if self.exist(section, key):
                return self.getvalue(section, key, boolean=boolean)
            else:
                return None

    def getvalue(self, section, key, boolean=False):
        """
            test if key is a boolean and return value
        """
        if boolean:
            return self.conf.getboolean(section, key)
        else:
            return self.conf.get(section, key)

    def exist(self, section, key):
        """
            Check if key exist in the section
        """
        if key in self.conf[section] and self.conf.get(section, key):
            return True
        else:
            return False
