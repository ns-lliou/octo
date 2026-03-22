import requests

HOST_HEADER = {"Host": "provisioner-pycore-provisioner-tm"}


def get_feature_flags(klbi: str, tenant_id: str) -> requests.Response:
    return requests.get(
        url=f"http://{klbi}/client/config",
        params={"tenantid": tenant_id},
        headers=HOST_HEADER,
    )


def set_feature_flag(klbi: str, tenant_id: str, flag: str, value: str) -> requests.Response:
    return requests.post(
        url=f"http://{klbi}/client/config",
        params={"tenantid": tenant_id},
        headers=HOST_HEADER,
        json={flag: value},
    )
