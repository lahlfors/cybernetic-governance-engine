# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""data_analyst_agent for finding information using generic search (DuckDuckGo)"""

import logging
from typing import Optional

from google.adk import Agent
from google.adk.tools import FunctionTool

from config.settings import MODEL_FAST
from src.governed_financial_advisor.utils.prompt_utils import Content, Part, Prompt, PromptData
from src.governed_financial_advisor.utils.telemetry import genai_span, get_tracer

logger = logging.getLogger(__name__)

DATA_ANALYST_PROMPT_OBJ = Prompt(
    prompt_data=PromptData(
        model=MODEL_FAST,
        contents=[
            Content(
                parts=[
                    Part(
                        text="""
Agent Role: data_analyst
Tool Usage: Use the provided `perform_market_search` tool.

Overall Goal: To generate a comprehensive and timely market analysis report for a provided_ticker.

Inputs (from calling agent/environment):

provided_ticker: (string, mandatory) The stock market ticker symbol.

Mandatory Process - Data Collection:
Perform multiple, distinct search queries to ensure comprehensive coverage using the `perform_market_search` tool.

Expected Final Output (Structured Report):
A comprehensive text report summarizing the search findings.
"""
                    )
                ]
            )
        ]
    )
)

def get_data_analyst_instruction() -> str:
    return DATA_ANALYST_PROMPT_OBJ.prompt_data.contents[0].parts[0].text

def perform_market_search(query: str) -> str:
    """
    Search for market data using DuckDuckGo (Open Source / No API Key).
    """
    tracer = get_tracer()

    # Trace the retrieval operation (Module 4: RAG Tracing)
    try:
        from duckduckgo_search import DDGS

        # OpenTelemetry Span for External Retrieval
        with genai_span("data.retrieval.duckduckgo", prompt=query) as span:
            if span:
                span.set_attribute("db.system", "duckduckgo")
                span.set_attribute("db.operation", "search")
                span.set_attribute("db.statement", query)

            logger.info(f"Searching DuckDuckGo for: {query}")
            results_text = []

            with DDGS() as ddgs:
                # Fetch up to 5 results
                results = list(ddgs.text(query, max_results=5))

                if not results:
                    if span:
                         span.set_attribute("db.row_count", 0)
                    return "No results found."

                for i, r in enumerate(results):
                    title = r.get("title", "No Title")
                    body = r.get("body", "")
                    href = r.get("href", "")
                    results_text.append(f"Source {i+1}: {title}\nURL: {href}\nSummary: {body}\n")

                if span:
                    span.set_attribute("db.row_count", len(results))
                    # Capture snippet of result for debugging (careful with PII)
                    span.set_attribute("db.result_preview", str(results_text[:1]))

            return "\n".join(results_text)

    except ImportError:
        return "Error: duckduckgo-search not installed. Please install it to use open search."
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return f"Error performing search: {e}"

def create_data_analyst_agent(model_name: str = MODEL_FAST) -> Agent:
    """Factory to create data analyst agent."""
    return Agent(
        model=model_name,
        name="data_analyst_agent",
        instruction=get_data_analyst_instruction(),
        output_key="market_data_analysis_output",
        tools=[FunctionTool(perform_market_search)],
    )
