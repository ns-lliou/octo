import requests

from api.base import do_request

API_PATH = "/org/config/dlp/refresh"


def regenerate_dlp_config(klbi: str, tenant_id: str) -> requests.Response:
    return do_request("POST", klbi, API_PATH, params={"tenantid": tenant_id})
