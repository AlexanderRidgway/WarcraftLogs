# Authentication & UI Overhaul Design

**Date:** 2026-03-01
**Goal:** Add officer authentication to protect config/sync endpoints, and completely overhaul the frontend UI with Tailwind CSS for a professional dark gaming aesthetic.

---

## Part 1: Authentication System

### Architecture

JWT-based auth with bcrypt password hashing, stored in PostgreSQL.

- **New `User` model**: `id`, `username`, `password_hash`, `role` ("officer"), `created_at`
- **Dependencies**: `pyjwt`, `passlib[bcrypt]`
- **JWT secret**: `JWT_SECRET` env var, 24-hour token expiry

### Backend Auth Routes (`/api/auth`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/auth/login` | Public | Accepts `{username, password}`, returns `{access_token, token_type}` |
| GET | `/api/auth/me` | Officer | Returns current user info |

### Protected Route Guard

FastAPI dependency `get_current_officer()`:
- Extracts JWT from `Authorization: Bearer <token>` header
- Returns 401 if missing/invalid/expired
- Applied to all write endpoints:
  - `PUT /api/config/specs/{spec_key}/contributions/{metric}`
  - `PUT /api/config/specs/{spec_key}/weights`
  - `PUT /api/config/attendance/{zone_id}`
  - `POST /api/sync/trigger`

All GET routes remain public (leaderboard, players, raids, attendance, config read-only).

### Seeding Officers

CLI command: `python -m web.api.create_user <username> <password>`

### Frontend Auth

- **AuthContext**: Stores JWT in memory, provides `login()`, `logout()`, `isAuthenticated`, `user`
- **API client**: Adds `Authorization: Bearer` header on protected requests
- **Login page** at `/login`: Clean form, redirects back after login
- **UI behavior**: Config page read-only for public, editable for officers. Sync buttons hidden when not logged in.

---

## Part 2: UI Overhaul

### Tech Stack Change

- **Add**: Tailwind CSS 4 (via Vite plugin)
- **Remove**: All inline `style={{}}` props across every component
- **Keep**: React 19, React Router, TanStack Query, Vite, TypeScript

### Color Palette (Dark Gaming Theme)

| Token | Value | Usage |
|-------|-------|-------|
| bg-base | `#0a0e14` | Page background |
| bg-surface | `#12161f` | Cards, panels |
| bg-elevated | `#1a1f2e` | Hover states, modals |
| border-default | `#2a2f3e` | Borders |
| border-hover | `#3a3f4e` | Hover borders |
| accent-gold | `#c9a959` | Active states, highlights |
| text-primary | `#e8e6e3` | Primary text |
| text-secondary | `#8a8f98` | Secondary text |
| text-muted | `#5a5f68` | Muted/disabled text |
| success | `#2ea043` | Success states |
| danger | `#da3633` | Error/danger states |

WoW class colors and parse tier colors remain unchanged.

### Layout: Collapsible Sidebar

- **Desktop (>1024px)**: Expanded sidebar (240px) + content area
- **Tablet (768-1024px)**: Collapsed to icon-only (64px)
- **Mobile (<768px)**: Hidden, hamburger toggle in top-left

**Sidebar contents:**
- Top: CRANK drum logo + guild name
- Nav items with icons: Leaderboard (trophy), Raids (swords), Attendance (calendar), Config (gear)
- Bottom: Login/Logout + officer indicator
- Sync status + controls in footer (officer-only)

### Component Designs

#### Leaderboard (Home)
- Full-width search bar with magnifying glass icon, glass-effect background
- Class icon filter row: clickable class icons, gold border when selected
- Segmented control for week range (2w / 4w / 8w)
- Polished table: alternating rows, hover glow with gold left-border, sortable columns
- Medal icons for rank 1-3 (gold/silver/bronze)
- Click row to navigate to player profile

#### Player Profile
- Hero header: large class icon, name in class color, score cards with radial progress
- Styled tab bar with gold underline indicator
- Performance: polished table with gradient parse bars
- Gear: cards with quality border glow, hover-expand for details, gem colored dots
- Attendance: visual weekly calendar grid

#### Raid History
- 3-column card grid
- Cards: zone name, date, player count badge
- Hover: lift effect (translateY), shadow increase, gold border glow
- Click: navigate to raid detail

#### Raid Detail
- Zone header with date and player count
- Scores table with ClassIcon links
- Collapsible consumables section with progress bars

#### Config
- Public: read-only config cards
- Officer: pencil icons on editable fields, inline editor or modal
- Spec accordion: expand to see contributions
- Weight editor: visual slider showing 3-way split
- Toast notifications for save feedback

### Global UI Patterns
- Skeleton loading (animated placeholders instead of "Loading..." text)
- Toast notifications (bottom-right, auto-dismiss 3s)
- CSS tooltips for icon-only elements
- 200ms ease transitions on all interactive elements
- Responsive tables become card layouts on mobile
