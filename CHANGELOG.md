# Changelog

All notable changes to this project are documented in this file.

The format is based on Keep a Changelog, and this project follows Semantic Versioning.

## [Unreleased]

## [0.2.0] - 2026-11-09

### Added

- Collect multiline answers through the `edital` MCP tool in independent terminal windows, with preloaded drafts, exact accepted text, and explicit cancellation.
- Clean up editor sessions when clients cancel or disconnect, without logging document contents.
- Create, edit, or repair terminal configuration with `edital-mcp conf`, using Confease's embedded editor.
- Select bundled Alacritty, Kitty, GNOME Terminal, or Konsole examples using `--term`, then `$TERM`, when creating or resetting configuration.
- Restore the configuration template with `--reset`, backing up existing settings first.

### Fixed

- Reject missing or invalid configuration at server startup instead of waiting for a tool call, and provide setup guidance for missing files.
