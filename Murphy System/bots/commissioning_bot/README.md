# commissioning_bot — Enhanced with FPT forms, unit conversions, and smarter BAS point-list mapping

New in this version:
- **FPT checklist forms** generation (`internal/forms/fpt.ts`) → `meta.forms[]` attached to output
- **Unit conversions** (`internal/util/units.ts`) and `params.desired_units` normalization
- **BAS point-list mapping** (`internal/adapters/point_map.ts`) for common synonyms + configurable mapping

Register:
- run: `src/clockwork/bots/commissioning_bot/commissioning_bot.ts::run`
- ping: `src/clockwork/bots/commissioning_bot/rollcall.ts::ping`
