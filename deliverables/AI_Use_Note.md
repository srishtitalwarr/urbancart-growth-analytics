# AI-use note

- **Tools:** Claude Code (Claude Opus) in VS Code, for profiling the raw CSVs, drafting the DuckDB SQL, the pandas cross-check, the charts, the Streamlit app and the tests.
- **How I checked it:** every headline number is recomputed independently in pandas, which shares no code with the SQL (`src/urbancart/sanity.py`, 11/11 checks match). The 42 pytest tests pin the key figures. I hand-checked Google's CAC (₹400,000 ÷ 655).
- **What the AI got wrong:** its first take was that the QA test accounts made Affiliate look like the *best* channel. The numbers showed 1.10 vs Google's 1.14, so they make it look *nearly as good*, not best. I corrected the memo and charts. It also first reported 310 test-account orders. That count included duplicate rows, and the correct figure after de-duplication is 285.
