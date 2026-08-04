
# Header

The desktop header is a `64px` bar containing the Portfell brand, the four-stage workspace label,
a write-only EODHD key input, saved masked-key status, and the `Fetch all metadata` button. Submission
stores a newly entered key through the credential vault and calls
`POST /api/metadata/fetch-all`. The plaintext key remains only in the controlled
session field until the page reloads; it is never returned, logged, or stored in
browser storage. An active saved credential
is shown only as its server-provided masked label and permits metadata refresh
without entering the plaintext key again.

Below the header, the desktop shell has a persistent project sidebar and one
main-content region constrained to `1240px` from the sidebar edge. Project navigation, the selected project, and workflow
stage status belong to the sidebar, not the header. Mobile drawer behavior is
defined in `docs/ui/layout/sidebar.md`.
