"""Optional Streamlit client.

Run:  streamlit run app/ui.py
"""
import streamlit as st

from app.generate.answer import answer

st.set_page_config(page_title="Car Manual Assistant", page_icon="🚗")
st.title("🚗 Automotive Maintenance Assistant")
st.caption("Answers are grounded in owner's manuals and cite their source.")

col1, col2, col3 = st.columns(3)
make = col1.text_input("Make", "")
model = col2.text_input("Model", "")
year_str = col3.text_input("Year", "")
reasoning = st.toggle("Diagnostic (multi-step) mode", value=False)

question = st.text_area("Your question", "What is the recommended tyre pressure?")

if st.button("Ask", type="primary"):
    year = int(year_str) if year_str.strip().isdigit() else None
    with st.spinner("Retrieving from the manual..."):
        res = answer(question, make or None, model or None, year, reasoning)
    if res["refused"]:
        st.warning(res["text"])
    else:
        st.markdown(res["text"])
        if res["citations"]:
            st.caption("Sources: " + ", ".join(res["citations"]))
