FROM node:20-slim AS base

FROM base AS deps
WORKDIR /app
COPY services/web/package.json services/web/package-lock.json* ./
RUN npm ci

FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY services/web/ .
ENV NEXT_PUBLIC_API_URL=https://api.jeromelu.ai
ENV NEXT_PUBLIC_AVATAR_CDN_BASE=https://jeromelu.ai
RUN npm run build

FROM base AS runner
WORKDIR /app
ENV NODE_ENV=production

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
RUN rm -rf ./public/avatar/clips
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000
ENV PORT=3000

CMD ["node", "server.js"]
