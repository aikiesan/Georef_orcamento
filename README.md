# Orçamento Georreferenciado São Paulo 2024

Uma aplicação interativa em Streamlit para visualização e análise da execução orçamentária da cidade de São Paulo, distribuída por subprefeitura.

## 🚀 Como Executar Localmente

1. **Clone o repositório:**
   ```bash
   git clone https://github.com/aikiesan/Georef_orcamento.git
   cd Georef_orcamento
   ```

2. **Instale as dependências:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Execute a aplicação:**
   ```bash
   streamlit run app.py
   ```

## 🌐 Deploy no Streamlit Cloud

1. Suba este código para o seu repositório no GitHub.
2. Acesse [share.streamlit.io](https://share.streamlit.io).
3. Conecte sua conta do GitHub.
4. Selecione o repositório `Georef_orcamento` e o arquivo `app.py`.
5. Clique em **Deploy!**

## 📊 Funcionalidades

- **Mapa Coroplético:** Visualização térmica do orçamento por subprefeitura.
- **Filtros Dinâmicos:** Filtre por Função, Órgão, Grupo de Despesa e Tipo de Crédito.
- **Upload de Dados:** Suporte para novos arquivos `.xlsx` seguindo o padrão do SOF.
- **Dashboard Analítico:** Gráficos de barras e tabelas detalhadas.

## 🛠️ Tecnologias Utilizadas

- **Streamlit**: Framework web.
- **Pandas/GeoPandas**: Processamento de dados e geometrias.
- **Folium**: Mapas interativos.
- **Plotly**: Gráficos analíticos.
