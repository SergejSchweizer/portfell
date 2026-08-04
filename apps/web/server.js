const http = require("node:http");
const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const { URL } = require("node:url");

if (process.argv.includes("--health")) {
  process.exit(0);
}

const port = Number.parseInt(process.env.PORT || "3000", 10);
const apiBaseUrl = process.env.CAMOVAR_API_BASE_URL || "http://api:8000";
const authMode = process.env.CAMOVAR_AUTH_MODE || "google";
const googleClientId = process.env.CAMOVAR_GOOGLE_CLIENT_ID || "";
const googleRedirectUri =
  process.env.CAMOVAR_GOOGLE_REDIRECT_URI || `http://localhost:${port}/auth/google/callback`;
const googleAllowedDomain = process.env.CAMOVAR_GOOGLE_ALLOWED_DOMAIN || "";
const googleAuthEndpoint =
  process.env.CAMOVAR_GOOGLE_AUTH_ENDPOINT || "https://accounts.google.com/o/oauth2/v2/auth";
const googleTokenEndpoint =
  process.env.CAMOVAR_GOOGLE_TOKEN_ENDPOINT || "https://oauth2.googleapis.com/token";
const googleJwksUri = process.env.CAMOVAR_GOOGLE_JWKS_URI || "https://www.googleapis.com/oauth2/v3/certs";
const googleStateTtlMs = Number.parseInt(process.env.CAMOVAR_GOOGLE_STATE_TTL_SECONDS || "600", 10) * 1000;
const localDevUserId = "local-google-dev-user";
const localDevCsrfToken = "valid-csrf";
const localDevGoogleEmail = (
  process.env.CAMOVAR_LOCAL_DEV_GOOGLE_EMAIL || "local-google-dev-user@example.test"
).toLowerCase();
const sessionCookieName = "camovar_session_user";
const csrfCookieName = "camovar_csrf";
const emailCookieName = "camovar_auth_email";
const providerCookieName = "camovar_auth_provider";
const pendingGoogleStates = new Map();
let googleJwksCache = { expiresAt: 0, keys: [] };

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function base64Url(buffer) {
  return Buffer.from(buffer).toString("base64url");
}

function randomToken(bytes = 32) {
  return base64Url(crypto.randomBytes(bytes));
}

function sha256Hex(value) {
  return crypto.createHash("sha256").update(value).digest("hex");
}

function stableGoogleUserId(subject) {
  return "google-" + sha256Hex(subject).slice(0, 32);
}

function localDevAuthEnabled() {
  if (authMode === "local-dev") return true;
  return false;
}

function googleAuthConfigured() {
  return Boolean(googleClientId && googleRedirectUri);
}

function privateIpv4Address(hostname) {
  const parts = hostname.split(".");
  if (parts.length !== 4) return false;
  const octets = parts.map((part) => Number.parseInt(part, 10));
  if (
    octets.some(
      (octet, index) => !Number.isInteger(octet) || String(octet) !== parts[index] || octet < 0 || octet > 255
    )
  ) {
    return false;
  }
  const [first, second] = octets;
  return (
    first === 10 ||
    first === 127 ||
    (first === 172 && second >= 16 && second <= 31) ||
    (first === 192 && second === 168)
  );
}

function googleRedirectUsesPrivateIp() {
  try {
    return privateIpv4Address(new URL(googleRedirectUri).hostname);
  } catch {
    return false;
  }
}

function applyGooglePrivateIpDeviceParams(url) {
  if (!googleRedirectUsesPrivateIp()) return;
  url.searchParams.set("device_id", "camovar-" + sha256Hex(googleRedirectUri).slice(0, 32));
  url.searchParams.set("device_name", "Camovar Research Local");
}

function readGoogleClientSecret() {
  if (process.env.CAMOVAR_GOOGLE_CLIENT_SECRET) return process.env.CAMOVAR_GOOGLE_CLIENT_SECRET;
  const secretPath = process.env.CAMOVAR_GOOGLE_CLIENT_SECRET_FILE;
  if (!secretPath) return "";
  return fs.readFileSync(secretPath, "utf8").trim();
}

function pruneExpiredGoogleStates(now = Date.now()) {
  for (const [stateHash, pending] of pendingGoogleStates.entries()) {
    if (pending.expiresAt <= now || pending.consumed) pendingGoogleStates.delete(stateHash);
  }
}

function createGoogleAuthRequest() {
  pruneExpiredGoogleStates();
  const state = randomToken();
  const nonce = randomToken();
  const codeVerifier = randomToken(48);
  const codeChallenge = base64Url(crypto.createHash("sha256").update(codeVerifier).digest());
  pendingGoogleStates.set(sha256Hex(state), {
    codeVerifier,
    nonce,
    expiresAt: Date.now() + googleStateTtlMs,
    consumed: false,
  });
  const url = new URL(googleAuthEndpoint);
  url.searchParams.set("client_id", googleClientId);
  url.searchParams.set("redirect_uri", googleRedirectUri);
  url.searchParams.set("response_type", "code");
  url.searchParams.set("scope", "openid email profile");
  url.searchParams.set("state", state);
  url.searchParams.set("nonce", nonce);
  url.searchParams.set("code_challenge", codeChallenge);
  url.searchParams.set("code_challenge_method", "S256");
  url.searchParams.set("prompt", "select_account");
  applyGooglePrivateIpDeviceParams(url);
  return url.toString();
}

async function exchangeGoogleCode(code, codeVerifier) {
  const clientSecret = readGoogleClientSecret();
  if (!clientSecret) throw new Error("google_client_secret_missing");
  const body = new URLSearchParams({
    client_id: googleClientId,
    client_secret: clientSecret,
    code,
    code_verifier: codeVerifier,
    grant_type: "authorization_code",
    redirect_uri: googleRedirectUri,
  });
  const response = await fetch(googleTokenEndpoint, {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded", accept: "application/json" },
    body,
  });
  const payload = await response.json();
  if (!response.ok || !payload.id_token) throw new Error("google_token_exchange_failed");
  return payload.id_token;
}

async function googleJwks() {
  if (googleJwksCache.expiresAt > Date.now() && googleJwksCache.keys.length > 0) {
    return googleJwksCache.keys;
  }
  const response = await fetch(googleJwksUri, { headers: { accept: "application/json" } });
  const payload = await response.json();
  if (!response.ok || !Array.isArray(payload.keys)) throw new Error("google_jwks_unavailable");
  googleJwksCache = { expiresAt: Date.now() + 3600 * 1000, keys: payload.keys };
  return googleJwksCache.keys;
}

function jsonPart(value) {
  return JSON.parse(Buffer.from(value, "base64url").toString("utf8"));
}

async function verifyGoogleIdToken(idToken, expectedNonce) {
  const parts = idToken.split(".");
  if (parts.length !== 3) throw new Error("invalid_google_id_token");
  const [encodedHeader, encodedPayload, encodedSignature] = parts;
  const header = jsonPart(encodedHeader);
  const claims = jsonPart(encodedPayload);
  if (header.alg !== "RS256" || !header.kid) throw new Error("invalid_google_id_token_algorithm");
  const keys = await googleJwks();
  const jwk = keys.find((key) => key.kid === header.kid && key.kty === "RSA");
  if (!jwk) throw new Error("google_jwk_not_found");
  const verifier = crypto.createVerify("RSA-SHA256");
  verifier.update(`${encodedHeader}.${encodedPayload}`);
  verifier.end();
  const valid = verifier.verify(crypto.createPublicKey({ key: jwk, format: "jwk" }), Buffer.from(encodedSignature, "base64url"));
  if (!valid) throw new Error("invalid_google_id_token_signature");
  const now = Math.floor(Date.now() / 1000);
  if (!["https://accounts.google.com", "accounts.google.com"].includes(claims.iss)) {
    throw new Error("invalid_google_issuer");
  }
  if (claims.aud !== googleClientId) throw new Error("invalid_google_audience");
  if (!claims.sub) throw new Error("missing_google_subject");
  if (claims.nonce !== expectedNonce) throw new Error("invalid_google_nonce");
  if (Number(claims.exp || 0) <= now) throw new Error("expired_google_id_token");
  if (claims.email_verified !== true && claims.email_verified !== "true") {
    throw new Error("google_email_unverified");
  }
  if (googleAllowedDomain && claims.hd !== googleAllowedDomain) {
    throw new Error("google_hosted_domain_not_allowed");
  }
  return claims;
}

function userLabel(session) {
  if (!session) return "";
  return String(session.email || session.display_name || session.user_id || "").toLowerCase();
}

function authProviderLabel(session) {
  if (!session || !session.auth_provider) return "";
  return String(session.auth_provider).toLowerCase();
}

function brandMarkup(session = null) {
  const label = userLabel(session);
  const provider = authProviderLabel(session);
  const userLine = label
    ? `<span class="brand-user" data-auth-user>${escapeHtml(label)}${provider ? ` · ${escapeHtml(provider)}` : ""}</span>`
    : "";
  return `<div class="brand"><span class="brand-mark" aria-hidden="true">F</span><span class="brand-copy"><span>Camovar Research</span>${userLine}</span></div>`;
}

function statisticsStepButton(step, index) {
  const current = index === 0 ? ' aria-current="step"' : "";
  const disabled = index === 0 ? "" : " disabled";
  return `<button class="statistics-path__step" type="button" data-statistics-step="${step.id}"${current}${disabled}>
    <span class="statistics-path__index" aria-hidden="true">${index + 1}</span>
    <span class="funnel-copy">
      <span class="funnel-label">${escapeHtml(step.label)}</span>
      <span class="funnel-status">ready</span>
    </span>
  </button>`;
}

function statisticsPanel(step, index) {
  return `<section class="statistics-page" data-statistics-page="${step.id}"${index === 0 ? "" : " hidden"}>
    <div class="progress-banner" data-statistics-progress-banner="${step.id}">
      <div>
        <p class="eyebrow">${step.id === "load-data" ? "data load" : "statistics compute"}</p>
        <h2>${escapeHtml(step.label)}</h2>
        <p class="subtle" data-statistics-status="${step.id}">Idle. Select ${escapeHtml(step.actionLabel || "Compute")} to run this step for the current project.</p>
      </div>
      <button class="primary" type="button" data-compute-statistics="${step.id}">${escapeHtml(step.actionLabel || "Compute")}</button>
      <progress value="0" max="100" data-statistics-progress="${step.id}"></progress>
    </div>
    ${step.id === "univariate" ? univariateStatisticsTableMarkup() : ""}
  </section>`;
}

function univariateStatisticsTableMarkup() {
  return `<div class="statistics-table-panel">
    <div>
      <h3>Univariate Statistics Filters</h3>
      <p class="subtle" data-univariate-summary-status>Compute univariate statistics to populate this table.</p>
    </div>
    <div class="statistics-table-wrap">
      <table class="statistics-table">
        <thead>
          <tr>
            <th>Statistic</th>
            <th>Mean</th>
            <th>Median</th>
            <th>+- 3 std</th>
            <th>Filter</th>
          </tr>
        </thead>
        <tbody data-univariate-summary-body>
          <tr><td colspan="5">Compute univariate statistics to populate this table.</td></tr>
        </tbody>
      </table>
    </div>
  </div>`;
}

const DIST_ROOT = path.join(__dirname, "dist");
const SPA_ROUTES = new Set([
  "/metadata-filter",
  "/univariate-statistics",
  "/univariate-filter",
  "/bivariate-statistics",
]);

function serveFile(response, filePath, contentType) {
  fs.readFile(filePath, (error, content) => {
    if (error) {
      response.writeHead(error.code === "ENOENT" ? 404 : 500, { "content-type": "text/plain" });
      response.end(error.code === "ENOENT" ? "Not found" : "Server error");
      return;
    }
    response.writeHead(200, { "content-type": contentType, "cache-control": "no-store" });
    response.end(content);
  });
}

function staticContentType(filePath) {
  if (filePath.endsWith(".js")) return "text/javascript; charset=utf-8";
  if (filePath.endsWith(".css")) return "text/css; charset=utf-8";
  if (filePath.endsWith(".svg")) return "image/svg+xml";
  if (filePath.endsWith(".json")) return "application/json; charset=utf-8";
  return "application/octet-stream";
}

const server = http.createServer((request, response) => {
  const requestUrl = new URL(request.url || "/", `http://${request.headers.host || "localhost"}`);
  if (requestUrl.pathname === "/health") {
    response.writeHead(200, { "content-type": "application/json" });
    response.end(JSON.stringify({ status: "ok" }));
    return;
  }
  if (requestUrl.pathname.startsWith("/api/")) {
    proxyApiRequest(request, response);
    return;
  }
  if (requestUrl.pathname === "/auth/google/start") {
    void startGoogleLogin(response);
    return;
  }
  if (requestUrl.pathname === "/auth/google/callback") {
    void completeGoogleLogin(requestUrl, response);
    return;
  }
  if (requestUrl.pathname === "/auth/logout") {
    logoutLocalGoogleSession(response);
    return;
  }
  if (requestUrl.pathname.startsWith("/auth/")) {
    proxyAuthRequest(request, response);
    return;
  }
  if (requestUrl.pathname === "/") {
    response.writeHead(303, { location: "/metadata-filter" });
    response.end();
    return;
  }
  if (!sessionFromRequest(request) && SPA_ROUTES.has(requestUrl.pathname)) {
    void startGoogleLogin(response);
    return;
  }
  if (requestUrl.pathname.startsWith("/assets/")) {
    const relativePath = requestUrl.pathname.slice(1);
    const resolvedPath = path.resolve(DIST_ROOT, relativePath);
    if (!resolvedPath.startsWith(path.resolve(DIST_ROOT) + path.sep)) {
      response.writeHead(400, { "content-type": "text/plain" });
      response.end("Bad request");
      return;
    }
    serveFile(response, resolvedPath, staticContentType(resolvedPath));
    return;
  }
  if (SPA_ROUTES.has(requestUrl.pathname)) {
    serveFile(response, path.join(DIST_ROOT, "index.html"), "text/html; charset=utf-8");
    return;
  }
  response.writeHead(404, { "content-type": "text/plain" });
  response.end("Not found");
});

server.listen(port, "0.0.0.0");

function cookieHeader(name, value, options = {}) {
  const parts = [`${name}=${encodeURIComponent(value)}`, "Path=/", "SameSite=Lax"];
  if (options.httpOnly) parts.push("HttpOnly");
  if (options.secure) parts.push("Secure");
  if (options.maxAge !== undefined) parts.push(`Max-Age=${options.maxAge}`);
  return parts.join("; ");
}

async function startGoogleLogin(response) {
  try {
    if (localDevAuthEnabled()) {
      startLocalGoogleLogin(response);
      return;
    }
    if (!googleAuthConfigured()) throw new Error("google_auth_not_configured");
    response.writeHead(303, { location: createGoogleAuthRequest() });
    response.end();
  } catch (_error) {
    writeAuthError(response, "google_auth_start_failed");
  }
}

async function completeGoogleLogin(callbackUrl, response) {
  try {
    const code = callbackUrl.searchParams.get("code");
    const state = callbackUrl.searchParams.get("state");
    if (!code || !state) throw new Error("google_callback_missing_code_or_state");
    const pending = pendingGoogleStates.get(sha256Hex(state));
    if (!pending || pending.consumed || pending.expiresAt <= Date.now()) {
      throw new Error("google_callback_invalid_state");
    }
    pending.consumed = true;
    pendingGoogleStates.delete(sha256Hex(state));
    const idToken = await exchangeGoogleCode(code, pending.codeVerifier);
    const claims = await verifyGoogleIdToken(idToken, pending.nonce);
    startGoogleSession(response, claims);
  } catch (_error) {
    writeAuthError(response, "google_auth_callback_failed");
  }
}

function startLocalGoogleLogin(response) {
  response.writeHead(303, {
    location: "/",
    "set-cookie": [
      cookieHeader(sessionCookieName, localDevUserId, { httpOnly: true, maxAge: 3600 }),
      cookieHeader(csrfCookieName, localDevCsrfToken, { maxAge: 3600 }),
      cookieHeader(emailCookieName, localDevGoogleEmail, { httpOnly: true, maxAge: 3600 }),
      cookieHeader(providerCookieName, "local-dev-google", { httpOnly: true, maxAge: 3600 }),
    ],
  });
  response.end();
}

function startGoogleSession(response, claims) {
  const csrfToken = randomToken();
  const email = String(claims.email || "").toLowerCase();
  response.writeHead(303, {
    location: "/",
    "set-cookie": [
      cookieHeader(sessionCookieName, stableGoogleUserId(claims.sub), { httpOnly: true, maxAge: 3600 }),
      cookieHeader(csrfCookieName, csrfToken, { maxAge: 3600 }),
      cookieHeader(emailCookieName, email, { httpOnly: true, maxAge: 3600 }),
      cookieHeader(providerCookieName, "google-oidc", { httpOnly: true, maxAge: 3600 }),
    ],
  });
  response.end();
}

function logoutLocalGoogleSession(response) {
  response.writeHead(303, {
    location: "/",
    "set-cookie": [
      cookieHeader(sessionCookieName, "", { httpOnly: true, maxAge: 0 }),
      cookieHeader(csrfCookieName, "", { maxAge: 0 }),
      cookieHeader(emailCookieName, "", { httpOnly: true, maxAge: 0 }),
      cookieHeader(providerCookieName, "", { httpOnly: true, maxAge: 0 }),
    ],
  });
  response.end();
}

function writeAuthError(response, errorCode) {
  response.writeHead(503, { "content-type": "application/json" });
  response.end(JSON.stringify({ error: errorCode }));
}

function parseCookies(cookieHeaderValue) {
  const cookies = {};
  for (const part of String(cookieHeaderValue || "").split(";")) {
    const [rawName, ...rawValueParts] = part.trim().split("=");
    if (!rawName) continue;
    cookies[rawName] = decodeURIComponent(rawValueParts.join("="));
  }
  return cookies;
}

function sessionFromRequest(request) {
  const cookies = parseCookies(request.headers.cookie);
  if (!cookies[sessionCookieName]) return null;
  return {
    authenticated: true,
    user_id: cookies[sessionCookieName],
    email: cookies[emailCookieName] || cookies[sessionCookieName],
    display_name: cookies[emailCookieName] || cookies[sessionCookieName],
    auth_provider: cookies[providerCookieName] || "unknown",
    csrf_token: cookies[csrfCookieName] || localDevCsrfToken,
  };
}

function proxyApiRequest(clientRequest, clientResponse) {
  const target = new URL(clientRequest.url.replace(/^\/api/, ""), apiBaseUrl);
  proxyRequestToTarget(clientRequest, clientResponse, target);
}

function proxyAuthRequest(clientRequest, clientResponse) {
  const target = new URL(clientRequest.url, apiBaseUrl);
  proxyRequestToTarget(clientRequest, clientResponse, target);
}

function proxyRequestToTarget(clientRequest, clientResponse, target) {
  const proxyRequest = http.request(
    target,
    {
      method: clientRequest.method,
      headers: Object.assign({}, clientRequest.headers, { host: target.host }),
    },
    (proxyResponse) => {
      clientResponse.writeHead(proxyResponse.statusCode || 502, proxyResponse.headers);
      proxyResponse.pipe(clientResponse);
    }
  );
  proxyRequest.on("error", () => {
    clientResponse.writeHead(502, { "content-type": "application/json" });
    clientResponse.end(JSON.stringify({ error: "api_unavailable" }));
  });
  clientRequest.pipe(proxyRequest);
}

module.exports = {
  applyGooglePrivateIpDeviceParams,
  createGoogleAuthRequest,
  logoutLocalGoogleSession,
  parseCookies,
  proxyApiRequest,
  proxyAuthRequest,
  sessionFromRequest,
  startLocalGoogleLogin,
};
