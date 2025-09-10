# Changelog

# IN DEVELOPMENT

[2.0.0] - 2025-xx-xx

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

[1.0.1.1] - 2024-09-5

### Fixed

- Duplicate Code on Shop, Economy Shop List
- Many Lazy Code

### Changed

- Price List Command now use Modal for Fetch Data

[1.0.1] - 2024-08-22

### Added

- PriceHandler

### Fixed

- Special Name Casing on SQL Querys

### Changed

- Moved Price List to PriceHandler Class
- Price List now supports (Rifter x1 Format)
