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

First, you should run `poetry install` in order to install all the
dependencies. Keep in mind that as the project is updated you should run have
to run it again.

To run SL execute

```bash
poetry run superlesson [lesson-id]
```

> Note: you can see the options available by running `poetry run superlesson --help`

This will execute all the following steps:

1. `transcribe`
2. Insert `tmarks`
3. `verify` all transitions using MPV
4. `replace` known bogus words
5. `improve` punctuation using ChatGPT
6. `annotate` the lecture notes

You can also run individual steps using

```bash
poetry run [step]
```

> Note: step names are highlighted above using monospace.

## Development

First, install `pre-commit`, then run `pre-commit install` to install all the
necessary hooks.

To test the project, run

```bash
poetry run pytest tests
```

## Troubleshooting

### I don't have a suitable python installed, how do I run?

You can use `pyenv` to manage python versions. After you've installed `pyenv`,
run

```bash
$ pyenv install 3.10.11
$ pyenv local 3.10.11
$ poetry env use $(which python3)
```
