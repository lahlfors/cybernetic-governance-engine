"""
Ontology for Neuro-Symbolic Logic (Phase 2).
Defines the entities and relationships for the Trading Knowledge Graph.
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field

class TradingEntity(BaseModel):
    name: str
    category: Literal["Asset", "Action", "Risk", "Regulation"]

class Asset(TradingEntity):
    category: Literal["Asset"] = "Asset"
    ticker: str
    volatility_score: float = 0.0 # 0-10
    liquidity_score: float = 0.0  # 0-10

class Action(TradingEntity):
    category: Literal["Action"] = "Action"
    type: Literal["Buy", "Sell", "Short", "Hedge", "Hold"]
    target_asset: str
    amount_usd: float

class Regulation(TradingEntity):
    category: Literal["Regulation"] = "Regulation"
    rule_id: str
    description: str

class TradingKnowledgeGraph(BaseModel):
    entities: List[TradingEntity]
    # Relationships can be implicit (Action targets Asset) or explicit triples if needed.
    # For now, a list of entities is sufficient for predicate logic.
