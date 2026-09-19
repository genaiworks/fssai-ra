"""The sector-neutral kernel of Trust by Construction.

The kernel holds what no domain pack may replace. Existing implementation imports
remain valid; submodules are imported explicitly so optional backends are never
loaded merely by importing the kernel.
"""
from .contracts import CapabilityContract, execute_contracts, load_contracts
from .state import EffectState, transition

__all__ = ['CapabilityContract', 'EffectState', 'execute_contracts', 'load_contracts', 'transition']
