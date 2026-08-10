"""Encrypted hosted EODHD credential vault contracts."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import tempfile
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol, cast, runtime_checkable

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from portfell.hosted_catalog import set_authenticated_user_sql


class CredentialVaultError(RuntimeError):
    """Raised when hosted credential handling fails closed."""


def read_credential_secret(path: Path, *, name: str, allowed_lengths: frozenset[int]) -> bytes:
    """Load one required binary credential secret from an external file."""

    try:
        value = path.read_bytes().strip()
    except OSError as error:
        raise CredentialVaultError(f"{name} is unavailable") from error
    if len(value) not in allowed_lengths:
        raise CredentialVaultError(f"{name} has an invalid length")
    return value


def load_key_encryption_key(path: Path, *, version: str) -> KeyEncryptionKey:
    """Load a versioned AES key-encryption key from an external secret file."""

    return KeyEncryptionKey(
        version=version,
        material=_read_key_encryption_key_material(path),
    )


def _read_key_encryption_key_material(path: Path) -> bytes:
    try:
        value = path.read_bytes().strip()
    except OSError as error:
        raise CredentialVaultError("credential key-encryption key is unavailable") from error
    if len(value) in {16, 24, 32}:
        return value
    try:
        decoded = base64.b64decode(value, validate=True)
    except ValueError:
        pass
    else:
        if len(decoded) in {16, 24, 32}:
            return decoded
    try:
        decoded = bytes.fromhex(value.decode("ascii"))
    except UnicodeDecodeError, ValueError:
        pass
    else:
        if len(decoded) in {16, 24, 32}:
            return decoded
    raise CredentialVaultError("credential key-encryption key has an invalid length")


@dataclass(frozen=True)
class KeyEncryptionKey:
    """Versioned key-encryption key loaded from an external secret source."""

    version: str
    material: bytes

    def __post_init__(self) -> None:
        if not self.version:
            raise ValueError("key version is required")
        if len(self.material) not in {16, 24, 32}:
            raise ValueError("KEK material must be 128, 192, or 256 bits")


@dataclass(frozen=True)
class CredentialAssociatedData:
    """Associated data binding encrypted credentials to their owner and schema."""

    credential_id: str
    user_id: str
    provider: str = "eodhd"
    schema_version: int = 1

    def canonical(self) -> bytes:
        """Return stable associated data bytes for authenticated encryption."""

        return (
            f"credential_id={self.credential_id}|user_id={self.user_id}|"
            f"provider={self.provider}|schema_version={self.schema_version}"
        ).encode()


@dataclass(frozen=True)
class EncryptedCredentialRecord:
    """Persistable encrypted credential row without plaintext provider material."""

    credential_id: str
    user_id: str
    provider: str
    status: str
    ciphertext: bytes
    nonce: bytes
    wrapped_data_key: bytes
    wrap_nonce: bytes
    key_version: str
    associated_data: CredentialAssociatedData
    fingerprint_hmac: str
    masked_label: str


@dataclass(frozen=True)
class CredentialStatus:
    """Client-safe credential status response."""

    credential_id: str
    provider: str
    status: str
    key_version: str
    masked_label: str


@runtime_checkable
class CredentialStore(Protocol):
    """Persist encrypted credentials without exposing plaintext provider material."""

    def upsert(self, record: EncryptedCredentialRecord) -> None:
        """Store one logical credential record."""

        ...

    def get(self, *, user_id: str, provider: str = "eodhd") -> EncryptedCredentialRecord | None:
        """Return one credential record for a user and provider."""

        ...


class InMemoryCredentialStore:
    """Small in-memory credential repository used by tests and local adapters."""

    def __init__(self) -> None:
        self._records_by_user_provider: dict[tuple[str, str], EncryptedCredentialRecord] = {}

    def upsert(self, record: EncryptedCredentialRecord) -> None:
        """Store one logical active credential per user and provider."""

        self._records_by_user_provider[(record.user_id, record.provider)] = record

    def get(self, *, user_id: str, provider: str = "eodhd") -> EncryptedCredentialRecord | None:
        """Return the current logical credential record when present."""

        return self._records_by_user_provider.get((user_id, provider))


class FileCredentialStore:
    """Persist encrypted credential records atomically in a trusted local volume."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def upsert(self, record: EncryptedCredentialRecord) -> None:
        """Store an encrypted credential without serializing provider plaintext."""

        records = self._load_records()
        records[(record.user_id, record.provider)] = record
        self._save_records(records)

    def get(self, *, user_id: str, provider: str = "eodhd") -> EncryptedCredentialRecord | None:
        """Return the current encrypted record for one local workspace user."""

        return self._load_records().get((user_id, provider))

    def _load_records(self) -> dict[tuple[str, str], EncryptedCredentialRecord]:
        try:
            payload = cast("object", json.loads(self._path.read_text(encoding="utf-8")))
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError as error:
            raise CredentialVaultError("credential store is invalid") from error
        if not isinstance(payload, list):
            raise CredentialVaultError("credential store has an invalid shape")
        records: dict[tuple[str, str], EncryptedCredentialRecord] = {}
        for item in cast("list[object]", payload):
            if not isinstance(item, dict):
                raise CredentialVaultError("credential store has an invalid record")
            record = _record_from_file_row(cast("dict[str, object]", item))
            records[(record.user_id, record.provider)] = record
        return records

    def _save_records(self, records: Mapping[tuple[str, str], EncryptedCredentialRecord]) -> None:
        self._path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        payload = [_record_to_file_row(record) for _, record in sorted(records.items())]
        with tempfile.NamedTemporaryFile(
            "w",
            dir=self._path.parent,
            encoding="utf-8",
            delete=False,
        ) as temporary:
            json.dump(payload, temporary, sort_keys=True, separators=(",", ":"))
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)
        temporary_path.chmod(0o600)
        temporary_path.replace(self._path)


class CredentialCursor(Protocol):
    """Minimal cursor result contract used by the PostgreSQL credential store."""

    def fetchone(self) -> tuple[object, ...] | None:
        """Return one database row when available."""

        ...


class CredentialConnection(Protocol):
    """Minimal parameterized SQL connection contract for encrypted credentials."""

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> CredentialCursor:
        """Execute parameterized SQL and return a cursor-like result."""

        ...


class PostgresCredentialStore:
    """Persist encrypted credentials through parameterized PostgreSQL statements."""

    def __init__(self, connection: CredentialConnection) -> None:
        self._connection = connection

    def upsert(self, record: EncryptedCredentialRecord) -> None:
        """Replace the active credential without retaining multiple active records."""

        self._bind_user(record.user_id)
        self._connection.execute(
            """
update portfell_app.provider_credentials
set status = 'deleted', deleted_at = now(), updated_at = now()
where user_id = %s and provider = %s and status = 'active' and credential_id <> %s
""",
            (record.user_id, record.provider, record.credential_id),
        )
        self._connection.execute(
            """
insert into portfell_app.provider_credentials (
    credential_id, user_id, provider, status, ciphertext, nonce, wrapped_data_key,
    wrap_nonce, key_version, associated_data, fingerprint_hmac, masked_label
) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
on conflict (credential_id) do update set
    status = excluded.status,
    ciphertext = excluded.ciphertext,
    nonce = excluded.nonce,
    wrapped_data_key = excluded.wrapped_data_key,
    wrap_nonce = excluded.wrap_nonce,
    key_version = excluded.key_version,
    associated_data = excluded.associated_data,
    fingerprint_hmac = excluded.fingerprint_hmac,
    masked_label = excluded.masked_label,
    updated_at = now(),
    revoked_at = case when excluded.status = 'revoked' then now() else null end,
    deleted_at = case when excluded.status = 'deleted' then now() else null end
""",
            (
                record.credential_id,
                record.user_id,
                record.provider,
                record.status,
                record.ciphertext,
                record.nonce,
                record.wrapped_data_key,
                record.wrap_nonce,
                record.key_version,
                json.dumps(
                    {
                        "credential_id": record.associated_data.credential_id,
                        "user_id": record.associated_data.user_id,
                        "provider": record.associated_data.provider,
                        "schema_version": record.associated_data.schema_version,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                record.fingerprint_hmac,
                record.masked_label,
            ),
        )

    def get(self, *, user_id: str, provider: str = "eodhd") -> EncryptedCredentialRecord | None:
        """Load the latest logical credential record for one user and provider."""

        self._bind_user(user_id)
        cursor = self._connection.execute(
            """
select credential_id, user_id, provider, status, ciphertext, nonce, wrapped_data_key,
       wrap_nonce, key_version, associated_data, fingerprint_hmac, masked_label
from portfell_app.provider_credentials
where user_id = %s and provider = %s
order by updated_at desc, credential_id desc
limit 1
""",
            (user_id, provider),
        )
        row = cursor.fetchone()
        return None if row is None else _record_from_postgres_row(row)

    def _bind_user(self, user_id: str) -> None:
        self._connection.execute(*set_authenticated_user_sql(user_id))


def _record_from_postgres_row(row: tuple[object, ...]) -> EncryptedCredentialRecord:
    """Reconstruct one encrypted credential record from a strictly shaped row."""

    if len(row) != 12:
        raise CredentialVaultError("credential row has an invalid shape")
    associated_data_value = row[9]
    if not isinstance(associated_data_value, Mapping):
        raise CredentialVaultError("credential associated data is invalid")
    associated_data = cast("Mapping[str, object]", associated_data_value)
    schema_version = associated_data.get("schema_version")
    if not isinstance(schema_version, int):
        raise CredentialVaultError("credential associated data schema is invalid")
    credential_id = _credential_text(row[0])
    user_id = _credential_text(row[1])
    provider = _credential_text(row[2])
    status = _credential_text(row[3])
    ciphertext = _credential_bytes(row[4])
    nonce = _credential_bytes(row[5])
    wrapped_data_key = _credential_bytes(row[6])
    wrap_nonce = _credential_bytes(row[7])
    key_version = _credential_text(row[8])
    fingerprint_hmac = _credential_text(row[10])
    masked_label = _credential_text(row[11])
    associated_credential_id = _credential_text(associated_data.get("credential_id"))
    associated_user_id = _credential_text(associated_data.get("user_id"))
    associated_provider = _credential_text(associated_data.get("provider"))
    if (associated_credential_id, associated_user_id, associated_provider) != (
        credential_id,
        user_id,
        provider,
    ):
        raise CredentialVaultError("credential associated data does not match row ownership")
    return EncryptedCredentialRecord(
        credential_id=credential_id,
        user_id=user_id,
        provider=provider,
        status=status,
        ciphertext=ciphertext,
        nonce=nonce,
        wrapped_data_key=wrapped_data_key,
        wrap_nonce=wrap_nonce,
        key_version=key_version,
        associated_data=CredentialAssociatedData(
            credential_id=associated_credential_id,
            user_id=associated_user_id,
            provider=associated_provider,
            schema_version=schema_version,
        ),
        fingerprint_hmac=fingerprint_hmac,
        masked_label=masked_label,
    )


def _record_to_file_row(record: EncryptedCredentialRecord) -> dict[str, object]:
    return {
        "credential_id": record.credential_id,
        "user_id": record.user_id,
        "provider": record.provider,
        "status": record.status,
        "ciphertext": base64.b64encode(record.ciphertext).decode("ascii"),
        "nonce": base64.b64encode(record.nonce).decode("ascii"),
        "wrapped_data_key": base64.b64encode(record.wrapped_data_key).decode("ascii"),
        "wrap_nonce": base64.b64encode(record.wrap_nonce).decode("ascii"),
        "key_version": record.key_version,
        "associated_data": {
            "credential_id": record.associated_data.credential_id,
            "user_id": record.associated_data.user_id,
            "provider": record.associated_data.provider,
            "schema_version": record.associated_data.schema_version,
        },
        "fingerprint_hmac": record.fingerprint_hmac,
        "masked_label": record.masked_label,
    }


def _record_from_file_row(row: Mapping[str, object]) -> EncryptedCredentialRecord:
    try:
        return _record_from_postgres_row(
            (
                row["credential_id"],
                row["user_id"],
                row["provider"],
                row["status"],
                base64.b64decode(_credential_text(row["ciphertext"]), validate=True),
                base64.b64decode(_credential_text(row["nonce"]), validate=True),
                base64.b64decode(_credential_text(row["wrapped_data_key"]), validate=True),
                base64.b64decode(_credential_text(row["wrap_nonce"]), validate=True),
                row["key_version"],
                row["associated_data"],
                row["fingerprint_hmac"],
                row["masked_label"],
            )
        )
    except (KeyError, ValueError) as error:
        raise CredentialVaultError("credential store record is invalid") from error


def _credential_text(value: object) -> str:
    """Require one text value from an encrypted credential row."""

    if not isinstance(value, str):
        raise CredentialVaultError("credential row contains invalid text")
    return value


def _credential_bytes(value: object) -> bytes:
    """Require one encrypted byte value from an encrypted credential row."""

    if not isinstance(value, bytes):
        raise CredentialVaultError("credential row contains invalid encrypted material")
    return value


class EodhdCredentialVault:
    """Envelope-encrypted EODHD credential service."""

    def __init__(
        self,
        *,
        store: CredentialStore,
        key_encryption_key: KeyEncryptionKey | None,
        fingerprint_secret: bytes,
    ) -> None:
        if not fingerprint_secret:
            raise ValueError("fingerprint_secret is required")
        self._store = store
        self._key_encryption_key = key_encryption_key
        self._fingerprint_secret = fingerprint_secret

    def set_credential(
        self,
        *,
        user_id: str,
        provider_key: str,
        credential_id: str | None = None,
    ) -> CredentialStatus:
        """Encrypt and store one active EODHD credential for a user."""

        if not provider_key:
            raise CredentialVaultError("provider key is required")
        key = self._require_kek()
        resolved_id = credential_id or str(uuid.uuid4())
        associated_data = CredentialAssociatedData(credential_id=resolved_id, user_id=user_id)
        data_key = AESGCM.generate_key(bit_length=256)
        data_nonce = os.urandom(12)
        wrap_nonce = os.urandom(12)
        ciphertext = AESGCM(data_key).encrypt(
            data_nonce,
            provider_key.encode("utf-8"),
            associated_data.canonical(),
        )
        wrapped_data_key = AESGCM(key.material).encrypt(
            wrap_nonce,
            data_key,
            associated_data.canonical(),
        )
        record = EncryptedCredentialRecord(
            credential_id=resolved_id,
            user_id=user_id,
            provider="eodhd",
            status="active",
            ciphertext=ciphertext,
            nonce=data_nonce,
            wrapped_data_key=wrapped_data_key,
            wrap_nonce=wrap_nonce,
            key_version=key.version,
            associated_data=associated_data,
            fingerprint_hmac=_credential_fingerprint(
                secret=self._fingerprint_secret,
                provider_key=provider_key,
            ),
            masked_label=mask_provider_key(provider_key),
        )
        self._store.upsert(record)
        return self.status(user_id=user_id)

    def unwrap_for_provider_call(self, *, user_id: str) -> str:
        """Decrypt a credential immediately before a provider request."""

        record = self._require_record(user_id=user_id)
        if record.status != "active":
            raise CredentialVaultError("credential is not active")
        if record.associated_data.user_id != user_id:
            raise CredentialVaultError("credential owner mismatch")
        key = self._require_kek()
        if key.version != record.key_version:
            raise CredentialVaultError("credential key version is unavailable")
        try:
            data_key = AESGCM(key.material).decrypt(
                record.wrap_nonce,
                record.wrapped_data_key,
                record.associated_data.canonical(),
            )
            plaintext = AESGCM(data_key).decrypt(
                record.nonce,
                record.ciphertext,
                record.associated_data.canonical(),
            )
        except InvalidTag as error:
            raise CredentialVaultError("credential authentication failed") from error
        return plaintext.decode("utf-8")

    def status(self, *, user_id: str) -> CredentialStatus:
        """Return client-safe credential status metadata."""

        record = self._require_record(user_id=user_id)
        return CredentialStatus(
            credential_id=record.credential_id,
            provider=record.provider,
            status=record.status,
            key_version=record.key_version,
            masked_label=record.masked_label,
        )

    def revoke(self, *, user_id: str) -> CredentialStatus:
        """Mark the current credential revoked."""

        record = self._require_record(user_id=user_id)
        updated = replace(record, status="revoked")
        self._store.upsert(updated)
        return self.status(user_id=user_id)

    def delete(self, *, user_id: str) -> CredentialStatus:
        """Mark the current credential deleted without exposing plaintext."""

        record = self._require_record(user_id=user_id)
        updated = replace(record, status="deleted")
        self._store.upsert(updated)
        return self.status(user_id=user_id)

    def rotate_key(
        self,
        *,
        user_id: str,
        new_key_encryption_key: KeyEncryptionKey,
    ) -> CredentialStatus:
        """Rewrap an active credential under a new KEK without provider-key re-entry."""

        plaintext = self.unwrap_for_provider_call(user_id=user_id)
        original = self._require_record(user_id=user_id)
        self._key_encryption_key = new_key_encryption_key
        return self.set_credential(
            user_id=user_id,
            provider_key=plaintext,
            credential_id=original.credential_id,
        )

    def _require_record(self, *, user_id: str) -> EncryptedCredentialRecord:
        record = self._store.get(user_id=user_id)
        if record is None:
            raise CredentialVaultError("credential not found")
        return record

    def _require_kek(self) -> KeyEncryptionKey:
        if self._key_encryption_key is None:
            raise CredentialVaultError("key-encryption key is unavailable")
        return self._key_encryption_key


def mask_provider_key(provider_key: str) -> str:
    """Return a non-secret label for a provider key."""

    if len(provider_key) <= 8:
        return "<redacted>"
    return f"{provider_key[:4]}...{provider_key[-4:]}"


def redact_credential_text(text: str, *, provider_key: str) -> str:
    """Redact provider-key occurrences from logs or exceptions."""

    return text.replace(provider_key, "<redacted>")


def _credential_fingerprint(*, secret: bytes, provider_key: str) -> str:
    return hmac.new(secret, provider_key.encode("utf-8"), hashlib.sha256).hexdigest()
