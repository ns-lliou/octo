from copy import deepcopy
from datetime import datetime, timedelta, timezone
import requests

from api import APIRequestError, APIResponseError

API_SCIM_ME_PATH = "/api/v2/platform/administration/scim/Me"

_BASE_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
}

COMMON_PATCH_OP_REQUEST_PAYLOAD = {
    "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
    "Operations": [],
}


def _headers(ci_session: str) -> dict:
    return {**_BASE_HEADERS, "Cookie": f"ci_session={ci_session}"}


def get_scim_me(hostname: str, ci_session: str) -> requests.Response:
    """
    (Get Method)
    Get details about the current web UI user via the SCIM Me endpoint.

    Example response:
    {
        "id": "42f89e07-5dcb-11f0-9eac-0242ac110002",
        "userName": "lliou@netskope.com",
        "active": true,
        "externalId": null,
        "metadata": {
            "created": null,
            "lastModified": null,
            "location": "https://hornet-01-stg01.stg.boomskope.com/api/v2/administration/scim/Users/42f89e07-5dcb-11f0-9eac-0242ac110002"
        },
        "urn:ietf:params:scim:schemas:netskope:2.0:User": {
            "lastLogin": "2026-03-29T12:46:43.000Z",
            "provisionedBy": "LOCAL",
            "recordType": "USER",
            "role": { "value": 1, "display": "Tenant Admin" },
            "apiAccessToken": {
                "expiresOn": "2028-12-22T12:52:15.000Z",
                "issuedOn": "2026-03-29T12:52:17.000Z"
            },
            "isVerified": true,
            "isLocked": false,
            "samlAssertedRoleId": null,
            "authType": "API_KEY",
            "mfa": { "enabled": false, "configs": [] }
        },
        "schemas": [
            "urn:ietf:params:scim:schemas:core:2.0:User",
            "urn:ietf:params:scim:schemas:extension:netskope:2.0:User"
        ]
    }
    """
    try:
        response = requests.get(
            f"https://{hostname}{API_SCIM_ME_PATH}",
            headers=_headers(ci_session),
            timeout=10,
        )
    except requests.exceptions.RequestException as e:
        raise APIRequestError(str(e)) from e

    if not response.ok:
        raise APIResponseError(response.status_code, response.text)

    return response


def generate_api_token(
    hostname: str, ci_session: str, expire_in_days: int = 12
) -> requests.Response:
    """
    (PATCH Method)
    Generate a new API token for the current user. Set the expire_in_days parameter to control the token expiration
    (default: 12 days).

    Example request payload (1 day expiration, today is 2026/03/29):
    {
        "schemas": [
            "urn:ietf:params:scim:api:messages:2.0:PatchOp"
        ],
        "Operations": [
            {
                "op": "Replace",
                "value": {
                    "urn:ietf:params:scim:schemas:netskope:2.0:User": {
                        "apiAccessToken": {
                            "expiresOn": "2026-03-30T13:51:00.000Z",
                            "generate": true
                        }
                    }
                }
            }
        ]
    }

    Example response:
    {
        "id": "42f89e07-5dcb-11f0-9eac-0242ac110002",
        "userName": "lliou@netskope.com",
        "active": true,
        "externalId": null,
        "metadata": {
            "created": null,
            "lastModified": null,
            "location": "https://hornet-01-stg01.stg.boomskope.com/api/v2/administration/scim/Users/42f89e07-5dcb-11f0-9eac-0242ac110002"
        },
        "urn:ietf:params:scim:schemas:netskope:2.0:User": {
            "lastLogin": "2026-03-29T12:46:43.000Z",
            "provisionedBy": "LOCAL",
            "recordType": "USER",
            "role": {
                "value": 1
            },
            "apiAccessToken": {
                "value": "cmJhY3YzOmZhRjdCTjRtM1EwOEkzYWdZRFFveg==",
                "expiresOn": "2026-03-30T13:51:00.000Z",
                "issuedOn": "2026-03-29T13:51:05.000Z"
            },
            "isVerified": true,
            "isLocked": false,
            "samlAssertedRoleId": null,
            "authType": "API_KEY",
            "mfa": {
                "enabled": false,
                "configs": []
            }
        },
        "schemas": [
            "urn:ietf:params:scim:schemas:core:2.0:User",
            "urn:ietf:params:scim:schemas:extension:netskope:2.0:User"
        ]
    }
    The "apiAccessToken" object will only exists when the API token is generated.
    Consider this can be used to check if the user has generated API token before.
    If yes and call this API, the old token will be invalidated and a new token will be generated and returned
    in the response.
    If no, a new token will be generated and returned in the response.

    Note: we can only get the new token value from the response of this endpoint, due to security reasons.
    So you need to capture the response to get the new token and return.
    Need to warn the user to keep the new token safe as it won't be retrievable again after this response.
    """

    # Count the expiry date based on the current date and expire_in_days, then format it to the required string format

    expire_on = (datetime.now(timezone.utc) + timedelta(days=expire_in_days)).strftime(
        "%Y-%m-%dT%H:%M:%S.000Z"
    )
    # Construct the request payload.
    generate_api_token_payload = deepcopy(COMMON_PATCH_OP_REQUEST_PAYLOAD)
    generate_api_token_payload["Operations"] = [
        {
            "op": "Replace",
            "value": {
                "urn:ietf:params:scim:schemas:netskope:2.0:User": {
                    "apiAccessToken": {"expiresOn": expire_on, "generate": True}
                }
            },
        }
    ]
    try:
        response = requests.patch(
            f"https://{hostname}{API_SCIM_ME_PATH}",
            headers=_headers(ci_session),
            json=generate_api_token_payload,
            timeout=10,
        )
    except requests.exceptions.RequestException as e:
        raise APIRequestError(str(e)) from e

    if not response.ok:
        raise APIResponseError(response.status_code, response.text)

    return response


def revoke_api_token(hostname: str, ci_session: str) -> requests.Response:
    """
    (Patch Method)
    Revoke the existing API token for the current user.

    Example request payload:
    {
        "schemas": [
            "urn:ietf:params:scim:api:messages:2.0:PatchOp"
        ],
        "Operations": [
            {
                "op": "Remove",
                "path": "urn:ietf:params:scim:schemas:netskope:2.0:User.apiAccessToken"
            }
        ]
    }

    Example response:
    {
        "id": "42f89e07-5dcb-11f0-9eac-0242ac110002",
        "userName": "lliou@netskope.com",
        "active": true,
        "externalId": null,
        "metadata": {
            "created": null,
            "lastModified": null,
            "location": "https://hornet-01-stg01.stg.boomskope.com/api/v2/administration/scim/Users/42f89e07-5dcb-11f0-9eac-0242ac110002"
        },
        "urn:ietf:params:scim:schemas:netskope:2.0:User": {
            "lastLogin": "2026-03-29T12:46:43.000Z",
            "provisionedBy": "LOCAL",
            "recordType": "USER",
            "role": {
                "value": 1
            },
            "isVerified": true,
            "isLocked": false,
            "samlAssertedRoleId": null,
            "authType": "API_KEY",
            "mfa": {
                "enabled": false,
                "configs": []
            }
        },
        "schemas": [
            "urn:ietf:params:scim:schemas:core:2.0:User",
            "urn:ietf:params:scim:schemas:extension:netskope:2.0:User"
        ]
    }

    After calling this endpoint, the existing API token will be revoked and can't be used anymore.
    The "apiAccessToken" object will be removed from the response after the token is revoked,
    which can be used to check if the token is revoked successfully.

    Repeating the revoke operation when there's no existing token or the token is already revoked will not cause error,
    it's idempotent. The response will be the same as above with no "apiAccessToken" object in the response.
    """
    revoke_api_token_payload = deepcopy(COMMON_PATCH_OP_REQUEST_PAYLOAD)
    revoke_api_token_payload["Operations"] = [
        {
            "op": "Remove",
            "path": "urn:ietf:params:scim:schemas:netskope:2.0:User.apiAccessToken",
        }
    ]
    try:
        response = requests.patch(
            f"https://{hostname}{API_SCIM_ME_PATH}",
            headers=_headers(ci_session),
            json=revoke_api_token_payload,
            timeout=10,
        )
    except requests.exceptions.RequestException as e:
        raise APIRequestError(str(e)) from e

    if not response.ok:
        raise APIResponseError(response.status_code, response.text)

    return response


# Test Code
if __name__ == "__main__":
    hostname = "hornet-01-stg01.stg.boomskope.com"
    ci_session = "bnNtZW1jYWNoZWQ61IKM6K6OorYHE4jPW4uSUVPOexbh97V"

    get_me_response = get_scim_me(hostname, ci_session)
    print(get_me_response.json())

    get_api_token_response = generate_api_token(hostname, ci_session, expire_in_days=1)
    print(
        "New API token value (only available in this response, won't be retrievable again):"
    )
    print(
        get_api_token_response.json()["urn:ietf:params:scim:schemas:netskope:2.0:User"][
            "apiAccessToken"
        ]["value"]
    )

    get_me_response = get_scim_me(hostname, ci_session)
    print(get_me_response.json())

    revoke_api_token_response = revoke_api_token(hostname, ci_session)
    print(
        "API token revoked, check response to confirm the apiAccessToken object is removed:"
    )
    print(revoke_api_token_response.json())
