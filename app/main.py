import os
import requests
import streamlit as st
import pandas as pd

API_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")

st.set_page_config(
    page_title="CFO Copilot",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
.stApp { background: #0B1220; color: #E8EEF8; }
[data-testid="stSidebar"] { background: #111C2E; border-right: 1px solid #26364D; }
.block-container { max-width: 1500px; padding-top: 2rem; padding-bottom: 3rem; }
h1, h2, h3 { color: #F2F6FC !important; font-weight: 650 !important; }
p, label, [data-testid="stMarkdownContainer"] { color: #C1CDDE; }
[data-testid="stMetric"] {
    background: linear-gradient(145deg, #1A2A42, #142136);
    border: 1px solid #2B4262; padding: 20px; border-radius: 13px;
}
[data-testid="stMetricLabel"] { color: #A9BBD3 !important; }
[data-testid="stMetricValue"] { color: #64A5FF !important; }
.stButton > button {
    background: #2878E7; color: white; border: 0;
    border-radius: 9px; font-weight: 600; min-height: 42px;
}
.stButton > button:hover { background: #1765CE; color: white; }
[data-baseweb="select"] > div, [data-baseweb="input"] > div {
    background: #182438; border-color: #344760; border-radius: 8px;
}
[data-testid="stDataFrame"] { border: 1px solid #2B405B; border-radius: 10px; }
[data-testid="stExpander"] { background: #152238; border: 1px solid #2B405B; border-radius: 10px; }
hr { border-color: #293B54; }
footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


def api_request(method, endpoint, **kwargs):
    try:
        response = requests.request(
            method,
            f"{API_URL}{endpoint}",
            timeout=120,
            **kwargs
        )
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as exc:
        return None, str(exc)


def show_error(error):
    st.error(f"API error: {error}")


st.title("📊 CFO Copilot")
st.caption("Evidence-grounded financial intelligence | MySQL | Local inference architecture")

health, health_error = api_request("GET", "/api/v1/health")

with st.sidebar:
    st.header("System Status")

    if health_error:
        st.error("API unavailable")
    else:
        st.success("API connected")
        st.write("Database initialized:", health.get("database_initialized"))

    st.caption(f"API: {API_URL}")

    if st.button("Initialize / Ingest Data", use_container_width=True):
        with st.spinner("Ingesting financial data..."):
            result, error = api_request("POST", "/api/v1/ingest")
        if error:
            show_error(error)
        else:
            st.success(result.get("status", "Completed"))
            st.rerun()

    st.divider()
    page = st.radio(
        "Navigation",
        [
            "Executive Dashboard",
            "Financial Analysis",
            "Document Search",
            "CFO Assistant",
            "System Information"
        ]
    )

companies, company_error = api_request("GET", "/api/v1/companies")

if company_error:
    companies = []
    st.warning("Unable to load companies. Check API and MySQL.")

company_df = pd.DataFrame(companies or [])

if not company_df.empty and "company_id" in company_df.columns:
    company_options = company_df["company_id"].astype(str).tolist()
else:
    company_options = []

if page != "System Information":
    st.sidebar.subheader("Analysis Context")

    if company_options:
        company_id = st.sidebar.selectbox("Company", company_options)
    else:
        company_id = None

    fiscal_year = st.sidebar.number_input(
        "Fiscal Year", min_value=2000, max_value=2100,
        value=2024, step=1
    )
    fiscal_quarter = st.sidebar.selectbox(
        "Fiscal Quarter", [1, 2, 3, 4], index=3
    )
else:
    company_id = None
    fiscal_year = 2024
    fiscal_quarter = 4


if page == "Executive Dashboard":
    st.header("Executive Dashboard")

    if company_id:
        result, error = api_request(
            "POST",
            "/api/v1/kpis",
            json={
                "company_id": company_id,
                "fiscal_year": int(fiscal_year),
                "fiscal_quarter": int(fiscal_quarter)
            }
        )

        if error:
            show_error(error)
        else:
            kpis = result.get("kpis", [])
            available = [k for k in kpis if k.get("value") is not None]
            missing = [k for k in kpis if k.get("value") is None]

            c1, c2, c3 = st.columns(3)
            c1.metric("Total KPIs", len(kpis))
            c2.metric("Available KPIs", len(available))
            c3.metric("Missing KPIs", len(missing))

            st.subheader(f"{company_id} | FY{fiscal_year} Q{fiscal_quarter}")

            if available:
                cols = st.columns(3)
                for i, kpi in enumerate(available):
                    with cols[i % 3]:
                        st.metric(
                            kpi["kpi_name"],
                            f'{kpi["value"]:.2f} {kpi["unit"]}'
                        )

            st.subheader("KPI Overview")
            if kpis:
                st.dataframe(pd.DataFrame(kpis), use_container_width=True)
    else:
        st.info("Initialize the database and ingest data to view the dashboard.")

    st.subheader("Company Directory")
    if not company_df.empty:
        st.dataframe(company_df, use_container_width=True)


elif page == "Financial Analysis":
    st.header("Financial Analysis")

    if company_id:
        result, error = api_request(
            "POST", "/api/v1/kpis",
            json={
                "company_id": company_id,
                "fiscal_year": int(fiscal_year),
                "fiscal_quarter": int(fiscal_quarter)
            }
        )

        if error:
            show_error(error)
        else:
            kpis = result.get("kpis", [])
            if kpis:
                names = [k["kpi_name"] for k in kpis]
                selected_name = st.selectbox("Select KPI", names)
                selected = next(k for k in kpis if k["kpi_name"] == selected_name)

                st.subheader(selected["kpi_name"])
                if selected.get("value") is not None:
                    st.metric(
                        "Calculated Value",
                        f'{selected["value"]:.3f} {selected["unit"]}'
                    )
                else:
                    st.warning("Value unavailable due to insufficient evidence.")

                st.write("Confidence:", selected.get("confidence", "unknown"))
                st.write("Confidence basis:", selected.get("confidence_basis", "Not provided"))

                with st.expander("Show your work / Source provenance", expanded=True):
                    st.write("KPI ID:", selected.get("kpi_id"))
                    st.write("Source row IDs:", selected.get("source_row_ids", []))
                    st.json(selected)
            else:
                st.info("No KPI records found for this period.")


elif page == "Document Search":
    st.header("Financial Document Search")
    st.info("Semantic filing search using FAISS retrieval, filtered by company and fiscal period.")

    question = st.text_input(
        "Ask about a financial filing",
        placeholder="What does the company report about revenue?"
    )

    if st.button("Search Evidence", type="primary"):
        if not company_id:
            st.warning("No company available.")
        elif len(question.strip()) < 3:
            st.warning("Enter at least 3 characters.")
        else:
            with st.spinner("Retrieving filing evidence..."):
                result, error = api_request(
                    "POST", "/api/v1/search",
                    json={
                        "company_id": company_id,
                        "fiscal_year": int(fiscal_year),
                        "fiscal_quarter": int(fiscal_quarter),
                        "question": question
                    }
                )

            if error:
                show_error(error)
            else:
                st.subheader("Retrieved Answer")
                st.write(result.get("answer"))

                st.write("Confidence:", result.get("confidence"))
                st.write("Confidence basis:", result.get("confidence_basis"))

                st.subheader("Evidence and Citations")
                citations = result.get("citations", [])

                if not citations:
                    st.warning("No filing citations were returned.")
                for i, citation in enumerate(citations, 1):
                    with st.expander(f'{i}. {citation.get("title", "Filing")}'):
                        st.write("Document ID:", citation.get("doc_id"))
                        st.write("Filed date:", citation.get("filed_date"))
                        st.write("Similarity:", citation.get("similarity"))
                        st.write(citation.get("excerpt"))


elif page == "CFO Assistant":
    st.header("CFO Assistant")
    st.caption("AI-powered financial Q&A using Google ADK, Ollama and evidence retrieval.")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
            if message.get("details"):
                with st.expander("Show your work and evidence"):
                    st.json(message["details"])

    prompt = st.chat_input("Ask a financial question...")

    if prompt and len(prompt.strip()) < 3:
        st.warning("Please enter at least 3 characters.")

    if prompt and len(prompt.strip()) >= 3:
        if not company_id:
            st.warning("No company available.")
        else:
            st.session_state.messages.append({
                "role": "user", "content": prompt
            })

            with st.chat_message("user"):
                st.write(prompt)

            with st.chat_message("assistant"):
                with st.spinner("Analyzing financial data and filing evidence..."):
                    result, error = api_request(
                        "POST",
                        "/api/v1/assistant",
                        json={
                            "company_id": company_id,
                            "fiscal_year": int(fiscal_year),
                            "fiscal_quarter": int(fiscal_quarter),
                            "question": prompt
                        }
                    )

                if error:
                    answer = f"Unable to process your question: {error}"
                    show_error(answer)
                    details = {}
                else:
                    result = result or {}
                    answer = (
                        result.get("answer")
                        or result.get("response")
                        or result.get("message")
                        or result.get("content")
                        or "No answer text returned. Check the response details below."
                    )
                    details = result
                    st.markdown(answer)

                    if details:
                        with st.expander("Show your work and evidence"):
                            st.json(details)

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer,
                    "details": details
                })


elif page == "System Information":
    st.header("System Information")

    if health_error:
        show_error(health_error)
    else:
        st.subheader("API Health")
        st.json(health)

    st.subheader("Companies")
    if not company_df.empty:
        st.dataframe(company_df, use_container_width=True)

    st.subheader("Architecture")
    st.markdown("""
    - **Frontend:** Streamlit
    - **API:** FastAPI
    - **Database:** MySQL 8
    - **Retrieval:** FAISS and sentence-transformers
    - **Agent layer:** Google ADK Runner with CFO tools
    - **Inference:** Local Ollama model via LiteLLM
    """)

    st.success(
        "ADK CFO agent is configured in the API. "
        "The assistant endpoint invokes the agent through Runner."
    )

st.divider()
st.caption("CFO Copilot | Local-first | Evidence-grounded financial analysis")
