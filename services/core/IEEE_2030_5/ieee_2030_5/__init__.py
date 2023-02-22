from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List
from dataclasses import dataclass, is_dataclass
from pathlib import Path
from typing import Type, Optional

from xsdata.formats.dataclass.context import XmlContext
from xsdata.formats.dataclass.parsers.config import ParserConfig
from xsdata.formats.dataclass.parsers.xml import XmlParser
from xsdata.formats.dataclass.serializers import XmlSerializer
from xsdata.formats.dataclass.serializers.config import SerializerConfig

__xml_context__ = XmlContext()
__parser_config__ = ParserConfig(fail_on_unknown_attributes=False,
                                 fail_on_unknown_properties=False)
__xml_parser__ = XmlParser(config=__parser_config__, context=__xml_context__)
__config__ = SerializerConfig(xml_declaration=False, pretty_print=True)
__serializer__ = XmlSerializer(config=__config__)
__ns_map__ = {None: "urn:ieee:std:2030.5:ns"}


def serialize_dataclass(obj) -> str:
    """
    Serializes a dataclass that was created via xsdata to an xml string for
    returning to a client.
    """
    if not is_dataclass(obj):
        raise ValueError("Invalid object, must be a dataclass object.")
    
    return __serializer__.render(obj, ns_map=__ns_map__)


def xml_to_dataclass(xml: str, type: Optional[Type] = None) -> object:
    """
    Parse the xml passed and return result from loaded classes.
    """
    return __xml_parser__.from_string(xml, type)


def dataclass_to_xml(dc) -> str:
    return serialize_dataclass(dc)


@dataclass
class AllPoints:
    points: Dict = field(default_factory=dict)
    meta: Dict = field(default_factory=dict)

    def add(self, name: str, value: Any, meta: Dict = {}):
        self.points[name] = value
        self.meta[name] = meta

    def forbus(self) -> List:
        return [self.points, self.meta]

    @staticmethod
    def frombus(message: List) -> AllPoints:
        assert len(message) == 2, "Message must have a length of 2"

        points = AllPoints()

        for k, v in message[0].items():
            points.add(name=k, value=v, meta=message[1].get(k))

        return points