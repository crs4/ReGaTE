import re
import copy
import urllib
import logging
import requests
from datauri import DataURI
from urllib.parse import urljoin
from .const import REGATE_SEPARATOR, TOOLSHED_PREFIX_ID, REGATE_PREFIX_ID
from .edam import (
    DEFAULT_EDAM_DATA, DEFAULT_EDAM_FORMAT, DEFAULT_EDAM_OPERATION,
    DEFAULT_EDAM_TOPIC, find_edam_format, find_edam_data, edam_to_uri
)

logger = logging.getLogger()


def map_tool(galaxy_metadata, conf, edam_mapping):
    """
    Extract informations from a galaxy json tool and return the general json in the biotools format
    :param tool_meta_data: galaxy json tool
    :conf : regate.ini config file
    :return: biotools dictionary
    :rtype: dictionary
    """
    tool_id = build_biotool_id(conf, galaxy_metadata)
    mapping = {
        ##### SUMMARY GROUP #########################################################################################
        'name': build_tool_name(galaxy_metadata['name'], conf.prefix_toolname, conf.suffix_toolname),
        'description': build_tool_description(galaxy_metadata),
        'homepage': "{0}?tool_id={1}".format(urljoin(conf.galaxy_url, '/tool_runner'),
                                             requests.utils.quote(galaxy_metadata['id'])),
        'version': [galaxy_metadata['version']],
        # TODO: check if required or auto filled on registration
        # to obtain an uniq id in galaxy we need the toolshed repository, the owner, the xml toolid, the xml version,
        # if the tool provide from a toolshed, if not we need the xml toolid and the xml version only
        # The easiest : use id of the tool
        'biotoolsID': tool_id,
        'biotoolsCURIE': 'biotools:{}'.format(tool_id),
        'otherID': [
            {
                'type': "biotoolsCURIE",
                'value': "{}_{}".format(REGATE_PREFIX_ID, tool_id),
                'version': galaxy_metadata['version']
            }
        ],

        ##### FUNCTION GROUP ######################################################################################
        'function': build_function_dict(galaxy_metadata, edam_mapping),

        ##### LABELS GROUP ######################################################################################
        'toolType': ["Web application"],
        'topic': galaxy_metadata['edam_topics'] \
            if 'edam_topics' in galaxy_metadata and len(galaxy_metadata['edam_topics']) > 0 \
            else [DEFAULT_EDAM_TOPIC],
        # TODO: check if can be detected from XML configuration file
        'operatingSystem': ['Linux'],
        'language': [],
        'license': '',  # TOD: check whether can be dectected inspecting the web site
        'collectionID': [conf.resourcename],
        'maturity': '',  # Available values: Mature, Emerging, Legacy
        # Avaialbe values: "Free of charge", "Free of charge (with restrictions)", "Commercial"
        'cost': '',
        # Available values: "Open access", "Restricted access",
        'accessibility': [conf.accessibility],
        'ELIXIRPlatform': '',
        'ELIXIRNode': '',

        ##### Link GROUP ######################################################################################
        # Miscellaneous links for the software: e.g., repository, issue tracker, etc.
        # see https://biotools.readthedocs.io/en/latest/curators_guide.html#linktype for the available link types
        'link': [],

        ##### Download GROUP ######################################################################################
        'download': [],

        ##### Documentation GROUP ######################################################################################
        'documentation': [],

        ##### Publication GROUP ######################################################################################
        'publication': [],  # TODO: see how "/citations" works

        ##### Relation GROUP ######################################################################################
        'relation': [],  # TODO: see if it is reasonable to connect tools on platform basis

        ##### Credit GROUP ######################################################################################
        'credit': [
            {
                'name': conf.contactName,
                'email': conf.contactEmail,
                'url': conf.contactUrl,
                'tel': conf.contactTel,
                'typeEntity': conf.contactTypeEntity,
                'typeRole': conf.contactTypeRole.split("."),
                # FIXME: to be completed
                'orcidid': '',
                'gridid': '',
                'note': ''
            }
        ]
    }

    ### Add ToolShedRepository ###
    if 'tool_shed_repository' in galaxy_metadata:
        toolshed = galaxy_metadata['tool_shed_repository']
        mapping['otherID'].extend([
            {
                'type': "biotoolsCURIE",
                'value': "{}{}{}{}{}{}{}".format(TOOLSHED_PREFIX_ID, REGATE_SEPARATOR,
                                                 toolshed['tool_shed'], REGATE_SEPARATOR,
                                                 toolshed['owner'], REGATE_SEPARATOR,
                                                 toolshed['name'], REGATE_SEPARATOR),
                'version': toolshed['changeset_revision']
            }
        ])

    ##### Download GROUP ######################################################################################
    tool_archive = galaxy_metadata.get_wrapper_archive()
    if tool_archive:
        mapping['download'].extend([
            {
                'type': 'Tool wrapper (galaxy)',
                'url': build_download_link(conf, tool_archive,
                                           filename="{}.tar.gz".format(tool_id),
                                           mimetype="application/tar+gzip"),
                'note': "Galaxy Tool tar.gz archive encoded as base64 dataURI on the 'data' URL parameter.",
                'version': galaxy_metadata['version']

            },
            {
                'type': 'Tool wrapper (galaxy)',
                'url': build_download_link(conf, galaxy_metadata.to_json(),
                                           filename="{}.json".format(galaxy_metadata['id']),
                                           mimetype="application/json"),
                'note': "JSON representation of the Galaxy tool as base64 encoded data URI on the 'data' URL parameter.",
                'version': galaxy_metadata['version']

            }
        ])
    if not conf.transient_instance:
        mapping['download'].extend([
            {
                'type': 'Tool wrapper (galaxy)',
                'url': galaxy_metadata.download_link,
                'note': "Download {} tool from the Galaxy platform {}".format(galaxy_metadata['name'], conf.galaxy_url),
                'version': galaxy_metadata['version']
            }
        ])

    ##### Link GROUP ######################################################################################
    # Miscellaneous links for the software: e.g., repository, issue tracker, etc.
    # see https://biotools.readthedocs.io/en/latest/curators_guide.html#linktype for the available link types
    if not conf.transient_instance:
        mapping['link'].extend([
            {
                'type': 'Galaxy service',
                'url': urljoin(conf.galaxy_url, galaxy_metadata['link']),
                'note': 'Run the "{}" tool on a Galaxy Platform'.format(galaxy_metadata['id'])
            },
            {
                'type': 'Other',
                'url': galaxy_metadata.metadata_link,
                'note': "Tool metadata available on the Galaxy Platform"
            }
        ])

    result = copy.deepcopy(mapping)
    clean_dict(result)
    return result


def map_workflow(galaxy_metadata, conf, mapping_edam):
    """
    Extract informations from a galaxy json tool and return the general json in the biotools format
    :param tool_meta_data: galaxy json tool
    :conf : regate.ini config file
    :return: biotools dictionary
    :rtype: dictionary
    """
    tools = map_workflow_tools(galaxy_metadata, conf, mapping_edam)
    topics = {topic['uri']: topic for t in tools.values() for topic in t['topic']}
    operations = [op for t in tools.values() for op in t['function']]
    name = build_tool_name(galaxy_metadata['name'], conf.prefix_toolname, conf.suffix_toolname)
    mapping = {
        ##### SUMMARY GROUP #########################################################################################
        'name': build_tool_name(name, conf.prefix_toolname, conf.suffix_toolname),
        # FIXME: define a default description if annotation is None
        'description': "workflow description: " + galaxy_metadata['annotation'],
        'homepage': "{}?id={}".format(urljoin(conf.galaxy_url, '/workflow/display_by_id'), galaxy_metadata['uuid']),
        'version': [str(galaxy_metadata['version'])],
        # TODO: check if required or auto filled on registration
        # to obtain an uniq id in galaxy we need the toolshed repository, the owner, the xml toolid, the xml version,
        # if the tool provide from a toolshed, if not we need the xml toolid and the xml version only
        # The easiest : use id of the tool
        'biotoolsID': galaxy_metadata['uuid'],
        'biotoolsCURIE': 'biotools:{}'.format(galaxy_metadata['uuid']),
        'otherID': [
            {
                'type': "biotoolsCURIE",
                'value': "{}_{}".format(REGATE_PREFIX_ID, galaxy_metadata['uuid']),
                'version': galaxy_metadata['version']
            }
        ],

        ##### FUNCTION GROUP ######################################################################################
        'function': operations,

        ##### LABELS GROUP ######################################################################################
        'toolType': ["Workflow"],
        'topic': [t for t in topics.values()],
        # TODO: check if can be detected from XML configuration file
        'operatingSystem': ['Linux'],
        'language': [],
        'license': '',  # TOD: check whether can be dectected inspecting the web site
        'collectionID': [conf.resourcename],
        'maturity': '',  # Available values: Mature, Emerging, Legacy
        # Avaialbe values: "Free of charge", "Free of charge (with restrictions)", "Commercial"
        'cost': '',
        # Available values: "Open access", "Restricted access",
        'accessibility': [conf.accessibility],
        'ELIXIRPlatform': '',
        'ELIXIRNode': '',

        ##### Link GROUP ######################################################################################
        # Miscellaneous links for the software: e.g., repository, issue tracker, etc.
        # see https://biotools.readthedocs.io/en/latest/curators_guide.html#linktype for the available link types
        'link': [],

        ##### Download GROUP ######################################################################################
        'download': [
            {
                'type': 'Tool wrapper (galaxy)',
                'url': build_download_link(conf, galaxy_metadata.to_json(),
                                           filename="{}.json".format(galaxy_metadata['uuid']),
                                           mimetype="application/json"),
                'note': "Galaxy Workflow definition as base64 encoded data URI on the 'data' URL parameter.",
                'version': galaxy_metadata['version']
            }
        ],

        ##### Documentation GROUP ######################################################################################
        'documentation': [],

        ##### Publication GROUP ######################################################################################
        'publication': [],  # TODO: see how "/citations" works

        ##### Relation GROUP ######################################################################################
        'relation': [],  # TODO: see if it is reasonable to connect tools on platform basis

        ##### Credit GROUP ######################################################################################
        'credit': [
            {
                'name': conf.contactName,
                'email': conf.contactEmail,
                'url': conf.contactUrl,
                'tel': conf.contactTel,
                'typeEntity': conf.contactTypeEntity,
                'typeRole': conf.contactTypeRole.split("."),
                # FIXME: to be completed
                'orcidid': '',
                'gridid': '',
                'note': ''
            }
        ]
    }

    # Miscellaneous links for the software: e.g., repository, issue tracker, etc.
    # see https://biotools.readthedocs.io/en/latest/curators_guide.html#linktype for the available link types
    if not conf.transient_instance:
        mapping['link'].append({
            'type': 'Galaxy service',
            'url': galaxy_metadata.service_link,
            'note': 'View and run the workflow "{}" on the Galaxy Platform'.format(galaxy_metadata['name'])
        })

    ##### Download GROUP ######################################################################################
    if not conf.transient_instance:
        mapping['download'].append({
            'type': 'Tool wrapper (galaxy)',
            'url': galaxy_metadata.download_link,
            'note': build_description_note(galaxy_metadata) + " [provided by Galaxy Platform]",
            'version': galaxy_metadata['version']
        })

    result = copy.deepcopy(mapping)
    clean_dict(result)
    return result


def build_biotool_id(conf, galaxy_metadata):
    return build_tool_name(galaxy_metadata['id'], conf.prefix_toolname, conf.suffix_toolname)


def map_workflow_tools(galaxy_metadata, config, mapping_edam):
    tools = {}
    tools_steps = galaxy_metadata["inputs"] + galaxy_metadata["operations"] + galaxy_metadata["outputs"]
    for tool in tools_steps:
        tools[tool['id']] = map_tool(tool, config, mapping_edam)
    return tools


def build_tool_description(galaxy_metadata):
    return format_description(galaxy_metadata['description']) if galaxy_metadata['description'] != '' \
        else 'Galaxy tool {0}.'.format(galaxy_metadata['name'])


def build_download_link(config, data, filename="data", mimetype="application/json", charset='utf-8'):
    return "{}?{}".format(
        config.data_uri_prefix,
        urllib.parse.urlencode({
            'filename': filename,
            'data': DataURI.make(mimetype, charset=charset, base64=True, data=data)
        })
    )


def check_str_data_length(data, length=1000):
    if not data or len(data) == 0:
        return ""
    return "{}...".format(data[:(length - 2)]) if len(data) > length else data


def build_description_note(galaxy_metadata):
    return "{} ({})".format(galaxy_metadata["name"],
                            re.sub('^[^a-zA-Z0-9_]+|[^a-zA-Z0-9]+$', '', build_tool_description(galaxy_metadata))) \
        if "description" in galaxy_metadata and galaxy_metadata["description"] \
        else galaxy_metadata["name"]


def format_description(description):
    """
    Test the first and last char of a description and replace them
    with the format adapted to Elixir
    """
    try:
        size = len(description)
        if description[size - 1] == '.':
            return description[0].upper() + description[1:size]
        else:
            return description[0].upper() + description[1:size] + '.'
    except IndexError:
        logger.warning(description)


def inputs_extract(inputs_json, mapping_edam):
    """
    Extract type data param of a galaxy json tool inputs and return a list of dictionary in the json biotools format
    :param inputs_json: inputs part of a json tool
    :return: list of dictionary in the json biotools format
    :rtype: list
    """

    def inputs_extract_data(data_json):
        """
        Save param type data from a json tool galaxy in a list
        :param data_json:
        :return: None
        """
        data_types = None
        data_formats = None
        if "edam" in data_json and "edam_formats" in data_json["edam"]:
            data_formats = [{'uri': edam_to_uri(f, 'format')} for f in data_json["edam"]["edam_formats"]]
        else:
            data_formats = [find_edam_format(extension, mapping_edam) for extension in data_json["extensions"]]
        if "edam" in data_json and "edam_data" in data_json["edam"]:
            data_types = [{'uri': edam_to_uri(d, 'data')} for d in data_json["edam"]["edam_data"]]
        else:
            data_types = [find_edam_data(extension, mapping_edam) for extension in data_json["extensions"]]

        if len(data_types) == 1:
            data_item = {
                'data': data_types[0],
                'format': data_formats,
                'dataHandle': data_json['name'],
                'dataDescription': data_json['label']
            }
        else:
            data_item = {
                'data': DEFAULT_EDAM_DATA,
                'format': data_formats,
                'dataHandle': data_json['name'],
                'dataDescription': data_json['label']
            }
        listdata.append(data_item)

    def inputs_extract_repeat(repeat_json):
        """
        Recursive function in order to explore repeat param of a galaxy json tool
        :param repeat_json: Repeat param part of a galaxy json tool
        :return: None
        """
        for dictinprep in repeat_json['inputs']:
            if dictinprep['type'] == "conditional":
                inputs_extract_conditional(dictinprep)
            elif dictinprep['type'] == "repeat":
                inputs_extract_repeat(dictinprep)
            elif dictinprep["type"] in ["data", "datacollection"]:
                inputs_extract_data(dictinprep)

    def inputs_extract_conditional(conditional_json):
        """
        Recursive function in order to explore conditional param of a galaxy json tool
        :param conditional_json: conditional param part of a galaxy json tool
        :return: None
        """
        for case in conditional_json["cases"]:
            for dictinpcond in case["inputs"]:
                if dictinpcond['type'] == "conditional":
                    inputs_extract_conditional(dictinpcond)
                elif dictinpcond['type'] == "repeat":
                    inputs_extract_repeat(dictinpcond)
                elif dictinpcond["type"] in ["data", "datacollection"]:
                    inputs_extract_data(dictinpcond)

    listdata = list()
    for dictinp in inputs_json:
        if dictinp['type'] == "conditional":
            inputs_extract_conditional(dictinp)
        elif dictinp['type'] == "repeat":
            inputs_extract_repeat(dictinp)
        elif dictinp["type"] in ["data", "datacollection", "data_collection_input"]:
            inputs_extract_data(dictinp)
    # if any([len(data['dataType'])==0 or len(data['dataFormat'])==0 for data in listdata]):
    #    logger.warning("data/formats mapping not found for inputs_json:" + str(inputs_json))
    return listdata


def outputs_extract(outputs_json, mapping_edam, biotools_inputs):
    """
    Extract type output param of a galaxy json tool outputs and return a list of dictionary in the json biotools format
    :param outputs_json: output param of a galaxy json tool outputs
    :return: list of dictionary in the json biotools format
    :rtype: dictionary
    """
    listoutput = list()
    for output in outputs_json:
        if output['format'] != 'input':
            try:
                edam_data = {'uri': edam_to_uri(output["edam_data"], 'data')} \
                    if "edam_data" in output else find_edam_data(output['format'], mapping_edam)
                edam_format = {'uri': edam_to_uri(output["edam_format"], 'format')} \
                    if "edam_format" in output else find_edam_format(output['format'], mapping_edam)
                outputdict = {
                    'data': edam_data,
                    'format': [edam_format],
                    'dataHandle': output['format'], 'dataDescription': output['name']
                }
            except KeyError:
                logger.warning(
                    "EDAM MAPPING: TERM ----{0}---- is missing from EDAM current version".format(output['format']))
        else:
            # FIXME: copying the datatype/format from the source would work if only the Galaxy API used
            # by bioblend sent the format_source information
            # biotools_input_source = [biotools_input for biotools_input in biotools_inputs if biotools_input['dataHandle']==output['format_source']][0]
            # outputdict = {'dataType': biotools_input_source['dataType'],
            #         'dataFormat': biotools_input_source['dataFormat'],
            #         'dataHandle': output['format'], 'dataDescription': output['name']
            #          }
            outputdict = {'data': DEFAULT_EDAM_DATA,
                          'format': [DEFAULT_EDAM_FORMAT],
                          'dataHandle': output['format'], 'dataDescription': output['name']
                          }
        listoutput.append(outputdict)
    return listoutput


def build_tool_name(tool_id, prefix, suffix):
    """
    @tool_id: tool_id
    builds the tool_name with the tool id, its version
    and the prefix/suffix defined in the config file
    """
    try:
        tool_name = str.split(tool_id, '/')[-2]
    except IndexError:
        tool_name = tool_id
    tool_name = re.sub('[^0-9a-zA-Z\_\-\.\~]', '-', tool_name)
    if len(tool_name) > 100:
        tool_name = tool_name[:100]
    if prefix and (len(tool_name) + len(prefix) <= 100):
        tool_name = str(prefix) + '-' + tool_name
    if suffix and (len(tool_name) + len(suffix) <= 100):
        tool_name = tool_name + '-' + str(suffix)
    return tool_name


def build_function_dict(json_tool, mapping_edam):
    """
    Extract information from a galaxy json tool and return a list of functions in the json biotools format
    :param json_tool: galaxy json tool
    :return: list of functions in the json biotools format
    :rtype: list
    """
    list_func = []
    listinps = inputs_extract(json_tool['inputs'], mapping_edam)
    listoutps = outputs_extract(json_tool['outputs'], mapping_edam, listinps)
    if 'edam_operations' in json_tool and len(json_tool['edam_operations']) > 0:
        edam_operation = [{'url': edam_to_uri(o, 'operation')} for o in json_tool['edam_operations']]
    else:
        edam_operation = [DEFAULT_EDAM_OPERATION]
    logger.debug("EDAM operation: %r -- %r -- %r", edam_operation, DEFAULT_EDAM_OPERATION, json_tool['edam_operations'])
    cmd = ""
    note = build_description_note(json_tool)
    if 'config' in json_tool and json_tool['config']:
        cmd = json_tool['config']['command'] if 'command' in json_tool['config'] else ""
    func_dict = {
        'operation': [DEFAULT_EDAM_OPERATION],
        'output': listoutps,
        'input': listinps,
        'cmd': check_str_data_length(cmd),
        'note': note,
    }
    list_func.append(func_dict)
    return list_func


def clean_dict(jsondict):
    """
    :param jsondict:
    :return:
    """
    for sonkey, sonvalue in list(jsondict.items()):
        if sonvalue:
            if isinstance(sonvalue, dict):
                clean_dict(sonvalue)
            if isinstance(sonvalue, list):
                clean_list(sonvalue)

        if not sonvalue:
            del jsondict[sonkey]
    return


def clean_list(jsonlist):
    """
    :param jsonlist:
    :return:
    """
    nullindexlist = []
    for elem in range(len(jsonlist)):
        if isinstance(jsonlist[elem], dict):
            clean_dict(jsonlist[elem])
        if isinstance(jsonlist[elem], list):
            clean_list(jsonlist[elem])
        if len(jsonlist[elem]) == 0:
            nullindexlist.append(elem)
    if nullindexlist:
        nullindexlist.sort(reverse=True)
        for i in nullindexlist:
            jsonlist.pop(i)
    return


def find_biotools_regate_id(tool):
    if tool:
        for oid in tool["otherID"]:
            if oid["value"].startswith(REGATE_PREFIX_ID):
                return oid
    return None


def find_biotools_toolshed_id(tool):
    toolshed_id = None
    try:
        for oid in tool["otherID"]:
            if oid["value"].startswith(TOOLSHED_PREFIX_ID):
                tid_parts = oid["value"].split(REGATE_SEPARATOR)
                toolshed_id = {
                    "tool_shed": tid_parts[1],
                    "owner": tid_parts[2],
                    "name": tid_parts[3],
                    "changeset_revision": oid["version"],
                }
    except Exception as e:
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)
    return toolshed_id
