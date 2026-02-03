
# engineering_bot (MAX) — Ultra-extensible, Bot-standards compliant

**Domains** covered (extensible): structural, electrical, aero/rocket, fluids, thermo, chemical, mechanical, 3D printing, manufacturing.
**Data packs** for materials/fluids; **standards registry** for rules with edition/section refs; **unit engine** with base-dimension conversions.

**Register**
- run: `src/clockwork/bots/engineering_bot/engineering_bot.ts::run`
- ping: `src/clockwork/bots/engineering_bot/rollcall.ts::ping`

**Extend**
- Add rules to `internal/registry/standards.ts` (packs)
- Add data packs under `internal/data/packs/*`
- Add domain calculators in `internal/domains/*`
- Expand `internal/util/units_engine.ts` with more units and dimensions
