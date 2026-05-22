# Stage 1: build
FROM node:22-alpine AS builder
WORKDIR /app
ARG PUBLIC_DEFAULT_LOCALE=en
ENV PUBLIC_DEFAULT_LOCALE=${PUBLIC_DEFAULT_LOCALE}
ARG APP_VERSION=v0.0.0-dev
ARG GIT_SHA=unknown
ENV APP_VERSION=${APP_VERSION}
ENV GIT_SHA=${GIT_SHA}
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN echo "export const version = '${APP_VERSION}'; export const gitSha = '${GIT_SHA}';" > src/lib/version.ts
RUN echo "{\"version\":\"${APP_VERSION}\",\"sha\":\"${GIT_SHA}\"}" > static/version.json
RUN npm run build

# Stage 2: serve
FROM nginx:alpine
COPY --from=builder /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
