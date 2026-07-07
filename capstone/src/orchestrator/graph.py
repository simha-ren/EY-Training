"""LangGraph orchestration for the agent pipeline.

Wraps the existing agents as nodes in a StateGraph:
    route -> guardrails -> retrieve -> generate -> suggest
Conditional edges short-circuit to END when the router needs a domain choice
or a guardrail refuses / asks to clarify. The graph is provider-agnostic: it
runs whatever LLM client the engine was built with (the online connector in
production). Follow-up suggestions are generated from the last question.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import StateGraph, END

from src.common import guardrails
from src.agents import suggest
from src.agents.generation import compose


class PipelineState(TypedDict, total=False):
    query: str
    pinned: Optional[str]
    confirmed_domain: Optional[str]
    domain: Optional[str]
    route: Any
    retrieved: Any
    answer: Any
    status: str
    message: str
    disclaimer: str
    follow_ups: List[str]
    cross_hint: Optional[str]


def build_pipeline_graph(router, domains, store, llm):
    """Compile and return the LangGraph pipeline for the given components."""

    def route_node(state: PipelineState) -> PipelineState:
        q = state["query"]
        pin = state.get("confirmed_domain") or state.get("pinned")
        route = router.route(q, pinned=pin)
        state["route"] = route
        if route.mode == "ask" and not pin:
            state["status"] = "ask_domain"
            state["message"] = "I'm not sure which area this is. Pick one:"
            return state
        domain = route.domain or (route.suggestions[0] if route.suggestions else None)
        if domain is None:
            state["status"] = "ask_domain"
            state["message"] = "I'm not sure which area this is. Pick one:"
            return state
        if route.mode == "suggest" and not pin:
            state["domain"] = domain
            state["status"] = "ask_domain"
            state["message"] = f"Looks like {domains[domain].label}. Confirm the domain:"
            return state
        state["domain"] = domain
        state["status"] = "route_ok"
        return state

    def guard_node(state: PipelineState) -> PipelineState:
        cfg = domains[state["domain"]]
        refusal = guardrails.refuse(cfg, state["query"])
        if refusal:
            state["status"] = "refuse"
            state["message"] = refusal
            state["disclaimer"] = guardrails.disclaimer(cfg)
            return state
        gap = guardrails.detect_gap(cfg, state["query"])
        if gap:
            state["status"] = "clarify"
            state["message"] = gap
            return state
        state["status"] = "guard_ok"
        return state

    def retrieve_node(state: PipelineState) -> PipelineState:
        state["retrieved"] = store.retrieve(state["query"], state["domain"])
        return state

    def generate_node(state: PipelineState) -> PipelineState:
        cfg = domains[state["domain"]]
        answer = compose(state["query"], cfg, state["retrieved"], llm)
        answer.text = guardrails.redact_pii(answer.text)
        state["answer"] = answer
        state["disclaimer"] = guardrails.disclaimer(cfg)
        state["status"] = "answer"
        return state

    def suggest_node(state: PipelineState) -> PipelineState:
        cfg = domains[state["domain"]]
        ans = state.get("answer")
        # Follow-ups tied to the LAST question (LLM-driven when online).
        state["follow_ups"] = suggest.followups_from_last(
            llm, cfg, state["query"], ans.text if ans else "")
        state["cross_hint"] = suggest.cross_domain_hint(cfg, state["query"])
        return state

    # ---- assemble graph ----
    g = StateGraph(PipelineState)
    g.add_node("route", route_node)
    g.add_node("guard", guard_node)
    g.add_node("retrieve", retrieve_node)
    g.add_node("generate", generate_node)
    g.add_node("suggest", suggest_node)

    g.set_entry_point("route")
    g.add_conditional_edges("route", lambda s: "guard" if s["status"] == "route_ok" else "end",
                            {"guard": "guard", "end": END})
    g.add_conditional_edges("guard", lambda s: "retrieve" if s["status"] == "guard_ok" else "end",
                            {"retrieve": "retrieve", "end": END})
    g.add_edge("retrieve", "generate")
    g.add_edge("generate", "suggest")
    g.add_edge("suggest", END)
    return g.compile()
