#!/bin/bash

[[ ! -d .venv ]] && python3 -m venv .venv

. .venv/bin/activate

pip install --no-cache-dir --upgrade pip

echo Bootstrap complete!
