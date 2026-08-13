const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");
const { URL } = require("node:url");

if (process.argv.includes("--health")) {
  process.exit(0);
}

const port = Number.parseInt(process.env.PORT || "3000", 10);
const apiBaseUrl = process.env.PORTFELL_API_BASE_URL || "http://api:8000";
const distRoot = path.resolve(__dirname, "dist");
const spaRoutes = new Set([
  "/metadata-builder",
  "/univariate-statistics",
  "/bivariate-statistics",
  "/multivariate-statistics",
]);

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
  if (requestUrl.pathname === "/") {
    response.writeHead(303, { location: "/metadata-builder" });
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
  if (spaRoutes.has(requestUrl.pathname) || /^\/projects\/[^/]+\/(metadata-builder|univariate-statistics|bivariate-statistics|multivariate-statistics)$/.test(requestUrl.pathname)) {
    serveFile(response, path.join(distRoot, "index.html"), "text/html; charset=utf-8");
    return;
  }

  response.writeHead(404, { "content-type": "text/plain; charset=utf-8" });
  response.end("Not found");
});

server.listen(port, "0.0.0.0");
