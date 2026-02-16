import logging
from src.gateway.core.policy import OPAClient
from src.gateway.governance.consensus import consensus_engine
from src.gateway.governance.safety import safety_filter
from src.gateway.governance.stpa_validator import STPAValidator
from src.gateway.governance.symbolic_governor import SymbolicGovernor

logger = logging.getLogger("Gateway.Governance.Singletons")

# Singleton Instances
opa_client = OPAClient()
stpa_validator = STPAValidator()

symbolic_governor = SymbolicGovernor(
    opa_client=opa_client,
    safety_filter=safety_filter,
    consensus_engine=consensus_engine,
    stpa_validator=stpa_validator
)

logger.info("✅ Governance Singletons Initialized.")
