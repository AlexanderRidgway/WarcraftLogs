# Frontend UI Polish — Design

**Status:** Approved
**Date:** 2026-03-01

## Goal

Make the guild website look more professional with proper branding, WoW class icons, and rich gear item display with Wowhead integration.

## Changes

### 1. Favicon & Title
- Favicon: `inv_misc_drum_02.jpg` (war drum icon) copied to `web/frontend/public/`
- Page title: "CRANK" (replaces "frontend")
- Drum icon displayed next to "CRANK Guild Dashboard" in the Layout header

### 2. Class Icons
- Replace text-only ClassIcon component with actual WoW class icon images
- Source: Wowhead CDN (`https://wow.zamimg.com/images/wow/icons/medium/classicon_{class}.jpg`)
- Render icon image alongside the colored player name
- Used on: Dashboard leaderboard, Player detail page header

### 3. Gear Grid with Wowhead Tooltips
- Add Wowhead tooltip script (`https://wow.zamimg.com/widgets/power.js`) to index.html
- Render gear items as Wowhead item links (`<a href="https://www.wowhead.com/tbc/item=XXXXX">`)
- Wowhead automatically resolves item names, quality colors, and hover tooltips
- Format: "Slot — [Item Name] (ilvl X)" with enchant info below
- Enchants resolved via Wowhead spell links

## Files Changed

| File | Change |
|------|--------|
| `web/frontend/index.html` | Title, favicon link, Wowhead script |
| `web/frontend/public/favicon.jpg` | New (copied from downloads) |
| `web/frontend/src/components/ClassIcon.tsx` | Class icon images from Wowhead CDN |
| `web/frontend/src/components/GearGrid.tsx` | Wowhead item links, item name display |
| `web/frontend/src/components/Layout.tsx` | Drum icon in header |
