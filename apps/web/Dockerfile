
FROM node:26-alpine AS build

WORKDIR /app
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci
COPY apps/web/index.html ./
COPY apps/web/tsconfig.json apps/web/tsconfig.node.json apps/web/vite.config.ts ./
COPY apps/web/src ./src
COPY apps/web/styles ./styles
RUN npm run typecheck && npm run build

FROM node:26-alpine AS runtime
WORKDIR /app
COPY apps/web/server.js ./server.js
COPY --from=build /app/dist ./dist
USER node
EXPOSE 3000
CMD ["node", "server.js"]
