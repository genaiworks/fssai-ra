"""Versioned proposal messages; authority always comes from the server."""
import re
from dataclasses import dataclass

from ..joined_workflow import strict_json


def parse_sdk_request(raw):
    if not isinstance(raw, str) or len(raw.encode()) > 262144:
        raise ValueError('request size or type')
    value = strict_json(raw)
    if not isinstance(value, dict):
        raise ValueError('object required')
    version = value.pop('schema_version', 1)
    if type(version) is not int or version != 1:
        raise ValueError('unsupported schema')
    if {'principal', 'roles', 'approved', 'reviewer', 'authority'} & value.keys():
        raise ValueError('server authority field')
    return value


def _id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_:.@-]{1,160}', value):
        raise ValueError('invalid identifier')
    return value


def _list(value):
    if not isinstance(value, list) or not 1 <= len(value) <= 128:
        raise ValueError('bounded nonempty list required')
    return tuple(_id(v) for v in value)


def _fields(value, names):
    if not isinstance(value, dict) or set(value) != set(names) | {'schema_version'}:
        raise ValueError('unexpected fields')
    if type(value['schema_version']) is not int or value['schema_version'] != 1:
        raise ValueError('unsupported schema')


@dataclass(frozen=True)
class ContextRequest:
    subjects: tuple[str, ...]
    fields: tuple[str, ...]
    purpose: str
    endpoint: str

    @classmethod
    def parse(cls, value):
        _fields(value, ('subjects', 'fields', 'purpose', 'endpoint'))
        return cls(_list(value['subjects']), _list(value['fields']),
                   _id(value['purpose']), _id(value['endpoint']))


@dataclass(frozen=True)
class EffectRequest:
    operation: str
    resource: str
    expected_version: int
    destination: str
    context_refs: tuple[str, ...]
    desired_state: str

    @classmethod
    def parse(cls, value):
        _fields(value, ('operation', 'resource', 'expected_version', 'destination', 'context_refs', 'desired_state'))
        version = value['expected_version']
        if type(version) is not int or not 0 <= version <= 2**53:
            raise ValueError('invalid version')
        return cls(_id(value['operation']), _id(value['resource']), version,
                   _id(value['destination']), _list(value['context_refs']), _id(value['desired_state']))
