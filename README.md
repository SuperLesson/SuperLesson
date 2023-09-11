# SuperLesson

[![Contributor Covenant](https://img.shields.io/badge/Contributor%20Covenant-2.1-4baaaa.svg)](code_of_conduct.md)

## Running

To run the scripts in this project using poetry, execute:

`poetry run python scripts/<script-name>`

To set your API key for OpenAI integration, create a `.env` file at the root of
the repository, and add `OPENAI_TOKEN=<your-token>`. Optionally, also add the
`OPENAI_ORG` key.

## Development

First, install `pre-commit`, then run `pre-commit install` to install all the
necessary hooks.
