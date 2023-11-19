from superlesson.steps.transcribe import Transcribe


def test_count_tokens():
    text = "This is a sample text for token counting."
    transcriber = Transcribe(slides=None, transcription_source=None)
    token_count = transcriber._count_tokens(text)
    expected_token_count = 13
    assert token_count == expected_token_count


def test_split_in_periods():
    # Prepare input text with punctuation
    text = "This is a sentence. And another one! The last sentence?"

    # Call the function under test
    result = Transcribe._split_in_periods(text)

    # Define the expected result after splitting
    expected_result = [
        "This is a sentence.",
        " And another one!",
        " The last sentence?",
    ]

    # Assert the function output matches the expected result
    assert result == expected_result