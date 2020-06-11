
import argparse
import sys

from os.path import expanduser
from pygments.token import Token
from PyInquirer import prompt as _prompt
from prompt_toolkit.styles import style_from_dict

from regate.const import PLATFORM, RESOURCE

PROMPT_STYLE = style_from_dict({
    Token.Separator: '#6C6C6C',
    Token.QuestionMark: '#FF9D00 bold',
    # Token.Selected: '',  # default
    Token.Selected: '#5F819D',
    Token.Pointer: '#FF9D00 bold',
    Token.Instruction: '',  # default
    Token.Answer: '#5F819D bold',
    Token.Question: 'bold',
})

PROMPT_OPTIONS = {
    "style": PROMPT_STYLE
}


def prompt(questions, answers=None):
    answers = _prompt(questions, answers=None, **PROMPT_OPTIONS)
    if not answers:
        sys.exit(0)
    return answers


class TERM_CONTROL_CODES:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def warning(message):
    return f"{TERM_CONTROL_CODES.WARNING}{message}{TERM_CONTROL_CODES.ENDC}"


def failure(message):
    return f"{TERM_CONTROL_CODES.FAIL}{message}{TERM_CONTROL_CODES.ENDC}"


def success(message):
    return f"{TERM_CONTROL_CODES.OKGREEN}{message}{TERM_CONTROL_CODES.ENDC}"


def underline(message):
    return f"{TERM_CONTROL_CODES.UNDERLINE}{message}{TERM_CONTROL_CODES.ENDC}"


def bold(message):
    return f"{TERM_CONTROL_CODES.BOLD}{message}{TERM_CONTROL_CODES.ENDC}"


def print_done():
    print(success("DONE"))


def print_error():
    print(failure("ERROR"))


def print_warning():
    print(warning("WARNING"))


def print_exists():
    print(warning("EXISTS"))


def format_platform_name(platform):
    return 'bio.tools' if platform == PLATFORM.BIOTOOLS else platform.value.capitalize()


def prompt_platform_resource_selection(platform,
                                       resource_type,
                                       resource_loader):
    selected_resources = None
    resource_id_label = 'biotoolsID' \
        if platform == PLATFORM.BIOTOOLS \
        else 'uuid' if resource_type == RESOURCE.WORKFLOW else 'id'
    questions = [
        {
            'type': 'confirm',
            'name': "disable_filter",
            'message': "Would you like to export all {}s?".format(resource_type.value),
            'default': True
        }
    ]
    answers = prompt(questions)
    if not answers["disable_filter"]:
        print(bold("> Loading list of {} {}s... ").format(format_platform_name(platform),
                                                          resource_type.value), end='', flush=True)
        # Build the list of tools to export
        resources = {"{} (id {}, version {})".format(
            w['name'], w[resource_id_label], w['version']): w for w in resource_loader()}
        print_done()
        questions = [
            {
                'type': 'checkbox',
                'message': 'Select {}s'.format(resource_type.value),
                'name': 'resources',
                'choices': [{'name': w} for w in list(resources)],
            }
        ]
        answers = prompt(questions)
        selected_resources = [w for k, w in resources.items() if k in answers["resources"]]
    return selected_resources


def build_cli_parser():
    parser = argparse.ArgumentParser(description="Bridging Tool for Galaxy and Biotools Registry",
                                     formatter_class=lambda prog: argparse.HelpFormatter(prog, width=140, max_help_position=100))
    parser.add_argument("--debug", action="store_true", help="Enable DEBUG level")
    parser.add_argument("-q", "--no-interactive", dest="no_interactive",
                        action="store_true", default=False, help="Disable interactive mode")
    parser.add_argument("--config_file",
                        help="configuration file for regate or remag",
                        default="regate.ini")
    parser.add_argument("--save-logs", nargs='?', metavar="DIR", const=expanduser("~"), default=None,
                        help="Specify whether to log to files. Optionally specify a directory where to store log files.")

    sp = parser.add_subparsers(title='available commands')

    # template command
    template_parser = sp.add_parser("template", help="generate a template for the 'regate.ini' configuration file")
    template_parser.set_defaults(command='template')
    template_parser.add_argument("-f", "--file", dest="filename", default="regate.ini",
                                 help="configuration filename for regate or remag (default 'regate.ini')")

    # export command
    export_parser = sp.add_parser("export",
                                  help="export (and optionally publish) tools and/or workflows ",
                                  formatter_class=lambda prog: argparse.HelpFormatter(prog, width=140, max_help_position=100))
    export_parser.add_argument("--from", dest="platform", choices=[o.value for o in PLATFORM],
                               required=True,
                               help="source platform for exporting tools and/or workflows")
    export_parser.add_argument("--push", action='store_true', help="Push tools and/or workflows")
    export_parser.set_defaults(command='export')
    export_parser.set_defaults(resource='all')

    # publish command
    publish_parser = sp.add_parser("push",
                                   help="publish just exported tools and/or workflows",
                                   formatter_class=lambda prog: argparse.HelpFormatter(prog, width=140, max_help_position=100))
    publish_parser.add_argument("--to", dest="platform", choices=[o.value for o in PLATFORM], required=True,
                                help="target platform for publishing tools and/or workflows")
    publish_parser.set_defaults(command='push')
    publish_parser.set_defaults(resource='all')

    # add resource_parser as subparser of the {export,publish}_pasers
    for parent_parser in [export_parser, publish_parser]:
        resource_subparsers = parent_parser.add_subparsers(
            title="types of resource to {}".format("export" if parent_parser == export_parser else "push"))
        all_res_parser = resource_subparsers.add_parser("all", help="tools and workflows (default)",
                                                        formatter_class=lambda prog: argparse.HelpFormatter(prog, width=140,
                                                                                                            max_help_position=100))
        all_res_parser.set_defaults(resource='all')

        tool_res_parser = resource_subparsers.add_parser("tools", help="tools")
        tool_res_parser.set_defaults(resource=RESOURCE.TOOL.value)
        tool_res_parser.add_argument("--filter", help="list of comma separated tool IDs")

        wf_res_parser = resource_subparsers.add_parser("workflows", help="workflows")
        wf_res_parser.set_defaults(resource=RESOURCE.WORKFLOW.value)
        wf_res_parser.add_argument("--filter", help="list of comma separated workflow IDs")

    return parser


REGATE_LOGO = """
    RRRRRRRRRRRRRRRRR                             GGGGGGGGGGGGG             TTTTTTTTTTTTTTTTTTTTTTEEEEEEEEEEEEEEEEEEEEEE
    R::::::::::::::::R                         GGG::::::::::::G             T:::::::::::::::::::::E::::::::::::::::::::E
    R::::::RRRRRR:::::R                      GG:::::::::::::::G             T:::::::::::::::::::::E::::::::::::::::::::E
    RR:::::R     R:::::R                    G:::::GGGGGGGG::::G             T:::::TT:::::::TT:::::EE::::::EEEEEEEEE::::E
    R::::R     R:::::R   eeeeeeeeeeee    G:::::G       GGGGGG aaaaaaaaaaaaTTTTTT  T:::::T  TTTTTT E:::::E       EEEEEE
    R::::R     R:::::R ee::::::::::::ee G:::::G               a::::::::::::a      T:::::T         E:::::E             
    R::::RRRRRR:::::R e::::::eeeee:::::eG:::::G               aaaaaaaaa:::::a     T:::::T         E::::::EEEEEEEEEE   
    R:::::::::::::RR e::::::e     e:::::G:::::G    GGGGGGGGGG          a::::a     T:::::T         E:::::::::::::::E   
    R::::RRRRRR:::::Re:::::::eeeee::::::G:::::G    G::::::::G   aaaaaaa:::::a     T:::::T         E:::::::::::::::E   
    R::::R     R:::::e:::::::::::::::::eG:::::G    GGGGG::::G aa::::::::::::a     T:::::T         E::::::EEEEEEEEEE   
    R::::R     R:::::e::::::eeeeeeeeeee G:::::G        G::::Ga::::aaaa::::::a     T:::::T         E:::::E             
    R::::R     R:::::e:::::::e           G:::::G       G::::a::::a    a:::::a     T:::::T         E:::::E       EEEEEE
    RR:::::R     R:::::e::::::::e           G:::::GGGGGGGG::::a::::a    a:::::a   TT:::::::TT     EE::::::EEEEEEEE:::::E
    R::::::R     R:::::Re::::::::eeeeeeee    GG:::::::::::::::a:::::aaaa::::::a   T:::::::::T     E::::::::::::::::::::E
    R::::::R     R:::::R ee:::::::::::::e      GGG::::::GGG:::Ga::::::::::aa:::a  T:::::::::T     E::::::::::::::::::::E
    RRRRRRRR     RRRRRRR   eeeeeeeeeeeeee         GGGGGG   GGGG aaaaaaaaaa  aaaa  TTTTTTTTTTT     EEEEEEEEEEEEEEEEEEEEEE
    """


def print_logo():
    print(REGATE_LOGO)
