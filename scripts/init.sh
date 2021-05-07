#!/bin/bash
set -e

if ! test -d venv; then
    echo "Creating python virtualenv...";
    python3 -m venv venv
    ./venv/bin/pip install --upgrade pip
    ./venv/bin/pip install -r requirements.txt
fi

./venv/bin/pip install -e .
git submodule update --init
