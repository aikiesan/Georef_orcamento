import streamlit as st
import pandas as pd
import geopandas as gpd
import plotly.express as px
import unicodedata
import json

# Page Configuration
st.set_page_config(
    page_title="Orçamento Georreferenciado - São Paulo 2024",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Utility function for string normalization
def normalize_str(s):
    if pd.isna(s):
        return ""
    s = unicodedata.normalize('NFD', str(s))
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return s.upper().strip()

# Data Loading Functions
@st.cache_data
def load_budget_data(path):
    # Read the main sheet 'basedadosexecucao'
    df = pd.read_excel(path, sheet_name='basedadosexecucao')
    
    # Clean the spatial join column
    # The handoff document mentions 'procv 32 sub' as the key column
    df['subpref_key'] = df['procv 32 sub'].apply(normalize_str)
    
    # Filter out invalid rows (keeping only rows with a valid subprefeitura key)
    # We keep 'ERROR:#N/A' as well if it's explicitly mentioned to be filtered,
    # but based on the plan, we filter rows that are NOT linked.
    df_spatial = df[~df['subpref_key'].isin(['', 'ERROR:#N/A', 'NAN'])]
    
    # Ensure financial columns are floats
    financial_cols = [
        'Vl_Orcado_Atualizado', 'Vl_EmpenhadoLiquido', 
        'Vl_Liquidado', 'Vl_Pago', 'Vl_Orcado_Ano'
    ]
    for col in financial_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
    return df, df_spatial

@st.cache_data
def load_shapes(path):
    gdf = gpd.read_file(path)
    # Re-project to WGS84 (EPSG:4326) for Plotly
    if gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs(epsg=4326)
    
    # Normalize join key in shapefile
    # Based on our previous check, the column is 'nm_subpref'
    gdf['join_key'] = gdf['nm_subpref'].apply(normalize_str)
    return gdf

# App Interface
st.title("🗺️ Orçamento Georreferenciado - São Paulo 2024")
st.markdown("""
Esta aplicação permite visualizar a execução orçamentária da cidade de São Paulo em 2024, 
distribuída espacialmente pelas 32 subprefeituras. 
*Nota: Apenas uma parcela das dotações é explicitamente vinculada a uma subprefeitura no sistema atual.*
""")

# File Paths (Local to the project)
BUDGET_FILE = 'basedadosexecucao_1224.xlsx'
SHAPE_FILE = 'geoportal_subprefeitura_v2/subprefeitura_v2.shp'

try:
    with st.spinner("Carregando dados..."):
        df_full, df_spatial = load_budget_data(BUDGET_FILE)
        gdf = load_shapes(SHAPE_FILE)

    # Sidebar Filters
    st.sidebar.header("Filtros de Visualização")

    # 1. Metric Selection
    metric_options = {
        "Vl_Orcado_Atualizado": "Orçado Atualizado",
        "Vl_EmpenhadoLiquido": "Empenhado Líquido",
        "Vl_Liquidado": "Liquidado",
        "Vl_Pago": "Pago"
    }
    selected_metric_key = st.sidebar.radio(
        "Métrica para o Mapa",
        options=list(metric_options.keys()),
        format_func=lambda x: metric_options[x]
    )

    # 2. Functional Filters
    st.sidebar.subheader("Filtrar Dotações")
    
    # Function Filter
    functions = sorted(df_full['Ds_Funcao'].unique().tolist())
    selected_functions = st.sidebar.multiselect("Função", options=functions)
    
    # Organ Filter
    organs = sorted(df_full['Sigla_Orgao'].unique().tolist())
    selected_organs = st.sidebar.multiselect("Órgão (Sigla)", options=organs)
    
    # Expense Category Filter
    categories = sorted(df_full['Ds_Categoria'].unique().tolist())
    selected_categories = st.sidebar.multiselect("Categoria de Despesa", options=categories)

    # Credit Type Filter
    credit_types = sorted(df_full['TXT_TIP_CRED_ORCM'].unique().tolist())
    selected_credit_types = st.sidebar.multiselect("Tipo de Crédito", options=credit_types)

    # Project Type Filter (PA)
    project_types = sorted(df_full['PA'].unique().tolist())
    selected_project_types = st.sidebar.multiselect("Tipo de Projeto (PA)", options=project_types)

    # Revenue Source Filter
    revenue_sources = sorted(df_full['Ds_Fonte'].unique().tolist())
    selected_revenue_sources = st.sidebar.multiselect("Fonte de Recurso", options=revenue_sources)

    # Filter the Data
    filtered_df = df_spatial.copy()
    if selected_functions:
        filtered_df = filtered_df[filtered_df['Ds_Funcao'].isin(selected_functions)]
    if selected_organs:
        filtered_df = filtered_df[filtered_df['Sigla_Orgao'].isin(selected_organs)]
    if selected_categories:
        filtered_df = filtered_df[filtered_df['Ds_Categoria'].isin(selected_categories)]
    if selected_credit_types:
        filtered_df = filtered_df[filtered_df['TXT_TIP_CRED_ORCM'].isin(selected_credit_types)]
    if selected_project_types:
        filtered_df = filtered_df[filtered_df['PA'].isin(selected_project_types)]
    if selected_revenue_sources:
        filtered_df = filtered_df[filtered_df['Ds_Fonte'].isin(selected_revenue_sources)]

    # Aggregate Data by Subprefeitura
    agg_df = filtered_df.groupby('subpref_key').agg({
        'Vl_Orcado_Atualizado': 'sum',
        'Vl_EmpenhadoLiquido': 'sum',
        'Vl_Liquidado': 'sum',
        'Vl_Pago': 'sum',
        'Cd_Dotacao_Id': 'count'
    }).reset_index().rename(columns={'Cd_Dotacao_Id': 'n_dotacoes'})

    # Merge with GeoPandas
    merged_gdf = gdf.merge(agg_df, left_on='join_key', right_on='subpref_key', how='left')
    merged_gdf[list(metric_options.keys()) + ['n_dotacoes']] = merged_gdf[list(metric_options.keys()) + ['n_dotacoes']].fillna(0)

    # Top Metrics Bar
    col1, col2, col3, col4 = st.columns(4)
    total_budgeted = filtered_df['Vl_Orcado_Atualizado'].sum()
    total_empenhado = filtered_df['Vl_EmpenhadoLiquido'].sum()
    match_count = len(filtered_df)
    total_count = len(df_full)

    col1.metric("Orçado (Filtro)", f"R$ {total_budgeted:,.2f}")
    col2.metric("Empenhado (Filtro)", f"R$ {total_empenhado:,.2f}")
    col3.metric("Dotações Localizadas", f"{match_count}")
    col4.metric("% Georreferenciado", f"{(match_count/total_count)*100:.1f}%")

    # Map Rendering
    st.subheader(f"Distribuição por Subprefeitura: {metric_options[selected_metric_key]}")
    
    # Prepare GeoJSON for Plotly
    geojson = json.loads(merged_gdf.to_json())

    fig = px.choropleth_mapbox(
        merged_gdf,
        geojson=geojson,
        locations=merged_gdf.index,
        color=selected_metric_key,
        color_continuous_scale="YlOrRd",
        range_color=(0, merged_gdf[selected_metric_key].max() if merged_gdf[selected_metric_key].max() > 0 else 1),
        mapbox_style="carto-positron",
        zoom=10,
        center={"lat": -23.6, "lon": -46.65},
        opacity=0.7,
        labels={selected_metric_key: metric_options[selected_metric_key]},
        hover_data={
            'nm_subpref': True,
            'Vl_Orcado_Atualizado': ':,.2f',
            'Vl_EmpenhadoLiquido': ':,.2f',
            'Vl_Liquidado': ':,.2f',
            'Vl_Pago': ':,.2f',
            'n_dotacoes': True
        }
    )
    
    fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, height=600)
    st.plotly_chart(fig, use_container_width=True)

    # Detailed Data Table
    if st.checkbox("Mostrar Tabela de Dados"):
        st.write(agg_df.sort_values(by=selected_metric_key, ascending=False))

except Exception as e:
    st.error(f"Erro ao carregar ou processar os dados: {e}")
    st.info("Certifique-se de que os arquivos 'basedadosexecucao_1224.xlsx' e a pasta 'geoportal_subprefeitura_v2' estão presentes no diretório raiz.")
