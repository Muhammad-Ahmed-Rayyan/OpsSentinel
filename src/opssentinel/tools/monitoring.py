from opssentinel.tools.remediation import SimulatedInfrastructure

_SECTIONS = {"service": "services", "host": "hosts"}


class MetricError(Exception):
    """Raised when a metric cannot be read."""


def read_metric(
    infra: SimulatedInfrastructure, entity_kind: str, name: str, metric: str
) -> float:
    try:
        return float(infra.state[_SECTIONS.get(entity_kind)][name][metric])
    except (KeyError, TypeError, ValueError) as exc:
        raise MetricError(f"{entity_kind} '{name}' has no readable metric '{metric}'") from exc