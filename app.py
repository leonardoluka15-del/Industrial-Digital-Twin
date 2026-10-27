import json
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from twin.plant import Plant, Settings

st.set_page_config(page_title='AQUA • Industrial Digital Twin', page_icon='💧', layout='wide')
st.markdown('''<style>
.block-container {padding-top:2rem;max-width:1500px}
[data-testid="stMetric"] {background:#111f30;border:1px solid #24364b;border-radius:12px;padding:18px}
h1 {letter-spacing:-1.5px} .stCaption {color:#93a9bf}
</style>''', unsafe_allow_html=True)
if 'plant' not in st.session_state:
    st.session_state.plant = Plant()
    st.session_state.running = False

with st.sidebar:
    st.title('💧 AQUA')
    st.caption('INDUSTRIAL DIGITAL TWIN / v0.1')
    st.divider()
    mode = st.selectbox('Control mode', ['Automatic', 'Manual'])
    enabled = st.toggle('Pump enabled', True)
    target = st.slider('Tank setpoint (m)', 0.5, 4.5, 3.0, 0.1)
    demand = st.slider('Water demand (L/s)', 0.0, 30.0, 12.0, 0.5)
    manual = st.slider('Manual motor speed (%)', 0, 100, 65, disabled=mode=='Automatic')
    speed = st.select_slider('Simulation speed', [1, 2, 5, 10], value=2)
    st.caption('Simulated seconds per 1-second dashboard update.')
    with st.expander('Controller tuning'):
        kp = st.number_input('Kp (1/m)', 0.0, 5.0, 0.55, 0.05)
        ki = st.number_input('Ki (1/m/s)', 0.0, 0.5, 0.015, 0.005, format='%.3f')
        kd = st.number_input('Kd (s/m)', 0.0, 2.0, 0.0, 0.05)
    with st.expander('Inject faults', expanded=True):
        blockage = st.slider('Pipe blockage (%)', 0, 95, 0)
        leak = st.slider('Leak at full tank (L/s)', 0.0, 15.0, 0.0, 0.5)
        bias = st.slider('Level sensor bias (m)', -1.0, 1.0, 0.0, 0.1)
        cooling = st.toggle('Cooling failure')
    st.caption('Faults remain active until you clear their controls.')

cfg = Settings(target, demand/1000, mode, manual/100, kp, ki, kd,
               blockage/100, leak/1000, bias, cooling, enabled)
st.caption('OPERATIONS / VIRTUAL PUMPING STATION')
st.title('Your plant. In real time.')
st.write('Explore water dynamics, tune the controller and investigate equipment faults.')
a,b,c,d = st.columns([1,1,1,3])
if a.button('▶ Start', width='stretch'): st.session_state.running = True
if b.button('Ⅱ Pause', width='stretch'): st.session_state.running = False
if c.button('↺ Reset', width='stretch'):
    st.session_state.plant = Plant()
    st.session_state.running = False
    st.rerun()
d.caption('Reset clears simulation history; sidebar settings stay as selected.')

@st.fragment(run_every='1s')
def live():
    p = st.session_state.plant
    if st.session_state.running:
        row, alerts = p.advance(cfg, speed)
    elif p.rows:
        row, alerts = p.rows[-1], sorted(p._active)
    else:
        st.info('Ready. Press Start to run the simulated station.')
        return
    st.caption(f"{'● RUNNING' if st.session_state.running else 'Ⅱ PAUSED'} · Simulation time {p.time:.1f} s · Physics step 0.2 s")
    cards = st.columns(6)
    for col, label, value in zip(cards,
        ['Tank level', 'Pump flow', 'Motor speed', 'Pressure', 'Motor temperature', 'Energy used'],
        [f"{row['level_m']:.2f} m", f"{row['inflow_ls']:.1f} L/s", f"{row['speed_pct']:.0f}%",
         f"{row['pressure_bar']:.2f} bar", f"{row['temperature_c']:.1f} °C", f"{row['energy_kwh']:.4f} kWh"]):
        col.metric(label, value)
    overview, trends, diagnostics, export = st.tabs(['Station overview', 'Process trends', 'Diagnostics', 'Export & model'])
    df = pd.DataFrame(p.rows)
    with overview:
        left, right = st.columns([1,2])
        with left:
            fig = go.Figure(go.Indicator(mode='gauge+number', value=row['level_m'],
                number={'suffix':' m'}, title={'text':'Storage tank'},
                gauge={'axis':{'range':[0,5]}, 'bar':{'color':'#25dfb4'},
                       'threshold':{'line':{'color':'#ffb75e','width':4},'value':cfg.target}}))
            fig.update_layout(height=310, margin=dict(t=45,b=20,l=30,r=30), paper_bgcolor='rgba(0,0,0,0)', font_color='#e2edf5')
            st.plotly_chart(fig, width='stretch')
        with right:
            st.subheader('Supply → motor & pump → pipe → tank → demand')
            st.progress(min(1.0, row['level_m']/5), text=f"Tank volume: {row['level_m']*4:.1f} / 20 m³")
            st.write(f"**Delivered:** {row['delivered_ls']:.1f} L/s  ·  **Leak:** {row['leak_ls']:.1f} L/s  ·  **Overflow:** {row['overflow_ls']:.1f} L/s")
            if alerts:
                for alert in alerts: st.warning(alert)
            else: st.success('Process indicators within configured thresholds.')
        chart(df, ['level_m','target_m','measured_level_m'], 'Tank level & setpoint', 'Level (m)')
    with trends:
        x,y=st.columns(2)
        with x:
            chart(df,['inflow_ls','demand_ls','delivered_ls','leak_ls'],'Water balance','Flow (L/s)')
            chart(df,['power_kw'],'Electrical load','Power (kW)')
        with y:
            chart(df,['speed_pct'],'Motor drive','Speed (%)')
            chart(df,['temperature_c'],'Motor thermal response','Temperature (°C)')
    with diagnostics:
        st.caption('Rule-based physics checks. These are suspected conditions, not a trained predictive maintenance model.')
        st.dataframe(pd.DataFrame(p.events[::-1], columns=['time_s','event']), width='stretch', hide_index=True)
        st.info('Sensor disagreement assumes an independent reference level measurement. Water loss assumes independent inlet and outlet metering. Fault injection supplies those virtual instruments.')
    with export:
        st.download_button('Download operating history (CSV)', df.to_csv(index=False), 'operating_history.csv','text/csv')
        st.download_button('Download experiment settings', json.dumps(cfg.__dict__,indent=2),'experiment.json','application/json')
        st.markdown('''**Model:** 4 m² tank, 5 m maximum level, variable-speed centrifugal pump.

Tank balance: `A dh/dt = Qin − Qdelivered − Qleak − Qoverflow`.

Pump curve: `H = 18 n² − R Q²`, with `R = 8000/(1 − blockage)²`.

Power: `P = ρgQH/0.68 + 120n²`. Temperature follows a lumped heat balance.

History retains the latest 6,000 samples (20 simulated minutes). Exports contain this retained window. Energy is cumulative since Reset. Sessions are independent and memory-only.

This is an educational simulation, with assumed parameters; it has not been calibrated against physical equipment. No real equipment connection or remaining-life prediction is included.''')

def chart(df, columns, title, ylabel):
    fig=go.Figure()
    colors=['#25dfb4','#ffb75e','#6baaff','#ef7b99']
    # Keep display light; exported history keeps all retained samples.
    view=df.iloc[::max(1,len(df)//800)]
    for column,color in zip(columns,colors):
        fig.add_trace(go.Scatter(x=view.time_s,y=view[column],name=column.replace('_',' '),line={'color':color,'width':2}))
    fig.update_layout(title=title,height=280,template='plotly_dark',paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='#111f30',margin=dict(l=15,r=15,t=45,b=20),legend={'orientation':'h'},
        xaxis_title='Simulation time (s)',yaxis_title=ylabel)
    st.plotly_chart(fig,width='stretch')

live()
