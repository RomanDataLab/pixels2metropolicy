# Pixels2MetroPolicy — Thailand slum / informal-settlement maps

Interactive maps of officially registered low-income communities (NHA)
against Thai comprehensive-plan (ผังเมืองรวม) land-use zones.

- `/` — slum map: 1,588 NHA communities on OpenStreetMap with modeled
  population estimates and plan-zone overlay
- `/app/` — full GeoHackathon 2026 app: admin boundaries, environment,
  infrastructure, live GISTDA/LDD services, plus the NHA communities layer
  colored by plan-zone category

Data sources: NHA gdcatalog (23_01), DPT comprehensive plan zones,
NGIS/DOPA vector layers. Household/resident figures are **modeled**
(log-normal calibrated to official NHA/CODI aggregates), not measured.
