import requests

from api.provisioner_base import do_request

API_PATH = "/pop/allpopmappings"

def get_all_tenants_in_stack(klbi: str) -> requests.Response:
    return do_request("GET", klbi, API_PATH)
