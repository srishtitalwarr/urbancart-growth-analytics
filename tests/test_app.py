"""Runs the real Streamlit script headlessly and drives the Q&A box."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py")


def test_app_renders_without_errors():
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    assert any("Channel performance" in t.value for t in at.title)


def test_app_answers_a_question():
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.text_input(key="question").input("What was Meta's CAC last month?").run()
    assert not at.exception
    assert any("₹1,115" in s.value for s in at.success)


def test_app_refuses_unknown_question():
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.text_input(key="question").input("What is the weather?").run()
    assert not at.exception
    assert at.warning and not at.success
