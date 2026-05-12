# Skill: Client Feature Flag

Manage client (tenant) feature flags on Octo stack environments via the provisioner API.
No auth is required. All calls go to `http://{klbi}/client/config` with a `Host` header.

## Environment → KLBI mapping

Read `src/config/stacks.json` to resolve the `k8s_klbi` value for the given environment.
Available environments: `qa01`, `stg01`, `hippo`, `fed1mp`, `devint`, `perf01`.

## API Details

- **Get flags:** `GET http://{klbi}/client/config?tenantid={tenant_id}`
- **Set flag:** `POST http://{klbi}/client/config?tenantid={tenant_id}` with JSON body `{"flag_name": "value"}`
- **Host header (required):** `Host: provisioner-pycore-provisioner-tm`
- All flag values are strings (use `"0"` to disable, `"1"` to enable, or a custom string value).

## Instructions

When the user invokes this skill, extract the following from their prompt:
- `env` — one of the environments above
- `tenant_id` — the tenant ID string
- `action` — `get` or `set`
- (for set) `flag` — the feature flag name
- (for set) `value` — the value to set (`0`, `1`, or custom)

If any required input is missing, ask for it before proceeding.

### Get Feature Flags

Run:
```bash
curl -s -H "Host: provisioner-pycore-provisioner-tm" \
  "http://{klbi}/client/config?tenantid={tenant_id}" | python3 -m json.tool
```

If the user specified a flag name, apply this decision tree in order:

**Step 1 — Exact match**
Check if the input key exists verbatim in the response. If yes, return its value. Done.

**Step 2 — Case-insensitive match**
Check if any key matches when both are lowercased. If yes, return its value with a note:
> "Found as `<actual_key>` (you typed `<input>` — check the casing)."
Done.

**Step 3 — Prefix / suffix match**

3a. **Prefix match** — input is a prefix of a real key (missing a trailing `_word` suffix):
Check if any key starts with `input.lower() + "_"`.
- One match → note "your input appears to be a prefix", ask user to confirm.
- Multiple matches → list them, ask which one they meant.

3b. **Suffix match** — input is a suffix of a real key (missing a leading ticket-number prefix like `nplan####_`):
Check if any key ends with `"_" + input.lower()`.
- One match → note "your input appears to be missing a leading prefix (e.g. `nplan####_`), found `<actual_key>`", ask user to confirm.
- Multiple matches → list them, ask which one they meant.

Flag names prefixed with `nplan####_` follow a newer naming convention tied to ticket numbers. Users commonly omit this prefix — this step is specifically designed to recover from that.

**Step 4 — Edit distance (typo recovery)**
Compute the Levenshtein edit distance between the input and every key in the full flag list. Use this python snippet:
```python
def levenshtein(a, b):
    m, n = len(a), len(b)
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev = dp[:]
        dp[0] = i
        for j in range(1, n + 1):
            dp[j] = prev[j-1] if a[i-1] == b[j-1] else 1 + min(prev[j], dp[j-1], prev[j-1])
    return dp[n]
```
- Compute distance between `input.lower()` and each `key.lower()`.
- Find the minimum distance across all keys.
- If the minimum distance is ≤ 3, collect all keys at that distance (up to 3).
- Present them as suggestions:
  > "Flag `<input>` not found. Did you mean one of these?"
  > - `<suggestion1>`
  > - `<suggestion2>`
  > Then stop — do not auto-select. Ask the user to confirm which one they meant.
- If minimum distance is > 3, say: "Flag `<input>` not found and no close matches found. Use search mode to explore available flags."

**Search mode** (user says "search for flags with X" or "flags containing X") → return all keys where X is a substring of the key (case-insensitive). No edit distance needed here.

### Set Feature Flag

Run:
```bash
curl -s -X POST \
  -H "Host: provisioner-pycore-provisioner-tm" \
  -H "Content-Type: application/json" \
  -d '{"flag_name": "value"}' \
  "http://{klbi}/client/config?tenantid={tenant_id}" | python3 -m json.tool
```

After a successful set, confirm the flag name, value, tenant ID, and environment back to the user.

## Examples

- "get feature flags for tenant 12345 on qa01" → returns all flags
- "get the feature flag destination_profile for tenant 12345 on qa01" → exact match, returns only that flag
- "search for flags with dlp for tenant 99999 on hippo" → partial match, returns all keys containing "dlp"
- "set npa_is_enabled to 1 for tenant 12345 on stg01"
