"""Golden-question set for the self-serve Q&A. Expected values are taken from
Part 1 (which is cross-checked against pandas in test_metrics)."""
import pytest

from urbancart import qa

MONTHS = [f"2026-0{m}" for m in range(1, 7)]

GOLDEN = [
    # question, expected first value (as shown), first channel
    ("What was Meta's CAC last month?", "₹1,115", "Meta Ads"),
    ("What was meta’s cac last month", "₹1,115", "Meta Ads"),          # curly apostrophe, lower case
    ("FB cost per customer in May", "₹958", "Meta Ads"),
    ("Which channel has the best LTV:CAC?", "1.14", "Google Ads"),
    ("Which channel gives the worst return on spend?", "0.42", "Affiliate"),
    ("Repeat purchase rate for Organic", "55.7%", "Organic"),
    ("How much did we spend on Google in March?", "₹62,000", "Google Ads"),
    ("Which channel is getting more expensive?", "+127.2%", "Meta Ads"),
    ("Which channel is cheapest?", "₹611", "Google Ads"),
    ("Revenue per customer for influencers", "₹2,858", "Influencer"),
    ("How many new customers did Instagram bring last month?", "104", "Meta Ads"),
    ("LTV:CAC for affiliate", "0.42", "Affiliate"),
]


@pytest.mark.parametrize("question,expected,channel", GOLDEN)
def test_golden_questions(con, question, expected, channel):
    a = qa.ask(con, question)
    assert a.ok, a.text
    assert expected in a.text
    assert channel in a.text
    assert a.sql and "mart_" in a.sql          # every number traceable to a mart query


@pytest.mark.parametrize("question,fragment", [
    ("What's the CAC for organic?", "no paid spend"),
    ("What was CAC in July?", "outside that range"),
    ("Repeat rate for Meta in March", "full Jan–Jun period"),
    ("What's the weather like?", "couldn't tell which metric"),
    ("", "type a question"),
])
def test_refuses_instead_of_guessing(con, question, fragment):
    a = qa.ask(con, question)
    assert not a.ok
    assert fragment in a.text
    assert a.table is None


@pytest.mark.parametrize("text,channel", [
    ("facebook", "Meta Ads"), ("insta via ig", "Meta Ads"), ("adwords", "Google Ads"),
    ("affiliates", "Affiliate"), ("creators", "Influencer"), ("seo", "Organic"),
])
def test_channel_aliases(text, channel):
    assert qa.parse(f"cac for {text}", MONTHS).channels == [channel]


def test_last_month_is_latest_month_in_data():
    assert qa.parse("spend last month", MONTHS).month == "2026-06"


def test_may_as_verb_is_not_a_month():
    assert qa.parse("May I see the repeat rate?", MONTHS).month is None
    assert qa.parse("Meta CAC in May", MONTHS).month == "2026-05"


def test_comparison_lists_each_channel(con):
    a = qa.ask(con, "Compare CAC for Google and Meta in April")
    assert a.ok and len(a.table) == 2
    assert "₹602" in a.text and "₹886" in a.text


def test_summary_for_a_channel(con):
    a = qa.ask(con, "How is Affiliate doing?")
    assert a.ok and "LTV:CAC 0.42" in a.text and "8.1%" in a.text
