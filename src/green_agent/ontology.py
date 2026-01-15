from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger("GreenAgent.Ontology")

@dataclass
class Constraint:
    """
    Represents a safety constraint derived from STPA analysis.
    """
    id: str
    description: str
    logic: str  # Simplified representation of the logic (e.g., "cash_balance > 1000")
    scope: List[str] = field(default_factory=list) # e.g., ["execute_trade", "withdraw"]

@dataclass
class TradingKnowledgeGraph:
    """
    A lightweight ontology representing the known state of the world and constraints.
    In a full implementation, this might wrap an RDF lib or graph DB.
    """
    constraints: Dict[str, Constraint] = field(default_factory=dict)

    def __post_init__(self):
        # Initialize with core STPA constraints mentioned in the report
        self.add_constraint(Constraint(
            id="SC-1",
            description="The Agent must never execute a write operation to the Production Database without a signed approval token.",
            logic="has_approval_token == True",
            scope=["write_db", "delete_db"]
        ))
        self.add_constraint(Constraint(
            id="SC-2",
            description="The Guardian must block any tool call if the latency of the decision loop exceeds 200ms.",
            logic="latency_ms <= 200",
            scope=["execute_trade"]
        ))
        self.add_constraint(Constraint(
            id="SC-3",
            description="The Agent must verify the data classification level of the output before displaying it.",
            logic="data_classification != 'PII'",
            scope=["display_output"]
        ))
        # Additional financial constraints
        self.add_constraint(Constraint(
            id="FIN-1",
            description="Cannot sell more than 10% of portfolio without explicit confirmation.",
            logic="sell_percentage <= 0.10",
            scope=["execute_sell"]
        ))

    def add_constraint(self, constraint: Constraint):
        self.constraints[constraint.id] = constraint
        logger.debug(f"Added constraint: {constraint.id}")

    def get_constraints_for_action(self, action_name: str) -> List[Constraint]:
        return [c for c in self.constraints.values() if action_name in c.scope]
