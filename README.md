# SuperLesson

[![Contributor Covenant](https://img.shields.io/badge/Contributor%20Covenant-2.1-4baaaa.svg)](code_of_conduct.md)

## Setup

SuperLesson (SL) uses [faster-whisper](https://github.com/guillaumekln/faster-whisper) in order to
transcribe audio.
You can use your GPU to run it faster, but you need to install some dependencies.
Refer to their documentation for more details.

<!-- TODO: add instructions for using other models -->

SL also uses ChatGPT in order to improve transcriptions. To set your API key
for OpenAI integration, create a `.env` file at the root of the repository, and
add `OPENAI_TOKEN=<your-token>`. Optionally, also add the `OPENAI_ORG` key.

Install [poetry](https://python-poetry.org/) and run `poetry install` in order to install
all the dependencies. Keep in mind that as the project is updated you should run have to run it
again.

### Lesson files

Each lesson should have at least a video file, and optionally a PDF for annotations. So for
example:

```raw
lessons/
├── biology-1/
│   ├── video.mp4
│   └── presentation.pdf
└── physics-2/
    └── lecture-2.mp4
```

## Running

> ⚠️ In order to run the `enumerate` step, SL needs to be run in a terminal that supports the [Kitty
> graphics protocol](https://sw.kovidgoyal.net/kitty/graphics-protocol/).

Use `poetry run` to run SL:

```sh
poetry run superlesson [lesson-id]
```

> A list of options is available through `poetry run superlesson --help`

This will execute all the following steps:

1. `transcribe`
2. `merge` segments using transition frames
3. `verify` all transitions using MPV
4. `enumerate` slides from tframes
5. `replace` known bogus words
6. `improve` punctuation using ChatGPT
7. `annotate` the lecture notes

You can also run individual steps using

```bash
poetry run [step]
```

> Note: step names are highlighted above using monospace.

### CUDA Support

Transcriptions can be run faster on GPU.
If you have an Nvidia GPU available, the transcription step can be run within a docker environment
with CUDA by passing the `--with-docker` flag.

If you prefer to run without a container, check out instructions on the [faster-whisper docs](https://github.com/guillaumekln/faster-whisper#gpu).

### Comparing steps

If you think some step is misbehaving, or would simply like to see what is happening, you can use
the `--diff` flag followed by the two steps you want to compare, e.g.:

```
poetry run superlesson --diff merge improve
```

Note that only steps that generate some text output may be used.

## Development

First, install `pre-commit`, then run `pre-commit install` to install all the
necessary hooks.

To test the project, run

```bash
poetry run pytest
```

## Troubleshooting

### I don't have a suitable python installed, how do I run?

You can use `pyenv` to manage python versions. After you've installed `pyenv`, run

```bash
$ pyenv install 3.10.11
$ pyenv local 3.10.11
$ poetry env use $(which python3)
```
