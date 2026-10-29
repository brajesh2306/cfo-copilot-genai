from __future__ import annotations
import streamlit as st
import pandas as pd
from sqlalchemy import text
from services.financials import ingest_all, list_companies, source_values, compute_kpis, connect, database_initialized

st.set_page_config(page_title='CFO Copilot', page_icon='📊', layout='wide')
st.title('CFO Copilot')
st.caption('Private, evidence-grounded financial assistant · local data pack · no hosted LLM inference')

with st.sidebar:
    st.header('System status')
    if st.button('Initialize / ingest data', type='primary', use_container_width=True):
        try:
            ingest_all(); st.success('Idempotent ingestion completed.')
        except Exception as e:
            st.error(f'Ingestion failed: {e}')
    st.caption('Database: MySQL 8.0 (configured via DATABASE_URL)')
    st.caption('Drop 2 dataset is included in the ingestion path.')

if not database_initialized():
    st.warning('Database not initialized. Click “Initialize / ingest data” in the sidebar first.')
    st.stop()
try:
    companies = list_companies()
except Exception as e:
    st.error(f'Database could not be read: {e}'); st.stop()
if companies.empty:
    st.warning('No companies loaded. Run ingestion from the sidebar.'); st.stop()

company_label = {f"{r.company_id} — {r['name']}": r.company_id for _,r in companies.iterrows()}
selected = st.selectbox('Company', list(company_label.keys()))
company_id = company_label[selected]
with connect() as con:
    periods = pd.read_sql_query(text('SELECT DISTINCT fiscal_year,fiscal_quarter FROM statement_lines WHERE company_id=:company_id ORDER BY fiscal_year,fiscal_quarter'), con, params={'company_id':company_id})
if periods.empty:
    st.info('No periods found for this company.'); st.stop()
period_options = [f"FY{int(r.fiscal_year)} Q{int(r.fiscal_quarter)}" for _,r in periods.iterrows()]
period_choice = st.selectbox('Fiscal period', period_options, index=len(period_options)-1)
year, quarter = map(int, period_choice.replace('FY','').replace(' Q',' ').split())

left, right = st.columns([1.25,1])
with left:
    st.subheader('KPI snapshot')
    kpis = compute_kpis(company_id, year, quarter)
    kdf = pd.DataFrame(kpis)
    if not kdf.empty:
        def fmt(r):
            if pd.isna(r['value']) or r['value'] is None: return 'Unavailable — missing input'
            if r['unit']=='%': return f"{r['value']:.2f}%"
            if r['unit']=='x': return f"{r['value']:.2f}x"
            return f"${r['value']:,.0f}"
        kdf['display_value'] = kdf.apply(fmt,axis=1)
        st.dataframe(kdf[['kpi_name','display_value','confidence','confidence_basis','source_row_ids']], use_container_width=True, hide_index=True)
        st.caption('KPI values are computed by deterministic Python logic. Unavailable inputs are not guessed. Source row IDs are shown for traceability.')
with right:
    st.subheader('Source statement lines')
    lines = source_values(company_id,year,quarter)
    st.dataframe(lines[['row_id','filing_id','line_item_raw','value_usd','raw_unit','filed_date','is_amendment']], use_container_width=True, hide_index=True, height=500)

st.divider()
st.subheader('Filing search (keyword baseline)')
query = st.text_input('Search filing text', placeholder='e.g. supply chain, revenue growth, restructuring charge')
if query.strip():
    with connect() as con:
        docs = pd.read_sql_query(text('SELECT chunk_id,doc_id,company_id,text FROM document_chunks WHERE company_id=:company_id AND lower(text) LIKE :query LIMIT 20'), con, params={'company_id':company_id,'query':f'%{query.lower()}%'})
    if docs.empty: st.info('No matching chunk found. This baseline uses keyword matching; semantic retrieval is a next implementation step.')
    for _,d in docs.iterrows():
        with st.expander(f"{d.doc_id} · {d.chunk_id}"):
            st.write(d.text)
            st.caption('Citation ID: '+d.chunk_id)

st.divider()
st.caption('Build status: data/KPI foundation in progress. Local model serving, Google ADK orchestration, streaming answer endpoint, retrieval evaluation and measured KV-cache benchmarks must be completed and verified before submission.')
