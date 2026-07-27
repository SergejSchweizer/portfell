FROM node:24-alpine AS runtime

WORKDIR /app
COPY apps/web/package.json ./
COPY apps/web/index.html ./
COPY apps/web/tsconfig.json ./
COPY apps/web/tsconfig.node.json ./
COPY apps/web/vite.config.ts ./
COPY apps/web/server.js ./
COPY apps/web/design-tokens.json ./
COPY apps/web/styles ./styles
COPY apps/web/src ./src

RUN addgroup -S camovar && adduser -S -G camovar -u 10001 camovar
USER camovar

EXPOSE 3000
CMD ["node", "server.js"]
