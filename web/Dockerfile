# Four stages; the LAST is the default target (D33).
#   deps     node_modules for the build
#   dev      deps + source, `next dev` — docker-compose.override.yml picks this
#   builder  `next build` with a placeholder API URL
#   runtime  node:24-alpine + the standalone server, as the `node` user
#
# Node 24 ships npm 11, matching the host npm that writes package-lock.json.
FROM node:24-alpine AS deps

WORKDIR /app

# Cached separately from source so an edit does not reinstall the dependency tree.
COPY package.json package-lock.json ./

# `npm install`, not `npm ci`: package-lock.json is generated on darwin/arm64 and does
# not carry the linux-musl builds of the Tailwind v4 and lightningcss native binaries
# (npm omits them even when asked with --os/--libc). `npm ci` refuses the lockfile as
# out of sync; `npm install` honours the pinned versions and resolves the platform
# binaries for the image it is building in.
RUN npm install --no-audit --no-fund


FROM deps AS dev

COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0", "--port", "3000"]


FROM deps AS builder

COPY . .

# NEXT_PUBLIC_API_URL is inlined into the browser bundle by `next build`, so a
# real address here would tie the image to one environment. The build gets a
# placeholder instead and entrypoint.sh swaps in the runtime value at
# start. One image then serves compose, the VM and every ECS environment.
ENV NEXT_PUBLIC_API_URL=__SOCIALOPS_API_URL__ \
    NEXT_TELEMETRY_DISABLED=1
# public/ is empty and untracked, so a clean checkout has none; the runtime
# stage COPYs it, so make sure it exists.
RUN mkdir -p public && npm run build


FROM node:24-alpine AS runtime

WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000

# Owned by `node` (not root) because the entrypoint rewrites the placeholder in place.
COPY --from=builder --chown=node:node /app/.next/standalone ./
COPY --from=builder --chown=node:node /app/.next/static ./.next/static
COPY --from=builder --chown=node:node /app/public ./public
COPY --chown=node:node entrypoint.sh /usr/local/bin/socialops-entrypoint.sh

USER node

EXPOSE 3000

ENTRYPOINT ["socialops-entrypoint.sh"]
CMD ["node", "server.js"]
