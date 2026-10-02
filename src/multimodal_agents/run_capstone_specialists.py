"""Follow-along script: ask the analysis, visualization, and edit-proposal
specialists one supported question and one unsupported question each,
against the real OpenSearch index built by run_opensearch_index.py.
"""

from __future__ import annotations

import asyncio
import json

from multimodal_agents.capstone_specialists import analyze, propose_edit, visualize

SUPPORTED_QUESTION = "How many tracked objects kept their identity across the video?"
UNSUPPORTED_QUESTION = "What is the capital of France?"


async def main() -> None:
    cases = [
        ("analysis", SUPPORTED_QUESTION, await analyze(SUPPORTED_QUESTION)),
        ("analysis", UNSUPPORTED_QUESTION, await analyze(UNSUPPORTED_QUESTION)),
        ("visualization", SUPPORTED_QUESTION, await visualize(SUPPORTED_QUESTION)),
        ("edit-proposal", SUPPORTED_QUESTION, await propose_edit(SUPPORTED_QUESTION)),
        ("edit-proposal", UNSUPPORTED_QUESTION, await propose_edit(UNSUPPORTED_QUESTION)),
    ]
    for specialist, question, result in cases:
        print(f"[{specialist}] {question}")
        print(json.dumps(result, indent=2))
        print()


if __name__ == "__main__":
    asyncio.run(main())
