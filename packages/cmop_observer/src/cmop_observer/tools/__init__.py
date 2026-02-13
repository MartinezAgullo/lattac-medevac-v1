"""
cmop_observer/tools

CMOP Observer tool definitions (basic API queries + medical domain logic).
"""

from cmop_observer.tools.basic import register_basic_tools
from cmop_observer.tools.medical import register_medical_tools

__all__ = ["register_basic_tools", "register_medical_tools"]