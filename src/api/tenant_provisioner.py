import json
from typing import Any

from api import APIResponseError
from operations.tsh_client import _parse_response, _run_on_knode

GSLB_DNS_URL = "https://gslb-dns-v2-npe.polaris.netskope.io/api/v0.1/dns/sync/zone/boomskope.com"


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
