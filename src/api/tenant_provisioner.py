import json
import re
import subprocess
from typing import Any

from api import APIRequestError, APIResponseError

TSH_CLUSTER = "iad0"
GSLB_DNS_URL = "https://gslb-dns-v2-npe.polaris.netskope.io/api/v0.1/dns/sync/zone/boomskope.com"


def _run_on_knode(knode: str, curl_cmd: str) -> str:
    """Run a curl command on a remote knode via tsh ssh. Returns stdout on success.

    Raises APIRequestError if tsh exits non-zero (VPN down, Teleport session expired,
    unreachable knode, etc.) so callers always receive clean curl output.
    """
    tsh_cmd = ["tsh", "ssh", "--cluster", TSH_CLUSTER, "--skip-version-check", knode, "bash", "-s"]
    try:
        result = subprocess.run(
            tsh_cmd,
            input=curl_cmd,
            capture_output=True,
            text=True,
            timeout=1200,
        )
        if result.returncode != 0:
            raw_output = re.sub(r"\x1b\[[0-9;]*m", "", (result.stderr or result.stdout))
            # Strip tsh browser-open lines (local proxy auth callbacks) — only keep ERROR: lines
            lines = [l for l in raw_output.splitlines() if not l.strip().startswith("If browser window")]
            tsh_output = " ".join(l.strip() for l in lines if l.strip())
            raise APIRequestError(
                f"[tsh] Failed to connect to {knode} (exit {result.returncode})"
                + (f": {tsh_output}" if tsh_output else " — check VPN and Teleport session")
            )
        return result.stdout
    except subprocess.TimeoutExpired as e:
        raise APIRequestError(f"tsh ssh timed out connecting to {knode}") from e
    except FileNotFoundError as e:
        raise APIRequestError("tsh not found in PATH — is Teleport installed?") from e
    except OSError as e:
        raise APIRequestError(f"Failed to run tsh: {e}") from e


def _parse_response(raw: str, knode: str, operation: str) -> dict[str, Any]:
    """Extract and parse JSON from curl output. curl -w writes HTTP status on the last line."""
    lines = raw.strip().splitlines()
    if not lines:
        raise APIResponseError(0, f"[{operation}] Empty response from {knode}")

    # Scan from the end for the HTTP status code written by curl -w "%{http_code}".
    # tsh may append auth/browser-open noise after the status code line (e.g. when
    # an Okta or Teleport session expires mid-run), so we can't assume lines[-1] is
    # the status. We find the last line whose leading 3 chars are a valid HTTP code.
    status_code = None
    body_end = len(lines)
    for i in range(len(lines) - 1, -1, -1):
        prefix = lines[i].strip()[:3]
        if prefix.isdigit() and 100 <= int(prefix) <= 599:
            status_code = int(prefix)
            body_end = i
            break

    if status_code is None:
        # tsh/curl never reached the server — entire output is an error message
        raise APIRequestError(f"[{operation}] curl failed on {knode}: {raw.strip()}")

    body = "\n".join(lines[:body_end]).strip()

    if status_code not in (200, 201, 202, 204):
        raise APIResponseError(status_code, f"[{operation}] {body}")

    if not body:
        return {}
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return {"_raw": body}


def ping_knode(knode: str) -> None:
    """Verify tsh can reach the knode. Raises APIRequestError if the session is expired or unreachable."""
    _run_on_knode(knode, "echo ok")


def create_tenant(knode: str, payload: dict[str, Any]) -> dict[str, Any]:
    payload_json = json.dumps(payload)
    curl = (
        f"curl -s -w '\\n%{{http_code}}' -X POST "
        f"-H 'Content-Type: application/json' "
        f"-d '{payload_json}' "
        f"http://tenant-provisioner/rest/create/org"
    )
    return _parse_response(_run_on_knode(knode, curl), knode, "create_tenant")


def refresh_cluster_mapping(knode: str) -> dict[str, Any]:
    curl = (
        "curl -s -w '\\n%{http_code}' -X POST "
        "-H 'Content-Type: application/json' "
        "http://provisioner-pycore-provisioner/clustermapping/refresh"
    )
    return _parse_response(_run_on_knode(knode, curl), knode, "refresh_cluster_mapping")


def sync_dns(knode: str, fqdn: str, home_pop: str) -> dict[str, Any]:
    body = json.dumps({"fqdn": fqdn, "home_pop": home_pop, "dry_run": False, "skip_notify": False})
    curl = (
        f"curl -s -w '\\n%{{http_code}}' -k -X PUT "
        f"-H 'Content-Type: application/json' "
        f"-d '{body}' "
        f"'{GSLB_DNS_URL}'"
    )
    return _parse_response(_run_on_knode(knode, curl), knode, "sync_dns")


def get_admin_uuid(knode: str, ms_platform_fqdn: str, admin_email: str, tenant_id: str) -> str:
    """Returns the admin user UUID for the given email + tenant."""
    curl = (
        f"curl -s -w '\\n%{{http_code}}' -G "
        f"'http://{ms_platform_fqdn}/api/v1/ui/platform/administration/internal/users' "
        f"--data-urlencode 'filter=username eq \"{admin_email}\"' "
        f"-H 'Host: ngweb-ms' "
        f"-H 'x-netskope-tenantid: {tenant_id}' "
        f"-H 'x-netskope-user-id: dummy@netskope.com' "
        f"-H 'x-netskope-user-role-id: 1'"
    )
    data = _parse_response(_run_on_knode(knode, curl), knode, "get_admin_uuid")
    resources = data.get("Resources", [])
    if not resources:
        raise APIResponseError(404, f"No user found for email {admin_email} in tenant {tenant_id}")
    return resources[0]["id"]


def send_verification_email(knode: str, ms_platform_fqdn: str, user_uuid: str, tenant_id: str) -> dict[str, Any]:
    body = json.dumps({
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
        "Operations": [{
            "op": "Replace",
            "value": {
                "urn:ietf:params:scim:schemas:netskope:2.0:User": {
                    "sendAdminVerificationEmail": True
                }
            }
        }]
    })
    curl = (
        f"curl -s -w '\\n%{{http_code}}' -X PATCH "
        f"'http://{ms_platform_fqdn}/api/v1/ui/platform/administration/internal/users/{user_uuid}' "
        f"-H 'Host: ngweb-ms' "
        f"-H 'x-netskope-tenantid: {tenant_id}' "
        f"-H 'x-netskope-user-id: dummy@netskope.com' "
        f"-H 'x-netskope-user-role-id: 1' "
        f"-H 'Content-Type: application/json' "
        f"-d '{body}'"
    )
    return _parse_response(_run_on_knode(knode, curl), knode, "send_verification_email")
