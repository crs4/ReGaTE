from enum import Enum

REGATE_SEPARATOR = "_____"
REGATE_PREFIX_ID = "biotools:regate"
TOOLSHED_PREFIX_ID = "biotools:toolshed"
REGATE_DATA_FILE = "regate_data_file"


class RESOURCE(Enum):
    ALL = "all"
    TOOL = "tool"
    WORKFLOW = "workflow"

    @staticmethod
    def values():
        return [o.value for o in RESOURCE]


class PLATFORM(Enum):
    GALAXY = "galaxy"
    BIOTOOLS = "biotools"

    @staticmethod
    def values():
        return [o.value for o in PLATFORM]


class COMMAND(Enum):
    EXPORT = "export"
    PUSH = "push"
    TEMPLATE = "template"

    @staticmethod
    def values():
        return [o.value for o in COMMAND]
