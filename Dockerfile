FROM nvidia/cuda:12.2.0-devel-ubuntu22.04

WORKDIR /SuperLesson

RUN apt-get update
RUN DEBIAN_FRONTEND=noninteractive apt-get -y install \
    python3.11 \
    python3-pip \
    nvidia-cudnn \
    libcudnn8-dev
RUN pip3 install poetry
RUN mkdir superlesson
RUN touch superlesson/__init__.py

COPY poetry.lock .
COPY pyproject.toml .
COPY README.md .

RUN poetry install --only transcribe

COPY superlesson/. superlesson

CMD exec poetry run transcribe $LESSON
