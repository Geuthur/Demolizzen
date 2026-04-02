# Changelog

## [In Development] - Unreleased

<!--
Section Order:

### Added
### Fixed
### Changed
### Removed
-->

## Added

-
- Open API Log
- On Member Update Listener
- Guild Join Event for Bank Cog [da1006a](https://github.com/Geuthur/Demolizzen/commit/da1006a3875be34bce98866184de7db1209afea5)
- Guild Join Event for Bank Cog [c020a25](https://github.com/Geuthur/Demolizzen/commit/c020a25e6edb9686c46803ff482b0f836efc0ada)
- Implement UniverseName dataclass for ESI data representation [dcd6248](https://github.com/Geuthur/Demolizzen/commit/dcd62480115b6787487d5e38069ff414db70697d)

## Fixed

- Update add_sub method to ensure only 1 km tracker per `group_id` [PR](https://github.com/Geuthur/Demolizzen/commit/027723e34b576f81c2c0b969c38c95b25590d1fe)
- Multiple Objects Returned [t7fa7fe8t](https://github.com/Geuthur/Demolizzen/commit/7fa7fe879105d2f34b4e3aa1f95b3906fd39fca9)
- Enhance response handling in TicketSystem and Demolizzen bot for improved user interaction and error management [002b77d](https://github.com/Geuthur/Demolizzen/commit/002b77d9d3f674f51311d706e7e0222fa6ec0dad)
- Refine subscription handling and type hinting for better clarity and maintenance [2778692](https://github.com/Geuthur/Demolizzen/commit/277869204bd8f3ce8dd45957bacfaead4526a32c)
- Enhance response handling in TicketSystem and Demolizzen bot for improved user interaction and error management [002b77d](https://github.com/Geuthur/Demolizzen/commit/002b77d9d3f674f51311d706e7e0222fa6ec0dad)

## Changed

- Update ticket handling to skip missing ticket owners and ensure proper view assignment [PR](https://github.com/Geuthur/Demolizzen/commit/8a37063068848fd695b9303e1844a3bf0563c827)
- Refactor Killmail handling
- Refactor ESI System
- Moving to R2Z2 Endpoint, as RedisQ will be discontinued on May 31, 2026 [R2Z2](<https://github.com/zKillboard/zKillboard/wiki/API-(R2Z2)>).
- update classifiers to include Python 3.14 [9c0efb9](https://github.com/Geuthur/Demolizzen/commit/9c0efb9f1c38701015b8baa7a5d3b09db317d5dd)
- pre-commit configuration: enhance hooks, update versions, and adjust exclusions [](https://github.com/Geuthur/Demolizzen/commit/7c623e3bcdad0dca970dc190bb5d24301cd98c85)

## Removed

- Removed Cache Logic in Killmail Cog
- Removed [FireTail](https://github.com/scragly/Firetail) Code Base @ Credits for inspiration
- [Unused Package](https://github.com/Geuthur/Demolizzen/commit/498e3292cbb85144d7b5a30a3b0762b5e5cc13b8)

## [2.0.2] - 2025-12-02

### Added

- Makefile ([6fb9b66](https://github.com/Geuthur/Demolizzen/commit/6fb9b66))
- Guild Bank Settings ([32b7f32](https://github.com/Geuthur/Demolizzen/commit/32b7f32))
- Application Command Mention Function ([95c131a](https://github.com/Geuthur/Demolizzen/commit/95c131a))
- Guild Name Change Checker on Bot load ([3bd8c1e](https://github.com/Geuthur/Demolizzen/commit/3bd8c1e))
- `close_old_connections` to each loop & Command ([65b8e6a](https://github.com/Geuthur/Demolizzen/commit/65b8e6a))
- Create Persistant Ticket Button for Voices of War ([d3a7a6b](https://github.com/Geuthur/Demolizzen/commit/d3a7a6b))
- CheckFailure for non existing BankAccounts ([32be212](https://github.com/Geuthur/Demolizzen/commit/32be212))
- `create_settings` for Guild ([a0fa41c](https://github.com/Geuthur/Demolizzen/commit/a0fa41c))

### Changed

- Killmails are now fetched from ESI instead of zKB. ([42c8deb](https://github.com/Geuthur/Demolizzen/commit/42c8deb))
- Optimize Ticket System ([85ad479](https://github.com/Geuthur/Demolizzen/commit/85ad479))
- Ticket Loader loads only once ([b718375](https://github.com/Geuthur/Demolizzen/commit/b718375))
- Update Bank System ([c7fa936](https://github.com/Geuthur/Demolizzen/commit/c7fa936))
- Added `set-interest-rate` & moved Bank Commands ([8ea50fa](https://github.com/Geuthur/Demolizzen/commit/8ea50fa))
- Update Admin Cog ([f21c97e](https://github.com/Geuthur/Demolizzen/commit/f21c97e))
- Only show help for available Commands ([eec1123](https://github.com/Geuthur/Demolizzen/commit/eec1123))
- Update Checks ([f53443f](https://github.com/Geuthur/Demolizzen/commit/f53443f))
- moved Guild Commands to `Guild` Cog ([8127237](https://github.com/Geuthur/Demolizzen/commit/8127237))
- make `killmail` Commands only available for Guild Manager or above ([be2fceb](https://github.com/Geuthur/Demolizzen/commit/be2fceb))
- Update LevelSystem Cog ([6fa57df](https://github.com/Geuthur/Demolizzen/commit/6fa57df))
- Update Ticket System ([5e9c817](https://github.com/Geuthur/Demolizzen/commit/5e9c817))
- Add Commands Permission ([e3a1ec5](https://github.com/Geuthur/Demolizzen/commit/e3a1ec5))
- Update Mission Cog ([ea8dd04](https://github.com/Geuthur/Demolizzen/commit/ea8dd04))
- Notify Owner if no Permission for Level UP Notification ([fc76667](https://github.com/Geuthur/Demolizzen/commit/fc76667))
- Added for each Command hint the mention for the Command ([6f57b8b](https://github.com/Geuthur/Demolizzen/commit/6f57b8b))
- moved `on_guild_join`, `on_guild_remove` listener to Guild Cog ([c0231f3](https://github.com/Geuthur/Demolizzen/commit/c0231f3))
- Level System Cog ([048ae1d](https://github.com/Geuthur/Demolizzen/commit/048ae1d))
- Update Bot Message ([4d7203b](https://github.com/Geuthur/Demolizzen/commit/4d7203b))
- move Guild, Member Worker to `Guild` Cog ([095e5e0](https://github.com/Geuthur/Demolizzen/commit/095e5e0))
- Commands & Logic ([42cac8d](https://github.com/Geuthur/Demolizzen/commit/42cac8d))
- Refactor Ticket Process ([f09ebb1](https://github.com/Geuthur/Demolizzen/commit/f09ebb1))

### Fixed

- Use old insurance instead of new one ([5fca949](https://github.com/Geuthur/Demolizzen/commit/5fca949))
- Create Counter wrong position ([2ef28f0](https://github.com/Geuthur/Demolizzen/commit/2ef28f0))
- AttributeError: 'UserRaidMission' object has no attribute 'get_dock_story' ([df3bd8e](https://github.com/Geuthur/Demolizzen/commit/df3bd8e))
- Missing ValueError Catch ([ee4a4f8](https://github.com/Geuthur/Demolizzen/commit/ee4a4f8))
- use `id` since it is channel_id ([661eaff](https://github.com/Geuthur/Demolizzen/commit/661eaff))
- async to sync Error ([49dbf1d](https://github.com/Geuthur/Demolizzen/commit/49dbf1d))
- Ensure Commands can only used in right Context ([2d4dc42](https://github.com/Geuthur/Demolizzen/commit/2d4dc42))
- DNS Error ([4c4943a](https://github.com/Geuthur/Demolizzen/commit/4c4943a))
- Out of range value for column 'threshold' ([97c1390](https://github.com/Geuthur/Demolizzen/commit/97c1390))
- Race Conditions ([53e3758](https://github.com/Geuthur/Demolizzen/commit/53e3758))
- Column 'user_name' cannot be null ([ae0fa5e](https://github.com/Geuthur/Demolizzen/commit/ae0fa5e))
- Pre-Commit ([3072709](https://github.com/Geuthur/Demolizzen/commit/3072709))
- IntegrityError ([87c22d0](https://github.com/Geuthur/Demolizzen/commit/87c22d0))
- discord.errors.Forbidden: 403 Forbidden (error code: 50007): Cannot send messages to this user ([58aa6de](https://github.com/Geuthur/Demolizzen/commit/58aa6de))

### Removed

- Queue Channel Function ([f898fda](https://github.com/Geuthur/Demolizzen/commit/f898fda))
- Watcher Cog ([162e9be](https://github.com/Geuthur/Demolizzen/commit/162e9be))
- Unnecessary Functions ([e267da5](https://github.com/Geuthur/Demolizzen/commit/e267da5))
- `is_in_channel` Check deprecated, use Discord Implementation ([941ce95](https://github.com/Geuthur/Demolizzen/commit/941ce95))

### Other

- Merge commits and dependency bumps, notable items:
  - Merge pull requests for various fixes and improvements (e.g. [6de7040](https://github.com/Geuthur/Demolizzen/commit/6de7040), [23575ab](https://github.com/Geuthur/Demolizzen/commit/23575ab), [f67754c](https://github.com/Geuthur/Demolizzen/commit/f67754c), ...)
  - Dependency bumps (django, py-cord, etc.) and test/workflow updates.

## [2.0.1] - 2025-09-13

### Added

- Ticket System Cog
- Guild Settings, Guild Ticket, Guild Ticket Settings Model
- [Django Migration Command (Bot Owner)](https://github.com/Geuthur/Demolizzen/commit/93f829a2c468e37f6db0c3ea0be389f6e930c335)
- [ADD] Private Policy ([d4dd877](https://github.com/Geuthur/Demolizzen/commit/d4dd877))

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
- Fixing Stuff ([cf34ed1](https://github.com/Geuthur/Demolizzen/commit/cf34ed1))

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

[2.0.0]: https://github.com/Geuthur/Demolizzen/compare/v1.0.1...v2.0.0 "2.0.0"
[2.0.1]: https://github.com/Geuthur/Demolizzen/compare/v2.0.0...v2.0.1 "2.0.1"
[2.0.2]: https://github.com/Geuthur/Demolizzen/compare/v2.0.1...v2.0.2 "2.0.2"
[in development]: https://github.com/Geuthur/Demolizzen/compare/v2.0.2...HEAD "In Development"
