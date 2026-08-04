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
const googleJwksUri =
  process.env.CAMOVAR_GOOGLE_JWKS_URI || "https://www.googleapis.com/oauth2/v3/certs";
const googleStateTtlMs =
  Number.parseInt(process.env.CAMOVAR_GOOGLE_STATE_TTL_SECONDS || "600", 10) * 1000;
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
const distRoot = path.resolve(__dirname, "dist");
const spaRoutes = new Set([
  "/metadata-filter",
  "/univariate-statistics",
  "/univariate-filter",
  "/bivariate-statistics",
]);
let googleJwksCache = { expiresAt: 0, keys: [] };

function base64Url(value) {
  return Buffer.from(value).toString("base64url");
}

function randomToken(bytes = 32) {
  return base64Url(crypto.randomBytes(bytes));
}

function sha256Hex(value) {
  return crypto.createHash("sha256").update(value).digest("hex");
}

function stableGoogleUserId(subject) {
  return `google-${sha256Hex(subject).slice(0, 32)}`;
}

function localDevAuthEnabled() {
  return authMode === "local-dev";
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
      (octet, index) =>
        !Number.isInteger(octet) ||
        String(octet) !== parts[index] ||
        octet < 0 ||
        octet > 255,
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
  url.searchParams.set("device_id", `portfell-${sha256Hex(googleRedirectUri).slice(0, 32)}`);
  url.searchParams.set("device_name", "Portfell Local");
}

function readGoogleClientSecret() {
  if (process.env.CAMOVAR_GOOGLE_CLIENT_SECRET) {
    return process.env.CAMOVAR_GOOGLE_CLIENT_SECRET;
  }
  const secretPath = process.env.CAMOVAR_GOOGLE_CLIENT_SECRET_FILE;
  return secretPath ? fs.readFileSync(secretPath, "utf8").trim() : "";
}

function pruneExpiredGoogleStates(now = Date.now()) {
  for (const [stateHash, pending] of pendingGoogleStates.entries()) {
    if (pending.expiresAt <= now || pending.consumed) {
      pendingGoogleStates.delete(stateHash);
    }
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
    headers: {
      accept: "application/json",
      "content-type": "application/x-www-form-urlencoded",
    },
    body,
  });
  const payload = await response.json();
  if (!response.ok || !payload.id_token) {
    throw new Error("google_token_exchange_failed");
  }
  return payload.id_token;
}

async function googleJwks() {
  if (googleJwksCache.expiresAt > Date.now() && googleJwksCache.keys.length > 0) {
    return googleJwksCache.keys;
  }
  const response = await fetch(googleJwksUri, { headers: { accept: "application/json" } });
  const payload = await response.json();
  if (!response.ok || !Array.isArray(payload.keys)) {
    throw new Error("google_jwks_unavailable");
  }
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
  if (header.alg !== "RS256" || !header.kid) {
    throw new Error("invalid_google_id_token_algorithm");
  }

  const keys = await googleJwks();
  const jwk = keys.find((key) => key.kid === header.kid && key.kty === "RSA");
  if (!jwk) throw new Error("google_jwk_not_found");

  const verifier = crypto.createVerify("RSA-SHA256");
  verifier.update(`${encodedHeader}.${encodedPayload}`);
  verifier.end();
  const valid = verifier.verify(
    crypto.createPublicKey({ key: jwk, format: "jwk" }),
    Buffer.from(encodedSignature, "base64url"),
  );
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

function secureCookies() {
  try {
    return new URL(googleRedirectUri).protocol === "https:";
  } catch {
    return false;
  }
}

function cookieHeader(name, value, options = {}) {
  const parts = [`${name}=${encodeURIComponent(value)}`, "Path=/", "SameSite=Lax"];
  if (options.httpOnly) parts.push("HttpOnly");
  if (options.secure) parts.push("Secure");
  if (options.maxAge !== undefined) parts.push(`Max-Age=${options.maxAge}`);
  return parts.join("; ");
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
    auth_provider: cookies[providerCookieName] || "unknown",
    csrf_token: cookies[csrfCookieName] || localDevCsrfToken,
  };
}

function startLocalGoogleLogin(response) {
  response.writeHead(303, {
    location: "/metadata-filter",
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
  const secure = secureCookies();
  const csrfToken = randomToken();
  const email = String(claims.email || "").toLowerCase();
  response.writeHead(303, {
    location: "/metadata-filter",
    "set-cookie": [
      cookieHeader(sessionCookieName, stableGoogleUserId(claims.sub), {
        httpOnly: true,
        secure,
        maxAge: 3600,
      }),
      cookieHeader(csrfCookieName, csrfToken, { secure, maxAge: 3600 }),
      cookieHeader(emailCookieName, email, { httpOnly: true, secure, maxAge: 3600 }),
      cookieHeader(providerCookieName, "google-oidc", {
        httpOnly: true,
        secure,
        maxAge: 3600,
      }),
    ],
  });
  response.end();
}

function logoutSession(response) {
  const secure = secureCookies();
  response.writeHead(303, {
    location: "/metadata-filter",
    "set-cookie": [
      cookieHeader(sessionCookieName, "", { httpOnly: true, secure, maxAge: 0 }),
      cookieHeader(csrfCookieName, "", { secure, maxAge: 0 }),
      cookieHeader(emailCookieName, "", { httpOnly: true, secure, maxAge: 0 }),
      cookieHeader(providerCookieName, "", { httpOnly: true, secure, maxAge: 0 }),
    ],
  });
  response.end();
}

function writeAuthError(response, errorCode) {
  response.writeHead(503, { "content-type": "application/json" });
  response.end(JSON.stringify({ error: errorCode }));
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
  } catch {
    writeAuthError(response, "google_auth_start_failed");
  }
}

async function completeGoogleLogin(callbackUrl, response) {
  try {
    const code = callbackUrl.searchParams.get("code");
    const state = callbackUrl.searchParams.get("state");
    if (!code || !state) throw new Error("google_callback_missing_code_or_state");

    const stateHash = sha256Hex(state);
    const pending = pendingGoogleStates.get(stateHash);
    if (!pending || pending.consumed || pending.expiresAt <= Date.now()) {
      throw new Error("google_callback_invalid_state");
    }
    pending.consumed = true;
    pendingGoogleStates.delete(stateHash);

    const idToken = await exchangeGoogleCode(code, pending.codeVerifier);
    const claims = await verifyGoogleIdToken(idToken, pending.nonce);
    startGoogleSession(response, claims);
  } catch {
    writeAuthError(response, "google_auth_callback_failed");
  }
}

function proxyRequestToTarget(clientRequest, clientResponse, target) {
  const proxyRequest = http.request(
    target,
    {
      method: clientRequest.method,
      headers: { ...clientRequest.headers, host: target.host },
    },
    (proxyResponse) => {
      clientResponse.writeHead(proxyResponse.statusCode || 502, proxyResponse.headers);
      proxyResponse.pipe(clientResponse);
    },
  );
  proxyRequest.on("error", () => {
    clientResponse.writeHead(502, { "content-type": "application/json" });
    clientResponse.end(JSON.stringify({ error: "api_unavailable" }));
  });
  clientRequest.pipe(proxyRequest);
}

function proxyApiRequest(clientRequest, clientResponse) {
  const target = new URL(clientRequest.url.replace(/^\/api/, ""), apiBaseUrl);
  proxyRequestToTarget(clientRequest, clientResponse, target);
}

function proxyAuthRequest(clientRequest, clientResponse) {
  const target = new URL(clientRequest.url, apiBaseUrl);
  proxyRequestToTarget(clientRequest, clientResponse, target);
}

function staticContentType(filePath) {
  if (filePath.endsWith(".js")) return "text/javascript; charset=utf-8";
  if (filePath.endsWith(".css")) return "text/css; charset=utf-8";
  if (filePath.endsWith(".svg")) return "image/svg+xml";
  if (filePath.endsWith(".json")) return "application/json; charset=utf-8";
  return "application/octet-stream";
}

function serveFile(response, filePath, contentType) {
  fs.readFile(filePath, (error, content) => {
    if (error) {
      response.writeHead(error.code === "ENOENT" ? 404 : 500, {
        "content-type": "text/plain; charset=utf-8",
      });
      response.end(error.code === "ENOENT" ? "Not found" : "Server error");
      return;
    }
    response.writeHead(200, {
      "content-type": contentType,
      "cache-control": filePath.endsWith("index.html")
        ? "no-store"
        : "public, max-age=31536000, immutable",
    });
    response.end(content);
  });
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
    logoutSession(response);
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
  if (requestUrl.pathname.startsWith("/assets/")) {
    const resolvedPath = path.resolve(distRoot, requestUrl.pathname.slice(1));
    if (!resolvedPath.startsWith(`${distRoot}${path.sep}`)) {
      response.writeHead(400, { "content-type": "text/plain; charset=utf-8" });
      response.end("Bad request");
      return;
    }
    serveFile(response, resolvedPath, staticContentType(resolvedPath));
    return;
  }
  if (spaRoutes.has(requestUrl.pathname)) {
    if (!sessionFromRequest(request)) {
      void startGoogleLogin(response);
      return;
    }
    serveFile(response, path.join(distRoot, "index.html"), "text/html; charset=utf-8");
    return;
  }

  response.writeHead(404, { "content-type": "text/plain; charset=utf-8" });
  response.end("Not found");
});

server.listen(port, "0.0.0.0");

module.exports = {
  createGoogleAuthRequest,
  parseCookies,
  sessionFromRequest,
  stableGoogleUserId,
};
