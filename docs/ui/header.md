
# Header

## Table Of Contents

- [Credential And Metadata Controls](#credential-and-metadata-controls)
- [Shell Layout](#shell-layout)

## Credential And Metadata Controls

The desktop header is a `64px` bar containing the Portfell brand, the four-module workspace label,
a write-only EODHD key input, saved masked-key status, and the `Fetch all metadata` button. Submission
stores a newly entered key through the credential vault and calls
`POST /api/metadata/fetch-all`. The plaintext key remains only in the controlled
session field until the page reloads; it is never returned, logged, or stored in
browser storage. An active saved credential
is shown only as its server-provided masked label and permits metadata refresh
without entering the plaintext key again.

## Shell Layout

Below the header, the desktop shell has a persistent project sidebar and one
main-content region constrained to `1240px` from the sidebar edge. At `900px`
and below, the header also exposes a native `Current project` selector so users
can switch among every server-returned project without opening navigation. The
workflow stages remain in the mobile drawer; its behavior is defined in
`docs/ui/layout/sidebar.md`.
