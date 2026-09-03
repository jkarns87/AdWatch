# Secrets

Two separate concerns, often conflated. Both are covered here.

1. **Redaction** — credentials that pass *through* the system must not settle in logs
   or database columns.
2. **Encryption at rest** — credentials the system stores *deliberately*, on behalf of
   a customer.

---

## 1. Redaction

`app/redact.py` is the single place that masks credential shapes. Anything derived from
an exception, a URL, or user configuration goes through it before being logged or
persisted.

**Why it exists.** `httpx` puts the full request URL in its exception message. A failed
webhook POST therefore wrote a complete Slack token — team id, bot id and the 24-character
secret — into `alerts.error` and printed it to stdout, where Fly retains it. `run.error`
was worse: `collect` returns it to the client in the 502 body.

Masked shapes: Slack and Discord webhook tokens, `api_key`/`token`/`secret`/`password`
key-value pairs, `sk-ant-` keys, 64-hex SerpApi keys, and bearer tokens.

Redaction keeps the identifying prefix — host, team id, `sk-ant-` — and masks only the
secret material. A fully masked string is useless for debugging, and people switch off
tooling that blinds them.

**Applied at:** `alerts/webhook.py`, `alerts/xano.py`, `engine/collect.py`.

`alerts.target` is *not* a leak — it stores `url[:60]` and is already truncated.

### Test fixtures

Use RFC 2606 reserved TLDs (`hooks.slack.invalid`, `discord.invalid`). Well-formed
lookalike credentials trip GitHub push protection, and once they are in git history they
keep tripping it. The redactor is host-agnostic, so coverage is unaffected.

---

## 2. Encryption at rest

Customer-supplied API keys live in `workspace_secrets`, encrypted with Fernet.

| | |
|---|---|
| Envelope | `app/crypto.py` — Fernet via `MultiFernet` |
| Storage | `workspace_secrets` (`workspace_id`, `kind`, `ciphertext`, `last4`) |
| Access | `app/workspace_secrets.py` — the **only** module that reads `ciphertext` |
| Key | `SECRET_ENCRYPTION_KEY`, held in Fly secrets |

Keeping decryption in one module is deliberate. A key decrypted in three routers is a key
that eventually gets logged in one of them.

### Threat model — narrow on purpose

This protects ciphertext **at rest**: a leaked `pg_dump`, a backup, a snapshot, read-only
SQL injection, anyone with `psql`.

It does **not** protect against full host compromise. The running process must be able to
decrypt, so anyone who holds both the database and the environment holds the keys. That is
the same trade every platform makes short of an HSM or an external KMS, and it is written
here so nobody assumes otherwise.

### Generating and rotating

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
flyctl secrets set SECRET_ENCRYPTION_KEY="<key>" -a adwatch-api
```

`SECRET_ENCRYPTION_KEY` accepts a comma-separated list. **The first key encrypts; every
listed key can decrypt.** To rotate:

1. Prepend the new key: `SECRET_ENCRYPTION_KEY="<new>,<old>"`
2. Let writes migrate naturally, or re-save each secret to force it
3. Drop the old key once nothing decrypts with it

A row that cannot be decrypted — typically a half-finished rotation — logs which workspace
and kind, never the contents, and `resolve_key` falls back to the platform key. A botched
rotation degrades a run to platform quota rather than 500-ing every collect.

### Resolution order

```
workspace key (workspace_secrets)  →  platform key (env)  →  ""
```

A workspace that supplies its own key spends its own provider quota. Everyone else uses
the platform key and the plan budget in `plans.py`. This is what makes BYO the unlimited
tier without rewriting the plan model.

### Rules

- **`ciphertext` never leaves the API.** `list_secrets()` returns `kind`, `last4` and
  timestamps only. `last4` is the only part of a credential that may be shown to a user.
- **Never degrade to plaintext.** With no `SECRET_ENCRYPTION_KEY`, `set_secret` raises
  `EncryptionUnavailable`. Storing an unencrypted key would be worse than refusing.
- **`/health` reports `secrets_encryption`** so a misconfigured deploy is visible rather
  than silently unable to accept customer keys.

---

## Platform secrets

These stay in Fly secrets and are never in the database or the image:

```
DATABASE_URL  ANTHROPIC_API_KEY  SERPAPI_API_KEY
DATAPLANE_SHARED_SECRET  SECRET_ENCRYPTION_KEY
```

CI credentials live in GitHub repo secrets: `FLY_API_TOKEN_API`, `FLY_API_TOKEN_WEB`,
`XANO_ACCESS_TOKEN`. Fly deploy tokens are **app-scoped** — one per app, or the other app
gets a bare `unauthorized` with no indication that scope is the problem.
