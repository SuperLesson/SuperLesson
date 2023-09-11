# SuperLesson

[![Contributor Covenant](https://img.shields.io/badge/Contributor%20Covenant-2.1-4baaaa.svg)](code_of_conduct.md)

## Running

### Setup

SuperLesson (SL) uses
[faster-whisper](https://github.com/guillaumekln/faster-whisper) in order to
transcribe audio. You can use your GPU to run it faster, but you need to install
some dependencies. Refer to their documentation for more details.

<!-- TODO: add instructions for using other models -->

SL also uses ChatGPT in order to improve transcriptions. To set your API key
for OpenAI integration, create a `.env` file at the root of the repository, and
add `OPENAI_TOKEN=<your-token>`. Optionally, also add the `OPENAI_ORG` key.

Finally, install poetry in order to run the project.

### Lesson files

Lessons are stored in the `lessons/` directory. Each lesson is a directory
named after the lesson ID (for now, it's an arbitrary string of your choice).

Each lesson should have at least a mp4, and optionally a pdf. Both should be
named after the lesson id, so for example:

```raw
lessons/
├── biology-1/
│   ├── biology-1.mp4
│   └── biology-1.pdf
└── physics-2/
    └── physics-2.mp4
```

### Executing

To run SL, first enter the `src/` directory, then run

```bash
poetry run python main.py [lesson-id]
```

## Development

First, install `pre-commit`, then run `pre-commit install` to install all the
necessary hooks.
