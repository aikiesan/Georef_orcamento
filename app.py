import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import plotly.express as px
import unicodedata
import json

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Orçamento Georreferenciado SP",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    .main .block-container {
        padding-top: 1.5rem;
        padding-bottom: 1.5rem;
    }
    /* Estilização para as métricas do topo */
    div[data-testid="metric-container"] {
        background-color: var(--secondary-background-color);
        border: 1px solid var(--border-color);
        padding: 5% 5% 5% 10%;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    </style>
""", unsafe_allow_html=True)

# --- UTILITIES ---
def normalize_str(s):
    if pd.isna(s):
        return ""
    s = unicodedata.normalize('NFD', str(s))
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return s.upper().strip()

def fmt_brl(value):
    if value >= 1e9:
        return f"R$ {value/1e9:.2f} Bi"
    elif value >= 1e6:
        return f"R$ {value/1e6:.2f} Mi"
    else:
        # Standard BRL formatting with dot as thousand separator and comma as decimal
        return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# Mapeamento manual de nomes XLSX para GeoJSON
manual_map = {
    "Subprefeitura Aricanduva/Formosa/Carrão":  "ARICANDUVA-FORMOSA-CARRAO",
    "Subprefeitura Butantã":                    "BUTANTA",
    "Subprefeitura Campo Limpo":                "CAMPO LIMPO",
    "Subprefeitura Capela do Socorro":          "CAPELA DO SOCORRO",
    "Subprefeitura Casa Verde/Cachoeirinha":    "CASA VERDE-LIMAO-CACHOEIRINHA",
    "Subprefeitura Cidade Ademar":              "CIDADE ADEMAR",
    "Subprefeitura Cidade Tiradentes":          "CIDADE TIRADENTES",
    "Subprefeitura Ermelino Matarazzo":         "ERMELINO MATARAZZO",
    "Subprefeitura Freguesia/Brasilândia":      "FREGUESIA-BRASILANDIA",
    "Subprefeitura Ipiranga":                   "IPIRANGA",
    "Subprefeitura Itaim Paulista":             "ITAIM PAULISTA",
    "Subprefeitura Itaquera":                   "ITAQUERA",
    "Subprefeitura Jabaquara":                  "JABAQUARA",
    "Subprefeitura Jaçanã/Tremembé":            "JACANA-TREMEMBE",
    "Subprefeitura Lapa":                       "LAPA",
    "Subprefeitura M'Boi Mirim":               "M BOI MIRIM",
    "Subprefeitura Mooca":                      "MOOCA",
    "Subprefeitura Parelheiros":                "PARELHEIROS",
    "Subprefeitura Penha":                      "PENHA",
    "Subprefeitura Perus/Anhanguera":           "PERUS-ANHANGUERA",
    "Subprefeitura Pinheiros":                  "PINHEIROS",
    "Subprefeitura Pirituba/Jaraguá":           "PIRITUBA-JARAGUA",
    "Subprefeitura Santana/Tucuruvi":           "SANTANA-TUCURUVI",
    "Subprefeitura Santo Amaro":                "SANTO AMARO",
    "Subprefeitura Sapopemba":                  "SAPOPEMBA",
    "Subprefeitura São Mateus":                 "SAO MATEUS",
    "Subprefeitura São Miguel Paulista":        "SAO MIGUEL",
    "Subprefeitura Sé":                         "SE",
    "Subprefeitura Vila Maria/Vila Guilherme":  "VILA MARIA-VILA GUILHERME",
    "Subprefeitura Vila Mariana":               "VILA MARIANA",
    "Subprefeitura de Guaianases":              "GUAIANASES",
    "Subprefeitura de Vila Prudente":           "VILA PRUDENTE",
}

# --- DATA LOADING ---
@st.cache_data
def load_budget_data(file):
    df_raw = pd.read_excel(file, sheet_name='basedadosexecucao')
    
    financial_cols = ['Vl_Orcado_Atualizado', 'Vl_EmpenhadoLiquido', 'Vl_Liquidado', 'Vl_Pago']
    for col in financial_cols:
        df_raw[col] = pd.to_numeric(df_raw[col], errors='coerce').fillna(0)
        
    df_spatial = df_raw[
        df_raw['procv 32 sub'].notna() &
        (~df_raw['procv 32 sub'].astype(str).str.contains('ERROR', na=True))
    ].copy()
    
    return df_raw, df_spatial

@st.cache_data
def load_base_geometry(path):
    gdf = gpd.read_file(path)
    if gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs(epsg=4326)
    return gdf

# --- APP START ---

# Cabeçalho da Aplicação
st.title("🗺️ Painel do Orçamento Georreferenciado")
st.markdown("#### São Paulo - Distribuição Espacial de Recursos por Subprefeitura")
st.divider()

# --- SIDEBAR: ENTRADA DE DADOS ---
st.sidebar.image("https://upload.wikimedia.org/wikipedia/commons/1/11/Brasao_da_cidade_de_Sao_Paulo.svg", width=100)
st.sidebar.header("📁 Fonte de Dados")
uploaded_file = st.sidebar.file_uploader("Substituir base Excel (.xlsx)", type=["xlsx"], help="Faça upload de uma nova extração do SOF.")

DEFAULT_BUDGET_FILE = 'basedadosexecucao_1224.xlsx'
GEOJSON_FILE = 'subprefeituras_orcamento_2024.geojson'

target_file = uploaded_file if uploaded_file is not None else DEFAULT_BUDGET_FILE
file_name_display = uploaded_file.name if uploaded_file else DEFAULT_BUDGET_FILE

st.sidebar.caption(f"**Base atual:** `{file_name_display}`")
st.sidebar.divider()

try:
    with st.spinner("Processando dados espaciais e financeiros..."):
        df_raw, df_spatial = load_budget_data(target_file)
        gdf_base = load_base_geometry(GEOJSON_FILE)

    # --- SIDEBAR: CONFIGURAÇÕES E FILTROS ---
    st.sidebar.header("⚙️ Configuração do Mapa")
    
    metric_labels = {
        'Vl_Orcado_Atualizado': 'Orçado Atualizado',
        'Vl_EmpenhadoLiquido':  'Empenhado Líquido',
        'Vl_Liquidado':         'Liquidado',
        'Vl_Pago':              'Pago',
    }
    
    selected_metric = st.sidebar.selectbox(
        "Métrica de Valor",
        options=list(metric_labels.keys()),
        format_func=lambda x: metric_labels[x]
    )

    st.sidebar.header("🔍 Filtros de Dotação")
    
    with st.sidebar.expander("📍 Filtros Estruturais", expanded=True):
        functions = sorted(df_raw['Ds_Funcao'].unique().tolist())
        selected_funcoes = st.multiselect("Função de Governo", options=functions, placeholder="Todas as funções")
        
        organs = sorted(df_raw['Sigla_Orgao'].unique().tolist())
        selected_orgaos = st.multiselect("Órgão Responsável", options=organs, placeholder="Todos os órgãos")
        
    with st.sidebar.expander("💰 Filtros Contábeis", expanded=False):
        groups = sorted(df_raw['Ds_Grupo'].unique().tolist())
        selected_grupos = st.multiselect("Grupo de Despesa", options=groups, placeholder="Todos os grupos")
        
        credits = sorted(df_raw['TXT_TIP_CRED_ORCM'].unique().tolist())
        selected_creditos = st.multiselect("Tipo de Crédito", options=credits, placeholder="Todos os tipos")

        project_types = sorted(df_raw['PA'].unique().tolist())
        selected_pa = st.multiselect("Tipo de Projeto (PA)", options=project_types, placeholder="Todos os PAs")

    st.sidebar.divider()
    st.sidebar.info(f"**Qualidade dos Dados:**\n\nForam encontradas **{len(df_spatial)}** dotações com localização explícita dentre o total de **{len(df_raw)}** registros.")

    # --- DATA PROCESSING ---
    df_filtered = df_spatial.copy()
    if selected_funcoes: df_filtered = df_filtered[df_filtered['Ds_Funcao'].isin(selected_funcoes)]
    if selected_orgaos: df_filtered = df_filtered[df_filtered['Sigla_Orgao'].isin(selected_orgaos)]
    if selected_grupos: df_filtered = df_filtered[df_filtered['Ds_Grupo'].isin(selected_grupos)]
    if selected_creditos: df_filtered = df_filtered[df_filtered['TXT_TIP_CRED_ORCM'].isin(selected_creditos)]
    if selected_pa: df_filtered = df_filtered[df_filtered['PA'].isin(selected_pa)]

    df_filtered['nm_subpref'] = df_filtered['procv 32 sub'].map(manual_map)
    agg = df_filtered.groupby('nm_subpref').agg(
        Vl_Orcado_Atualizado=('Vl_Orcado_Atualizado', 'sum'),
        Vl_EmpenhadoLiquido =('Vl_EmpenhadoLiquido',  'sum'),
        Vl_Liquidado        =('Vl_Liquidado',          'sum'),
        Vl_Pago             =('Vl_Pago',               'sum'),
        n_dotacoes          =('Cd_Dotacao_Id',          'count'),
    ).reset_index()

    gdf = gdf_base[['nm_subpref', 'geometry', 'sg_subpref', 'nm_regiao_', 'nm_regiao0']].merge(
        agg, on='nm_subpref', how='left'
    ).fillna(0)

    # --- DASHBOARD UI: KPIs ---
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("📌 Orçado Atualizado", fmt_brl(df_filtered['Vl_Orcado_Atualizado'].sum()))
    kpi2.metric("📋 Empenhado Líquido", fmt_brl(df_filtered['Vl_EmpenhadoLiquido'].sum()))
    kpi3.metric("✔️ Liquidado", fmt_brl(df_filtered['Vl_Liquidado'].sum()))
    kpi4.metric("💸 Pago", fmt_brl(df_filtered['Vl_Pago'].sum()))
    
    st.markdown("<br>", unsafe_allow_html=True)

    # --- MAIN TABS ---
    tab_mapa, tab_dados = st.tabs(["🌍 Visão Geográfica", "📊 Visão Analítica"])

    with tab_mapa:
        col_map, col_spacer = st.columns([1, 0.01])
        with col_map:
            # Determine scaling for the legend
            max_val = gdf[selected_metric].max()
            if max_val >= 1e9:
                scaling_factor = 1e9
                unit_label = "Bi R$"
            elif max_val >= 1e6:
                scaling_factor = 1e6
                unit_label = "Mi R$"
            else:
                scaling_factor = 1
                unit_label = "R$"
            
            # Create a scaled column for the map legend
            gdf['metric_scaled'] = gdf[selected_metric] / scaling_factor
            
            st.markdown(f"**Distribuição Espacial:** Valores em `{unit_label}`")
            
            # Map Rendering
            bounds = gdf.total_bounds
            center_lat = (bounds[1] + bounds[3]) / 2
            center_lon = (bounds[0] + bounds[2]) / 2

            m = folium.Map(location=[center_lat, center_lon], tiles="CartoDB positron", zoom_control=True)
            m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])

            # Improved Choropleth with clean legend
            cp = folium.Choropleth(
                geo_data=gdf.__geo_interface__,
                data=gdf,
                columns=['nm_subpref', 'metric_scaled'],
                key_on='feature.properties.nm_subpref',
                fill_color='YlOrRd',
                fill_opacity=0.8,
                line_opacity=0.4,
                legend_name=f"{metric_labels[selected_metric]} ({unit_label})",
                nan_fill_color='#fdfdfd',
                highlight=True
            ).add_to(m)

            # Move and style the legend to prevent overlapping/cluttering
            # Note: Folium legends are SVG elements, we can try to nudge them slightly via JS if needed, 
            # but usually scaling the numbers is 90% of the fix.

            folium.GeoJson(
                gdf,
                style_function=lambda x: {'fillColor': '#ffffff00', 'color': '#ffffff00', 'weight': 0},
                tooltip=folium.GeoJsonTooltip(
                    fields=['nm_subpref', 'Vl_Orcado_Atualizado', 'Vl_EmpenhadoLiquido', 'Vl_Liquidado', 'Vl_Pago', 'n_dotacoes'],
                    aliases=['Subprefeitura:', 'Orçado (R$):', 'Empenhado (R$):', 'Liquidado (R$):', 'Pago (R$):', 'Nº Dotações:'],
                    localize=True,
                    labels=True,
                    sticky=True,
                    # Format numbers in tooltips with thousands separators
                    style="font-family: sans-serif; font-size: 13px; color: #333; background-color: white; border: 1px solid #ddd; padding: 10px;"
                )
            ).add_to(m)

            st_folium(m, width="100%", height=600, returned_objects=[])

    with tab_dados:
        col_chart, col_table = st.columns([1.2, 1])

        with col_chart:
            st.markdown(f"**Top 10 Subprefeituras por `{metric_labels[selected_metric]}`**")
            top_10 = agg.sort_values(by=selected_metric, ascending=False).head(10)
            
            fig = px.bar(
                top_10, 
                x=selected_metric, 
                y='nm_subpref', 
                orientation='h',
                text=selected_metric,
                labels={selected_metric: 'Valor (R$)', 'nm_subpref': ''},
                color=selected_metric,
                color_continuous_scale="YlOrRd"
            )
            fig.update_traces(
                texttemplate='R$ %{x:,.3s}', 
                textposition='auto',
                hovertemplate='%{y}<br>R$ %{x:,.2f}<extra></extra>'
            )
            fig.update_layout(
                yaxis={'categoryorder':'total ascending'},
                plot_bgcolor='rgba(0,0,0,0)',
                xaxis_visible=False,
                coloraxis_showscale=False,
                margin=dict(l=0, r=0, t=10, b=0),
                height=450
            )
            st.plotly_chart(fig, use_container_width=True)

        with col_table:
            st.markdown("**Tabela de Dados Consolidados**")
            display_df = agg.copy()
            
            # Format display dataframe safely
            def brl_formatter(x): return f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            
            for col in list(metric_labels.keys()):
                display_df[col] = display_df[col].apply(brl_formatter)
                
            display_df = display_df.rename(columns={
                'nm_subpref': 'Subprefeitura',
                'n_dotacoes': 'Qtd. Dotações',
                'Vl_Orcado_Atualizado': 'Orçado',
                'Vl_EmpenhadoLiquido': 'Empenhado',
                'Vl_Liquidado': 'Liquidado',
                'Vl_Pago': 'Pago'
            })
            
            # Use original data for sorting but display formatted dataframe
            st.dataframe(
                display_df.sort_values(by='Subprefeitura', key=lambda col: agg.sort_values(by=selected_metric, ascending=False)['nm_subpref']), 
                use_container_width=True, 
                hide_index=True,
                height=450
            )

except Exception as e:
    st.error("Ocorreu um erro ao processar os dados.")
    st.exception(e)
    st.info("Verifique se os arquivos de dados (.xlsx) são compatíveis com a estrutura esperada do SOF de São Paulo.")
