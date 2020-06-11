import os
import json
import base64
import urllib
from Cheetah.Template import Template
from regate.edam import get_data_path


def write_json_files(tool_name, general_dict, tool_dir):
    """
    :param tool_name:
    :param general_dict:
    :return:
    """
    with open(os.path.join(tool_dir, tool_name + ".json"), 'w') as tool_file:
        json.dump(general_dict, tool_file, indent=4)


def write_xml_files(tool_name, general_dict, tool_dir, xmltemplate=None):
    """
    :param tool_name:
    :param general_dict:
    :return:
    """
    if xmltemplate:
        template_path = xmltemplate
    else:
        template_path = get_data_path('xmltemplate.tmpl')

    with open(os.path.join(tool_dir, tool_name + ".xml"), 'w') as tool_file:
        template = Template(file=template_path, searchList=[general_dict])
        tool_file.write(str(template))


def get_resource_folder(conf, platform, type):
    base_dir = conf.tool_dir
    return "{}{}".format(os.path.join(base_dir, platform, type), 's')


def decode_datafile_from_datauri(link, output_folder, write_datafile=True):
    unuri = urllib.parse.urlparse(link)
    qparams = urllib.parse.parse_qs(unuri.query)
    filename = qparams['filename'][0]
    dataURI = qparams['data'][0]
    header, encoded = dataURI.split(",", 1)
    header_parts = header.replace('data:', '').split(';')
    is_json = header_parts[0] == 'application/json'
    data = base64.b64decode(encoded).decode('utf-8') if is_json else base64.b64decode(encoded)
    datafile = os.path.join(output_folder, filename)
    if write_datafile:
        with open(datafile, "w" if is_json else 'wb') as out:
            out.write(data)
    return filename, datafile
