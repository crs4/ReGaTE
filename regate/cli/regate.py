#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Created on Oct. 23, 2014

@author: Olivia Doppelt-Azeroual, CIB-C3BI, Institut Pasteur, Paris
@author: Fabien Mareuil, CIB-C3BI, Institut Pasteur, Paris
@author: Hervé Ménager, CIB-C3BI, Institut Pasteur, Paris
@contact: olivia.doppelt@pasteur.fr
@project: ReGaTE
@githuborganization: C3BI-pasteur-fr
"""

import sys
import os
import json
import glob
import logging
import requests
import itertools
import ruamel.yaml
from logging.handlers import RotatingFileHandler

from regate.edam import load_edam_dict
from regate.objects import DynamicObject
from regate.biotools import BioToolsPlatform
from regate.config import load_config, generate_template
from regate.const import REGATE_DATA_FILE, RESOURCE, PLATFORM
from regate.galaxy import GalaxyPlatform, build_filename, get_galaxy_resource_id_label
from regate.mapping import map_tool, map_workflow, find_biotools_toolshed_id
from regate.utils import write_json_files, get_resource_folder, decode_datafile_from_datauri
from regate.cli.helpers import (
    warning, failure, bold,
    prompt_platform_resource_selection,
    print_done, print_error, print_exists, prompt, print_logo, build_cli_parser, success
)

# init root logger
logger = logging.getLogger()


def configure_logging(opts):
    formatter = logging.Formatter('%(asctime)s :: %(levelname)s :: %(message)s')

    logger.setLevel(logging.DEBUG if opts.debug else logging.INFO)

    # Append logger to the console
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    if opts.debug:
        stream_handler.setLevel(logging.DEBUG)
    logger.addHandler(stream_handler)

    if opts.save_logs:
        log_dir = opts.save_logs
        logger.info("Saving logs to directory %s", log_dir)
        # first logger
        file_handler = RotatingFileHandler(os.path.join(log_dir, 'activity.log'), 'a', 1000000, 1)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # second logger
        file_handler_edam = RotatingFileHandler(os.path.join(log_dir, 'edam_mapping.log'), 'a', 1000000, 1)
        file_handler_edam.setLevel(logging.WARNING)
        file_handler_edam.setFormatter(formatter)
        logger.addHandler(file_handler_edam)


def template(args):
    logger.debug("cmd: %s", args.command)
    generate_template(args.filename)


def export(args):
    logger.debug("cmd: %s", args.command)
    if args.platform == "galaxy":
        export_from_galaxy(args)
    elif args.platform == "biotools":
        export_from_biotools(args)
    else:
        raise Exception("Unsupported platform ''")


def export_from_galaxy(options):
    # Load configuration file
    config = load_config(options)
    # configure the Galaxy instance
    GalaxyPlatform.get_instance().configure(config.galaxy_url, config.api_key)

    # Export tools
    tools_selected = None
    tools_exported = None
    tools_errors = None
    if options.resource == RESOURCE.TOOL.value or options.resource == RESOURCE.ALL.value:
        tools_selected, tools_exported, tools_errors = \
            export_galaxy_resources(config, RESOURCE.TOOL,
                                    options.filter if "filter" in options else None,
                                    ignore_list=config.tools_default)
    # Export workflows
    workflows_selected = None
    workflows_exported = None
    workflows_errors = None
    # TODO: add ignore list for workflows, ignore=config.tools_default)
    if options.resource == RESOURCE.WORKFLOW.value or options.resource == RESOURCE.ALL.value:
        workflows_selected, workflows_exported, workflows_errors = \
            export_galaxy_resources(config, RESOURCE.WORKFLOW,
                                    options.filter if "filter" in options else None)
    # Publish tool/workflows
    biotools_json_files = None
    tools_pushed = tools_push_errors = None
    workflows_pushed = workflows_push_errors = None
    if options.push:
        # Build list of BioTools JSON files to publish
        biotools_json_files = []
        # collect biotools files
        for biotool in itertools.chain(tools_exported or [], workflows_exported or []):
            tools_dir = get_resource_folder(config,
                                            PLATFORM.BIOTOOLS.value,
                                            "workflow" if biotool["toolType"][0] == "Workflow" else "tool")
            filename = os.path.join(tools_dir, "{}.json".format(
                build_filename(biotool['biotoolsID'], biotool['version'][0])))
            if os.path.exists(filename):
                biotools_json_files.append(filename)
        # Publish BioTools files
        if len(biotools_json_files) == 0:
            print(warning(
                "\n  WARNING: no resource to publish on the ELIXIR registry '{}'\n".format(config.bioregistry_host)))
        else:
            tools_pushed, tools_push_errors, workflows_pushed, workflows_push_errors = \
                push_to_biotools(config, biotools_json_files, config.resourcename)
    #
    print_report(tools_selected=tools_selected, tools_exported=tools_exported, tools_errors=tools_errors,
                 tools_pushed=tools_pushed, tools_push_errors=tools_push_errors,
                 workflows_selected=workflows_selected,
                 workflows_exported=workflows_exported, workflows_errors=workflows_errors,
                 workflows_pushed=workflows_pushed, workflows_push_errors=workflows_push_errors)


def print_report(**kwargs):
    print("\n")
    for resource in ("tools", "workflows"):
        selected = kwargs.get("{}_selected".format(resource))
        exported = kwargs.get("{}_exported".format(resource))
        pushed = kwargs.get("{}_pushed".format(resource))
        errors = kwargs.get("{}_errors".format(resource))
        push_errors = kwargs.get("{}_push_errors".format(resource))
        if selected:
            print(" > {} {} selected, {} export ok, {} push ok, {} export failures, {} push errors".format(
                bold("{}:{}".format(resource.upper(), ' ' * 4 if resource == "tools" else '')),
                warning(len(selected) if selected else 0),
                success(len(exported) if exported else 0),
                success(len(pushed) if pushed else 0),
                failure(len(errors) if errors else 0),
                failure(len(push_errors) if push_errors else 0)))
    print("\n")


def export_galaxy_resources(config, resource_type, resources_filter=None, ignore_list=None):
    resources_metadata = None
    resource_id_label = get_galaxy_resource_id_label(resource_type)
    resource_loader = getattr(GalaxyPlatform.get_instance(), "get_{}s".format(resource_type.value))
    if not resources_filter and not config.no_interactive:
        resources_metadata = prompt_platform_resource_selection(PLATFORM.GALAXY,
                                                                resource_type,
                                                                resource_loader)
    print(bold("> Loading Galaxy {}s... ".format(resource_type.value)), end='', flush=True)
    if not resources_metadata:
        resources_metadata = resource_loader(resources_filter, details=True, ignore=ignore_list)
        print_done()
    else:
        to_load = resources_metadata
        resources_metadata = resource_loader(resources_metadata, details=True)
        if len(to_load) > len(resources_metadata):
            logger.error("Error when loading {}s metadata.".format(resource_type.value))
            print(failure("ERROR: unable to load the following {}s...".format(resource_type.value)))
            for w in [wf for wf in to_load
                      if wf[resource_id_label] not in [wfm[resource_id_label] for wfm in resources_metadata]]:
                print("  {} {} (id {}, version {})".format(failure("X"), w['name'], w[resource_id_label], w['version']))
        else:
            print_done()
    # Generate BioTools files for both tools and workflows
    exported, errors = build_biotools_files(config, resource_type=resource_type, galaxy_metadata=resources_metadata)
    return resources_metadata, exported, errors


def build_biotools_files(config, resource_type, galaxy_metadata):
    """
    :param tools_metadata:
    :return:
    """
    # setup tools paths
    tools_dir = get_resource_folder(config, "biotools", resource_type.value)
    if not os.path.exists(tools_dir):
        os.makedirs(tools_dir)

    # load edam mapping
    mapping_edam = load_edam_dict(config)

    # write tools
    errors = []
    mappings = []
    if len(galaxy_metadata) > 0:
        print(bold("> Exporting {}s to the bio.tools format...".format(resource_type.value)))
    for metadata in galaxy_metadata:
        try:
            print("  - {} (id {}, version {})...".format(metadata["name"],
                                                         metadata[get_galaxy_resource_id_label(resource_type)],
                                                         metadata["version"]), end='', flush=True)
            biotools_metadata = map_tool(metadata, config, mapping_edam) \
                if resource_type == RESOURCE.TOOL else map_workflow(metadata, config, mapping_edam)
            file_name = build_filename(metadata[get_galaxy_resource_id_label(resource_type)], metadata['version'])
            write_json_files(file_name, biotools_metadata, tools_dir)
            with open(os.path.join(tools_dir, "{}.yaml".format(file_name)), 'w') as outfile:
                ruamel.yaml.safe_dump(biotools_metadata, outfile)
            mappings.append(biotools_metadata)
            print_done()
        except Exception as e:
            print_error()
            errors.append(metadata)
            if logger.level == logging.DEBUG:
                logger.exception(e)
    return mappings, errors


def export_from_biotools(options):
    # Load configuration file
    config = load_config(options)
    # config BioToolsPlatform instance
    BioToolsPlatform.get_instance().configure(config)
    # Export tools
    tools_selected = None
    tools_exported = None
    tools_errors = None
    if options.resource == RESOURCE.TOOL.value or options.resource == RESOURCE.ALL.value:
        tools_selected, tools_exported, tools_errors = \
            export_biotools_resources(config, RESOURCE.TOOL,
                                      options.filter if "filter" in options else None)
    # Export workflows
    workflows_selected = None
    workflows_exported = None
    workflows_errors = None
    workflows_failures = None
    if options.resource == RESOURCE.WORKFLOW.value or options.resource == RESOURCE.ALL.value:
        workflows_selected, workflows_exported, workflows_failures = \
            export_biotools_resources(config, RESOURCE.WORKFLOW,
                                      options.filter if "filter" in options else None)
    # Publish tool/workflows
    tools_pushed = tools_push_errors = None
    workflows_pushed = workflows_push_errors = None
    if options.push:
        # Build list of BioTools JSON files to publish
        galaxy_json_files = [resource[REGATE_DATA_FILE] for resource in tools_exported] + \
                            [resource[REGATE_DATA_FILE] for resource in workflows_exported]
        tools_pushed, tools_push_errors, workflows_pushed, workflows_push_errors = \
            push_to_galaxy(config, galaxy_json_files, check_exists=True)
    #
    print_report(tools_selected=tools_selected, tools_exported=tools_exported, tools_errors=tools_errors,
                 tools_pushed=tools_pushed, tools_push_errors=tools_push_errors,
                 workflows_selected=workflows_selected,
                 workflows_exported=workflows_exported, workflows_errors=workflows_errors,
                 workflows_pushed=workflows_pushed, workflows_push_errors=workflows_push_errors)


def export_biotools_resources(config, resource_type, resource_filter=None):
    biotools = None
    bi = BioToolsPlatform.get_instance()
    resource_loader = bi.get_tools if resource_type == RESOURCE.TOOL else bi.get_workflows
    if not config.no_interactive and not resource_filter:
        biotools = prompt_platform_resource_selection(PLATFORM.BIOTOOLS,
                                                      resource_type,
                                                      resource_loader)
    # Build the list of tools to export
    if not biotools:
        # NOTE: the 'only_regate_tools' constraint might be relaxed
        print(bold("> Loading list of bio.tools {}s... ".format(resource_type.value)), end='', flush=True)
        biotools = resource_loader(identifier_list=resource_filter.split(',') if resource_filter else None)
        print_done()
    # init output folder
    output_folder = get_resource_folder(config, PLATFORM.GALAXY.value, resource_type.value)
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    success = []
    failures = []
    if len(biotools) == 0:
        print(warning("\n  WARNING: no bio.tools {} to export\n".format(resource_type.value)))
    else:
        print(bold("> Exporting bio.tools {}s to the Galaxy format... ".format(resource_type.value)))
        success, failures = build_galaxy_files(config, resource_type, biotools)
    return biotools, success, failures


def build_galaxy_files(config, resource_type, biotools_metadata):
    success = []
    failures = []
    build_handler = build_galaxy_tool_files if resource_type == RESOURCE.TOOL else build_galaxy_workflow_files
    for data in biotools_metadata:
        print("  - {} (id {}, version {})... ".format(data["name"],
                                                      data["biotoolsID"],
                                                      data["version"][0]), end='', flush=True)
        result = build_handler(config, data)
        if result:
            success.append(result)
        else:
            failures.append(data)
    return success, failures


def build_galaxy_tool_files(config, tool):
    output_folder = get_resource_folder(config, PLATFORM.GALAXY.value, RESOURCE.TOOL.value)
    toolshed_info = find_biotools_toolshed_id(tool)
    if toolshed_info:
        data_json = {
            "id": tool["biotoolsID"],
            "model_class": "Tool",
            "name": tool["name"],
            "version": tool["version"][0],
            "panel_section_name": config.resourcename,
            "tool_shed_repository": toolshed_info,
        }
        data_file = os.path.join(output_folder, "{}.json".format(tool["biotoolsID"]))
        try:
            with open(data_file, "w") as out:
                out.write(json.dumps(data_json, indent=2))
                tool[REGATE_DATA_FILE] = data_file
            print_done()
            return tool
        except Exception as e:
            print_error()
            if logger.isEnabledFor(logging.DEBUG):
                logger.exception(e)
    else:
        tool_folder = os.path.join(output_folder, "not_imported", tool["name"])
        os.makedirs(tool_folder, exist_ok=True)
        try:
            links = [link["url"] for link in tool["download"]
                     if link["url"].startswith(config.data_uri_prefix)]
            if len(links) == 0:
                raise Exception("No DataURI link found")
            for link in links:
                filename, datafile = decode_datafile_from_datauri(link, output_folder=tool_folder, write_datafile=True)
                if filename.endswith('json'):
                    tool[REGATE_DATA_FILE] = datafile
            print_done()
            return tool
        except Exception as e:
            print_error()
            logger.error("Unable to extract the Galaxy tool definition from bio.tools")
            if logger.isEnabledFor(logging.DEBUG):
                logger.exception(e)
    return None


def build_galaxy_workflow_files(config, workflow):
    output_folder = get_resource_folder(config, PLATFORM.GALAXY.value, RESOURCE.WORKFLOW.value)
    try:
        links = [link["url"] for link in workflow["download"]
                 if link["url"].startswith(config.data_uri_prefix)]
        if len(links) == 0:
            raise Exception("No DataURI link found")
        elif len(links) > 1:
            raise Exception("More than one DataURI link found. We support one version only")
        for link in links:
            filename, datafile = decode_datafile_from_datauri(link, output_folder=output_folder, write_datafile=True)
            if filename.endswith('json'):
                workflow[REGATE_DATA_FILE] = datafile
        print_done()
        return workflow
    except Exception as e:
        print_error()
        logger.error("Unable to extract the Galaxy workflow definition from bio.tools")
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)
        return None


def push(args):
    logger.debug("cmd: %s", args.command)
    if args.platform == "biotools":
        push_to_target_platform(args)
    elif args.platform == "galaxy":
        push_to_target_platform(args)
    else:
        logger.error("Unsupported target platform '%s'", args.platform)


def push_to_target_platform(options):
    # Build list of BioTools JSON files to publish
    biotools_json_files = []
    # Load configuration file
    config = load_config(options)
    #
    tools_dir = get_resource_folder(config, options.platform, "tool")
    workflows_dir = get_resource_folder(config, options.platform, "workflow")
    resource_type_list = [t for t in [RESOURCE.TOOL.value, RESOURCE.WORKFLOW.value]
                          if t == options.resource or options.resource == RESOURCE.ALL.value]
    tools_selected = []
    workflows_selected = []
    for resource_type in resource_type_list:
        selection = None
        is_tool = resource_type == RESOURCE.TOOL.value
        is_galaxy_platform = options.platform == PLATFORM.GALAXY.value
        resource_dir = tools_dir if is_tool else workflows_dir
        if 'filter' in options and options.filter:
            tools_filter = options.filter.split(",")
            selection = [f for f in glob.glob(os.path.join(resource_dir, "*.json"))
                         if os.path.isfile(f) and os.path.splitext(os.path.basename(f))[0] in tools_filter]
            biotools_json_files.extend(selection)
            tools_selected.extend(selection) if is_tool else workflows_selected.extend(selection)
        elif not options.no_interactive:
            tools_files = [f for f in glob.glob(os.path.join(resource_dir, "*.json")) if os.path.isfile(f)]
            tools = {}
            for tool_filename in tools_files:
                with open(tool_filename) as tool_file:
                    tool = json.load(tool_file)
                    tools["{} (id {}, version {})".format(
                        tool["name"],
                        tool[
                            "id" if is_galaxy_platform and is_tool else "uuid" if is_galaxy_platform else "biotoolsID"],
                        tool["version"] if is_galaxy_platform else tool["version"][0]
                    )] = tool
            questions = [
                {
                    'type': 'confirm',
                    'name': "disable_filter",
                    'message': 'Would you like to push all {}?'.format("tools" if is_tool else "workflows"),
                    'default': True
                }
            ]
            answers = prompt(questions)
            if not answers["disable_filter"]:
                questions = [
                    {
                        'type': 'checkbox',
                        'message': 'Select {}'.format("tools" if is_tool else "workflows"),
                        'name': 'tools',
                        'choices': [{'name': t} for t in list(tools)],
                    }
                ]
                answers = prompt(questions)
                selection = [t for k, t in tools.items() if k in answers["tools"]]
                biotools_json_files.extend(selection)
                tools_selected.extend(selection) if is_tool else workflows_selected.extend(selection)
        # select all files by default
        if not selection:
            selection = [f for f in glob.glob(os.path.join(resource_dir, "*.json")) if os.path.isfile(f)]
            tools_selected.extend(selection) if is_tool else workflows_selected.extend(selection)
            biotools_json_files.extend(selection)

    tools_pushed = tools_push_errors = None
    workflows_pushed = workflows_push_errors = None
    if len(biotools_json_files) == 0:
        print(warning("\n  WARNING: no resource to publish "
                      "on the bio.tools registry '{}'\n".format(config.bioregistry_host)))
    else:
        if options.platform == PLATFORM.BIOTOOLS.value:
            tools_pushed, tools_push_errors, workflows_pushed, workflows_push_errors = \
                push_to_biotools(config, biotools_json_files, config.resourcename)
        else:
            tools_pushed, tools_push_errors, workflows_pushed, workflows_push_errors = \
                push_to_galaxy(config, biotools_json_files, check_exists=True)
    #
    print_report(tools_selected=tools_selected, workflows_selected=workflows_selected,
                 tools_pushed=tools_pushed, tools_push_errors=tools_push_errors,
                 workflows_pushed=workflows_pushed, workflows_push_errors=workflows_push_errors)


def biotools_authenticate(config):
    """
    :param login:
    :return:
    """
    key = None
    while key is None:
        questions = [
            {
                'type': 'password',
                'qmark': ">",
                'message': "Enter the password for the bio.tools user '{}':".format(config.login),
                'name': 'password'
            }
        ]
        answers = prompt(questions)
        key = BioToolsPlatform.get_instance().authenticate(config.login, answers["password"], config.ssl_verify)
    return key


def push_to_biotools(config, biotools_json_data_list, resourcename):
    """
    :param login:
    :param tool_dir:
    :return:
    """
    # init BioTools
    BioToolsPlatform.get_instance().configure(config)

    # Get Auth Token
    logger.debug("authenticating...")
    token = biotools_authenticate(config)
    logger.debug("authentication ok")

    print(bold("> Pushing tools and workflows on the bio.tools platform..."))

    # POST BioTool JSON files
    tools_pushed = []
    tools_errors = []
    workflows_pushed = []
    workflows_errors = []
    for json_data in biotools_json_data_list:
        if isinstance(json_data, str) and os.path.isfile(json_data):
            with open(json_data, 'r') as jsonfile:
                json_string = jsonfile.read()
                json_data = json.loads(json_string)
        else:
            json_string = json.dumps(json_data)
        print(" - {} (id {}, version {})... ".format(json_data['name'],
                                                     json_data['biotoolsID'],
                                                     json_data['version'][0]), end='',
              flush=True)
        try:
            # TODO: replace removal with a proper upgrade
            bi = BioToolsPlatform.get_instance()
            bi.remove_existing_elixir_tool_version(json_data['biotoolsID'], json_data['version'][0], resourcename)
            bi.push_tool(json_string)
            logger.debug("{0} ok".format(json_data["name"]))
            workflows_pushed.append(json_data) \
                if json_data["toolType"][0] == "Workflow" else tools_pushed.append(json_data)
            print_done()
        except Exception as e:
            logger.error("{0} ko, error".format(json_data["name"]))
            workflows_errors.append(json_data) \
                if json_data["toolType"][0] == "Workflow" else tools_errors.append(json_data)
            print_error()
            if logger.isEnabledFor(logging.DEBUG):
                logger.exception(e)
    return tools_pushed, tools_errors, workflows_pushed, workflows_errors


def push_to_galaxy(config, galaxy_json_data_list, check_exists=True):
    # Init Galaxy
    gi = GalaxyPlatform.get_instance()
    gi.configure(config.galaxy_url, config.api_key)
    # Preload all JSON files
    tools = []
    workflows = []
    for galaxy_json_file in galaxy_json_data_list:
        try:
            resource = galaxy_json_file
            if isinstance(galaxy_json_file, str) and os.path.isfile(galaxy_json_file):
                with open(galaxy_json_file) as f:
                    resource = json.load(f)
            if resource.get('model_class', False) == "StoredWorkflow" \
                    or resource.get("a_galaxy_workflow", False) == "true":
                workflows.append(resource)
            elif resource.get('model_class', False) == "Tool":
                tools.append(resource)
        except Exception as e:
            logger.error("Error when loading file '%s'", galaxy_json_file)
            if logger.isEnabledFor(logging.DEBUG):
                logger.exception(e)

    # Push Galaxy tools/workflows
    tools_pushed = []
    tools_errors = []
    workflows_pushed = []
    workflows_errors = []
    for resources in [tools, workflows]:
        if len(resources) > 0:
            # Import all tools/workflows
            print(bold("> Pushing tools on the Galaxy platform..."))
            for resource in resources:
                resource_id = resource["id" if resources == tools else 'uuid']
                print("  - {} (id {}, version {})... ".format(resource["name"],
                                                              resource_id,
                                                              resource["version"]), end='', flush=True)
                try:
                    if check_exists and \
                            (gi.get_tool(resource['id']) if resources == tools else gi.get_workflow(resource['uuid'])):
                        logger.info("Tool %s [version %s] already exists", resource_id, resource['version'])
                        print_exists()
                        continue
                    if resources == tools:
                        gi.import_tool(resource)
                        tools_pushed.append(resource)
                    else:
                        gi.import_workflow(resource)
                        workflows_pushed.append(resource)
                    print_done()
                except Exception as e:
                    print_error()
                    if resources == tools:
                        tools_errors.append(resource)
                    else:
                        workflows_errors.append(resource)
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.exception(e)
    return tools_pushed, tools_errors, \
           workflows_pushed, workflows_errors


def wizard(args):
    questions = [
        {
            'type': 'list',
            'name': 'platform',
            'message': 'Which platform do you want to export from?',
            'choices': PLATFORM.values()
        },
        {
            'type': 'list',
            'name': 'resource',
            'message': 'Which type of resource?',
            'choices': RESOURCE.values()
        },
        {
            'type': 'confirm',
            'name': "push",
            'message': 'Would you like to push the exported resources to bio.tools?',
            'default': True,
            'when': lambda answers: answers['platform'] == PLATFORM.GALAXY.value
        },
        {
            'type': 'confirm',
            'name': "push",
            'message': 'Would you like to push the exported resources to Galaxy?',
            'default': True,
            'when': lambda answers: answers['platform'] == PLATFORM.BIOTOOLS.value
        }
    ]

    try:
        answers = prompt(questions)
        options = DynamicObject(answers)
        options.merge(vars(args))
        options.command = "export"
        logger.debug("Selected options: %s", options)
        sub_cmd = "export_from_{}".format(options.platform)
        globals()[sub_cmd](options)
    except KeyError as e:
        logger.error("Command '%s' not found", options.command)
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)
        sys.exit(1)
    except KeyboardInterrupt as e:
        logger.error("'%s' command interrupted by user", options.command)


def run():
    print_logo()
    requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)
    logging.getLogger("requests").setLevel(logging.ERROR)
    parser = build_cli_parser()
    args = parser.parse_args()
    configure_logging(args)
    logger.debug("CLI options: %s", args)
    try:
        if "command" in args:
            globals()[args.command](args)
        elif not args.no_interactive:
            wizard(args)
        else:
            parser.print_help()
            sys.exit(1)
    except KeyError as e:
        logger.error("Command '%s' not found", args.command)
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)
        parser.print_help()
        sys.exit(1)
    except KeyboardInterrupt as e:
        logger.error("'%s' command interrupted by user", args.command)
    except Exception as e:
        logger.error(e)
        print("%s %s\n" % (failure("ERROR:"), e))
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)
