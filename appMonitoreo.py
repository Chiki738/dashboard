import locale
import pandas as pd
import plotly.express as px
from flask import Flask, render_template_string
from dash import Dash, dcc, html as dash_html
from dash.dependencies import Input, Output
from supabase import create_client, Client
import plotly.graph_objects as go

try:
    locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
except locale.Error:
    locale.setlocale(locale.LC_TIME, '')  # Usa el locale por defecto
hoy = pd.Timestamp.today()
mes_anio_actual = hoy.strftime("%B %Y").capitalize()
mes_anio_anterior = (hoy - pd.DateOffset(months=1)).strftime("%B %Y").capitalize()
año_actual = hoy.year
año_anterior = año_actual - 1

url = "https://lyxhceqquioucmlmhvuj.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imx5eGhjZXFxdWlvdWNtbG1odnVqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDg5MDMxOTcsImV4cCI6MjA2NDQ3OTE5N30.9Ukt-vw_Sxv_bGFE265upP2ZLwqM76T39mHooFH_mfY"
supabase: Client = create_client(url, key)

server = Flask(__name__)

def fetch_table(query):
    response = supabase.rpc("ejecutar_sql", {"query": query}).execute()
    if response.data:
        raw_data = response.data[0].get("data", [])
        if isinstance(raw_data, list):
            df = pd.DataFrame(raw_data)
        else:
            df = pd.DataFrame()
    else:
        df = pd.DataFrame()
    return df

def get_sales_data_and_figures():
    df1 = fetch_table(f"""
        SELECT EXTRACT(YEAR FROM fecha) AS año,
               EXTRACT(MONTH FROM fecha) AS mes,
               SUM(total) AS total
        FROM pedidos
        WHERE fecha >= CURRENT_DATE - INTERVAL '1 year'
        GROUP BY año, mes
        ORDER BY año, mes
    """).pivot(index='mes', columns='año', values='total').reset_index()

    df2 = fetch_table(f"""
        SELECT TO_CHAR(fecha, 'YYYY-MM') AS periodo,
               EXTRACT(MONTH FROM fecha) AS mes,
               EXTRACT(YEAR FROM fecha) AS año,
               SUM(total) AS total
        FROM pedidos
        WHERE fecha >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')
          AND fecha <= CURRENT_DATE
        GROUP BY periodo, mes, año
        ORDER BY periodo
    """)

    df3 = fetch_table(f"""
        SELECT p.nombre AS producto,
               SUM(dp.cantidad) AS unidades
        FROM detalle_pedido dp
        JOIN pedidos o ON dp.pedido_id = o.id
        JOIN productos p ON dp.producto_codigo = p.codigo
        WHERE EXTRACT(YEAR FROM o.fecha) = {año_actual}
          AND EXTRACT(MONTH FROM o.fecha) = {hoy.month}
        GROUP BY p.codigo, p.nombre
        ORDER BY unidades DESC
        LIMIT 10
    """)

    df4 = fetch_table(f"""
        SELECT c.nombre AS categoria,
               SUM(dp.cantidad * dp.precio_unit) AS ingresos
        FROM detalle_pedido dp
        JOIN pedidos o ON dp.pedido_id = o.id
        JOIN productos p ON dp.producto_codigo = p.codigo
        JOIN categorias c ON p.categoria_id = c.categoria_id
        WHERE EXTRACT(YEAR FROM o.fecha) = {año_actual}
          AND EXTRACT(MONTH FROM o.fecha) = {hoy.month}
        GROUP BY c.categoria_id, c.nombre
        ORDER BY ingresos DESC
    """)

    df5 = fetch_table(f"""
        SELECT d.nombre AS distrito,
               EXTRACT(MONTH FROM o.fecha) AS mes,
               SUM(o.total) AS total
        FROM pedidos o
        JOIN users cl ON o.cliente_id = cl.cliente_id
        JOIN distritos d ON cl.distrito_id = d.distrito_id
        WHERE o.fecha >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')
          AND o.fecha <= CURRENT_DATE
        GROUP BY d.distrito_id, d.nombre, mes
        ORDER BY d.nombre, mes
    """)

    df6 = fetch_table(f"""
        WITH first_orders AS (
            SELECT cliente_id, MIN(fecha) AS first_order_date
            FROM pedidos
            GROUP BY cliente_id
        ), current_orders AS (
            SELECT DISTINCT o.cliente_id, f.first_order_date
            FROM pedidos o
            JOIN first_orders f USING(cliente_id)
            WHERE EXTRACT(YEAR FROM o.fecha) = {año_actual}
              AND EXTRACT(MONTH FROM o.fecha) = {hoy.month}
        )
        SELECT CASE
                    WHEN EXTRACT(YEAR FROM first_order_date) = {año_actual}
                     AND EXTRACT(MONTH FROM first_order_date) = {hoy.month}
                    THEN 'Nuevo'
                    ELSE 'Recurrente'
                END AS tipo_cliente,
                COUNT(*) AS cantidad
        FROM current_orders
        GROUP BY tipo_cliente
    """)

    meses_es = {
        1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
        5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
        9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
    }

    columnas_disponibles = [col for col in [año_anterior, año_actual] if col in df1.columns]

    def update_common_layout(fig, height_val=None):
        fig.update_layout(
            plot_bgcolor='#ffffff',
            paper_bgcolor='#ffffff',
            font_color='#34495e',
            autosize=True, 
            margin=dict(l=40, r=40, t=40, b=40),
            uirevision='constant' 
        )
        if height_val:
            fig.update_layout(height=height_val)
        return fig

    fig1 = px.line(df1, x='mes', y=columnas_disponibles,
                     title=f'Ganancias Mensuales: {año_anterior} vs {año_actual}',
                     labels={'mes': 'Mes', 'value': 'S/ Ingresos'})
    fig1.update_traces(mode='lines+markers+text', textposition='top center')
    fig1 = update_common_layout(fig1, height_val=400)

    fig2 = px.bar(df2.sort_values('periodo').assign(mes_nombre=lambda x: x['mes'].map(meses_es),
                                                    etiqueta=lambda x: x['mes_nombre'] + ' ' + x['año'].astype(str)),
                  x='etiqueta', y='total',
                  title=f'Ganancia del Mes: {mes_anio_anterior} vs {mes_anio_actual}',
                  labels={'etiqueta': 'Mes', 'total': 'S/ Ingresos'},
                  color_discrete_sequence=['#7ED957'], text='total')
    fig2.update_traces(texttemplate='%{text:.2f}', textposition='outside')
    fig2 = update_common_layout(fig2, height_val=400)

    fig3 = px.bar(df3, x='unidades', y='producto', orientation='h',
                      title=f'Top 10 Productos Más Vendidos ({mes_anio_actual})',
                      labels={'unidades': 'Unidades', 'producto': 'Producto'},
                      color_discrete_sequence=['#F266AB'], text='unidades')
    fig3.update_traces(texttemplate='%{text}', textposition='outside')
    fig3.update_layout(yaxis={'categoryorder': 'total ascending'})
    fig3 = update_common_layout(fig3, height_val=450)

    if not df4.empty and 'categoria' in df4.columns and 'ingresos' in df4.columns:
        fig4 = px.pie(df4, names='categoria', values='ingresos', title=f"Distribución de ingresos por categoría ({mes_anio_actual})")
        fig4.update_traces(textinfo='percent+value')
    else:
        fig4 = go.Figure()
        fig4.update_layout(title_text="No hay datos disponibles para el gráfico de ingresos por categoría")
    fig4 = update_common_layout(fig4, height_val=400)

    df5_piv = df5.pivot(index='distrito', columns='mes', values='total').fillna(0)
    df5_piv.columns = [
        mes_anio_anterior if col == (hoy.month - 1) else mes_anio_actual
        for col in df5_piv.columns
    ]
    fig5 = px.bar(df5_piv, barmode='group',
                      title=f'Ventas por Distrito: {mes_anio_anterior} vs {mes_anio_actual}',
                      labels={'value': 'S/ Ingresos', 'distrito': 'Distrito'},
                      color_discrete_sequence=['#FFA600', '#FF6361'])
    fig5 = update_common_layout(fig5, height_val=400)

    fig6 = px.pie(df6, names='tipo_cliente', values='cantidad',
                      title=f'Usuarios Nuevos vs Recurrentes ({mes_anio_actual})')
    fig6.update_traces(textinfo='percent+value')
    fig6 = update_common_layout(fig6, height_val=400)

    return fig1, fig2, fig3, fig4, fig5, fig6

def get_inventory_figures():
    fig_placeholder = go.Figure()
    fig_placeholder.update_layout(
        title_text="Gráfico de Inventario (próximamente)",
        height=500,
        template="plotly_white",
        font_color='#34495e',
        paper_bgcolor='#ffffff',
        plot_bgcolor='#ffffff',
        autosize=True,
        uirevision='constant'
    )
    return fig_placeholder

def get_platform_monitoring_figures():
    fig_placeholder = go.Figure()
    fig_placeholder.update_layout(
        title_text="Gráfico de Monitoreo de Plataforma (próximamente)",
        height=500,
        template="plotly_white",
        font_color='#34495e',
        paper_bgcolor='#ffffff',
        plot_bgcolor='#ffffff',
        autosize=True,
        uirevision='constant'
    )
    return fig_placeholder

# Dashboard
def create_dashboard(server):
    dash_app = Dash(__name__, server=server, url_base_pathname='/dashboard/')

    dash_app.layout = dash_html.Div([
        dash_html.H1(
            '📊 Monitoreo Ecommerce — MARBELLIN LENCERÍA 🛍️',
            style={
                'textAlign': 'center',
                'color': '#2c3e50',
                'fontFamily': 'Segoe UI, Roboto, Helvetica Neue, sans-serif',
                'fontSize': '2.8em',
                'fontWeight': 'bold',
                'marginBottom': '30px',
                'textShadow': '2px 2px 4px rgba(0,0,0,0.1)'
            }
        ),
        dcc.Interval(
            id='interval-component',
            interval=5*1000,
            n_intervals=0
        ),
        dcc.Tabs(
            id="tabs-main",
            value='tab-sales',
            style={
                'fontFamily': 'Segoe UI, Roboto, Helvetica Neue, sans-serif',
                'fontWeight': 'bold',
                'borderBottom': '1px solid #ddd',
                'backgroundColor': '#f8f9fa',
                'color': '#34495e',
                'marginBottom': '20px'
            },
            children=[
                dcc.Tab(
                    label='📈 Monitoreo de Ventas',
                    value='tab-sales',
                    style={
                        'padding': '15px 25px',
                        'borderTopLeftRadius': '8px',
                        'borderTopRightRadius': '8px',
                        'border': '1px solid #ddd',
                        'borderBottom': 'none',
                        'backgroundColor': '#ecf0f1',
                        'color': '#34495e'
                    },
                    selected_style={
                        'padding': '15px 25px',
                        'borderTopLeftRadius': '8px',
                        'borderTopRightRadius': '8px',
                        'border': '1px solid #4CAF50',
                        'borderBottom': '3px solid #4CAF50',
                        'backgroundColor': '#4CAF50',
                        'color': 'white'
                    }
                ),
                dcc.Tab(
                    label='📦 Monitoreo de Inventario',
                    value='tab-inventory',
                    style={
                        'padding': '15px 25px',
                        'borderTopLeftRadius': '8px',
                        'borderTopRightRadius': '8px',
                        'border': '1px solid #ddd',
                        'borderBottom': 'none',
                        'backgroundColor': '#ecf0f1',
                        'color': '#34495e'
                    },
                    selected_style={
                        'padding': '15px 25px',
                        'borderTopLeftRadius': '8px',
                        'borderTopRightRadius': '8px',
                        'border': '1px solid #FFC107',
                        'borderBottom': '3px solid #FFC107',
                        'backgroundColor': '#FFC107',
                        'color': '#2c3e50'
                    }
                ),
                dcc.Tab(
                    label='⚙️ Monitoreo de Plataforma',
                    value='tab-platform',
                    style={
                        'padding': '15px 25px',
                        'borderTopLeftRadius': '8px',
                        'borderTopRightRadius': '8px',
                        'border': '1px solid #ddd',
                        'borderBottom': 'none',
                        'backgroundColor': '#ecf0f1',
                        'color': '#34495e'
                    },
                    selected_style={
                        'padding': '15px 25px',
                        'borderTopLeftRadius': '8px',
                        'borderTopRightRadius': '8px',
                        'border': '1px solid #007bff',
                        'borderBottom': '3px solid #007bff',
                        'backgroundColor': '#007bff',
                        'color': 'white'
                    }
                ),
            ]
        ),
        dash_html.Div(id='tabs-content-main', style={'padding': '20px', 'backgroundColor': '#f5f5f5', 'borderRadius': '8px'})
    ])

    @dash_app.callback(
        Output('tabs-content-main', 'children'),
        Input('tabs-main', 'value'),
        Input('interval-component', 'n_intervals')
    )
    def render_content(tab_selected, n_intervals):
        sales_graph_item_base_style = {
            'padding': '10px',
            'backgroundColor': '#ffffff',
            'borderRadius': '8px',
            'boxShadow': '0 4px 8px rgba(0,0,0,0.1)',
            'marginBottom': '20px',
            'flexGrow': '1', 
            'flexShrink': '1', 
            'flexBasis': 'calc(50% - 20px)', 
            'minHeight': '450px' 
        }

        sales_graphs_container_style = {
            'display': 'flex',
            'flexWrap': 'wrap',
            'justifyContent': 'center',
            'gap': '20px', 
            'width': '100%',
            'maxWidth': '1200px',
            'margin': '0 auto'
        }

        if tab_selected == 'tab-sales':
            fig1, fig2, fig3, fig4, fig5, fig6 = get_sales_data_and_figures()
            return dash_html.Div([
                dash_html.Div([
                    dash_html.Div(dcc.Graph(figure=fig1, config={'responsive': True}), className='dash-graph-item', style=sales_graph_item_base_style),
                    dash_html.Div(dcc.Graph(figure=fig2, config={'responsive': True}), className='dash-graph-item', style=sales_graph_item_base_style),
                    dash_html.Div(dcc.Graph(figure=fig3, config={'responsive': True}), className='dash-graph-item', style=sales_graph_item_base_style),
                    dash_html.Div(dcc.Graph(figure=fig4, config={'responsive': True}), className='dash-graph-item', style=sales_graph_item_base_style),
                    dash_html.Div(dcc.Graph(figure=fig5, config={'responsive': True}), className='dash-graph-item', style=sales_graph_item_base_style),
                    dash_html.Div(dcc.Graph(figure=fig6, config={'responsive': True}), className='dash-graph-item', style=sales_graph_item_base_style),
                ], style=sales_graphs_container_style)
            ])
        elif tab_selected == 'tab-inventory':
            fig_inv = get_inventory_figures()
            return dash_html.Div([
                dash_html.Div(
                    dcc.Graph(figure=fig_inv, config={'responsive': True}),
                    style={
                        'width': '100%',
                        'padding': '20px',
                        'backgroundColor': '#ffffff',
                        'borderRadius': '8px',
                        'boxShadow': '0 4px 8px rgba(0,0,0,0.1)',
                        'marginBottom': '20px',
                        'minHeight': '500px' 
                    }
                ),
                dash_html.H3(
                    "🛠️ ¡Esta sección está en construcción! Aquí encontrarás métricas clave de tu inventario pronto.",
                    style={'textAlign': 'center', 'color': '#34495e', 'fontFamily': 'Segoe UI, sans-serif', 'fontSize': '1.5em', 'marginTop': '30px'}
                ),
            ])
        elif tab_selected == 'tab-platform':
            fig_plat = get_platform_monitoring_figures()
            return dash_html.Div([
                dash_html.Div(
                    dcc.Graph(figure=fig_plat, config={'responsive': True}),
                    style={
                        'width': '100%',
                        'padding': '20px',
                        'backgroundColor': '#ffffff',
                        'borderRadius': '8px',
                        'boxShadow': '0 4px 8px rgba(0,0,0,0.1)',
                        'marginBottom': '20px',
                        'minHeight': '500px' 
                    }
                ),
                dash_html.H3(
                    "🚀 Monitoreando el pulso de tu plataforma. ¡Pronto aquí los datos de rendimiento!",
                    style={'textAlign': 'center', 'color': '#34495e', 'fontFamily': 'Segoe UI, sans-serif', 'fontSize': '1.5em', 'marginTop': '30px'}
                ),
            ])
        return dash_html.Div("Selecciona una pestaña para ver el contenido.")

    return dash_app

dash_app = create_dashboard(server)

INDEX_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>Monitoreo Ecommerce — Marbellin Lencería</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body {
      margin: 0;
      padding: 0;
      font-family: 'Segoe UI', 'Roboto', 'Helvetica Neue', sans-serif;
      background: #f5f5f5;
      color: #34495e;
    }
    h1 { text-align: center; }
    iframe {
      width: 100%;
      height: 95vh;
      border: none;
      box-shadow: 0 0 15px rgba(0,0,0,0.1);
      border-radius: 8px;
    }
    .main-container {
      max-width: 1200px;
      margin: 20px auto;
      padding: 0 20px;
    }

    .dash-graph-item ._dash-graph { 
        height: 100% !important; 
        width: 100% !important; 
    }

    .dash-graph-item {
        flex-grow: 1;
        flex-shrink: 1;
        flex-basis: calc(50% - 10px); 
        min-width: 300px; 
        box-sizing: border-box; 
    }

    /* pantallas medianas/pequeñas */
    @media (max-width: 992px) {
        .main-container {
            padding: 0 10px;
            max-width: 100%;
        }
        .dash-graph-item {
            flex-basis: 100%; 
            min-width: unset; 
        }
    }

    /* pantallas muy pequeñas */
    @media (max-width: 576px) {
        body {
            font-size: 14px;
        }
        h1 {
            font-size: 2em;
        }
        .main-container {
            padding: 0 5px;
        }
        .modebar {
            display: none !important; /* Ocultar barra Plotly en móviles */
        }
    }
  </style>
</head>
<body>
  <div class="main-container">
    <h1>Panel de Monitoreo General</h1>
    <iframe src="/dashboard/"></iframe>
  </div>
</body>
</html>
"""

@server.route('/')
def index():
    return render_template_string(INDEX_HTML)

if __name__ == '__main__':
    server.run(debug=True, port=8050)
