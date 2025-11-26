# Translating Apps with Argos Translate

This project provides a script to translate `.arb` files from a source language to a target language using Argos Translate.

## Overview

* Place your input `.arb` files in the `input/` folder.
* Run the translation script `main.py`.
* Translated files will be generated in the `output/` folder.

## Environment Variables

* `SOURCE_LANG` → source language code (e.g., `fr`)
* `TARGET_LANG` → target language code (e.g., `en`)

These can be set in your shell or through `docker-compose.yml` for dynamic language selection.

## Running Locally

1. Create a Python virtual environment (if not already):

```bash
python3 -m venv venv
source venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the script:

```bash
python src/main.py
```

## Running with Docker

1. Build and start the container:

```bash
docker-compose up --build
```

2. Input files are mounted or copied into the container; translated output will appear in `output/`.

## Folder Structure

```
.
├── src/            # Python script (main.py)
├── input/          # ARB input files
├── output/         # Translated ARB output files
├── requirements.txt
├── docker-compose.yml
└── Dockerfile
```

## Notes

* Avoid copying the Python virtual environment (`venv`) into the Docker image; let Docker handle package installation.
* Docker images can be pre-built and pushed to a container registry to speed up deployments.
* Example ARB files should include the `@@locale` key for proper language translation.

## Example

Input (`input/input.arb`):

```json
{
  "@@locale": "fr",
  "hello": "Bonjour",
  "welcome": "Bienvenue",
  "logout": "Se déconnecter"
}
```

Output (`output/input.arb` after translation to English):

```json
{
  "@@locale": "en",
  "hello": "Hello",
  "welcome": "Welcome",
  "logout": "Log out"
}
```
