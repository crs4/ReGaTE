from __future__ import annotations

import json
from abc import ABC, abstractmethod, ABCMeta


class DynamicObject(dict):
    def __init__(self, properties=None):
        super().__init__()
        if properties:
            self.merge(properties)

    def __bool__(self):
        return True

    def __getitem__(self, k):
        return self.__getattr__(k)

    def __setitem__(self, k, v) -> None:
        self.__setattr__(k, v)

    def __delitem__(self, k) -> None:
        del self.__dict__[k]

    def __getattr__(self, name):
        return self.__dict__[name]

    def __setattr__(self, name, value):
        self.__dict__[name] = value

    def __contains__(self, key):
        return key in self.__dict__

    def __str__(self):
        return self.__dict__.__str__()

    def __repr__(self):
        return "{}({})".format(self.__class__.__name__, self.__dict__.__repr__())

    def to_json(self):
        return json.dumps(self.__dict__)

    def merge(self, properties):
        if not isinstance(properties, dict):
            raise TypeError("'properties' should be a dict")
        for k, v in properties.items():
            self.__dict__[k] = v


class Platform(ABC):
    __instance = None

    @classmethod
    def get_instance(cls) -> Platform:
        if not cls.__instance:
            cls.__instance = cls()
        return cls.__instance

    def __init__(self):
        if self.__instance:
            raise Exception("Singleton class: an instance of this class already exists!")
        self.__instance = self

    @abstractmethod
    def configure(self, **kwargs):
        pass

    @abstractmethod
    def get_tool(self, identifier):
        pass

    @abstractmethod
    def import_tool(self, dict_or_filename):
        pass

    @abstractmethod
    def get_tools(self, identifier_list=None, ignore=None, details=False):
        pass

    @abstractmethod
    def get_workflow(self, identifier):
        pass

    @abstractmethod
    def import_workflow(self, dict_or_filename):
        pass

    @abstractmethod
    def get_workflows(self, identifier_list=None, ignore=None, details=False):
        pass


class ReadOnlyPropertyException(Exception):
    pass


class Resource(DynamicObject):

    def __init__(self, platform, data):
        super().__init__(data)
        self._data = data
        self._platform = platform

    def __setattr__(self, name, value):
        try:
            if name in self._data:
                raise ReadOnlyPropertyException()
        except KeyError:
            pass
        self.__dict__[name] = value

    def to_json(self):
        return json.dumps(self._data)

    @property
    def data(self) -> object:
        return self._data.copy()

    @property
    def platform(self) -> Platform:
        return self._platform


class Tool(Resource):
    pass


class Workflow(Resource):
    pass
