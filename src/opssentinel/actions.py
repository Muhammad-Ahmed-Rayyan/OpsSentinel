from dataclasses import dataclass


@dataclass(frozen=True)
class ActionSpec:
    description: str
    risk_tier: str  # "low" or "high"
    required_params: tuple[str, ...] = ()


ACTION_CATALOG: dict[str, ActionSpec] = {
    "rollback_deployment": ActionSpec(
        "Roll a service back to its previous version", "high", ("service", "target_version")
    ),
    "restart_service": ActionSpec("Restart all instances of a service", "high", ("service",)),
    "scale_up_service": ActionSpec(
        "Add instances to a service to absorb load", "high", ("service", "replicas")
    ),
    "cleanup_old_logs": ActionSpec(
        "Delete rotated or archived log files on a host", "low", ("host", "path")
    ),
    "clear_cache": ActionSpec("Flush a service's cache", "low", ("service",)),
    "escalate_to_human": ActionSpec(
        "Page the on-call engineer; no automated fix is justified", "low"
    ),
}


def describe_catalog() -> str:
    """Render the catalog as text for the LLM prompt."""
    lines = []
    for name, spec in ACTION_CATALOG.items():
        params = ", ".join(spec.required_params) or "none"
        lines.append(f"- {name}: {spec.description} (required parameters: {params})")
    return "\n".join(lines)