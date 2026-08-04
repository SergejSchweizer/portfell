
# Header

The header contains the Portfell brand, a write-only EODHD key input, and the
`Fetch all metadata` button. Submission stores the key through the credential
vault and calls `POST /api/metadata-filter/fetch-all-metadata`. The plaintext key
is cleared immediately and is never returned, logged, or stored in browser
storage.
