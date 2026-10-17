from copy import deepcopy

BASELINE_ERROR_RATE = 0.5
CLEANED_DISK_USAGE = 55.0
MAX_REPLICAS = 20
LOG_ROOT = "/var/log"

REMEDIATION_ACTIONS = (
    "rollback_deployment",
    "restart_service",
    "scale_up_service",
    "cleanup_old_logs",
    "clear_cache",
)


class RemediationError(Exception):
    """Raised when an action cannot be carried out safely."""


def default_infrastructure() -> dict:
    """Starting state that matches the two sample incidents."""
    return {
        "services": {
            "checkout-api": {
                "version": "v2.14.0",
                "previous_version": "v2.13.2",
                "error_rate_percent": 38.0,
                "replicas": 3,
                "cache_entries": 12000,
            },
            "inventory-api": {
                "version": "v1.8.1",
                "previous_version": "v1.8.0",
                "error_rate_percent": 0.2,
                "replicas": 2,
                "cache_entries": 800,
            },
        },
        "hosts": {
            "log-server-02": {"disk_usage_percent": 96.8},
        },
    }


class SimulatedInfrastructure:
    def __init__(self, state: dict | None = None):
        self.state = deepcopy(state) if state is not None else default_infrastructure()

    def _service(self, name: str) -> dict:
        try:
            return self.state["services"][name]
        except KeyError:
            raise RemediationError(f"unknown service '{name}'") from None

    def _host(self, name: str) -> dict:
        try:
            return self.state["hosts"][name]
        except KeyError:
            raise RemediationError(f"unknown host '{name}'") from None

    def rollback_deployment(self, service: str, target_version: str) -> dict:
        svc = self._service(service)
        if target_version != svc["previous_version"]:
            raise RemediationError(
                f"cannot roll {service} back to {target_version}; "
                f"last known good version is {svc['previous_version']}"
            )
        before = svc["version"]
        svc["version"], svc["previous_version"] = target_version, before
        svc["error_rate_percent"] = BASELINE_ERROR_RATE
        return {"message": f"rolled back {service} from {before} to {target_version}"}

    def restart_service(self, service: str) -> dict:
        svc = self._service(service)
        svc["restarts"] = svc.get("restarts", 0) + 1
        return {"message": f"restarted all instances of {service}"}

    def scale_up_service(self, service: str, replicas) -> dict:
        svc = self._service(service)
        try:
            target = int(replicas)
        except (TypeError, ValueError):
            raise RemediationError(f"replicas must be a whole number, got {replicas!r}") from None
        if not svc["replicas"] < target <= MAX_REPLICAS:
            raise RemediationError(
                f"replicas must be greater than {svc['replicas']} and at most {MAX_REPLICAS}"
            )
        before = svc["replicas"]
        svc["replicas"] = target
        return {"message": f"scaled {service} from {before} to {target} replicas"}

    def cleanup_old_logs(self, host: str, path: str) -> dict:
        host_state = self._host(host)
        if not str(path).startswith(LOG_ROOT):
            raise RemediationError(f"refusing to delete outside {LOG_ROOT}: {path}")
        before = host_state["disk_usage_percent"]
        host_state["disk_usage_percent"] = CLEANED_DISK_USAGE
        return {
            "message": f"removed archived logs under {path} on {host}; "
            f"disk usage {before}% -> {CLEANED_DISK_USAGE}%"
        }

    def clear_cache(self, service: str) -> dict:
        svc = self._service(service)
        entries = svc.get("cache_entries", 0)
        svc["cache_entries"] = 0
        return {"message": f"flushed {entries} cache entries for {service}"}

    def execute(self, action: str, parameters: dict) -> dict:
        if action not in REMEDIATION_ACTIONS:
            raise RemediationError(f"no handler for action '{action}'")
        try:
            outcome = getattr(self, action)(**parameters)
        except TypeError as exc:
            raise RemediationError(f"invalid parameters for {action}: {exc}") from exc
        return {"action": action, "success": True, **outcome}