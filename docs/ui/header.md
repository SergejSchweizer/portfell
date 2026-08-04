
# Header

The desktop header is a `64px` bar containing the Portfell brand, the four-stage workspace label,
a write-only EODHD key input, and the `Fetch all metadata` button. Submission
stores the key through the credential vault and calls
`POST /api/metadata/fetch-all`. The plaintext key is cleared immediately and is
retained in the field until the page reloads. It is never returned, logged, or
stored in browser storage.

Below the header, the desktop shell has a persistent project sidebar and one
main-content region constrained to `1240px` from the sidebar edge. Project navigation, the selected project, and workflow
stage status belong to the sidebar, not the header. Mobile drawer behavior is
defined in `docs/ui/layout/sidebar.md`.
