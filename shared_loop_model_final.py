"""
Shared ground loop with supermarket heat recovery: homeowner LCOH optimisation
==============================================================================

A street of homes, each with its own ground source heat pump and hot water tank, shares
one borehole field. A nearby supermarket rejects its refrigeration heat into the same loop,
and a small reverse air source heat pump (the "surplus ASHP") can dump excess loop heat to air.

For a candidate design (number and depth of boreholes, heat pump size, tank size, surplus ASHP
size and set-point, tank charging fraction) the model:
  1. simulates one year of a home (all homes identical), with tank charging driven by
     Octopus Agile electricity prices,
  2. simulates 25 years of the shared loop hour by hour: the homes extract heat, the supermarket
     rejects heat, the surplus ASHP removes excess heat, and the ground responds through the
     pygfunction g-function using the full load history (FFT convolution),
  3. finds the minimum annual fee per home that gives the supermarket its target internal rate
     of return (IRR) over the analysis horizon, and
  4. returns the homeowner's levelised cost of heat (LCOH, p/kWh), which is the objective.

scipy's differential_evolution searches the design space, for each number of homes and each
target IRR.

Run:    python shared_loop_model.py
Needs:  numpy, scipy, pandas, matplotlib, openpyxl, pygfunction
"""

import os
import time
import math
import numpy as np
import pygfunction as gt
import pandas as pd
from scipy.optimize import differential_evolution
import matplotlib
matplotlib.use("Agg")          # save figures to files (no window needed)
import matplotlib.pyplot as plt

# =============================================================================
# 1. SETTINGS
# =============================================================================

# ---- Files ------------------------------------------------------------------
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_from_paul")   # folder holding the input data files
OUTPUT_DIR = "results"                              # figures and CSVs are written here
FILE_DEMAND = "HeatDemandProfiles_kW.csv"           # hourly heat demand, column 'Building 3'
FILE_WEATHER = "TMY_ClimateData_2007_2016.csv"      # hourly air temperature (column 'Temperature')
FILE_AGILE = "agile_electricity_london_way_more_years.csv"  # half-hourly Agile import prices
FILE_DESNZ = "commercial_electricty_prices.xlsx"    # DESNZ QEP table 3.4.2 (non-domestic prices)

# ---- Homes ------------------------------------------------------------------
N_HOMES_LIST = [20, 30, 40, 50, 60, 70, 80]   # numbers of homes to sweep (one optimisation each)
BUILDING = "Building 3"
AGILE_YEAR = 2025                 # year of Agile prices used (repeated every year)

# ---- Home heat pump ---------------------------------------------------------
COP_K = 1.45                      # scaling factor fitted to the flexoTHERM 8 kW datasheet (6 points)
COP_CAP = 6.0                     # maximum COP
T_HOT = 55.0                      # tank hot-zone / heat pump flow temperature [°C]
T_COLD = 47.0                     # tank cold-zone temperature [°C] (swing = 8 K)
T_ROOM = 20.0                     # room temperature around the tank [°C]
TANK_UA = 1.71                    # tank heat loss coefficient [W/K]
TANK_RESERVE = 0.3                # outside charging hours, keep the tank at least 30 % full
BUS_GRANT = 7500.0                # £ per home (Ofgem Boiler Upgrade Scheme)
BUS_CAP_KW = 300.0                # BUS shared ground loop cap: N_HOMES × HP kW <= 300 kWth
SCOP_MIN = 2.8                    # BUS minimum seasonal COP

# ---- Ground -----------------------------------------------------------------
T_GROUND = 12.0                   # undisturbed ground temperature [°C]
K_GROUND = 2.0                    # ground thermal conductivity [W/m/K] (BGS range)
CP_GROUND = 2.2e6                 # ground volumetric heat capacity [J/m3/K]
R_BOREHOLE = 0.065                # borehole radius [m] (MCS, 130 mm diameter)
RB = 0.1                          # borehole thermal resistance [m K/W] (MCS)
BOREHOLE_SPACING = 10.0           # distance between neighbouring boreholes [m]
BURIED_DEPTH = 2.0                # depth from the surface to the top of each borehole [m]
G_BOUNDARY = "UBWT"               # pygfunction boundary condition (uniform borehole wall temperature)
G_POINTS = 50                     # number of times at which pygfunction calculates g
T_LOOP_MIN = 0.0                  # loop temperature limits [°C]
T_LOOP_MAX = 25.0
YEARS = 25                        # analysis horizon [years]
LOOP_RELAX = 0.5                  # damping: take half of each new loop-temperature estimate

# ---- Supermarket ------------------------------------------------------------
Q_COOL = 80.0                     # constant refrigeration (cooling) load [kW]
T_EVAP = -8.0                     # refrigeration evaporating temperature [°C] (chilled)
COP_K_REF = 1.0                   # scaling so cooling COP ≈ 2.5 at 15 °C condensing (Efstratiadi 2019)
HX_APPROACH = 3.0                 # store-to-loop heat exchanger approach [K] (Efstratiadi 2019)
# Alternative system (no shared loop): one large reverse ASHP does the store's refrigeration and rejects to air
ALT_ASHP_AIR_APPROACH = 10.0      # alternative system condensing temperature = air + 10 K
ALT_ASHP_MIN_COND = 10.9          # its minimum condensing temperature [°C]
STORE_PRICE_FALLBACK = 28.25      # p/kWh, DESNZ 2025 Small/Medium incl. CCL (used if the Excel file can't be read)
STORE_BAND = "Electricity: Small/Medium (Pence per kWh)"

# ---- Surplus ASHP (small reverse ASHP on the loop: removes surplus heat, rejects it to air) ----
SURPLUS_EVAP_APPROACH = 3.0       # evaporator runs 3 K below the loop temperature
SURPLUS_AIR_APPROACH = 10.0       # rejects to air at air temperature + 10 K
SURPLUS_COP_CAP = 10.0            # cooling COP cap (when the loop is warmer than the air it is mostly fan power)
SURPLUS_RAMP = 1.0                # control ramp above the set-point [K] (smooths the on/off switch)

# ---- Gas comparison (Ofgem price cap 2025, direct debit, GB average, incl. VAT) ----
GAS_UNIT_Q = [6.34, 6.99, 6.33, 6.29]          # p/kWh for Q1..Q4 2025
GAS_STANDING_Q = [31.65, 32.67, 29.82, 34.03]  # p/day for Q1..Q4 2025
BOILER_EFF = 0.875                # seasonal boiler efficiency (85–90 %)
BOILER_CAPEX = 4200.0             # £ to buy and install a gas boiler
BOILER_OM = 100.0                 # £/yr boiler maintenance (annual service)
LIFE_BOILER = 15.0                # boiler lifetime [years]
ASHP_LCOH_P = (9.6, 14.6)         # p/kWh, IEA 2019 UK air-to-water HP, converted to 2025 £ (÷1.2765 $/£, ×CPI 138.4/107.8)

# ---- Economics ----------------------------------------------------------------
DISCOUNT = 0.035                  # discount rate (homeowner LCOH and reported payback)
IRR_TARGETS = [0.06, 0.09, 0.12]  # supermarket target IRR over the full YEARS horizon
SETUP_COST = 35000.0              # £ one-off construction / project set-up
DRILL_PER_M = 93.0                # £/m drilled
COST_PER_BOREHOLE = 1000.0        # £ fixed per borehole
PIPE_PER_M = 198.86               # £/m: street, field and connection pipework (hard dig)
FIELD_TO_STREET_M = 50.0          # m of pipe from the borehole field to the street
PIPE_PER_HOME_M = 10.0            # m of pipe per home (street frontage + connection)
FIELD_PIPE_PER_BOREHOLE_M = BOREHOLE_SPACING  # m of in-field pipe per borehole (≈ spacing)
HP_COST_FIXED, HP_COST_PER_KW = 6114.0, 809.0      # installed heat pump £ = fixed + per kW
TANK_COST_FIXED, TANK_COST_PER_L = 425.0, 1.16      # cylinder £ = fixed + per litre
SURPLUS_ASHP_COST_PER_KW = 600.0  # surplus ASHP £ per kW of heat removed
ALT_ASHP_COST_PER_KW = 600.0      # alternative large reverse ASHP £ per kW of heat rejected
HX_U = 3000.0                     # heat exchanger overall U [W/m2/K] for sizing
CEPCI_2018, CEPCI_2014 = 603.1, 576.1               # cost indices for the Jaric heat exchanger correlation
# Asset lifetimes for the capital recovery factor CRF = i(1+i)^n / ((1+i)^n - 1)
LIFE_HP = YEARS                   # heat pump + tank life [years]
LIFE_GROUND = 60.0                # boreholes + buried pipework life [years]
GROUND_ITEMS = ("drilling", "borehole_fixed", "pipework")   # capex items that use LIFE_GROUND

# ---- Optimiser ------------------------------------------------------------------
#            name                     lower   upper
BOUNDS = [("n_boreholes",               10.0,  150.0),
          ("depth_m",                   50.0,  200.0),
          ("hp_kw",                      4.0,    8.0),
          ("tank_l",                   100.0,  210.0),
          ("surplus_ashp_kw",            0.0,  200.0),
          ("surplus_ashp_setpoint_c",   15.0,   30.0),
          ("charge_fraction",            0.1,    0.5)]
DE_POPSIZE = 8    # candidates per design variable: 8 × 7 = 56 designs in play each generation
DE_MAXITER = 8    # number of generations 
DE_SEED = 1       # fixes the random numbers, so the starting designs and search path are repeatable
# Each generation, every candidate builds one trial design from the differences between other
# candidates, simulates it, and keeps it only if it beats the parent.

RUN_NO_SUPERMARKET_BASELINE = False   # also optimise the same scheme with no supermarket (Q_COOL = 0)
OPT_YEARS = YEARS                 # years simulated inside the optimiser (later years repeat the last one);
                                  # the final design is always re-simulated over the full YEARS

# =============================================================================
# 2. DATA LOADING
# =============================================================================
HOURS = 8760


def load_data():
    """Read every input file and return hourly (8760) arrays for one year."""
    dem = pd.read_csv(os.path.join(DATA_DIR, FILE_DEMAND))[BUILDING].to_numpy(float)     # heat demand
    assert len(dem) == HOURS, "heat demand must have 8760 hourly values"

    t_air = pd.read_csv(os.path.join(DATA_DIR, FILE_WEATHER))["Temperature"].to_numpy(float)   # air temperature
    assert len(t_air) == HOURS, "weather file must have 8760 hourly values"

    ag = pd.read_csv(os.path.join(DATA_DIR, FILE_AGILE))                                # home electricity price
    ag.columns = [c.strip() for c in ag.columns]
    ag["t"] = pd.to_datetime(ag["date"], dayfirst=True)
    ag = ag.drop_duplicates("t").set_index("t").sort_index()["rate"].astype(float)
    ag = ag[str(AGILE_YEAR)]
    ag = ag.resample("1h").mean().interpolate()          # half-hourly -> hourly
    price = ag.to_numpy()[:HOURS]
    if len(price) < HOURS:
        raise ValueError(f"Agile data for {AGILE_YEAR} has only {len(price)} hours")

    try:                                                                                 # supermarket electricity price
        x = pd.read_excel(os.path.join(DATA_DIR, FILE_DESNZ), sheet_name="3.4.2 (Annual inc CCL)", header=6)
        x["Year"] = pd.to_numeric(x["Year"].astype(str).str[:4], errors="coerce")
        store_price = float(x.loc[x["Year"] == AGILE_YEAR, STORE_BAND].iloc[0])
    except Exception as err:
        print(f"  (could not read DESNZ Excel: {err}; using {STORE_PRICE_FALLBACK} p/kWh)")
        store_price = STORE_PRICE_FALLBACK

    # constant supermarket cooling load [kW], the same every hour
    q_cool = np.full(HOURS, Q_COOL)

    # gas price per hour by quarter (non-leap year)
    q_of_hour = np.repeat(pd.date_range(f"{AGILE_YEAR}-01-01", periods=365, freq="D").quarter.to_numpy() - 1, 24)
    gas_unit = np.array(GAS_UNIT_Q)[q_of_hour]
    gas_standing_day = np.array(GAS_STANDING_Q)[q_of_hour[::24]]

    return dict(demand=dem, t_air=t_air, price=price, store_price=store_price,
                gas_unit=gas_unit, gas_standing_day=gas_standing_day, q_cool=q_cool)


# =============================================================================
# 3. PHYSICS
# =============================================================================

def cop_heating(t_loop_c):
    """Home heat pump heating COP: √(Th/(Th−Tc)) correlation scaled to the flexoTHERM datasheet."""
    th = T_HOT + 273.15
    tc = np.minimum(t_loop_c + 273.15, th - 5.0)          # guard against divide-by-zero
    return np.minimum(COP_CAP, COP_K * np.sqrt(th / (th - tc)))


def cop_cooling(t_cond_c):
    """Refrigeration (cooling) COP = heating COP − 1, same √ form, for a given condensing temperature [°C]."""
    th = t_cond_c + 273.15
    te = T_EVAP + 273.15
    th = np.maximum(th, te + 5.0)
    return np.maximum(0.5, COP_K_REF * np.sqrt(th / (th - te)) - 1.0)


def cop_surplus_ashp(t_loop_c, t_air_c):
    """Surplus ASHP cooling COP: lifts heat from the loop (cold side) to the air (hot side)."""
    tc = t_loop_c - SURPLUS_EVAP_APPROACH + 273.15
    th = t_air_c + SURPLUS_AIR_APPROACH + 273.15
    lift = np.maximum(th - tc, 1e-3)
    cop = COP_K_REF * np.sqrt(th / lift) - 1.0
    return np.clip(np.where(th - tc <= 0, SURPLUS_COP_CAP, cop), 0.5, SURPLUS_COP_CAP)


def simulate_home_year(demand, price, hp_kw, tank_l, charge_fraction):
    """
    One home, one year, hourly. The heat pump always heats the home through the tank.

    Ideal two-zone tank: stored energy E = volume × ρcp × (T_hot − T_cold).
    Each day, the cheapest `charge_fraction` of hours are charging hours, when the heat pump
    fills the tank at up to full power. In other hours it only runs to keep the tank above
    the reserve level (TANK_RESERVE). The year is simulated twice so the second pass starts
    from a realistic tank state.

    Returns heat pump output per hour [kW], unmet demand [kWh] and tank energy per hour [kWh].
    """
    e_max = tank_l * 4.186 * (T_HOT - T_COLD) / 3600.0               # full tank energy [kWh]
    n_charge = max(1, int(round(charge_fraction * 24)))               # charging hours per day
    daily = price.reshape(365, 24)
    charge = np.zeros((365, 24), bool)
    idx = np.argsort(daily, axis=1)[:, :n_charge]                     # cheapest hours of each day
    np.put_along_axis(charge, idx, True, axis=1)
    charge = charge.ravel()

    reserve = TANK_RESERVE * e_max
    ua = TANK_UA / 1000.0                                             # kW/K
    loss_hot, loss_cold = ua * (T_HOT - T_ROOM), ua * (T_COLD - T_ROOM)
    q_hp = np.zeros(HOURS)
    e_hist = np.zeros(HOURS)
    e = e_max                                                          # start full
    unmet = 0.0
    for sweep in range(2):
        unmet = 0.0
        for h in range(HOURS):
            x = e / e_max
            need = demand[h] + loss_hot * x + loss_cold * (1 - x)
            if charge[h]:
                q = min(hp_kw, need + (e_max - e))
            else:                                                      # top up to the reserve level only
                q = min(hp_kw, max(0.0, need + reserve - e))
            e = e + q - need
            if e < 0.0:
                unmet -= e
                e = 0.0
            elif e > e_max:
                e = e_max
            q_hp[h] = q
            e_hist[h] = e
    return q_hp, unmet, e_hist


def make_field(n_boreholes, depth):
    """Borehole layout for pygfunction: a near-square grid at BOREHOLE_SPACING, trimmed to n_boreholes."""
    rows = max(1, int(math.floor(math.sqrt(n_boreholes))))
    cols = math.ceil(n_boreholes / rows)
    field = gt.boreholes.rectangle_field(cols, rows, BOREHOLE_SPACING, BOREHOLE_SPACING,
                                         depth, BURIED_DEPTH, R_BOREHOLE)
    return field[:n_boreholes]


def gfunction_field(n_boreholes, depth, n_hours):
    """g-function of the borehole field (pygfunction), evaluated at 1, 2, ..., n_hours hours."""
    field = make_field(n_boreholes, depth)
    alpha = K_GROUND / CP_GROUND                                        # thermal diffusivity [m2/s]
    t_calc = np.geomspace(3600.0, (n_hours + 1) * 3600.0, G_POINTS)    # log-spaced times [s]
    g_calc = gt.gfunction.gFunction(field, alpha, time=t_calc, boundary_condition=G_BOUNDARY).gFunc
    t_hours = np.arange(1, n_hours + 1) * 3600.0
    return np.interp(np.log(t_hours), np.log(t_calc), g_calc)          # interpolate in log time


# Cache for the most recent design's kernel only: each 25-year kernel is a few MB and the
# optimiser tries thousands of designs, but the loop solver reuses the same kernel many times.
_KERNEL = {"key": None, "value": None}


def ground_kernel(n_hours, n_boreholes, depth):
    """
    Hourly step-response increments h_j = [G(j+1) − G(j)] / (2πk) and their FFT.
    Cached for the current design.
    """
    key = (n_hours, n_boreholes, depth)
    if _KERNEL["key"] != key:
        g = gfunction_field(n_boreholes, depth, n_hours)
        h = np.diff(np.concatenate([[0.0], g])) / (2 * np.pi * K_GROUND)   # K per (W/m) per hour of load
        nfft = 1 << int(np.ceil(np.log2(2 * n_hours)))
        _KERNEL["key"], _KERNEL["value"] = key, (h, np.fft.rfft(h, nfft), nfft)
    return _KERNEL["value"]


def ground_response(q_per_m, n_boreholes, depth):
    """Borehole wall temperature change from the full load history (temporal superposition via FFT)."""
    n = len(q_per_m)
    _, h_f, nfft = ground_kernel(n, n_boreholes, depth)
    return np.fft.irfft(np.fft.rfft(q_per_m, nfft) * h_f, nfft)[:n]


def loop_flows(t_loop, q_hp, t_air, q_cool, dc_kw, dc_set, n_homes):
    """
    Heat balance on the shared loop for given loop temperatures [kW].
    Returns the net heat into the ground (positive = into the ground) and the individual flows.
    """
    cop_h = cop_heating(t_loop)
    extract = n_homes * q_hp * (1.0 - 1.0 / cop_h)                      # homes take heat out
    cop_c = cop_cooling(t_loop + HX_APPROACH)
    reject = q_cool * (1.0 + 1.0 / cop_c)                               # store puts heat in
    ramp = np.clip((t_loop - dc_set) / SURPLUS_RAMP, 0.0, 1.0)          # smoothed switch-on rule
    q_sur = ramp * dc_kw                                                # surplus ASHP removes heat
    cop_sur = cop_surplus_ashp(t_loop, t_air)
    return reject - extract - q_sur, dict(cop_h=cop_h, cop_c=cop_c, extract=extract, reject=reject,
                                          q_sur=q_sur, w_sur=q_sur / cop_sur)


def simulate_loop(design, q_hp_year, data, q_cool, years=YEARS, max_iter=60, tol=0.02, quick_reject=False):
    """
    Hourly loop simulation over `years` years.

    T_loop(hour n) = T_ground + [response to all earlier hours' loads] + (h0 + Rb) × load(hour n)

    The earlier-hours part comes from one FFT convolution of the full history. The current-hour
    part is solved for every hour at once by bisection, because the loads depend on T_loop
    (through the COPs and the surplus ASHP). The two steps are repeated, with damping, until the
    temperature series stops changing.
    """
    nb, depth = design["n_boreholes"], design["depth_m"]
    dc_kw, dc_set = design["surplus_ashp_kw"], design["surplus_ashp_setpoint_c"]
    n_homes = design["n_homes"]
    length = nb * depth                                                 # total borehole length [m]
    n = years * HOURS
    q_hp = np.tile(q_hp_year, years)
    t_air = np.tile(data["t_air"], years)
    q_cool = np.tile(q_cool, years)
    h0 = ground_kernel(n, nb, depth)[0][0]
    c0 = h0 + RB                                                        # K per (W/m) felt in the same hour

    t_loop = np.full(n, T_GROUND)
    change = np.inf
    for it in range(max_iter):
        q_net, _ = loop_flows(t_loop, q_hp, t_air, q_cool, dc_kw, dc_set, n_homes)
        q_m = q_net * 1000.0 / length                                   # W per metre of borehole
        t_hist = T_GROUND + ground_response(q_m, nb, depth) - h0 * q_m  # effect of all earlier hours
        lo, hi = np.full(n, -40.0), np.full(n, 80.0)                    # solve T = t_hist + c0·q_m(T)
        for _ in range(16):                                             # 120 K / 2^16 ≈ 0.002 K
            mid = 0.5 * (lo + hi)
            qn, _ = loop_flows(mid, q_hp, t_air, q_cool, dc_kw, dc_set, n_homes)
            f = mid - t_hist - c0 * qn * 1000.0 / length
            hi = np.where(f > 0, mid, hi)
            lo = np.where(f > 0, lo, mid)
        t_new = 0.5 * (lo + hi)
        change = np.max(np.abs(t_new - t_loop))
        t_loop = t_loop + LOOP_RELAX * (t_new - t_loop)                 # damped update (stops oscillation)
        if change < tol:
            break
        if quick_reject and it >= 5 and (t_loop.min() < T_LOOP_MIN - 5 or t_loop.max() > T_LOOP_MAX + 5):
            break                                                       # clearly infeasible: stop early

    q_net, fl = loop_flows(t_loop, q_hp, t_air, q_cool, dc_kw, dc_set, n_homes)
    return dict(t_loop=t_loop, q_hp=q_hp, t_air=t_air, q_net=q_net, converged=change < tol,
                iterations=it + 1, **fl)


# =============================================================================
# 4. ECONOMICS
# =============================================================================

def annuity_factors():
    """Discount factors 1/(1+i)^y for y = 1..YEARS at DISCOUNT."""
    y = np.arange(1, YEARS + 1)
    return 1.0 / (1.0 + DISCOUNT) ** y


def discount_factors(rate):
    """Discount factors 1/(1+rate)^y for y = 1..YEARS (used at the supermarket's target IRR)."""
    y = np.arange(1, YEARS + 1)
    return 1.0 / (1.0 + rate) ** y


def crf(life, i=DISCOUNT):
    """Capital recovery factor CRF = i(1+i)^n / ((1+i)^n - 1)."""
    return i * (1 + i) ** life / ((1 + i) ** life - 1)


def capex_in_horizon(cost, life):
    """
    Part of an up-front cost that belongs to the YEARS-long analysis:
    cost × CRF(life) × Σ 1/(1+i)^y over YEARS.
    If life = YEARS this returns the full cost; if life > YEARS the remainder is residual value.
    """
    return cost * crf(life) * annuity_factors().sum()


def per_year(x):
    """Sum an hourly multi-year series into annual totals, extended to YEARS by repeating the last year."""
    totals = x.reshape(-1, HOURS).sum(axis=1)
    return np.concatenate([totals, np.repeat(totals[-1], YEARS - len(totals))])


def gas_lcoh(data):
    """Gas boiler LCOH = (CRF · CAPEX + OPEX per year) / heat delivered, with OPEX = maintenance + gas bill."""
    dem = data["demand"]
    fuel = (dem / BOILER_EFF * data["gas_unit"]).sum() / 100 + data["gas_standing_day"].sum() / 100   # £/yr gas bill
    capex_annual = crf(LIFE_BOILER) * BOILER_CAPEX                    # £/yr
    opex = BOILER_OM + fuel                                           # £/yr
    return (capex_annual + opex) / dem.sum() * 100                    # p/kWh


def evaluate(x, data, q_cool=None, detail=False, years=YEARS, n_homes=None, irr=None):
    """
    Objective for the optimiser: homeowner LCOH [p/kWh] plus penalties for broken constraints.
    With detail=True, returns a dictionary of all results for the given design instead.
    """
    design = {name: v for (name, _, _), v in zip(BOUNDS, x)}
    design["n_boreholes"] = int(round(design["n_boreholes"]))          # whole boreholes only
    if n_homes is None:
        raise ValueError("n_homes must be given")
    design["n_homes"] = int(n_homes)
    if irr is None:
        raise ValueError("irr must be given")
    design["irr"] = float(irr)
    penalty = 0.0
    if q_cool is None:
        q_cool = data["q_cool"]                                         # hourly cooling load [kW], one year
    q_peak = q_cool.max()                                               # equipment is sized on the peak hour
    if q_peak == 0:                                                     # no store heat, so no surplus ASHP
        design["surplus_ashp_kw"] = 0.0

    # --- homes ---
    q_hp_year, unmet, e_hist = simulate_home_year(data["demand"], data["price"], design["hp_kw"],
                                                  design["tank_l"], design["charge_fraction"])
    if unmet > 0.001 * data["demand"].sum():
        penalty += 100 + unmet / 10

    # --- loop and ground ---
    loop = simulate_loop(design, q_hp_year, data, q_cool, years=years, quick_reject=not detail)
    t_loop = loop["t_loop"]
    if t_loop.min() < T_LOOP_MIN:
        penalty += 100 + 10 * (T_LOOP_MIN - t_loop.min())
    if t_loop.max() > T_LOOP_MAX:
        penalty += 100 + 10 * (t_loop.max() - T_LOOP_MAX)
    if loop["q_sur"].max() <= 0:                                        # surplus ASHP never runs, so don't build it
        design["surplus_ashp_kw"] = 0.0

    # --- homeowner running cost (per home) ---
    price = np.tile(data["price"], years)
    w_hp = loop["q_hp"] / loop["cop_h"]                                 # kW electricity per home
    elec_cost_y = per_year(w_hp * price) / 100                          # £/yr per home
    heat_y = np.full(YEARS, data["demand"].sum())
    scop_y = per_year(loop["q_hp"]) / per_year(w_hp)
    if scop_y.min() < SCOP_MIN:
        penalty += 50 + 10 * (SCOP_MIN - scop_y.min())

    # --- supermarket capital (extra cost compared with its alternative system) ---
    nb, depth = design["n_boreholes"], design["depth_m"]
    q_rej_design = q_peak * (1 + 1 / cop_cooling(T_LOOP_MAX + HX_APPROACH))
    hx_area = q_rej_design * 1000 / (HX_U * HX_APPROACH) if q_peak > 0 else 0.0
    capex = {
        "setup": SETUP_COST,
        "drilling": DRILL_PER_M * nb * depth,
        "borehole_fixed": COST_PER_BOREHOLE * nb,
        "pipework": PIPE_PER_M * (FIELD_TO_STREET_M + n_homes * PIPE_PER_HOME_M + FIELD_PIPE_PER_BOREHOLE_M * nb),
        "heat_exchanger": 832 * hx_area ** 0.637 * CEPCI_2018 / CEPCI_2014 if hx_area > 0 else 0.0,
        "surplus_ashp": SURPLUS_ASHP_COST_PER_KW * design["surplus_ashp_kw"],
        "avoided_big_ashp": -ALT_ASHP_COST_PER_KW * q_rej_design if q_peak > 0 else 0.0,
    }
    store_capex_upfront = sum(capex.values())                           # actually spent in year 0
    # ground works last LIFE_GROUND years, so only the part used up within YEARS is charged
    ground_capex = sum(capex[k] for k in GROUND_ITEMS)
    ground_charged = capex_in_horizon(ground_capex, LIFE_GROUND)
    ground_residual = ground_capex - ground_charged
    store_capex = store_capex_upfront - ground_residual

    # --- supermarket annual savings: refrigeration via the loop vs the alternative, minus surplus ASHP power ---
    t_cond_alt = np.maximum(loop["t_air"] + ALT_ASHP_AIR_APPROACH, ALT_ASHP_MIN_COND)
    q_cool_n = np.tile(q_cool, years)
    e_air = q_cool_n / cop_cooling(t_cond_alt)
    e_loop = q_cool_n / loop["cop_c"] + loop["w_sur"]
    savings_y = per_year(e_air - e_loop) * data["store_price"] / 100   # £/yr

    # --- minimum annual fee per home giving the supermarket its target IRR over YEARS ---
    # IRR = the discount rate at which fees + savings over YEARS exactly repay the net capex.
    df = annuity_factors()                     # at DISCOUNT: homeowner LCOH and the reported payback
    df_irr = discount_factors(irr)             # at the target IRR: supermarket's fee
    pv_sav = (savings_y * df_irr).sum()
    fee = max(0.0, (store_capex - pv_sav) / (n_homes * df_irr.sum()))

    # --- BUS grant: lost for every home if the network exceeds the cap ---
    network_kw = n_homes * design["hp_kw"]
    grant = BUS_GRANT if network_kw <= BUS_CAP_KW else 0.0

    # --- homeowner LCOH (the objective) ---
    home_capex = HP_COST_FIXED + HP_COST_PER_KW * design["hp_kw"] + TANK_COST_FIXED + TANK_COST_PER_L * design["tank_l"]
    home_capex_net = max(0.0, home_capex - grant)
    home_capex_charged = capex_in_horizon(home_capex_net, LIFE_HP)
    pv_cost = home_capex_charged + ((elec_cost_y + fee) * df).sum()
    lcoh = pv_cost / (heat_y * df).sum() * 100                         # p/kWh

    if not detail:
        return lcoh + penalty

    # cumulative discounted cash flow for the supermarket (fees paid every year for the full horizon)
    cash = -store_capex + np.cumsum((n_homes * fee + savings_y) * df)
    payback = next((i + 1 for i, c in enumerate(cash) if c >= 0), None)
    return dict(design=design, lcoh=lcoh, penalty=penalty, fee=fee, grant=grant, network_kw=network_kw,
                capex=capex, store_capex=store_capex, store_capex_upfront=store_capex_upfront,
                ground_capex=ground_capex, ground_charged=ground_charged, ground_residual=ground_residual,
                home_capex=home_capex, home_capex_net=home_capex_net, elec_cost_y=elec_cost_y,
                savings_y=savings_y, scop_y=scop_y, unmet=unmet, loop=loop, e_hist=e_hist,
                q_hp_year=q_hp_year, payback=payback, cash=cash, q_cool=q_cool)


# =============================================================================
# 5. OPTIMISATION AND REPORTING
# =============================================================================

def optimise(data, q_cool, label, n_homes, irr):
    """
    Search the design space with differential evolution, then re-evaluate the best design in detail.
    workers=-1 scores several designs in parallel, one per processor core.
    """
    print(f"\n=== Optimising: {label} ===")
    t0 = time.time()

    def progress(xk, convergence):
        print(f"  generation done — {time.time() - t0:.0f} s")

    res = differential_evolution(evaluate, [(lo, hi) for _, lo, hi in BOUNDS],
                                 args=(data, q_cool, False, OPT_YEARS, n_homes, irr),
                                 popsize=DE_POPSIZE, maxiter=DE_MAXITER, seed=DE_SEED,
                                 polish=False, tol=1e-4, callback=progress,
                                 updating="deferred", workers=-1)
    return evaluate(res.x, data, q_cool, detail=True, n_homes=n_homes, irr=irr)


def report(r, data, label):
    """Print and return a text summary of one optimised design."""
    d, L = r["design"], r["loop"]
    gas = gas_lcoh(data)
    lines = [
        f"\n----- RESULT: {label} -----",
        f"Penalty (0 = all constraints met): {r['penalty']:.1f}",
        "Design:",
        f"  boreholes            {d['n_boreholes']:.1f} × {d['depth_m']:.0f} m  (= {d['n_boreholes'] * d['depth_m']:.0f} m total)",
        f"  homes                {d['n_homes']}",
        f"  target IRR           {d['irr'] * 100:.0f} % over {YEARS} yr",
        f"  heat pump per home   {d['hp_kw']:.2f} kW   (network total {r['network_kw']:.0f} kW, BUS cap {BUS_CAP_KW:.0f})",
        f"  tank per home        {d['tank_l']:.0f} L",
        f"  surplus ASHP         {d['surplus_ashp_kw']:.0f} kW, switches on above {d['surplus_ashp_setpoint_c']:.1f} °C",
        f"  charging hours       cheapest {d['charge_fraction'] * 24:.0f} h of each day",
        "Loop:",
        f"  T_loop range         {L['t_loop'].min():.1f} to {L['t_loop'].max():.1f} °C (limits {T_LOOP_MIN}–{T_LOOP_MAX})",
        f"  year-1 / year-25 mean {L['t_loop'][:HOURS].mean():.1f} / {L['t_loop'][-HOURS:].mean():.1f} °C",
        f"  homes' SCOP          {r['scop_y'].min():.2f}–{r['scop_y'].max():.2f}",
        f"  heat dumped by surplus ASHP {L['q_sur'][:HOURS].sum() / 1000:.0f} MWh/yr, using {L['w_sur'][:HOURS].sum() / 1000:.0f} MWh/yr electricity (year 1)",
        f"  store heat rejected  {L['reject'][:HOURS].sum() / 1000:.0f} MWh/yr; homes extract {L['extract'][:HOURS].sum() / 1000:.0f} MWh/yr",
        f"  loop iterations of final design      {L['iterations']} (converged: {L['converged']})",
        "Supermarket:",
        *[f"  {k:<20} £{v:,.0f}" for k, v in r["capex"].items()],
        f"  up-front extra capex £{r['store_capex_upfront']:,.0f}",
        f"  ground works         £{r['ground_capex']:,.0f} over {LIFE_GROUND:.0f} yr -> £{r['ground_charged']:,.0f} charged to {YEARS} yr",
        f"  ground residual value £{r['ground_residual']:,.0f} (years {YEARS + 1}–{LIFE_GROUND:.0f})",
        f"  NET extra capex      £{r['store_capex']:,.0f}  (recovered by fees + savings)",
        f"  refrigeration saving £{r['savings_y'][0]:,.0f}/yr (store price {data['store_price']:.2f} p/kWh)",
        f"  required fee         £{r['fee']:,.0f} per home per year  (discounted payback at {DISCOUNT * 100:.1f} %: {r['payback']} yr)",
        "Homeowner (per home):",
        f"  BUS grant            £{r['grant']:,.0f}"
        f"{'' if r['grant'] > 0 else '  — CAP EXCEEDED, grant lost'}",
        f"  heat pump + tank     £{r['home_capex']:,.0f}  (after grant: £{r['home_capex_net']:,.0f})",
        f"  electricity          £{r['elec_cost_y'][0]:,.0f}/yr (year 1)",
        f"  LCOH shared loop     {r['lcoh']:.2f} p/kWh",
        f"  LCOH gas boiler      {gas:.2f} p/kWh  (fuel + boiler capex + maintenance)",
        f"  => shared loop is {'CHEAPER' if r['lcoh'] < gas else 'MORE EXPENSIVE'} than gas by {abs(gas - r['lcoh']):.2f} p/kWh",
    ]
    text = "\n".join(lines)
    print(text)
    return text


def plots(r, data, tag):
    """Save the figures and hourly data for one optimised design."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    L = r["loop"]
    yrs = np.arange(len(L["t_loop"])) / HOURS

    # loop temperature over the full horizon
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(yrs, L["t_loop"], lw=0.3, color="tab:blue", label="T_loop (hourly)")
    daily = L["t_loop"].reshape(-1, 24).mean(1)
    ax.plot(np.arange(len(daily)) / 365, daily, lw=1, color="navy", label="daily mean")
    ax.axhline(T_LOOP_MAX, ls="--", color="red", lw=1)
    ax.axhline(T_LOOP_MIN, ls="--", color="red", lw=1)
    ax.set_xlabel("year"); ax.set_ylabel("loop temperature (°C)"); ax.legend(); ax.set_title(f"Loop temperature — {tag}")
    fig.tight_layout(); fig.savefig(os.path.join(OUTPUT_DIR, f"loop_temperature_{tag}.png"), dpi=150); plt.close(fig)

    # one January week: Agile price, demand and heat pump output, tank energy
    wk = slice(24 * 14, 24 * 21)
    fig, ax = plt.subplots(3, 1, figsize=(10, 7), sharex=True)
    hrs = np.arange(24 * 7)
    ax[0].step(hrs, data["price"][wk], where="post"); ax[0].set_ylabel("Agile p/kWh")
    ax[1].plot(hrs, data["demand"][wk], label="demand"); ax[1].plot(hrs, r["q_hp_year"][wk], label="heat pump")
    ax[1].set_ylabel("kW"); ax[1].legend()
    ax[2].plot(hrs, r["e_hist"][wk]); ax[2].set_ylabel("tank kWh"); ax[2].set_xlabel("hour of week")
    fig.suptitle(f"One home, January week — {tag}"); fig.tight_layout()
    fig.savefig(os.path.join(OUTPUT_DIR, f"january_week_{tag}.png"), dpi=150); plt.close(fig)

    # supermarket capital breakdown
    fig, ax = plt.subplots(figsize=(8, 4))
    items = {k: v for k, v in r["capex"].items()}
    ax.barh(list(items.keys()), [v / 1000 for v in items.values()], color="tab:green")
    ax.set_xlabel("£ thousand"); ax.set_title(f"Supermarket capital vs alternative — {tag}")
    fig.tight_layout(); fig.savefig(os.path.join(OUTPUT_DIR, f"store_capex_{tag}.png"), dpi=150); plt.close(fig)

    # hourly loop data
    pd.DataFrame({"t_loop_C": L["t_loop"], "q_surplus_ashp_kW": L["q_sur"], "store_reject_kW": L["reject"],
                  "homes_extract_kW": L["extract"], "cop_home": L["cop_h"]}).to_csv(
        os.path.join(OUTPUT_DIR, f"hourly_loop_{tag}.csv"), index_label="hour")


def main():
    """Load the data, optimise every case (target IRR × number of homes) and save all results."""
    print("Loading data ...")
    data = load_data()
    print(f"  demand {data['demand'].sum() / 1000:.2f} MWh/yr per home, Agile {AGILE_YEAR} mean "
          f"{data['price'].mean():.2f} p/kWh, store price {data['store_price']:.2f} p/kWh")
    print(f"  store cooling load mean {data['q_cool'].mean():.1f} kW, peak {data['q_cool'].max():.1f} kW")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    cases = [("with_supermarket", data["q_cool"])]
    if RUN_NO_SUPERMARKET_BASELINE:
        cases.append(("no_supermarket", np.zeros(HOURS)))

    texts, rows = [], []
    for case, qc in cases:
        for irr in IRR_TARGETS:
            for n in N_HOMES_LIST:
                tag = f"{case}_IRR{irr * 100:.0f}_N{n}"
                r = optimise(data, qc, tag, n, irr)
                texts.append(report(r, data, tag))
                plots(r, data, tag)
                d = r["design"]
                rows.append({
                    "case": case,
                    "target_irr_pct": round(irr * 100),
                    "achieved_payback_yr": r["payback"],
                    "n_homes": n,
                    "n_boreholes": d["n_boreholes"],
                    "borehole_depth_m": round(d["depth_m"], 1),
                    "total_borehole_length_m": round(d["n_boreholes"] * d["depth_m"]),
                    "hp_kw_per_home": round(d["hp_kw"], 2),
                    "tank_l_per_home": round(d["tank_l"]),
                    "surplus_ashp_kw": round(d["surplus_ashp_kw"], 1),
                    "surplus_ashp_setpoint_C": round(d["surplus_ashp_setpoint_c"], 1),
                    "charging_hours_per_day": round(d["charge_fraction"] * 24),
                    "lcoh_p_per_kWh": round(r["lcoh"], 2),
                    "fee_gbp_per_home_per_yr": round(r["fee"]),
                    "grant_gbp": r["grant"],
                    "network_kw": round(r["network_kw"], 1),
                    "store_upfront_capex_gbp": round(r["store_capex_upfront"]),
                    "ground_residual_gbp": round(r["ground_residual"]),
                    "store_net_capex_gbp": round(r["store_capex"]),
                    "penalty": round(r["penalty"], 1),
                    "t_loop_min_C": round(r["loop"]["t_loop"].min(), 1),
                    "t_loop_max_C": round(r["loop"]["t_loop"].max(), 1),
                })

    with open(os.path.join(OUTPUT_DIR, "summary.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(texts))
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUTPUT_DIR, "optimal_designs.csv"), index=False)

    # LCOH against number of homes for each target IRR, marking points where the BUS grant was lost
    fig, ax = plt.subplots(figsize=(10, 4))
    for (case, irr), g in df.groupby(["case", "target_irr_pct"]):
        ax.plot(g["n_homes"], g["lcoh_p_per_kWh"], "o-", label=f"{irr}% IRR")
    lost = df[df["grant_gbp"] == 0]
    if len(lost):
        ax.plot(lost["n_homes"], lost["lcoh_p_per_kWh"], "x", color="red", ms=12, mew=2, label="BUS grant lost")
    ax.axhspan(*ASHP_LCOH_P, color="grey", alpha=0.2, label="ASHP, IEA range (2025 £)")
    ax.axhline(gas_lcoh(data), ls="--", color="grey", label="gas boiler (incl. capex + O&M)")
    ax.set_xlabel("number of homes"); ax.set_ylabel("homeowner LCOH (p/kWh)")
    ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5))
    ax.set_xlim(left=0); ax.set_ylim(bottom=0)
    fig.tight_layout(); fig.savefig(os.path.join(OUTPUT_DIR, "lcoh_vs_n_homes.png"), dpi=150, bbox_inches="tight"); plt.close(fig)

    print(f"\nSaved figures and CSVs to '{OUTPUT_DIR}/'")


if __name__ == "__main__":
    main()
