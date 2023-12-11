from click.testing import CliRunner

from superlesson.cli import cli


def test_transcribe():
    runner = CliRunner()
    result = runner.invoke(cli, ["transcribe", "test meow"])

    assert result.exit_code == 0
    assert "Transcribing lesson" in result.output
    # Adicione mais asserções conforme necessário
