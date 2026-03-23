import requests

from api.provisioner_base import do_request

API_PATH = "/org/config/proxy/refresh"


def regenerate_proxy_config(klbi: str, tenant_id: str) -> requests.Response:
    return do_request("POST", klbi, API_PATH, params={"tenantid": tenant_id})
