# Node 24 ships npm 11, matching the host npm that writes package-lock.json.
FROM node:24-alpine

WORKDIR /app

# Cached separately from source so an edit does not reinstall the dependency tree.
COPY package.json package-lock.json ./

# `npm install`, not `npm ci`: package-lock.json is generated on darwin/arm64 and does
# not carry the linux-musl builds of the Tailwind v4 and lightningcss native binaries
# (npm omits them even when asked with --os/--libc). `npm ci` refuses the lockfile as
# out of sync; `npm install` honours the pinned versions and resolves the platform
# binaries for the image it is building in.
RUN npm install --no-audit --no-fund

COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0", "--port", "3000"]
