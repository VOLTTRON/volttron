from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional

__NAMESPACE__ = "http://pypi.org/project/xsdata"


@dataclass
class TypeName:

    class Meta:
        name = "ClassName"
        namespace = "http://pypi.org/project/xsdata"

    case: Optional[str] = field(default=None, metadata={
        "type": "Attribute",
        "required": True,
    })
    safePrefix: Optional[str] = field(default=None,
                                      metadata={
                                          "type": "Attribute",
                                          "required": True,
                                      })


@dataclass
class CompoundFields:

    class Meta:
        namespace = "http://pypi.org/project/xsdata"

    defaultName: Optional[str] = field(default=None,
                                       metadata={
                                           "type": "Attribute",
                                           "required": True,
                                       })
    forceDefaultName: Optional[bool] = field(default=None,
                                             metadata={
                                                 "type": "Attribute",
                                                 "required": True,
                                             })
    value: Optional[bool] = field(default=None, metadata={
        "required": True,
    })


@dataclass
class ConstantName:

    class Meta:
        namespace = "http://pypi.org/project/xsdata"

    case: Optional[str] = field(default=None, metadata={
        "type": "Attribute",
        "required": True,
    })
    safePrefix: Optional[str] = field(default=None,
                                      metadata={
                                          "type": "Attribute",
                                          "required": True,
                                      })


@dataclass
class FieldName:

    class Meta:
        namespace = "http://pypi.org/project/xsdata"

    case: Optional[str] = field(default=None, metadata={
        "type": "Attribute",
        "required": True,
    })
    safePrefix: Optional[str] = field(default=None,
                                      metadata={
                                          "type": "Attribute",
                                          "required": True,
                                      })


@dataclass
class Format:

    class Meta:
        namespace = "http://pypi.org/project/xsdata"

    repr: Optional[bool] = field(default=None, metadata={
        "type": "Attribute",
        "required": True,
    })
    eq: Optional[bool] = field(default=None, metadata={
        "type": "Attribute",
        "required": True,
    })
    order: Optional[bool] = field(default=None, metadata={
        "type": "Attribute",
        "required": True,
    })
    unsafeHash: Optional[bool] = field(default=None,
                                       metadata={
                                           "type": "Attribute",
                                           "required": True,
                                       })
    frozen: Optional[bool] = field(default=None,
                                   metadata={
                                       "type": "Attribute",
                                       "required": True,
                                   })
    slots: Optional[bool] = field(default=None, metadata={
        "type": "Attribute",
        "required": True,
    })
    kwOnly: Optional[bool] = field(default=None,
                                   metadata={
                                       "type": "Attribute",
                                       "required": True,
                                   })
    value: str = field(default="", metadata={
        "required": True,
    })


@dataclass
class ModuleName:

    class Meta:
        namespace = "http://pypi.org/project/xsdata"

    case: Optional[str] = field(default=None, metadata={
        "type": "Attribute",
        "required": True,
    })
    safePrefix: Optional[str] = field(default=None,
                                      metadata={
                                          "type": "Attribute",
                                          "required": True,
                                      })


@dataclass
class PackageName:

    class Meta:
        namespace = "http://pypi.org/project/xsdata"

    case: Optional[str] = field(default=None, metadata={
        "type": "Attribute",
        "required": True,
    })
    safePrefix: Optional[str] = field(default=None,
                                      metadata={
                                          "type": "Attribute",
                                          "required": True,
                                      })


@dataclass
class Substitution:

    class Meta:
        namespace = "http://pypi.org/project/xsdata"

    type_value: Optional[str] = field(default=None,
                                      metadata={
                                          "name": "type",
                                          "type": "Attribute",
                                          "required": True,
                                      })
    search: Optional[str] = field(default=None, metadata={
        "type": "Attribute",
        "required": True,
    })
    replace: Optional[str] = field(default=None,
                                   metadata={
                                       "type": "Attribute",
                                       "required": True,
                                   })


@dataclass
class Conventions:

    class Meta:
        namespace = "http://pypi.org/project/xsdata"

    ClassName: Optional[TypeName] = field(default=None,
                                          metadata={
                                              "type": "Element",
                                              "required": True,
                                          })
    FieldName: Optional[FieldName] = field(default=None,
                                           metadata={
                                               "type": "Element",
                                               "required": True,
                                           })
    ConstantName: Optional[ConstantName] = field(default=None,
                                                 metadata={
                                                     "type": "Element",
                                                     "required": True,
                                                 })
    ModuleName: Optional[ModuleName] = field(default=None,
                                             metadata={
                                                 "type": "Element",
                                                 "required": True,
                                             })
    PackageName: Optional[PackageName] = field(default=None,
                                               metadata={
                                                   "type": "Element",
                                                   "required": True,
                                               })


@dataclass
class Output:

    class Meta:
        namespace = "http://pypi.org/project/xsdata"

    maxLineLength: Optional[int] = field(default=None,
                                         metadata={
                                             "type": "Attribute",
                                             "required": True,
                                         })
    Package: Optional[str] = field(default=None, metadata={
        "type": "Element",
        "required": True,
    })
    Format: Optional[Format] = field(default=None,
                                     metadata={
                                         "type": "Element",
                                         "required": True,
                                     })
    Structure: Optional[str] = field(default=None,
                                     metadata={
                                         "type": "Element",
                                         "required": True,
                                     })
    DocstringStyle: Optional[str] = field(default=None,
                                          metadata={
                                              "type": "Element",
                                              "required": True,
                                          })
    FilterStrategy: Optional[str] = field(default=None,
                                          metadata={
                                              "type": "Element",
                                              "required": True,
                                          })
    RelativeImports: Optional[bool] = field(default=None,
                                            metadata={
                                                "type": "Element",
                                                "required": True,
                                            })
    CompoundFields: Optional[CompoundFields] = field(default=None,
                                                     metadata={
                                                         "type": "Element",
                                                         "required": True,
                                                     })
    PostponedAnnotations: Optional[bool] = field(default=None,
                                                 metadata={
                                                     "type": "Element",
                                                     "required": True,
                                                 })
    UnnestClasses: Optional[bool] = field(default=None,
                                          metadata={
                                              "type": "Element",
                                              "required": True,
                                          })
    IgnorePatterns: Optional[bool] = field(default=None,
                                           metadata={
                                               "type": "Element",
                                               "required": True,
                                           })


@dataclass
class Substitutions:

    class Meta:
        namespace = "http://pypi.org/project/xsdata"

    Substitution: List[Substitution] = field(default_factory=list,
                                             metadata={
                                                 "type": "Element",
                                                 "min_occurs": 1,
                                             })


@dataclass
class Config:

    class Meta:
        namespace = "http://pypi.org/project/xsdata"

    version: Optional[float] = field(default=None,
                                     metadata={
                                         "type": "Attribute",
                                         "required": True,
                                     })
    Output: Optional[Output] = field(default=None,
                                     metadata={
                                         "type": "Element",
                                         "required": True,
                                     })
    Conventions: Optional[Conventions] = field(default=None,
                                               metadata={
                                                   "type": "Element",
                                                   "required": True,
                                               })
    Substitutions: Optional[Substitutions] = field(default=None,
                                                   metadata={
                                                       "type": "Element",
                                                       "required": True,
                                                   })
