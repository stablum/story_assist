from app.service import build_question_block, load_template


def test_research_prompt_template_contains_placeholders():
    template = load_template("research_prompt.txt")
    assert "{story_sketch}" in template
    assert "{question_block}" in template


def test_question_block_template_without_preamble():
    output = build_question_block("Where did this happen?", None)
    assert output == "Where did this happen?"


def test_question_block_template_with_preamble():
    output = build_question_block(
        question="Where did this happen?",
        question_preamble="Focus on policy implications.",
    )
    assert "Common preamble to apply:" in output
    assert "Focus on policy implications." in output
    assert "Specific question:" in output
    assert "Where did this happen?" in output
