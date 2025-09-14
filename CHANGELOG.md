# Changelog

## [2.0.1] - 2025-09-13

### Added

- Ticket System Cog
- Guild Settings, Guild Ticket, Guild Ticket Settings Model
- [Django Migration Command (Bot Owner)](https://github.com/Geuthur/Demolizzen/commit/93f829a2c468e37f6db0c3ea0be389f6e930c335)

### Changed

- [moved `Core` commands from `core` to `cogs`](https://github.com/Geuthur/Demolizzen/commit/dd57e592b73ea8677dbb2a32d0859ae027a65e72)
- [Restructured Commands Cog](https://github.com/Geuthur/Demolizzen/commit/bd7e5b6b1320c31d3b797fda42833ced19729f44)
- [Give more information on Permission Check](https://github.com/Geuthur/Demolizzen/commit/047acd47b61a80aa3d1c0a962b9d35f8bab7b686)
- [Reduced Bank interests from `1%` to `0.1%`](https://github.com/Geuthur/Demolizzen/commit/10e2602ba6f99264914b2811e22250ebe88c25e9)
- [Use Timezone instead of time](https://github.com/Geuthur/Demolizzen/commit/f8df7fa6cbc726cb57403c2f3b5ae68c620bf319)
- [Economy, BankSystem Commands require now at least admin permission](https://github.com/Geuthur/Demolizzen/commit/a7a9cabf2f0c1af33647faa0048bf600a4f4ea0b)
- [moved Owner commands to Owner Cog & restricted to bot_dm only](https://github.com/Geuthur/Demolizzen/commit/001d76281b0f4c3e0ae66e3ae8c7a69054e1f22f)
- [ignore CheckFailure error (use own check failure)](https://github.com/Geuthur/Demolizzen/commit/1a4039fe8449ea96ffa025a4435cac01727e95a9)

### Fixed

- [Django models don't have a __table__.columns attribute like SQLAlchemy.](https://github.com/Geuthur/Demolizzen/commit/b78dbddd714f4a90af734cbe3134e899ffbc9f5a)
- [Use correct async call `.aget` instead of `.get`](https://github.com/Geuthur/Demolizzen/commit/fe0d555129bb8c5b7d605864cc5a4ee6272526b0)
- [get() returned more than one ZKillboard -- it returned 2!](https://github.com/Geuthur/Demolizzen/commit/183b364dcb0e74fd03fdd669d16f7de09e84427c)
- [Register Command work on DM's](https://github.com/Geuthur/Demolizzen/commit/e1d5f12e10fd9c08c207eec47803723884bf5967)

### Removed

- [`is_bot_manager` check](https://github.com/Geuthur/Demolizzen/commit/0dadc524fd174a563e63272d1ac52bb3dba4c28c)
- [Cog Listener in Bank System](https://github.com/Geuthur/Demolizzen/commit/620ae18774d41b3a98ad25a656536a85a1925140)

## [2.0.0] - 2025-09-10

> [IMPORTANT]
> This version changes the entire bot system including database structure, commands, etc.

### Added

- Django Framework

### Changed

- Migrated database system to Django for improved reliability and maintainability.
- Logger system optimized for better performance and clarity.
- Enhanced UserAgent with additional information.
- Major refactoring across multiple cogs and systems:
  - Economy Cog
  - Killmail Cog (improved character, corporation, alliance info fetching)
  - BankSystem Cog
  - Database System
  - Shop Cog
  - Levelsystem Cog
  - Token Cog
  - Vow Cog
  - Games Cog
  - Eve Online Cog
- Improved code readability and context throughout the project.
- [replaced deprecated code for `clear` command](https://github.com/Geuthur/Demolizzen/commit/46862d25155c68d75eee764c584766b02863ff83)
- [Cooldown values now use datetime objects instead of strings.](https://github.com/Geuthur/Demolizzen/commit/79df5b60d4977262bbcad56ba6a2ae0200e80158)
- SQL model system optimized and database structure refactored.
- [Bag System](https://github.com/Geuthur/Demolizzen/commit/dd476b5d42afac853e25cab85d040a0927051b13)
- [Updated Pre-Commit](https://github.com/Geuthur/Demolizzen/commit/71436410bdbbc98ced1c07667d9d79f7dc6dfead)
- [Deprecated decorator `cached_property`](https://github.com/Geuthur/Demolizzen/commit/e6ddf63de15b743888851a1cfc086a8c8987df68)

### Removed

- [Pricelist command](https://github.com/Geuthur/Demolizzen/commit/7bc2efc1b8786548d4178123048e6e95501ee0c9)
- chatGPT Cog
- [Cache Manager](https://github.com/Geuthur/Demolizzen/commit/73b850b6ded7ce9f71e00d108b3bf6562632510e)
- [WebSocket support for zKB](https://github.com/Geuthur/Demolizzen/commit/8190116df6aa4cb8620f2de27f5430ed3eaf9ee9)
- Replaced `easy_pil` with `Pillow`
- SQLAlchemy

### Fixed

- [cog load](https://github.com/Geuthur/Demolizzen/commit/5ab261023ff106e488269a942b9bf24b4fde1062)
- [Uptime property not working](https://github.com/Geuthur/Demolizzen/commit/292a460552bdf7d5e869b4510b9fef7398e42290)

## [1.0.1.1] - 2024-09-5

### Fixed

- Duplicate Code on Shop, Economy Shop List
- Many Lazy Code

### Changed

- Price List Command now use Modal for Fetch Data

## [1.0.1] - 2024-08-22

### Added

- PriceHandler

### Fixed

- Special Name Casing on SQL Querys

### Changed

- Moved Price List to PriceHandler Class
- Price List now supports (Rifter x1 Format)
