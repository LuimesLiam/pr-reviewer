ARG VARIANT

# This is a base devcontainer image that runs Ubuntu 24.04 LTS with some basic tools for development.
FROM mcr.microsoft.com/devcontainers/base:${VARIANT:-1.2.6-noble}

# Install additional OS updates and packages.
RUN apt-get update 