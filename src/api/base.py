import requests

from api import APIRequestError, APIResponseError

HOST_HEADER = {"Host": "provisioner-pycore-provisioner-tm"}


def do_request(method: str, klbi: str, api_path: str, **kwargs) -> requests.Response:
    try:
        response = requests.request(method, url=f"http://{klbi}{api_path}", headers=HOST_HEADER, **kwargs)
    except requests.exceptions.RequestException as e:
        raise APIRequestError(str(e)) from e

    if not response.ok:
        raise APIResponseError(response.status_code, response.text)

    return response
