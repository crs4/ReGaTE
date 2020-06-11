import os
import re
import logging
import ruamel.yaml
from bioblend.galaxy import Client
from bioblend.galaxy.datatypes import DatatypesClient

logger = logging.getLogger()

DEFAULT_EDAM_DATA = {
    "term": "Data",
    "uri": "http://edamontology.org/data_0006"
}
DEFAULT_EDAM_FORMAT = {
    "term": "Textual format",
    "uri": "http://edamontology.org/format_2330"
}
DEFAULT_EDAM_OPERATION = {
    "uri": "http://edamontology.org/operation_0004",
    "term": "Operation"
}
DEFAULT_EDAM_TOPIC = {
    "uri": "http://edamontology.org/topic_0003",
    "term": "Topic"
}

_ROOT = os.path.abspath(os.path.dirname(__file__))


def get_data_path(path):
    return os.path.join(_ROOT, 'data', path)


def build_edam_dict(yaml_file):
    """
    :param yaml_file:
    :return:
    """
    # map_edam = extract_edam_from_galaxy()
    with open(yaml_file, "r") as file_edam:
        map_edam = ruamel.yaml.load(file_edam, Loader=ruamel.yaml.Loader)
        for key, value in map_edam.items():
            for term in value['formats']:
                term['uri'] = edam_to_uri(term['uri'], 'format')
            for term in value['data']:
                term['uri'] = edam_to_uri(term['uri'], 'data')
    return map_edam


def load_edam_dict(config):
    # if not EDAM_DICT:
    if config.yaml_file:
        EDAM_DICT = build_edam_dict(config.yaml_file)
    else:
        EDAM_DICT = build_edam_dict(get_data_path('yaml_mapping.yaml'))
    return EDAM_DICT


def find_edam_format(format_name, mapping_edam):
    """
    :param format_name:
    :param mapping_edam:
    :return: edam format from a format (extension) in galaxy
    """
    if format_name in mapping_edam:
        edam_format = mapping_edam[format_name]['formats'][0]
    else:
        edam_format = DEFAULT_EDAM_FORMAT
    return edam_format


def find_edam_data(format_name, mapping_edam):
    """
    :param format_name:
    :param mapping_edam:
    :return edam data of a defined format_name:
    """
    if format_name in mapping_edam:
        edam_data = mapping_edam[format_name]['data'][0]
    else:
        edam_data = DEFAULT_EDAM_DATA
    return edam_data


def edam_to_uri(edam, element):
    """
    :param edam:
    :returns edam uri from an edam term:
    """
    try:
        uri = re.split("_|:", edam)
        if len(uri) == 2:
            uri = "http://edamontology.org/{}_{:0>4d}".format(uri[0], int(uri[1]))
        else:
            uri = "http://edamontology.org/{}_{:0>4d}".format(uri[1], int(uri[2]))
    except TypeError:
        if element == 'data':
            uri = "http://edamontology.org/data_0006"
        else:
            uri = "http://edamontology.org/format_1915"
        logger.warning("EDAM MAPPING: TERM ----{0}---- is missing from EDAM current version".format(edam))
    return uri


class EdamDatatypesClient(DatatypesClient):
    """
    Override of the bioblend DatatypesClient class to add a get_edam_formats method
    """

    def get_edam_formats(self):
        """
        Displays a collection (dict) of edam formats.
        :rtype: dict
        :return: A dict of  individual edam_format.
                 For example::
             {
                "RData": "format_2333",
                "Roadmaps": "format_2561",
                "Sequences": "format_1929",
                "ab1": "format_2333",
                "acedb": "format_2330",
                "affybatch": "format_2331",
                "afg": "format_2561",
                "arff": "format_2330",
                "asn1": "format_2330",
                "asn1-binary": "format_2333"}
        """
        url = self.gi._make_url(self)
        url = '/'.join([url, "edam_formats"])

        return Client._get(self, url=url)