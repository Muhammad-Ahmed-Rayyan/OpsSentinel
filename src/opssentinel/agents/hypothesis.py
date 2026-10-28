import json

from langchain_core.messages import HumanMessage, SystemMessage

from opssentinel.actions import ACTION_CATALOG, ActionSpec, describe_catalog
from opssentinel.audit import audit_entry
from opssentinel.schemas import HypothesisReport
from opssentinel.state import IncidentState
from opssentinel.tools.knowledge_base import search_similar_incidents

AGENT_NAME = "hypothesis"
MAX_ATTEMPTS = 2
MAX_PROMPT_LOGS = 8
ESCALATE = "escalate_to_human"
CATALOG_PLACEHOLDER = "<<ACTION_CATALOG>>"

SYSTEM_PROMPT = f"""You are the Root-Cause Hypothesis Agent in an incident response system.
Given an alert, correlated evidence, similar past incidents and runbooks, produce ranked root-cause
hypotheses and ONE proposed remediation action.

Rules:
- Base every hypothesis only on the evidence provided. Never invent logs, metrics or deployments.
- Past incidents are hints, not proof. Prefer causes supported by the current evidence.
- Runbooks are the approved procedures for each action. If a runbook caution applies to this
  incident, mention it in the rationale, and prefer escalate_to_human over an action the caution rules out.
- Choose the action ONLY from the action catalog below and fill every required parameter with
  values found in the evidence (service names, versions, hosts).
- If no catalog action is clearly justified, use escalate_to_human.
- Confidence is a number between 0 and 1.

Action catalog:
{CATALOG_PLACEHOLDER}

Respond with ONLY a JSON object (no markdown fences) in exactly this shape:
{{"hypotheses": [{{"cause": "...", "confidence": 0.0, "evidence": ["..."]}}],
 "proposed_action": {{"action": "<catalog name>", "parameters": {{"<param>": "<value>"}}, "rationale": "..."}}}}
List hypotheses from most to least likely."""


def _section(title: str, lines: list[str]) -> list[str]:
    return ["", title, *(lines or ["- none"])]


def _build_query(alert: dict, context: dict) -> str:
    return alert["summary"] + " " + " ".join(context.get("signals", []))


def _build_user_prompt(
    alert: dict, context: dict, similar: list[dict], runbooks: list[dict]
) -> str:
    lines = [
        "ALERT",
        f"- source: {alert['source']}, name: {alert['name']}, severity: {alert['severity']}",
        f"- summary: {alert['summary']}",
        f"- service: {alert.get('service')}, host: {alert.get('host')}, "
        f"environment: {alert.get('environment')}",
        f"- triggered at: {alert['triggered_at']}",
    ]
    lines += _section("SIGNALS", [f"- {s}" for s in context.get("signals", [])])
    lines += _section(
        "RECENT DEPLOYMENTS",
        [
            f"- {d['timestamp']} {d['service']} {d['previous_version']} -> {d['version']}: "
            f"{d['change_summary']}"
            for d in context.get("deployments", [])
        ],
    )
    lines += _section(
        "RECENT WARN/ERROR LOGS",
        [
            f"- {entry['timestamp']} [{entry['level']}] {entry['host']}: {entry['message']}"
            for entry in context.get("logs", [])[-MAX_PROMPT_LOGS:]
        ],
    )
    lines += _section(
        "SIMILAR PAST INCIDENTS (hints, not proof)",
        [
            f"- {s['id']} {s['title']}: root cause: {s['root_cause']}; "
            f"action taken: {s['remediation_action']}; outcome: {s['resolution']}"
            for s in similar
        ],
    )
    lines += _section(
        "RELEVANT RUNBOOKS (approved procedures; respect the cautions)",
        [
            f"- {rb.get('id', '?')} {rb.get('title', '')} [action: {rb.get('action', '?')}]: "
            f"steps: {rb.get('steps', '')}; cautions: {rb.get('cautions', '')}"
            for rb in runbooks
        ],
    )
    return "\n".join(lines)


def _response_text(response) -> str:
    content = response.content
    if isinstance(content, list):  # some providers return content blocks
        return "".join(
            part.get("text", "") if isinstance(part, dict) else str(part) for part in content
        )
    return str(content)


def _extract_json(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object found in the response")
    return json.loads(text[start : end + 1])


def _check_action(report: HypothesisReport) -> ActionSpec:
    proposal = report.proposed_action
    spec = ACTION_CATALOG.get(proposal.action)
    if spec is None:
        raise ValueError(f"unknown action '{proposal.action}'; choose one of {sorted(ACTION_CATALOG)}")
    missing = [p for p in spec.required_params if p not in proposal.parameters]
    if missing:
        raise ValueError(f"action '{proposal.action}' is missing required parameters: {missing}")
    return spec


def make_hypothesis_agent(llm, search_fn=search_similar_incidents, runbook_fn=None):
    """Build the LangGraph node.

    The LLM, the past-incident search and the runbook search are injected so tests can fake
    them. runbook_fn=None switches runbook retrieval off.
    """

    def hypothesize(state: IncidentState) -> dict:
        audit_log = list(state.get("audit_log", []))
        errors = list(state.get("errors", []))

        def failed(reason: str) -> dict:
            errors.append({"agent": AGENT_NAME, "error": reason})
            audit_log.append(audit_entry(AGENT_NAME, "hypothesis_failed", reason))
            return {"status": "failed", "errors": errors, "audit_log": audit_log}

        try:
            alert, context = state["alert"], state["context"]
            query = _build_query(alert, context)
        except (KeyError, TypeError, AttributeError) as exc:
            return failed(f"alert and context are required in state: {exc!r}")

        try:
            similar = search_fn(query)
        except Exception as exc:  # knowledge base down: carry on without history
            similar = []
            errors.append({"agent": AGENT_NAME, "error": f"knowledge base unavailable: {exc}"})

        runbooks: list[dict] = []
        if runbook_fn is not None:
            try:
                runbooks = runbook_fn(query)
            except Exception as exc:  # runbooks down: carry on without them
                errors.append({"agent": AGENT_NAME, "error": f"runbooks unavailable: {exc}"})

        runbook_ids = ", ".join(str(rb.get("id", "?")) for rb in runbooks) or "none"
        audit_log.append(
            audit_entry(
                AGENT_NAME,
                "knowledge_retrieved",
                f"{len(similar)} past incidents, {len(runbooks)} runbooks ({runbook_ids})",
            )
        )

        try:
            user_prompt = _build_user_prompt(alert, context, similar, runbooks)
        except (KeyError, TypeError, AttributeError) as exc:
            return failed(f"malformed alert or context: {exc!r}")

        messages = [
            SystemMessage(content=SYSTEM_PROMPT.replace(CATALOG_PLACEHOLDER, describe_catalog())),
            HumanMessage(content=user_prompt),
        ]
        report, spec, failure = None, None, ""
        for _ in range(MAX_ATTEMPTS):
            try:
                response = llm.invoke(messages)
            except Exception as exc:  # provider/network error: retrying would only burn quota
                failure = f"LLM call failed: {type(exc).__name__}: {exc}"
                break
            try:
                report = HypothesisReport.model_validate(_extract_json(_response_text(response)))
                spec = _check_action(report)
                break
            except ValueError as exc:
                report, spec = None, None
                reason = str(exc)[:500]
                failure = f"Invalid LLM output: {reason}"
                messages = [
                    *messages,
                    HumanMessage(
                        content=f"Your previous answer was invalid: {reason}. "
                        "Return a corrected JSON object only."
                    ),
                ]

        if report is None or spec is None:
            errors.append({"agent": AGENT_NAME, "error": failure})
            audit_log.append(audit_entry(AGENT_NAME, "escalated", failure))
            return {
                "hypotheses": [],
                "proposed_action": {
                    "action": ESCALATE,
                    "parameters": {},
                    "rationale": f"Automated analysis failed: {failure}",
                },
                "risk_tier": ACTION_CATALOG[ESCALATE].risk_tier,
                "status": "escalated",
                "errors": errors,
                "audit_log": audit_log,
            }

        hypotheses = sorted(report.hypotheses, key=lambda h: h.confidence, reverse=True)
        audit_log.append(
            audit_entry(
                AGENT_NAME,
                "hypotheses_ranked",
                f"top: {hypotheses[0].cause} ({hypotheses[0].confidence:.2f}); "
                f"proposed {report.proposed_action.action} [{spec.risk_tier} risk]",
            )
        )
        return {
            "hypotheses": [h.model_dump() for h in hypotheses],
            "proposed_action": report.proposed_action.model_dump(),
            "risk_tier": spec.risk_tier,  # from the catalog, never from the LLM
            "status": "hypothesized",
            "errors": errors,
            "audit_log": audit_log,
        }

    return hypothesize