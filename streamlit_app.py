import streamlit as st
import pandas as pd
import numpy as np
import random
import time
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="F1 Strategy Commander 2026", layout="wide", initial_sidebar_state="expanded")

# --- 1. SIMULATED ML MODELS & LOGIC (For the ML Architect) ---
def predict_tire_degradation(tire_age, compound):
    """
    MOCK LINEAR REGRESSION: Predicts lap time penalty based on tire age.
    Swap this with your actual trained Sklearn model later.
    """
    deg_rates = {"Soft": 0.3, "Medium": 0.15, "Hard": 0.08}
    base_penalty = deg_rates.get(compound, 0.15)
    # The older the tire, the exponentially worse it gets (the "cliff")
    return (tire_age * base_penalty) + (0.02 * (tire_age ** 2))

def predict_safety_car():
    """
    MOCK RANDOM FOREST: Predicts if a Safety Car triggers.
    Swap with actual probability logic based on track history.
    """
    probability = 0.08 # 8% chance per lap for this simulation
    return random.random() < probability

def format_time(seconds):
    if seconds is None or pd.isna(seconds):
        return "-"
    total_seconds = float(seconds)
    mins = int(total_seconds // 60)
    secs = int(total_seconds % 60)
    hundredths = int(round((total_seconds - int(total_seconds)) * 100))
    if hundredths == 100:
        hundredths = 0
        secs += 1
    if secs == 60:
        secs = 0
        mins += 1
    return f"{mins:02d}:{secs:02d}.{hundredths:02d}"

def create_mock_opponents():
    return [
        {"Driver": "Max Verstappen", "Compound": "Medium", "Tire Age": 1, "Total Time": 0.0, "Last Lap Time": None, "Next Pit Lap": random.randint(14, 20), "Pace Bias": -0.35},
        {"Driver": "Lando Norris", "Compound": "Medium", "Tire Age": 1, "Total Time": 0.0, "Last Lap Time": None, "Next Pit Lap": random.randint(14, 20), "Pace Bias": -0.1},
        {"Driver": "Charles Leclerc", "Compound": "Medium", "Tire Age": 1, "Total Time": 0.0, "Last Lap Time": None, "Next Pit Lap": random.randint(14, 20), "Pace Bias": 0.05},
        {"Driver": "Lewis Hamilton", "Compound": "Medium", "Tire Age": 1, "Total Time": 0.0, "Last Lap Time": None, "Next Pit Lap": random.randint(14, 20), "Pace Bias": 0.15},
    ]

def build_standings_df():
    your_last_lap = st.session_state.history[-1]["Lap Time (s)"] if st.session_state.history else None
    standings_rows = [{"Driver": "You", "Last Lap (s)": your_last_lap}]
    standings_rows.extend(
        {"Driver": opponent["Driver"], "Last Lap (s)": opponent["Last Lap Time"]}
        for opponent in st.session_state.opponents
    )
    standings_df = pd.DataFrame(standings_rows)
    standings_df = standings_df.sort_values("Last Lap (s)", na_position="last").reset_index(drop=True)
    standings_df["Position"] = standings_df.index + 1
    fastest_lap = standings_df["Last Lap (s)"].min()
    standings_df["Gap To Fastest Lap (s)"] = (standings_df["Last Lap (s)"] - fastest_lap).round(2)
    standings_df["Last Lap"] = standings_df["Last Lap (s)"].apply(format_time)
    standings_df["Gap To Fastest Lap"] = standings_df["Gap To Fastest Lap (s)"].apply(format_time)
    return standings_df[["Position", "Driver", "Last Lap", "Gap To Fastest Lap"]]

# --- 2. SESSION STATE MANAGEMENT (The "Game Engine") ---
# We use st.session_state to remember the race data between button clicks.
if 'race_started' not in st.session_state:
    st.session_state.race_started = False
    st.session_state.lap = 1
    st.session_state.total_laps = 50
    st.session_state.tire_age = 1
    st.session_state.compound = "Medium"
    st.session_state.sc_active = False
    st.session_state.sc_laps_remaining = 0
    st.session_state.total_race_time = 0.0
    st.session_state.history = [] # Stores lap-by-lap data
    st.session_state.opponents = create_mock_opponents()
    st.session_state.last_lap_advanced_at = time.time()

# --- 3. RACE ACTIONS (Backend Logic) ---
def advance_lap(pit_stop=False, new_compound=None):
    base_lap_time = 85.0 # Base pace in seconds (e.g., 1m 25s)
    lap_time = base_lap_time
    event = "Clean Air"
    
    # Handle Pit Stop
    if pit_stop:
        lap_time += 22.0 # Pit lane time loss
        st.session_state.tire_age = 0
        st.session_state.compound = new_compound
        event = f"Pit Stop ({new_compound})"
    
    # Handle Safety Car Status
    if st.session_state.sc_laps_remaining > 0:
        lap_time += 15.0 # Slower laps behind Safety Car
        st.session_state.sc_laps_remaining -= 1
        event = "Safety Car (Slow Pace)"
        if st.session_state.sc_laps_remaining == 0:
            st.session_state.sc_active = False
    else:
        # Check if a NEW Safety Car triggers (only if not already active and not pitting)
        if not pit_stop and predict_safety_car():
            st.session_state.sc_active = True
            st.session_state.sc_laps_remaining = random.randint(2, 4)
            event = "SC DEPLOYED!"
            lap_time += 10.0 # Slowing down this lap
    
    # Add Tire Degradation Penalty
    deg_penalty = predict_tire_degradation(st.session_state.tire_age, st.session_state.compound)
    lap_time += deg_penalty

    # Simulate opponents for this lap
    for opponent in st.session_state.opponents:
        opponent_lap_time = 85.0 + opponent["Pace Bias"] + random.uniform(-0.6, 0.8)

        if st.session_state.lap >= opponent["Next Pit Lap"]:
            opponent_lap_time += 21.0
            opponent["Tire Age"] = 0
            opponent["Compound"] = random.choice(["Soft", "Medium", "Hard"])
            opponent["Next Pit Lap"] = st.session_state.lap + random.randint(14, 20)

        if st.session_state.sc_active or st.session_state.sc_laps_remaining > 0:
            opponent_lap_time += 15.0

        opponent_lap_time += predict_tire_degradation(opponent["Tire Age"], opponent["Compound"])
        opponent["Total Time"] += opponent_lap_time
        opponent["Last Lap Time"] = round(opponent_lap_time, 2)
        opponent["Tire Age"] += 1
    
    # Save lap data
    st.session_state.history.append({
        "Lap": st.session_state.lap,
        "Lap Time (s)": round(lap_time, 2),
        "Tire Age": st.session_state.tire_age,
        "Compound": st.session_state.compound,
        "Event": event
    })
    
    # Update global state
    st.session_state.total_race_time += lap_time
    st.session_state.lap += 1
    st.session_state.tire_age += 1
    st.session_state.last_lap_advanced_at = time.time()

# --- 4. FRONTEND / UI (For the UI/UX Designer) ---
st.title("🏁 F1 Strategy Commander 2026")
st.markdown("You are the Lead Strategist. Manage your tires, react to Safety Cars, and get to Lap 50 as fast as possible.")

if not st.session_state.race_started:
    if st.button("🚦 START SIMULATION"):
        st.session_state.race_started = True
        st.session_state.last_lap_advanced_at = time.time()
        st.rerun()

else:
    # Top Dashboard / Metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(label="Current Lap", value=f"{st.session_state.lap} / {st.session_state.total_laps}")
    with col2:
        st.metric(label="Tire Age (Laps)", value=st.session_state.tire_age)
    with col3:
        st.metric(label="Current Compound", value=st.session_state.compound)
    with col4:
        st.metric(label="Total Race Time", value=format_time(st.session_state.total_race_time))

    st.divider()

    # Main Interaction Area
    if st.session_state.lap <= st.session_state.total_laps:
        # Refresh every second while race is active (without full page reload/session reset)
        st_autorefresh(interval=1000, key="race_timer_refresh")

        elapsed = time.time() - st.session_state.last_lap_advanced_at
        time_left = max(0, int(np.ceil(10 - elapsed)))

        if elapsed >= 10:
            advance_lap()
            st.rerun()

        st.info(f"⏱️ Auto-advance in **{time_left}s** (or advance manually below).")
        
        # Alerts (Safety Car Warning)
        if st.session_state.sc_active:
            st.warning("⚠️ **SAFETY CAR DEPLOYED!** Pit stops cost less time under SC. Do you box now?")

        # Control Panel
        st.subheader("Command Center")
        c1, c2, c3 = st.columns([1, 1, 2])
        
        with c1:
            if st.button("🏎️ ADVANCE 1 LAP (Stay Out)", width=True):
                advance_lap()
                st.rerun()
                
        with c2:
            st.markdown("**Box For:**")
            new_tire = st.radio("Select Compound", ["Soft", "Medium", "Hard"], horizontal=True, label_visibility="collapsed")
            if st.button("🛠️ BOX NOW", type="primary", width=True):
                advance_lap(pit_stop=True, new_compound=new_tire)
                st.rerun()

        with c3:
            standings_df = build_standings_df()
            your_row = standings_df[standings_df["Driver"] == "You"]
            your_position = int(your_row["Position"].iloc[0]) if not your_row.empty else 1
            st.metric("Current Position", f"P{your_position}")
            st.dataframe(standings_df, width=True, hide_index=True)
                
    else:
        st.success("🏁 RACE FINISHED!")
        # Post-Race Analytics could go here (comparing to AI baseline)
        if st.button("Restart Simulation"):
            st.session_state.clear()
            st.rerun()

    # Visualizations (Plotly)
    if len(st.session_state.history) > 0:
        st.subheader("Live Telemetry")
        df = pd.DataFrame(st.session_state.history)
        
        # Line chart for Lap Times
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df['Lap'], y=df['Lap Time (s)'], mode='lines+markers', name='Lap Time', line=dict(color='cyan')))
        
        # Highlight Pit Stops and Safety Cars
        pit_stops = df[df['Event'].str.contains("Pit Stop")]
        if not pit_stops.empty:
            fig.add_trace(go.Scatter(x=pit_stops['Lap'], y=pit_stops['Lap Time (s)'], mode='markers', marker=dict(color='red', size=12, symbol='x'), name='Pit Stop'))
            
        fig.update_layout(xaxis_title="Lap", yaxis_title="Lap Time (Seconds)", template="plotly_dark", height=400)
        st.plotly_chart(fig, width=True)
        
        # Data Log
        with st.expander("Detailed Race Log"):
            log_df = df.copy()
            log_df["Lap Time"] = log_df["Lap Time (s)"].apply(format_time)
            st.dataframe(log_df[["Lap", "Lap Time", "Tire Age", "Compound", "Event"]], width=True)