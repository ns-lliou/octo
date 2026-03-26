import requests
import uuid

from api import APIRequestError, APIResponseError

HOST_HEADER = {
    "Host": "referential-integrity",
    "x-netskope-trid": str(uuid.uuid4()),
    "x-netskope-tenantid": "",
    "x-netskope-caller-id": "swg-tw",
}

API_OBJECT_CONSUMER_PATH = "/internal/v1/objectconsumers/"
API_CONFIG_OBJECT_PATH = "/internal/v1/objects/"


# Object Consumer APIs
def list_object_consumer(
    klbi: str, tenant_id: str, consumer_name: str
) -> requests.Response:
    """
    List object consumer by name.
    Example: list_object_consumer(klbi="klbivip-ext.c1.qa01-mp-npe.nc1.iad0.nsscloud.net", tenant_id="9988", consumer_name="rtp")
    Expected response: List of object consumers with the specified name.
    {
        "elements": [
            {
                "setting_id": "1",
                "references": [
                    {
                        "object_name": "destination",
                        "ids": ["934e12ab-7da5-4887-b1a2-dc9fd3667298"],
                    }
                ],
                "create_by": "lliou@netskope.com",
                "create_time": "2026-03-26T03:11:10.844Z",
                "modify_by": "lliou@netskope.com",
                "modify_time": "2026-03-26T03:11:18.668Z",
            }
        ],
        "total_count": 1,
    }
    """
    # Update tenant ID in header
    HOST_HEADER["x-netskope-tenantid"] = tenant_id

    try:
        response = requests.get(
            url=f"http://{klbi}{API_OBJECT_CONSUMER_PATH}{consumer_name}",
            headers=HOST_HEADER,
        )
    except requests.exceptions.RequestException as e:
        raise APIRequestError(str(e)) from e

    if not response.ok:
        raise APIResponseError(response.status_code, response.text)

    return response


def get_object_consumer_by_id(
    klbi: str, tenant_id: str, consumer_name: str, consumer_id: str
) -> requests.Response:
    """
    Get object consumer by name and ID.
    Example: get_object_consumer_by_id(klbi="klbivip-ext.c1.qa01-mp-npe.nc1.iad0.nsscloud.net", tenant_id="9988", consumer_name="rtp", consumer_id="1234")
    Expected response: Object consumer details along with its references.
    {
        "setting_id": "1",
        "consumer_name": "rtp",
        "references": [
            {"object_name": "destination", "ids": ["934e12ab-7da5-4887-b1a2-dc9fd3667298"]}
        ],
        "create_by": "lliou@netskope.com",
        "create_time": "2026-03-26T03:11:10.844Z",
        "modify_by": "lliou@netskope.com",
        "modify_time": "2026-03-26T03:11:18.668Z",
    }
    """
    # Update tenant ID in header
    HOST_HEADER["x-netskope-tenantid"] = tenant_id

    try:
        response = requests.get(
            url=f"http://{klbi}{API_OBJECT_CONSUMER_PATH}{consumer_name}/{consumer_id}/references",
            headers=HOST_HEADER,
        )
    except requests.exceptions.RequestException as e:
        raise APIRequestError(str(e)) from e

    if not response.ok:
        raise APIResponseError(response.status_code, response.text)

    return response


# Config Object APIs
def list_config_object(
    klbi: str, tenant_id: str, object_name: str
) -> requests.Response:
    """
    List config object by name.
    Example: list_config_object(klbi="klbivip-ext.c1.qa01-mp-npe.nc1.iad0.nsscloud.net", tenant_id="9988", object_name="destination")
    Expected response: List of config objects with the specified name.
    {
        "elements": [
            {
                "id": "934e12ab-7da5-4887-b1a2-dc9fd3667298",
                "references": [{"consumer": "rtp", "id": ["1"]}]
            }
        ],
        "total_count": 1
    }
    """
    # Update tenant ID in header
    HOST_HEADER["x-netskope-tenantid"] = tenant_id

    try:
        response = requests.get(
            url=f"http://{klbi}{API_CONFIG_OBJECT_PATH}{object_name}",
            headers=HOST_HEADER,
        )
    except requests.exceptions.RequestException as e:
        raise APIRequestError(str(e)) from e

    if not response.ok:
        raise APIResponseError(response.status_code, response.text)

    return response


def get_config_object_by_id(
    klbi: str, tenant_id: str, object_name: str, object_id: str
) -> requests.Response:
    """
    Get config object by name and ID.
    Example: get_config_object_by_id(klbi="klbivip-ext.c1.qa01-mp-npe.nc1.iad0.nsscloud.net", tenant_id="9988", object_name="destination", object_id="1234")
    Expected response: Config object details along with its references.
    {
        "references": [
            {
                "consumer": "rtp",
                "id": [
                    "1"
                ]
            }
        ]
    }
    """
    # Update tenant ID in header
    HOST_HEADER["x-netskope-tenantid"] = tenant_id

    try:
        response = requests.get(
            url=f"http://{klbi}{API_CONFIG_OBJECT_PATH}{object_name}/{object_id}/references",
            headers=HOST_HEADER,
        )
    except requests.exceptions.RequestException as e:
        raise APIRequestError(str(e)) from e

    if not response.ok:
        raise APIResponseError(response.status_code, response.text)

    return response


## Test Code
if __name__ == "__main__":
    klbi = "klbivip-ext.c1.qa01-mp-npe.nc1.iad0.nsscloud.net"
    consumer_name = "rtp"
    object_name = "destination"
    tenant_id = "8268"

    try:
        # consumer_response = list_object_consumer(klbi, tenant_id, consumer_name)
        # print(f"Object Consumer Response: {consumer_response.json()}")

        # config_response = list_config_object(klbi, tenant_id, object_name)
        # print(f"Config Object Response: {config_response.json()}")
        consumer_id = "1"
        consumer_ref_response = get_object_consumer_by_id(
            klbi, tenant_id, consumer_name, consumer_id
        )
        print(f"Object Consumer Reference Response: {consumer_ref_response.json()}")

        object_id = "934e12ab-7da5-4887-b1a2-dc9fd3667298"
        config_ref_response = get_config_object_by_id(
            klbi, tenant_id, object_name, object_id
        )
        print(f"Config Object Reference Response: {config_ref_response.json()}")
    except (APIRequestError, APIResponseError) as e:
        print(f"API Error: {e}")
