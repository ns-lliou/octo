import requests

from api.base import do_request

API_PATH = "/client/config"


def get_feature_flags(klbi: str, tenant_id: str) -> requests.Response:
    return do_request("GET", klbi, API_PATH, params={"tenantid": tenant_id})


def set_feature_flag(
    klbi: str, tenant_id: str, flag: str, value: str
) -> requests.Response:
    return do_request("POST", klbi, API_PATH, params={"tenantid": tenant_id}, json={flag: value})
