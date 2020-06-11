from __future__ import annotations

import os
import json
import logging
import tarfile
import tempfile
import collections
from urllib.parse import urljoin
from xml.etree import ElementTree as ET

from bioblend import ConnectionError
from bioblend.galaxy import GalaxyInstance as _GalaxyInstance
from bioblend.galaxy.objects import GalaxyInstance as _GalaxyObjectInstance

from regate.const import RESOURCE
from regate.objects import Platform, Tool as BaseTool, Workflow as BaseWorkflow

logger = logging.getLogger()


class Tool(BaseTool):

    @property
    def metadata_link(self):
        return urljoin(self.platform.url,
                       "api/tools/{}?io_details=true&link_details=true".format(self.id))

    @property
    def download_link(self):
        return urljoin(self.platform.url, "api/tools//{}/download".format(self.id))

    def get_wrapper_archive(self):
        return self.platform.get_galaxy_tool_wrapper_archive(self.id)

    @property
    def platform(self) -> GalaxyPlatform:
        return super().platform


class Workflow(BaseWorkflow):

    def __init__(self, platform, data):
        super().__init__(platform, data)
        if "uuid" not in data and 'latest_workflow_uuid' in data:
            self.uuid = data['latest_workflow_uuid']

    @property
    def service_link(self):
        return urljoin(self.platform.url, "workflow/display_by_id?id={}".format(self.id))

    @property
    def download_link(self):
        return urljoin(self.platform.url,
                       "{}/{}/download?format=json-download".format('api/workflows/', self.id))

    @property
    def platform(self) -> GalaxyPlatform:
        return super().platform


class GalaxyPlatform(Platform):
    def __init__(self):
        super().__init__()
        self._galaxy_instance = None
        self._galaxy_instance_obj = None

    @property
    def api(self):
        if not self._galaxy_instance:
            raise Exception("Bioblend API not initialized")
        return self._galaxy_instance

    @property
    def url(self):
        return self.api.base_url

    def configure(self, galaxy_url, galaxy_api_key):
        self._galaxy_instance = _GalaxyInstance(galaxy_url, key=galaxy_api_key)
        self._galaxy_instance_obj = _GalaxyObjectInstance(galaxy_url, galaxy_api_key)
        self._galaxy_instance.verify = False

    def get_tool(self, identifier):
        try:
            metadata = self.api.tools.show_tool(tool_id=identifier, io_details=True, link_details=True)
            tool_config = self.get_galaxy_tool_wrapper_config(metadata)
            if tool_config:
                metadata['config'] = tool_config
            return Tool(self, metadata)
        except ConnectionError as e:
            if e.status_code == 404:
                logger.warning("Unable to find the tool '%r' on the Galaxy platform @ '%s'", identifier, self.api.base_url)
            else:
                logger.error("Error during connection with exposed API method for tool {0}".format(str(identifier)), exc_info=True)
            if logger.level == logging.DEBUG:
                logger.exception(e)
            return None

    def get_tools(self, identifier_list=None, ignore=None, details=False):
        tools_metadata = []
        # List of tools to retrieve
        galaxy_tools = identifier_list
        if identifier_list and isinstance(identifier_list, str):
            galaxy_tools = [{'id': tool_id} for tool_id in identifier_list.split(",")]
        elif not identifier_list:
            # Retrieve all available tools in the Galaxy platform
            try:
                galaxy_tools = self.api.tools.get_tools()
                # Ensure the list doesn't contain diplicates checking ID and version
                detect_toolid_duplicate(galaxy_tools)
            except ConnectionError as e:
                raise ConnectionError("Connection with the Galaxy server {0} failed, {1}".format(self.api.base_url, e))
        try:
            if galaxy_tools:
                # Set list of tools to be ignored
                ignore_list = ignore.split(',') if ignore else []
                # Load tools details
                for tool in galaxy_tools:
                    if not tool['id'] in ignore_list:
                        if details:
                            tool = self.get_tool(tool['id'])
                            if tool:
                                tools_metadata.append(tool)
                        else:
                            tools_metadata.append(tool if isinstance(tool, Tool) else Tool(self, tool))
            tools_metadata.sort(key=lambda x: x['name'])
        except Exception as e:
            if logger.isEnabledFor(logging.DEBUG):
                logger.exception(e)
        return tools_metadata

    def get_galaxy_tool_wrapper_archive(self, tool_id):
        try:
            tool_url = '{}/{}/download'.format(self.api.tools.url, tool_id)
            r = self.api.tools._get(url=tool_url, json=False)
            if r.status_code == 200:
                return r.content
        except Exception as e:
            if logger.level == logging.DEBUG:
                logger.exception(e)
        return None

    def get_galaxy_tool_wrapper_config(self, tool_metadata):
        temp = tempfile.NamedTemporaryFile()
        temp_dir = tempfile.TemporaryDirectory()
        try:
            archive = self.get_galaxy_tool_wrapper_archive(tool_metadata['id'])
            if archive:
                with open(temp.name, "wb") as out:
                    out.write(archive)
                tar_archive = tarfile.open(temp.name, 'r:gz')
                if "config_file" in tool_metadata:
                    config_file = os.path.basename(tool_metadata['config_file'])
                    tar_archive.extractall(path=temp_dir.name)
                    xml_filename = os.path.join(temp_dir.name, config_file)
                    xml_config = ET.parse(xml_filename)
                    root = xml_config.getroot()
                    return {
                        'command': root.find("command").text,
                        'help': root.find("help").text if root.find("help") else "",
                    }
                else:
                    logger.debug("Unable to detect the wrapper config file for tool '%s'", tool_metadata['id'])
        except Exception as e:
            logger.debug("Unable to detect the wrapper config file for tool '%s'", tool_metadata['id'])
            if logger.isEnabledFor(logging.DEBUG):
                logger.exception(e)
        finally:
            temp.close()
            temp_dir.cleanup()

    def get_workflow(self, identifier, details=False):
        try:
            workflows = self.api.workflows.get_workflows()
            for wf in workflows:
                wf['uuid'] = wf['latest_workflow_uuid']
                if wf['latest_workflow_uuid'] == identifier:
                    return Workflow(self, self._load_workflow_details(wf['uuid'], load_io_details=details))
            return None
        except ConnectionError as e:
            logger.error("Error during connection with exposed API method for workflow {0}".format(identifier, exc_info=True))
            if logger.isEnabledFor(logging.DEBUG):
                logger.exception(e)
            return None

    def get_workflows(self, identifier_list=None, ignore=None, details=False):
        workflows_metadata = []
        # build the list of workflows to export
        galaxy_workflows = identifier_list
        if identifier_list and isinstance(identifier_list, str):
            galaxy_workflows = [{'uuid': workflow_id} for workflow_id in identifier_list.split(",")]
        elif not identifier_list:
            # Retrieve all available tools in the Galaxy platform
            try:
                galaxy_workflows = self.api.workflows.get_workflows()
                # Ensure the list doesn't contain diplicates checking ID and version
                # detect_toolid_duplicate(galaxy_workflows)
            except ConnectionError as e:
                raise ConnectionError("Connection with the Galaxy server {0} failed, {1}".format(self.api.base_url, e))
        # Load workdlows details
        if galaxy_workflows:
            # Define list of workflows to be ignored
            ignore_list = ignore.split(',') if ignore else []
            # Load workflow details
            for wf in galaxy_workflows:
                if 'uuid' not in wf and 'latest_workflow_uuid' in wf:
                    wf['uuid'] = wf['latest_workflow_uuid']
                if not wf['uuid'] in ignore_list:
                    workflow_metadata = self._load_workflow_details(wf['uuid'], load_io_details=details)
                    if workflow_metadata:
                        workflows_metadata.append(Workflow(self, workflow_metadata))
        workflows_metadata.sort(key=lambda x: x["name"])
        return workflows_metadata

    def _load_workflow_details(self, workflow_uuid, load_io_details=True):
        try:
            workflow_metadata = None
            workflows = self.api.workflows.get_workflows()
            for wf in workflows:
                wf['uuid'] = wf['latest_workflow_uuid']
                if wf['latest_workflow_uuid'] == workflow_uuid:
                    workflow_metadata = wf
                    break
            if not workflow_metadata:
                return None
            workflow_id = workflow_metadata['id']
            workflow_obj = self._galaxy_instance_obj.workflows.get(workflow_id)
            workflow_metadata = workflow_obj.export()
            workflow_metadata['id'] = workflow_id
            if load_io_details:
                workflow_io_details = [
                    ('inputs', list(workflow_obj.inputs)),
                    ('outputs', workflow_obj.sink_ids),
                    ('operations', set(workflow_obj.steps) - workflow_obj.sink_ids - set(workflow_obj.inputs))
                ]
                for collection, _ in workflow_io_details:
                    if collection not in workflow_metadata:
                        workflow_metadata[collection] = []
                for collection, steps in workflow_io_details:
                    for step in steps:
                        step_metadata = workflow_obj.steps[step]
                        if step_metadata.tool_id:
                            tool_step = self.get_tool(step_metadata.tool_id)
                            if not tool_step:
                                logger.error("Unable to load metadata of tools related with step %r", step_metadata.id)
                                return None
                            else:
                                workflow_metadata[collection].append(tool_step)
            return workflow_metadata
        except ConnectionError as e:
            logger.error("Error during connection with exposed API method for workflow {0}".format(workflow_uuid), exc_info=True)
            if logger.isEnabledFor(logging.DEBUG):
                logger.exception(e)

    def import_workflow(self, dict_or_filename):
        try:
            data_json = dict_or_filename
            if isinstance(dict_or_filename, str) and os.path.isfile(dict_or_filename):
                with open(dict_or_filename) as data_file:
                    data_json = json.load(data_file)
            self.api.workflows.import_workflow_dict(data_json, publish=True)
        except ConnectionError as e:
            logger.error("Galaxy import error for workflow in the '%s' JSON file", dict_or_filename)
            if logger.isEnabledFor(logging.DEBUG):
                logger.exception(e)

    def import_tool(self, dict_or_filename):
        try:
            data_json = dict_or_filename
            if isinstance(dict_or_filename, str):
                with open(dict_or_filename) as data_file:
                    data_json = json.load(data_file)
            if "tool_shed_repository" in data_json:
                toolshed = data_json["tool_shed_repository"]
                self.api.toolShed.install_repository_revision(
                    tool_shed_url="https://{}".format(toolshed["tool_shed"]),
                    name=toolshed["name"],
                    owner=toolshed["owner"],
                    changeset_revision=toolshed["changeset_revision"],
                    install_tool_dependencies=False,
                    install_repository_dependencies=False,
                    install_resolver_dependencies=False,
                    tool_panel_section_id=None,
                    new_tool_panel_section_label=data_json["panel_section_name"]
                )
            else:
                logger.error("Unable to find ToolShed repository info for tool '%s'", data_json["name"])
        except ConnectionError as e:
            logger.error("Galaxy import error for workflow in the '%s' JSON file", dict_or_filename)
            if logger.isEnabledFor(logging.DEBUG):
                logger.exception(e)


def detect_toolid_duplicate(tool_list):
    id_list = list()
    for tool in tool_list:
        id_list.append(build_filename(tool['id'], tool['version']))

    duplicate_tools = [item for item, count in list(collections.Counter(id_list).items()) if count > 1]
    if duplicate_tools:
        for dup in duplicate_tools:
            logger.warning("The tool {0} is present multiple times on this instance with the same version.".format(dup))


def build_filename(tool_id, version):
    try:
        try:
            source = str.split(tool_id, '/')[-2]
        except IndexError:
            source = tool_id
        return source + "_" + str(version)
    except ValueError:
        logger.warning("ValueError:", tool_id)
        return ""


def get_galaxy_resource_id_label(resource_type):
    return 'uuid' if resource_type == RESOURCE.WORKFLOW else 'id'
