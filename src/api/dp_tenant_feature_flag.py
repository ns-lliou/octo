import requests

from api.provisioner_base import do_request

API_PATH = "/dp/config/sync"


def get_dp_tenant_feature_flags(klbi: str, tenant_id: str) -> requests.Response:
    return do_request("GET", klbi, API_PATH, params={"tenantid": tenant_id})


def set_dp_tenant_feature_flag(
    klbi: str, tenant_id: str, flag_dict: dict
) -> requests.Response:
    return do_request("POST", klbi, API_PATH, params={"tenantid": tenant_id}, json=flag_dict)
