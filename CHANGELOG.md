# Changelog

## [0.1.0] - 2025-05-03
### Added
- Initial release of winregenv.

## [0.2.0] - 2025-05-18
### Added
- `winapi.broadcast_setting_change()` helper to broadcast `WM_SETTINGCHANGE` messages after registry edits  
- `MessageTimeoutError` (subclass of `RegistryError`) for timeout failures in the broadcast API  
- Unit tests covering the new `broadcast_setting_change` functionality  
- Documentation in `README.md` describing how to use the broadcast helper  
