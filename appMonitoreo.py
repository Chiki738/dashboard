import locale
import pandas as pd
import plotly.express as px
from flask import Flask, render_template_string
from dash import Dash, dcc, html as dash_html
from dash.dependencies import Input, Output
from supabase import create_client, Client
import plotly.graph_objects as go
from functools import lru_cache 

locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
hoy = pd.Timestamp.today()
mes_anio_actual = hoy.strftime("%B %Y").capitalize()
mes_anio_anterior = (hoy - pd.DateOffset(months=1)).strftime("%B %Y").capitalize()
año_actual = hoy.year
año_anterior = año_actual - 1

url = "https://lyxhceqquioucmlmhvuj.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imx5eGhjZXFxdWlvdWNtbG1odnVqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDg5MDMxOTcsImV4cCI6MjA2NDQ3OTE5N30.9Ukt-vw_Sxv_bGFE265upP2ZLwqM76T39mHooFH_mfY"
supabase: Client = create_client(url, key)

server = Flask(__name__)

@lru_cache(maxsize=128) 
def fetch_table_cached(query):
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

@lru_cache(maxsize=1)
def get_sales_data_and_figures_cached(n_intervals_dummy):
    df1 = fetch_table_cached(f"""
        SELECT EXTRACT(YEAR FROM fecha) AS año,
               EXTRACT(MONTH FROM fecha) AS mes,
               SUM(total) AS total
        FROM pedidos
        WHERE fecha >= CURRENT_DATE - INTERVAL '1 year'
        GROUP BY año, mes
        ORDER BY año, mes
    """).pivot(index='mes', columns='año', values='total').reset_index()

    df2 = fetch_table_cached(f"""
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

    df3 = fetch_table_cached(f"""
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

    df4 = fetch_table_cached(f"""
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

    df5 = fetch_table_cached(f"""
        SELECT d.nombre AS distrito,
               EXTRACT(MONTH FROM o.fecha) AS mes,
               SUM(o.total) AS total
        FROM pedidos o
        JOIN users cl ON o.cliente_id = cl.cliente_id
        JOIN distritos d ON cl.distrito_id = d.distrito_id
        WHERE o.fecha >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')
          AND fecha <= CURRENT_DATE
        GROUP BY d.distrito_id, d.nombre, mes
        ORDER BY d.nombre, mes
    """)

    df6 = fetch_table_cached(f"""
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

@lru_cache(maxsize=1)
def get_inventory_figures_cached(n_intervals_dummy):
    queries = [
        """
        SELECT vp.id AS variante_id, p.nombre AS nombre_producto, vp.talla, vp.color, vp.cantidad AS stock_actual
        FROM variantes_producto vp
        JOIN productos p ON vp.producto_codigo = p.codigo
        ORDER BY vp.cantidad ASC
        """,
        """
        SELECT vp.id AS variante_id, p.nombre AS nombre_producto, vp.talla, vp.color, vp.cantidad AS stock_actual
        FROM variantes_producto vp
        JOIN productos p ON vp.producto_codigo = p.codigo
        WHERE vp.cantidad < 10
        ORDER BY vp.cantidad ASC
        """,
        """
        SELECT EXTRACT(MONTH FROM fecha_movimiento) AS mes,
               EXTRACT(YEAR FROM fecha_movimiento) AS año,
               SUM(CASE WHEN tipo_movimiento IN ('ingreso_lote_fabricacion', 'ajuste_positivo') THEN cantidad_afectada ELSE 0 END) AS entradas,
               SUM(CASE WHEN tipo_movimiento IN ('salida_venta', 'ajuste_negativo') THEN cantidad_afectada ELSE 0 END) AS salidas
        FROM movimientos_inventario
        GROUP BY EXTRACT(YEAR FROM fecha_movimiento), EXTRACT(MONTH FROM fecha_movimiento)
        ORDER BY EXTRACT(YEAR FROM fecha_movimiento), EXTRACT(MONTH FROM fecha_movimiento)
        """,
        f"""
        SELECT EXTRACT(YEAR FROM fecha_fin_fabricacion) AS año,
               EXTRACT(MONTH FROM fecha_fin_fabricacion) AS mes,
               SUM(cantidad_a_fabricar) AS total_unidades_producidas
        FROM ordenes_fabricacion
        WHERE estado_fabricacion = 'finalizado'
          AND fecha_fin_fabricacion >= CURRENT_DATE - INTERVAL '1 year'
        GROUP BY año, mes
        ORDER BY año, mes
        """,
        f"""
        SELECT estado_fabricacion, COUNT(id) AS numero_de_ordenes
        FROM ordenes_fabricacion
        WHERE EXTRACT(QUARTER FROM fecha_creacion) = EXTRACT(QUARTER FROM CURRENT_DATE)
          AND EXTRACT(YEAR FROM fecha_creacion) = EXTRACT(YEAR FROM CURRENT_DATE)
          AND estado_fabricacion IN ('en_proceso', 'finalizado')
        GROUP BY estado_fabricacion
        ORDER BY numero_de_ordenes DESC
        """,
        """
        SELECT of.variante_id, p.nombre AS nombre_producto, vp.talla, vp.color,
               SUM(of.cantidad_a_fabricar) AS cantidad_pendiente_fabricacion
        FROM ordenes_fabricacion of
        JOIN variantes_producto vp ON of.variante_id = vp.id
        JOIN productos p ON vp.producto_codigo = p.codigo
        WHERE of.estado_fabricacion IN ('en_proceso', 'planificada', 'pausada')
        GROUP BY of.variante_id, p.nombre, vp.talla, vp.color
        ORDER BY cantidad_pendiente_fabricacion DESC
        """,
        """
        SELECT
            il.ubicacion_lote,
            COUNT(DISTINCT il.id) AS numero_de_lotes_ingresados,
            ARRAY_AGG(
                DISTINCT p.nombre || ' (Talla: ' || vp.talla || ', Color: ' || vp.color || ', Cant: ' || il.cantidad_lote || ')'
            ) AS detalles_productos
        FROM
            ingresos_fabricacion_lote il
        JOIN
            variantes_producto vp ON il.variante_id = vp.id
        JOIN
            productos p ON vp.producto_codigo = p.codigo
        WHERE
            il.ubicacion_lote IS NOT NULL AND il.ubicacion_lote != ''
        GROUP BY
            il.ubicacion_lote
        ORDER BY
            numero_de_lotes_ingresados DESC
        """,
        """
        SELECT p.nombre AS nombre_producto, SUM(vp.cantidad) AS stock_total
        FROM productos p
        JOIN variantes_producto vp ON p.codigo = vp.producto_codigo
        GROUP BY p.codigo, p.nombre
        ORDER BY stock_total DESC
        """
    ]

    dfs = [fetch_table_cached(q) for q in queries]

    def update_common_layout_inventory(fig, height_val=None):
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

    df_stock_actual = dfs[0]
    df_stock_actual['display_name'] = df_stock_actual['nombre_producto'] 

    fig1 = px.bar(df_stock_actual,
                  x='stock_actual',
                  y='display_name',
                  color='talla', 
                  orientation='h',
                  title="Stock Actual por Variante",
                  labels={'stock_actual': 'Cantidad', 'display_name': 'Producto'},
                  text='stock_actual', 
                  custom_data=['talla', 'color']
                 )
    fig1.update_traces(texttemplate='<b>%{text}</b>', textposition='inside')
    fig1.update_layout(yaxis={'categoryorder': 'total ascending'})
    fig1.update_traces(hovertemplate="<b>Producto</b>: %{y}<br>" +
                                     "<b>Talla</b>: %{customdata[0]}<br>" +
                                     "<b>Color de Prenda</b>: %{customdata[1]}<br>" +
                                     "<b>Cantidad</b>: %{x}<extra></extra>") 
    fig1 = update_common_layout_inventory(fig1, height_val=450)

    df_stock_critico = dfs[1]
    df_stock_critico['display_name'] = df_stock_critico['nombre_producto']
    fig2 = px.bar(df_stock_critico,
                  x='stock_actual',
                  y='display_name',
                  color='talla',
                  orientation='h',
                  title="Variantes con Stock Crítico (<10)",
                  labels={'stock_actual': 'Cantidad', 'display_name': 'Producto'},
                  text='stock_actual',
                  custom_data=['talla', 'color']
                 )
    fig2.update_traces(texttemplate='<b>%{text}</b>', textposition='inside')
    fig2.update_layout(yaxis={'categoryorder': 'total ascending'})
    fig2.update_traces(hovertemplate="<b>Producto</b>: %{y}<br>" +
                                     "<b>Talla</b>: %{customdata[0]}<br>" +
                                     "<b>Color de Prenda</b>: %{customdata[1]}<br>" +
                                     "<b>Cantidad</b>: %{x}<extra></extra>")
    fig2 = update_common_layout_inventory(fig2, height_val=450)

    df_movimientos = dfs[2]
    df_movimientos['mes_nombre'] = df_movimientos['mes'].apply(lambda x: pd.to_datetime(f'2000-{int(x)}-01').strftime('%b'))
    df_movimientos['periodo_display'] = df_movimientos.apply(lambda row: f"{row['mes_nombre']} {int(row['año'])}" if len(df_movimientos['año'].unique()) > 1 else row['mes_nombre'], axis=1)
    df_movimientos = df_movimientos.sort_values(by=['año', 'mes'])

    fig3 = px.area(df_movimientos, x="periodo_display", y=["entradas", "salidas"],
                   title="Movimientos de Inventario (Entradas vs. Salidas por Mes)",
                   labels={'periodo_display': 'Mes', 'value': 'Cantidad de Unidades'})
    fig3.update_layout(hovermode="x unified")
    fig3 = update_common_layout_inventory(fig3, height_val=450)


    df_produccion_mensual = dfs[3].pivot(index='mes', columns='año', values='total_unidades_producidas').reset_index()
    columnas_produccion_disponibles = [col for col in [año_anterior, año_actual] if col in df_produccion_mensual.columns]

    fig4 = px.line(df_produccion_mensual, x='mes', y=columnas_produccion_disponibles,
                     title=f'Producción Mensual de Lencería: {año_anterior} vs {año_actual}',
                     labels={'mes': 'Mes', 'value': 'Unidades Producidas'})
    fig4.update_traces(mode='lines+markers+text', textposition='top center')
    fig4 = update_common_layout_inventory(fig4, height_val=450)


    df_estados_fabricacion = dfs[4]
    if not df_estados_fabricacion.empty:
        fig5 = px.pie(df_estados_fabricacion, names="estado_fabricacion", values="numero_de_ordenes",
                      title=f"Distribución de Órdenes de Fabricación (Trimestre Actual)",
                      hole=.3)
        fig5.update_traces(textinfo='percent+label', pull=[0.05 if s == 'en_proceso' else 0 for s in df_estados_fabricacion['estado_fabricacion']])
    else:
        fig5 = go.Figure()
        fig5.update_layout(
            title_text="No hay órdenes de fabricación 'en proceso' o 'finalizadas' en el trimestre actual.",
            annotations=[dict(text="No hay datos", x=0.5, y=0.5, font_size=20, showarrow=False)]
        )
    fig5 = update_common_layout_inventory(fig5, height_val=450)


    df_ordenes_pendientes = dfs[5]
    df_ordenes_pendientes['display_name'] = df_ordenes_pendientes['nombre_producto']
    fig6 = px.bar(df_ordenes_pendientes,
                  x='cantidad_pendiente_fabricacion',
                  y='display_name',
                  color='talla',
                  orientation='h',
                  title="Órdenes Pendientes por Variante",
                  labels={'cantidad_pendiente_fabricacion': 'Cantidad Pendiente', 'display_name': 'Producto'},
                  text='cantidad_pendiente_fabricacion',
                  custom_data=['talla', 'color']
                 )
    fig6.update_traces(texttemplate='<b>%{text}</b>', textposition='inside')
    fig6.update_layout(yaxis={'categoryorder': 'total ascending'})
    fig6.update_traces(hovertemplate="<b>Producto</b>: %{y}<br>" +
                                     "<b>Talla</b>: %{customdata[0]}<br>" +
                                     "<b>Color de Prenda</b>: %{customdata[1]}<br>" +
                                     "<b>Cantidad Pendiente</b>: %{x}<extra></extra>")
    fig6 = update_common_layout_inventory(fig6, height_val=450)

    df_stock_total_productos = dfs[7] 

    stock_cards = []
    if not df_stock_total_productos.empty:
        for index, row in df_stock_total_productos.iterrows():
            stock_cards.append(
                dash_html.Div(
                    [
                        dash_html.H4(row['nombre_producto'], style={'margin-bottom': '5px', 'color': '#2c3e50'}),
                        dash_html.P(f"Stock Total: {int(row['stock_total'])}", style={'fontSize': '1.2em', 'fontWeight': 'bold', 'color': '#4CAF50'}),
                    ],
                    style={
                        'backgroundColor': '#ffffff',
                        'padding': '15px 20px',
                        'borderRadius': '8px',
                        'boxShadow': '0 2px 4px rgba(0,0,0,0.05)',
                        'textAlign': 'center',
                        'flexBasis': 'calc(33% - 20px)', 
                        'minWidth': '200px',
                        'maxWidth': '300px',
                        'margin': '10px 0', 
                        'display': 'flex',
                        'flexDirection': 'column',
                        'justifyContent': 'center',
                        'alignItems': 'center'
                    }
                )
            )
    else:
        stock_cards.append(
            dash_html.Div(
                dash_html.P("No hay datos de stock total por producto disponibles.", style={'textAlign': 'center', 'color': '#7f8c8d'}),
                style={
                    'width': '100%',
                    'padding': '20px',
                    'backgroundColor': '#ffffff',
                    'borderRadius': '8px',
                    'boxShadow': '0 4px 8px rgba(0,0,0,0.1)'
                }
            )
        )

    stock_cards_container = dash_html.Div(
        [
            dash_html.H3("Stock Total por Producto", style={'textAlign': 'center', 'width': '100%', 'margin-bottom': '20px', 'color': '#2c3e50'}),
            dash_html.Div(
                stock_cards,
                style={
                    'display': 'flex',
                    'flexWrap': 'wrap',
                    'justifyContent': 'center',
                    'gap': '20px', 
                    'width': '100%'
                }
            )
        ],
        style={
            'backgroundColor': '#f8f9fa',
            'borderRadius': '8px',
            'padding': '20px',
            'boxShadow': '0 4px 8px rgba(0,0,0,0.1)',
            'margin-bottom': '20px'
        }
    )


    figs = [fig1, fig2, fig3, fig4, fig5, fig6]

    for fig in figs:
        update_common_layout_inventory(fig, height_val=450) 
    return figs, stock_cards_container

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
                )
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
            fig1, fig2, fig3, fig4, fig5, fig6 = get_sales_data_and_figures_cached(n_intervals)
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
            figs, stock_cards_container = get_inventory_figures_cached(n_intervals)
            return dash_html.Div([
                stock_cards_container, 
                dash_html.Div([
                    dash_html.Div(dcc.Graph(figure=figs[0], config={'responsive': True}), className='dash-graph-item', style=sales_graph_item_base_style),
                    dash_html.Div(dcc.Graph(figure=figs[1], config={'responsive': True}), className='dash-graph-item', style=sales_graph_item_base_style),
                    dash_html.Div(dcc.Graph(figure=figs[2], config={'responsive': True}), className='dash-graph-item', style=sales_graph_item_base_style),
                    dash_html.Div(dcc.Graph(figure=figs[3], config={'responsive': True}), className='dash-graph-item', style=sales_graph_item_base_style),
                    dash_html.Div(dcc.Graph(figure=figs[4], config={'responsive': True}), className='dash-graph-item', style=sales_graph_item_base_style),
                    dash_html.Div(dcc.Graph(figure=figs[5], config={'responsive': True}), className='dash-graph-item', style=sales_graph_item_base_style),                 
                ], style=sales_graphs_container_style)
            ])
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
  </body>
</html>
"""

@server.route('/')
def index():
    return render_template_string(INDEX_HTML)

if __name__ == '__main__':
    server.run(debug=True, port=8050)
