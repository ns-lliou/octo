import requests

from api import APIRequestError, APIResponseError

HOST_HEADER = {"Host": "provisioner-pycore-provisioner-tm"}
API_PATH = "/dp/config/sync"


def _do_request(method: str, klbi: str, **kwargs) -> requests.Response:
    try:
        response = requests.request(method, url=f"http://{klbi}{API_PATH}", headers=HOST_HEADER, **kwargs)
    except requests.exceptions.RequestException as e:
        raise APIRequestError(str(e)) from e

    if not response.ok:
        raise APIResponseError(response.status_code, response.text)

    return response


def get_dp_tenant_feature_flags(klbi: str, tenant_id: str) -> requests.Response:
    return _do_request("GET", klbi, params={"tenantid": tenant_id})


def set_dp_tenant_feature_flag(
    klbi: str, tenant_id: str, flag_dict: dict
) -> requests.Response:
    return _do_request("POST", klbi, params={"tenantid": tenant_id}, json=flag_dict)
