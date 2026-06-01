import base64
import hashlib
import json
import os
from pathlib import Path
from typing import Any

# Must be set before pylclient reads it
os.environ.setdefault("NSFLIGHT_UNMASKED_SECRETS", "1")

from api import APIRequestError, APIResponseError

try:
    from pylclient.secrets.secret import Secret as _PylSecret
    _PYLCLIENT_OK = True
except ImportError:
    _PylSecret = None  # type: ignore[assignment]
    _PYLCLIENT_OK = False

try:
    import psycopg2 as _psycopg2
    _PSYCOPG2_OK = True
except ImportError:
    _psycopg2 = None  # type: ignore[assignment]
    _PSYCOPG2_OK = False

try:
    import pymysql as _pymysql
    _PYMYSQL_OK = True
except ImportError:
    _pymysql = None  # type: ignore[assignment]
    _PYMYSQL_OK = False

_POSTGRES_VAULT_PATH = "webui/aws_postgres_db"
_POSTGRES_DB_NAME = "cpcs-authentication"
_MARIADB_PORT = 3306

_STACKS_LOCAL_PATH = Path(__file__).parent.parent / "config" / "stacks_local.json"


def _load_mariadb_creds(stack_env: str) -> tuple[str, str]:
    """Load MariaDB user/password from stacks_local.json for the given stack."""
    if not _STACKS_LOCAL_PATH.exists():
        raise APIRequestError(
            f"stacks_local.json not found at {_STACKS_LOCAL_PATH} — "
            f"copy src/config/stacks_local.json.example to stacks_local.json and fill in credentials"
        )
    local = json.loads(_STACKS_LOCAL_PATH.read_text())
    stack = local.get(stack_env.lower())
    if not stack:
        raise APIRequestError(
            f"No MariaDB credentials found for stack '{stack_env}' in stacks_local.json"
        )
    user = stack.get("mariadb_user")
    password = stack.get("mariadb_password")
    if not user or not password:
        raise APIRequestError(
            f"stacks_local.json entry for '{stack_env}' is missing mariadb_user or mariadb_password"
        )
    return user, password


def _make_pbkdf2_credential(password: str) -> tuple[str, str]:
    """Return (secret_data_json, metadata_json) for a fresh PBKDF2-HMAC-SHA256 credential."""
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 600000, dklen=64)
    secret_data = json.dumps({
        "salt": base64.b64encode(salt).decode("ascii"),
        "password": base64.b64encode(dk).decode("ascii"),
    })
    metadata = json.dumps({
        "config": {"iterations": 600000, "derivedKeyLength": 64},
        "algorithm": "PBKDF2-HMAC-SHA256",
    })
    return secret_data, metadata


def is_aws_migrated(stack_env: str, mariadb_host: str, tenant_url_hostname: str) -> bool:
    """
    Detect whether a tenant is on the AWS-migrated Postgres path by checking if
    admin_users exists in its MariaDB tenant DB.

    Returns True  → Postgres path (use activate_admin_postgres)
    Returns False → legacy MariaDB path (use activate_admin_mariadb)
    """
    if not _PYMYSQL_OK:
        raise APIRequestError("pymysql is not installed — run: pip install -r requirements.txt")

    db_user, db_password = _load_mariadb_creds(stack_env)
    try:
        conn = _pymysql.connect(
            host=mariadb_host,
            port=_MARIADB_PORT,
            user=db_user,
            password=db_password,
            database="core_data",
            connect_timeout=10,
        )
    except Exception as e:
        raise APIRequestError(f"Could not connect to MariaDB at {mariadb_host}: {e}") from e

    try:
        with conn.cursor() as cur:
            # Resolve the per-tenant DB name from core_data
            cur.execute(
                "SELECT dbname FROM org_info WHERE ui_hostname LIKE %s LIMIT 1",
                (f"%{tenant_url_hostname}%",),
            )
            row = cur.fetchone()
            if not row:
                raise APIResponseError(
                    404,
                    f"Could not find tenant DB for hostname '{tenant_url_hostname}' in core_data.org_info",
                )
            tenant_db = row[0]

            cur.execute(f"USE `{tenant_db}`")
            cur.execute(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_name = 'admin_users'"
            )
            count = cur.fetchone()[0]
    except (APIRequestError, APIResponseError):
        raise
    except Exception as e:
        raise APIResponseError(500, f"MariaDB migration check failed: {e}") from e
    finally:
        conn.close()

    return count == 0  # 0 = table gone → AWS-migrated


def activate_admin_mariadb(
    stack_env: str, mariadb_host: str, tenant_url_hostname: str, admin_email: str, admin_password: str
) -> dict[str, Any]:
    """
    Step 5 (legacy MariaDB path, e.g. STG01): activate the admin account via direct SQL.

    :param stack_env: Stack key from stacks.json, e.g. "stg01"
    :param mariadb_host: MariaDB host IP from stacks.json mariadb_host
    :param tenant_url_hostname: Short hostname portion of the tenant FQDN (e.g. "tomcat-02-qa01")
    :param admin_email: Admin email address (username in admin_users)
    :param admin_password: Password to set
    :returns: dict with per-operation outcomes
    """
    if not _PYMYSQL_OK:
        raise APIRequestError("pymysql is not installed — run: pip install -r requirements.txt")

    try:
        from passlib.hash import sha256_crypt as _sha256_crypt
    except ImportError:
        raise APIRequestError("passlib is not installed — run: pip install -r requirements.txt")

    db_user, db_password = _load_mariadb_creds(stack_env)
    password_hash = _sha256_crypt.using(rounds=5000).hash(admin_password)

    try:
        conn = _pymysql.connect(
            host=mariadb_host,
            port=_MARIADB_PORT,
            user=db_user,
            password=db_password,
            database="core_data",
            connect_timeout=10,
        )
    except Exception as e:
        raise APIRequestError(f"Could not connect to MariaDB at {mariadb_host}: {e}") from e

    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT dbname FROM org_info WHERE ui_hostname LIKE %s LIMIT 1",
                (f"%{tenant_url_hostname}%",),
            )
            row = cur.fetchone()
            if not row:
                raise APIResponseError(
                    404,
                    f"Could not find tenant DB for hostname '{tenant_url_hostname}' in core_data.org_info",
                )
            tenant_db = row[0]

        conn.select_db(tenant_db)

        with conn.cursor() as cur:
            # Verify admin row exists
            cur.execute("SELECT admin_id FROM admin_users WHERE username = %s", (admin_email,))
            if not cur.fetchone():
                raise APIResponseError(
                    404,
                    f"No admin_users row for '{admin_email}' in {tenant_db} — provisioner may not have created it yet",
                )

            cur.execute(
                """
                UPDATE admin_users
                SET password            = %s,
                    logged_in_once      = 1,
                    admin_verified      = 1,
                    tos_seen            = 1,
                    num_failed_login    = 0,
                    passwd_last_changed = UNIX_TIMESTAMP(),
                    last_login          = UNIX_TIMESTAMP()
                WHERE username = %s
                """,
                (password_hash, admin_email),
            )
            cur.execute(
                "DELETE FROM admin_users_verification "
                "WHERE admin_id IN (SELECT admin_id FROM admin_users WHERE username = %s)",
                (admin_email,),
            )
        conn.commit()
    except (APIRequestError, APIResponseError):
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise APIResponseError(500, f"SQL activation failed: {e}") from e
    finally:
        conn.close()

    return {"tenant_db": tenant_db, "admin_users_updated": True, "verification_row_deleted": True}


def activate_admin_postgres(stack_env: str, admin_uuid: str, admin_password: str) -> dict[str, Any]:
    """
    Step 5 (Postgres / AWS-migrated path): activate the admin account directly via SQL,
    bypassing the email verification and password-set flows.

    Requires nsflightauth login and network access to the AWS RDS endpoint.

    :param stack_env: Stack key from stacks.json, e.g. "qa01"
    :param admin_uuid: Admin user UUID (obtained from Step 4a get_admin_uuid)
    :param admin_password: Password to set on the admin account
    :returns: dict with per-operation outcomes
    """
    if not _PYLCLIENT_OK:
        raise APIRequestError(
            "pylclient is not installed — run:\n"
            "pip install --no-cache-dir -r requirements_local.txt "
            "--index-url https://artifactory-rd.netskope.io/artifactory/api/pypi/ns-pypi/simple"
        )
    if not _PSYCOPG2_OK:
        raise APIRequestError("psycopg2-binary is not installed — run: pip install -r requirements.txt")

    vault_key = stack_env.upper()
    try:
        all_creds = _PylSecret(_POSTGRES_VAULT_PATH).get_all()
    except Exception as e:
        raise APIRequestError(
            f"Vault credential fetch failed (nsflightauth login required?): {e}"
        ) from e

    if vault_key not in all_creds:
        raise APIRequestError(
            f"No Postgres credentials found for stack key '{vault_key}' in vault path "
            f"'{_POSTGRES_VAULT_PATH}'. Available: {sorted(all_creds.keys())}. "
            f"This stack may not yet be AWS-migrated."
        )

    creds = all_creds[vault_key]
    secret_data, metadata = _make_pbkdf2_credential(admin_password)

    try:
        conn = _psycopg2.connect(
            host=creds["aws_cpcs_host"],
            port=int(creds["aws_cpcs_port"]),
            user=creds["aws_cpcs_user"],
            password=creds["aws_cpcs_password"],
            dbname=_POSTGRES_DB_NAME,
        )
    except Exception as e:
        raise APIRequestError(f"Could not connect to Postgres ({_POSTGRES_DB_NAME}): {e}") from e

    try:
        with conn:
            with conn.cursor() as cur:
                # Verify the user row exists before touching anything
                cur.execute(
                    "SELECT id, is_verified FROM public.users WHERE id = %s::uuid",
                    (admin_uuid,),
                )
                user_row = cur.fetchone()
                if not user_row:
                    raise APIResponseError(
                        404,
                        f"User '{admin_uuid}' not found in public.users — "
                        f"stack '{stack_env}' may not be AWS-migrated, or the UUID is incorrect",
                    )

                # 1. Mark user as verified
                cur.execute(
                    "UPDATE public.users SET is_verified = true WHERE id = %s::uuid",
                    (admin_uuid,),
                )

                # 2. Replace any existing PASSWORD credential, then insert fresh one
                cur.execute(
                    "DELETE FROM public.user_credential WHERE user_id = %s::uuid AND type = 'PASSWORD'",
                    (admin_uuid,),
                )
                cur.execute(
                    """
                    INSERT INTO public.user_credential
                        (user_id, type, secret_data, metadata, is_active, created_at, updated_at)
                    VALUES
                        (%s::uuid, 'PASSWORD', %s::jsonb, %s::jsonb, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    (admin_uuid, secret_data, metadata),
                )

                # 3. Clear set_password required action
                cur.execute(
                    "UPDATE public.user_required_action SET is_active = false "
                    "WHERE user_id = %s::uuid AND required_action_name = 'set_password'",
                    (admin_uuid,),
                )

                # 4. Clear tos required action
                cur.execute(
                    "UPDATE public.user_required_action SET is_active = false "
                    "WHERE user_id = %s::uuid AND required_action_name = 'tos'",
                    (admin_uuid,),
                )
    except (APIRequestError, APIResponseError):
        raise
    except Exception as e:
        raise APIResponseError(500, f"SQL activation failed: {e}") from e
    finally:
        conn.close()

    return {"users_row_updated": True, "credential_set": True}
