"""Single-agent psyche foundation.

The package defines candidate computational roles and a staged runtime.
It does not claim that these roles are a final ontology of human psychology.
"""

from .contracts import (
    PsycheActionCandidate,
    PsycheContext,
    PsycheModule,
    PsycheOutput,
    PsycheSelection,
    PsycheStage,
    PsycheUpdate,
)
from .foundation_map import FOUNDATION_MAP, FoundationMechanismSpec
from .runtime import PsycheContractError, PsycheRunResult, PsycheRuntime
from .state import PsycheState
from .whole_agent import SingleAgentPsycheV01, build_foundation_modules
from .life_modules import build_life_modules

__all__ = [
    "FOUNDATION_MAP",
    "FoundationMechanismSpec",
    "PsycheActionCandidate",
    "PsycheContext",
    "PsycheContractError",
    "PsycheModule",
    "PsycheOutput",
    "PsycheRunResult",
    "PsycheRuntime",
    "PsycheSelection",
    "PsycheStage",
    "PsycheState",
    "PsycheUpdate",
    "SingleAgentPsycheV01",
    "build_foundation_modules",
    "build_life_modules",
]

from .organism import SingleOrganismPsycheV03, SingleOrganismPsycheV05
from .organism_modules import build_organism_modules, build_sensorimotor_modules
from .sensorimotor import SensorimotorConfig, SensorimotorStore

__all__ += [
    "SingleOrganismPsycheV03",
    "SingleOrganismPsycheV05",
    "SensorimotorConfig",
    "SensorimotorStore",
    "build_organism_modules",
    "build_sensorimotor_modules",
]

from .developmental import (
    DevelopmentalCondition,
    DevelopmentalConfig,
    DevelopmentalGateModule,
    DevelopmentalStage,
    compute_developmental_gate,
    measure_experience_structure,
    measure_local_experience,
    local_experience_maturity,
    cognitive_depth_from_gate,
)

__all__ += [
    "DevelopmentalCondition",
    "DevelopmentalConfig",
    "DevelopmentalGateModule",
    "DevelopmentalStage",
    "compute_developmental_gate",
    "measure_experience_structure",
    "measure_local_experience",
    "local_experience_maturity",
    "cognitive_depth_from_gate",
]
