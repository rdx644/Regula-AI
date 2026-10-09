FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG NEXT_PUBLIC_API_URL=/api
ARG API_PROXY_ORIGIN
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL API_PROXY_ORIGIN=$API_PROXY_ORIGIN NEXT_TELEMETRY_DISABLED=1
RUN npm run build
FROM node:22-slim AS runtime
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3000
WORKDIR /app
RUN groupadd --gid 10001 regulaai && useradd --uid 10001 --gid regulaai --no-create-home regulaai
COPY --from=build --chown=regulaai:regulaai /app/.next/standalone ./
COPY --from=build --chown=regulaai:regulaai /app/.next/static ./.next/static
COPY --from=build --chown=regulaai:regulaai /app/public ./public
USER regulaai
EXPOSE 3000
CMD ["node", "server.js"]
