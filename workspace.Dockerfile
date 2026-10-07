FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    build-essential \
    git \
    curl \
    wget \
	nodejs \
	npm \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g opencode-ai

WORKDIR /workspace

ENTRYPOINT ["/bin/bash"]
