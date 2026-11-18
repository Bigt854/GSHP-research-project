# Model inputs and sources

Every setting in the shared loop model (`shared_loop_model_v12.py` SETTINGS, as updated 18 Nov 2026), with its current value, the source that backs Citation keys refer to `references.bib`. The same data, one row per setting, is in `model_inputs.csv`.

**Status:** **Verified** = source read and value matches.  **Modelling choice** = scenario or numerical setting, explained in the method.


| Status | Rows |
|---|---|
| Verified | 52 |
| Modelling choice | 13 |



## Data files

| Setting | Value in code | Status | Sources | Note |
|---|---|---|---|---|
| `FILE_DEMAND, BUILDING` | Building 3: 16.96 MWh/yr, 7.22 kW peak | Verified | pauldata, cambridgehousingmodel (v5 register: R1) | Totals recalculated. The origin, house type and hot water is included
| `FILE_WEATHER` | TMY 2007 to 2016 (mean 9.3 °C) | Verified | pauldata (v5 register: R2) | 
| `FILE_AGILE, AGILE_YEAR` | London Agile 2025, mean 18.5 p/kWh | Verified | agilebuddy (v5 register: R3), octopusagile | Mean recalculated. 
| `FILE_DESNZ, STORE_BAND, STORE_PRICE_FALLBACK` | 28.25 p/kWh (Small/Medium 2025, incl. CCL) | Verified | desnznondomprices (v5 register: R4) | Read from the sheet (published 29 Sep 2026) |
| `Store load workbook (not used in v12)` | 80 kW mean rejected, synthetic | Modelling choice | steuer2026 | 

## Homes and heat pumps

| Setting | Value in code | Status | Sources | Note |
|---|---|---|---|---|
| `N_HOMES_LIST` | (20,30,40,50, 60, 70, 80 ) | Modelling choice | steuer2026 (balance ~60 to 90 homes), ofgembus (300 kW ≈ 50 to 60 homes) |  |
| `COP_K` | 1.45 | Verified | vaillant2017 (v5 register: R6, 6 points p.4 and 5) | Fit reproduced (RMSE 0.39). Cite where the √Carnot form comes from (e.g. prataviera2026 uses Carnot × fixed efficiency) |
| `COP_CAP` | 6 | Verified | vaillant2017 (v5 register) | |
| `T_HOT` | 55 °C | Verified | idealpartl (v5 register: R7) | Blog. Approved Document L is the stronger citation |
| `T_COLD` | 47 °C | Verified | vaillant2017 (v5 register: 8 K spread for W55 ratings) |  |
| `T_ROOM` | 20 °C | Modelling choice | none | No source needed (group decision, 17 Nov 2026) |
| `TANK_UA` | 1.71 W/K | Verified | tempestcylinder (v5 register: R8) | Web datasheet, not rechecked |
| `BOUNDS tank | 100 to 210 L | Verified | beesizing (v5 register: R9) | Web guide |
| `TANK_RESERVE` | 0.3 | Modelling choice | none | No source needed (group decision, 17 Nov 2026). Control choice |
| `BUS_GRANT` | £7,500 | Verified | ofgembus (v5 register: R14) | Ofgem BUS guidance v4.1 |
| `SCOP_MIN` | 2.8 | Verified | ofgembusinstallers (v5 register: R14) | Installer guidance v4.2, para 3.75, checked 17 Nov 2026 |
| `HP_COST_FIXED, HP_COST_PER_KW` | £6,114 + £809/kW | Verified | uswitchhp, getplumbflexotherm, checkatradegshp (v5 register: R10 to R12); desnz2025note, escatapult2022, deltaee2018 | Code updated 18 Nov to the refit of the cited prices. 
| `TANK_COST_FIXED, TANK_COST_PER_L` | £425 + £1.16/L | Verified | beejoule (v5 register: R13): £425.43 + £1.1562/L | Code updated 18 Nov to the sourced fit (rounded) |

## Ground and boreholes

| Setting | Value in code | Status | Sources | Note |
|---|---|---|---|---|
| `T_GROUND` | 12 °C | Verified | busby2015 , sailer2015 Table 2 | London value to be read from Busby (2015) and quoted with its figure number. Sailer used 11.34 °C for London (Heathrow mean air temperature) |
| `K_GROUND` | 2.0 W/mK | Verified | loveridge2013 (TRT 1.95 to 2.07), busby2011 (1.94) |  |
| `CP_GROUND` | 2.2 MJ/m³K | Verified | lawley2025 (~1.9), loveridge2013 
| `R_BOREHOLE` | 0.065 m | Verified | sailer2015 Table 3 (v5 register: R16) | Borehole diameter 0.13 m, the MCS MIS 3005 assumption (section 2.2) |
| `RB` | 0.1 m·K/W | Verified | supervisorrb (v5 register: R16 "MCS") | Confirmed with the supervisor (17 Nov). 
| `BOREHOLE_SPACING` | 10 m | Verified | gtc2026 (v5 register: R15; Section Six p. 17, "a minimum of 10m", read directly 18 Nov); mcs022 (6 m min), sailer2015 | GTC is a UK shared-loop network operator's rule, which suits our case. 
| `BOUNDS depth | 50 to 200 m | Verified | gtc2026 (v5 register: typically 150 to 200 m), desnz2025annexb (150 m) | Upper bound only. The lower bound is a choice |
| `BURIED_DEPTH` | 2 m |Verified | gshpa2011 (§9.2 ≥1 m), guo2021, eskilson1987 | Check the GSHPA wording, which we read via a summary |
| `G_BOUNDARY, G_POINTS` | UBWT, 50 | Modelling choice | cimmino2018b, cimmino2022 (v5 register: R26) |  |
| `T_LOOP_MIN` | 0 °C | Verified | gshpa2011 (§4.4, quoting MIS 3005), curtis2017 |  |
| `T_LOOP_MAX` | 25 °C | Verified | vaillant2017 (v5 register: brine limit p.4), dimplexsi90tu, qvantumrs2, nistco2 |  |
| `YEARS, LOOP_RELAX` | 25, 0.5 | Modelling choice | - |  |

## Supermarket

| Setting | Value in code | Status | Sources | Note |
|---|---|---|---|---|
| `Q_COOL` | 80 kW (cooling) | Verified | enex (v5 register: R17), efstratiadi2019 (v5 register: p.19); steuer2026, prataviera2026, giunta2021 |
| `T_EVAP` | −8 °C | Verified | giunta2021 (Table A1 row 13), karampour2019 |  |
| `COP_K_REF` | 1.0 (COP ≈ 2.5 at 15 °C) | Verified | efstratiadi2019 (v5 register: Table 2 p.19, 2.40 to 2.65) | One-point calibration |
| `HX_APPROACH` | 3 K |  Verified | efstratiadi2019 (v5 register: p.12), karampour2019 (3 K subcooler), giunta2021 (2 K) | |
| `HX_U` | 3000 W/m²K | Verified | engtoolbox (1000 to 4000) 
| `ALT_ASHP_AIR_APPROACH` | 10 K | Verified | russell1996 (v5 register: R19, ≈11 K); giunta2021, karampour2019 (7 K) | The sources disagree; see point 5 above |
| `ALT_ASHP_MIN_COND` | 10.9 °C | Verified | efstratiadi2019 (v5 register: p.12, 45 bar); giunta2021 (10 °C) |
| `STORE_PRICE_FALLBACK` | 28.25 p/kWh | Verified | desnznondomprices (v5 register: R4) |  |

## Surplus ASHP

| Setting | Value in code | Status | Sources | Note |
|---|---|---|---|---|
| `SURPLUS_EVAP_APPROACH` | 3 K | Verified | By analogy with the HX approach (v5 register: R18 p.12) 
| `SURPLUS_AIR_APPROACH` | 10 K | Verified | By analogy with russell1996 (v5 register) | 7 K in giunta2021/karampour2019 |
| `SURPLUS_RAMP` | 1 K | Verified | danfossekc102 (v5 register: R20 p.7, 0.1 to 20 K) |  |
| `SURPLUS_ASHP_COST_PER_KW` | £600/kW | Verified | beis2022nondom p. 16 (median £600/kW); cross-checks rhi2012, sweett2013 |  

## Gas comparator

| Setting | Value in code | Status | Sources | Note |
|---|---|---|---|---|
| `GAS_UNIT_Q, GAS_STANDING_Q` | 6.34/6.99/6.33/6.29 p/kWh; 31.65/32.67/29.82/34.03 p/day | Verified | ofgemcapq42025 (v5 register: R21) | Q4 checked on Ofgem's page (17 Nov). 
| `BOILER_EFF` | 0.875 | Verifed | lawal2017 (v5 register: R22, 82 to 91%, new ~90%) | Midpoint of 85 to 90%. 
| `BOILER_CAPEX` | £4,200 | Verified | deltaee2018 (£2,700 ex VAT 2018) + VAT + ~30% inflation |
| `BOILER_OM` | £100/yr | Verified | homeboiler (v5 register: R23) | 
| `LIFE_BOILER` | 15 yr | Verified | beis2022boiler, desnz2024boiler, homeboiler (v5 register) |  |
| `ASHP_LCOH_P, GSHP_LCOH_P` | 9.6 to 14.6; 6.5 to 11.1 p/kWh | Verified | sapingses (v5 register), onscpi2019 (v5 register: R25) | 

## Economics and costs

| Setting | Value in code | Status | Sources | Note |
|---|---|---|---|---|
| `DISCOUNT` | 3.5% | Verified | beis2021ghnf, beis2020ghnfia (3.5%), greenbookdiscounting (3.0%) | 
| `IRR_TARGETS` | 12% (6, 9, 12% in v12) | Verified | cmapr24, ofgemriio3, decc2015invest, carbontrust2018, ofgemfairpricing2026 |  |
| `SETUP_COST` | £35,000 | Verified | desnz2025annexb (Arup 2021: £20 to 50k) | Arup 2021 via DESNZ 2025 Annex B (gov.uk link in the bib) |
| `DRILL_PER_M` | £93/m | Verified | desnz2025annexb (£100/m), liu2018ornl |  |
| `COST_PER_BOREHOLE` | £1,000 | Verified | liu2018ornl | Inferred from a US cost ratio |
| `PIPE_PER_M` | £198.86/m | Verified | severntrent2026 (v5 register: R24 p.41) | Value kept. It is the rate for one 180 mm main in a road, so describe it as close to a blended flow+return rate (~£200/m
| `PIPE_PER_HOME_M` | 10 m | Modelling choice | group decision | Range 5 to 20 m in borehole-cost-data.md |
| `FIELD_TO_STREET_M` | 50 m | Modelling choice | none | No source needed (group decision, 17 Nov 2026). 
| `FIELD_PIPE_PER_BOREHOLE_M` | = spacing (10 m) | Modelling choice | 
| `ALT_ASHP_COST_PER_KW` | £600/kW | Verified | beis2022nondom p. 16 (median £600/kW); cross-checks rhi2012, sweett2013 |
| `Jaric HX cost 832·A^0.637, CEPCI_2018/CEPCI_2014` | 603.1 / 576.1 | Verified | safeground2023 (Paul's code) | Both registers lack the original Jaric paper |
| `LIFE_HP` | 25 yr | Modelling choice | none | No source needed (group decision, 17 Nov 2026). Paul's code used 20 yr |
| `LIFE_GROUND` | 60 yr | Verified | desnz2025note (Annex B), safeground2023 |  |

## Optimiser and run settings (modelling choices)

| Setting | Value in code | Status | Sources | Note |
|---|---|---|---|---|
| `DE_MAXITER` | 12 | Modelling choice | - |  |
| `DE_POPSIZE, DE_SEED` | 8, 1 | Modelling choice | - |  |



