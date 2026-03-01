# Authentication & UI Overhaul Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add JWT-based officer authentication to protect config/sync endpoints, and completely overhaul the frontend with Tailwind CSS for a professional dark gaming dashboard aesthetic.

**Architecture:** Backend adds a User model with bcrypt-hashed passwords, JWT auth middleware, and protected route guards on all write endpoints. Frontend migrates from inline styles to Tailwind CSS 4, adds a collapsible sidebar layout, auth context with login flow, and redesigns every page with professional UI patterns (sortable tables, glass-effect search, hover animations, skeleton loading, toast notifications).

**Tech Stack:** FastAPI + PyJWT + passlib[bcrypt] (backend auth), Tailwind CSS 4 + @tailwindcss/vite (frontend styling), React 19 + TypeScript + TanStack Query (unchanged)

**Design Doc:** `docs/plans/2026-03-01-auth-and-ui-overhaul-design.md`

---

## Phase 1: Backend Authentication

### Task 1: Add Auth Dependencies and User Model

**Files:**
- Modify: `web/requirements.txt`
- Modify: `web/api/models.py`

**Step 1: Add dependencies to web/requirements.txt**

Add these lines to `web/requirements.txt`:
```
PyJWT==2.8.0
passlib[bcrypt]==1.7.4
```

**Step 2: Install dependencies**

Run: `pip install -r web/requirements.txt`
Expected: All packages install successfully

**Step 3: Add User model to models.py**

Add after the existing imports in `web/api/models.py`:

```python
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="officer")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

**Step 4: Run existing tests to verify no breakage**

Run: `pytest tests/ -q`
Expected: All 96 tests pass

**Step 5: Commit**

```bash
git add web/requirements.txt web/api/models.py
git commit -m "feat: add User model and auth dependencies"
```

---

### Task 2: Auth Utilities and Login Route

**Files:**
- Create: `web/api/auth.py`
- Create: `web/api/routes/auth.py`
- Modify: `web/api/main.py`

**Step 1: Create auth utilities**

Create `web/api/auth.py`:

```python
import os
from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from web.api.database import get_db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)

JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS)
    return jwt.encode(
        {"sub": username, "exp": expire},
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


async def get_current_officer(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    from web.api.models import User
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user
```

**Step 2: Create auth routes**

Create `web/api/routes/auth.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from web.api.database import get_db
from web.api.models import User
from web.api.auth import verify_password, create_access_token, get_current_officer

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    username: str
    role: str


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(user.username)
    return LoginResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_officer)):
    return UserResponse(username=user.username, role=user.role)
```

**Step 3: Register auth router in main.py**

In `web/api/main.py`, add after the existing router imports:

```python
from web.api.routes.auth import router as auth_router
```

And add after the existing `app.include_router()` calls:

```python
app.include_router(auth_router)
```

**Step 4: Run tests**

Run: `pytest tests/ -q`
Expected: All tests pass (no existing tests depend on auth)

**Step 5: Commit**

```bash
git add web/api/auth.py web/api/routes/auth.py web/api/main.py
git commit -m "feat: add JWT auth login endpoint and auth utilities"
```

---

### Task 3: Protect Write Endpoints

**Files:**
- Modify: `web/api/routes/config.py`
- Modify: `web/api/routes/sync_status.py`

**Step 1: Add auth guard to config PUT routes**

In `web/api/routes/config.py`, add the import at the top:

```python
from web.api.auth import get_current_officer
from web.api.models import User
```

Then add `officer: User = Depends(get_current_officer)` as a parameter to each PUT handler:

```python
@router.put("/specs/{spec_key}/contributions/{metric}")
async def update_target(spec_key: str, metric: str, body: dict, db: AsyncSession = Depends(get_db), officer: User = Depends(get_current_officer)):
    # ... existing code unchanged ...

@router.put("/specs/{spec_key}/weights")
async def update_weights(spec_key: str, body: dict, db: AsyncSession = Depends(get_db), officer: User = Depends(get_current_officer)):
    # ... existing code unchanged ...

@router.put("/attendance/{zone_id}")
async def update_attendance(zone_id: int, body: dict, db: AsyncSession = Depends(get_db), officer: User = Depends(get_current_officer)):
    # ... existing code unchanged ...
```

**Step 2: Add auth guard to sync trigger**

In `web/api/routes/sync_status.py`, add the import at the top:

```python
from web.api.auth import get_current_officer
from web.api.models import User
```

Then add the guard to the POST handler:

```python
@router.post("/trigger")
async def trigger_sync(background_tasks: BackgroundTasks, force: bool = False, db: AsyncSession = Depends(get_db), officer: User = Depends(get_current_officer)):
    # ... existing code unchanged ...
```

**Step 3: Run tests**

Run: `pytest tests/ -q`
Expected: All pass. The existing web route tests for config PUT endpoints may need updating if they exist — check `test_web_routes.py`.

**Step 4: Commit**

```bash
git add web/api/routes/config.py web/api/routes/sync_status.py
git commit -m "feat: protect config PUT and sync trigger with auth guard"
```

---

### Task 4: Create-User CLI Script

**Files:**
- Create: `web/api/create_user.py`

**Step 1: Create the CLI script**

Create `web/api/create_user.py`:

```python
"""CLI to create officer accounts.

Usage: python -m web.api.create_user <username> <password>
"""
import asyncio
import sys

from sqlalchemy import select

from web.api.database import engine, async_session
from web.api.models import Base, User
from web.api.auth import hash_password


async def main():
    if len(sys.argv) != 3:
        print("Usage: python -m web.api.create_user <username> <password>")
        sys.exit(1)

    username, password = sys.argv[1], sys.argv[2]

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        existing = await session.execute(select(User).where(User.username == username))
        if existing.scalar_one_or_none():
            print(f"User '{username}' already exists.")
            sys.exit(1)

        user = User(username=username, password_hash=hash_password(password), role="officer")
        session.add(user)
        await session.commit()
        print(f"Officer account '{username}' created successfully.")


if __name__ == "__main__":
    asyncio.run(main())
```

**Step 2: Test it runs without errors (syntax check)**

Run: `python -c "import web.api.create_user"`
Expected: No import errors

**Step 3: Commit**

```bash
git add web/api/create_user.py
git commit -m "feat: add create-user CLI for seeding officer accounts"
```

---

### Task 5: Auth Tests

**Files:**
- Create: `tests/test_web_auth.py`

**Step 1: Write auth tests**

Create `tests/test_web_auth.py`:

```python
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from web.api.main import app
from web.api.auth import hash_password, verify_password, create_access_token


@pytest.fixture
def transport():
    return ASGITransport(app=app)


def test_hash_and_verify_password():
    hashed = hash_password("testpass")
    assert verify_password("testpass", hashed)
    assert not verify_password("wrong", hashed)


def test_create_access_token():
    token = create_access_token("admin")
    assert isinstance(token, str)
    assert len(token) > 0


@pytest.mark.asyncio
async def test_login_missing_user(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/auth/login", json={"username": "nobody", "password": "pass"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_no_token(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_bad_token(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/auth/me", headers={"Authorization": "Bearer bad-token"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_config_no_auth(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.put(
            "/api/config/specs/warrior:protection/contributions/sunder_armor_uptime",
            json={"target": 90},
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_sync_no_auth(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/sync/trigger")
    assert response.status_code == 401
```

**Step 2: Run tests**

Run: `pytest tests/test_web_auth.py -v`
Expected: All tests pass

**Step 3: Run full test suite**

Run: `pytest tests/ -q`
Expected: All tests pass (existing tests that call protected endpoints may now get 401 — fix those by adding mock auth headers or removing those specific tests)

**Step 4: Commit**

```bash
git add tests/test_web_auth.py
git commit -m "test: add auth tests for login, token validation, and protected routes"
```

---

## Phase 2: Tailwind CSS Setup

### Task 6: Install and Configure Tailwind CSS 4

**Files:**
- Modify: `web/frontend/package.json`
- Modify: `web/frontend/vite.config.ts`
- Modify: `web/frontend/src/index.css`

**Step 1: Install Tailwind CSS 4 and Vite plugin**

Run:
```bash
cd web/frontend && npm install tailwindcss @tailwindcss/vite
```

**Step 2: Add Tailwind plugin to Vite config**

Replace `web/frontend/vite.config.ts` with:

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
```

**Step 3: Replace index.css with Tailwind directives and custom theme**

Replace `web/frontend/src/index.css` with:

```css
@import "tailwindcss";

@theme {
  /* Background colors */
  --color-bg-base: #0a0e14;
  --color-bg-surface: #12161f;
  --color-bg-elevated: #1a1f2e;
  --color-bg-hover: #222838;

  /* Border colors */
  --color-border-default: #2a2f3e;
  --color-border-hover: #3a3f4e;

  /* Accent */
  --color-accent-gold: #c9a959;
  --color-accent-gold-light: #e0c872;
  --color-accent-gold-dim: #8a7a3a;

  /* Text */
  --color-text-primary: #e8e6e3;
  --color-text-secondary: #8a8f98;
  --color-text-muted: #5a5f68;

  /* Status */
  --color-success: #2ea043;
  --color-danger: #da3633;
  --color-info: #58a6ff;

  /* WoW class colors */
  --color-class-warrior: #C79C6E;
  --color-class-paladin: #F58CBA;
  --color-class-hunter: #ABD473;
  --color-class-rogue: #FFF569;
  --color-class-priest: #FFFFFF;
  --color-class-shaman: #0070DE;
  --color-class-mage: #69CCF0;
  --color-class-warlock: #9482C9;
  --color-class-druid: #FF7D0A;

  /* Parse tier colors */
  --color-parse-legendary: #e268a8;
  --color-parse-epic: #a335ee;
  --color-parse-rare: #0070dd;
  --color-parse-uncommon: #1eff00;
  --color-parse-common: #999999;

  /* Item quality colors */
  --color-quality-poor: #9d9d9d;
  --color-quality-common: #ffffff;
  --color-quality-uncommon: #1eff00;
  --color-quality-rare: #0070dd;
  --color-quality-epic: #a335ee;
  --color-quality-legendary: #ff8000;

  /* Sizing */
  --width-sidebar: 240px;
  --width-sidebar-collapsed: 64px;
}

/* Base styles */
body {
  background-color: var(--color-bg-base);
  color: var(--color-text-primary);
  font-family: system-ui, -apple-system, sans-serif;
  margin: 0;
}

/* Scrollbar styling */
::-webkit-scrollbar {
  width: 8px;
}
::-webkit-scrollbar-track {
  background: var(--color-bg-base);
}
::-webkit-scrollbar-thumb {
  background: var(--color-border-default);
  border-radius: 4px;
}
::-webkit-scrollbar-thumb:hover {
  background: var(--color-border-hover);
}

/* Skeleton animation */
@keyframes shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

.skeleton {
  background: linear-gradient(90deg, var(--color-bg-surface) 25%, var(--color-bg-elevated) 50%, var(--color-bg-surface) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: 4px;
}

/* Toast animation */
@keyframes slide-in {
  from { transform: translateX(100%); opacity: 0; }
  to { transform: translateX(0); opacity: 1; }
}

@keyframes slide-out {
  from { transform: translateX(0); opacity: 1; }
  to { transform: translateX(100%); opacity: 0; }
}
```

**Step 4: Build to verify Tailwind works**

Run: `cd web/frontend && npm run build`
Expected: Build succeeds with no errors

**Step 5: Commit**

```bash
git add web/frontend/package.json web/frontend/package-lock.json web/frontend/vite.config.ts web/frontend/src/index.css
git commit -m "feat: add Tailwind CSS 4 with dark gaming theme"
```

---

## Phase 3: Frontend Auth

### Task 7: Auth Context, API Client Updates, and Login Page

**Files:**
- Create: `web/frontend/src/contexts/AuthContext.tsx`
- Create: `web/frontend/src/pages/Login.tsx`
- Modify: `web/frontend/src/api/client.ts`
- Modify: `web/frontend/src/App.tsx`

**Step 1: Create AuthContext**

Create `web/frontend/src/contexts/AuthContext.tsx`:

```tsx
import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import type { ReactNode } from 'react'

interface AuthUser {
  username: string
  role: string
}

interface AuthContextType {
  token: string | null
  user: AuthUser | null
  isAuthenticated: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('auth_token'))
  const [user, setUser] = useState<AuthUser | null>(null)

  const fetchUser = useCallback(async (t: string) => {
    try {
      const res = await fetch('/api/auth/me', { headers: { Authorization: `Bearer ${t}` } })
      if (res.ok) {
        setUser(await res.json())
      } else {
        setToken(null)
        setUser(null)
        localStorage.removeItem('auth_token')
      }
    } catch {
      setToken(null)
      setUser(null)
      localStorage.removeItem('auth_token')
    }
  }, [])

  useEffect(() => {
    if (token) fetchUser(token)
  }, [token, fetchUser])

  const login = async (username: string, password: string) => {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      throw new Error(data.detail || 'Login failed')
    }
    const data = await res.json()
    setToken(data.access_token)
    localStorage.setItem('auth_token', data.access_token)
  }

  const logout = () => {
    setToken(null)
    setUser(null)
    localStorage.removeItem('auth_token')
  }

  return (
    <AuthContext.Provider value={{ token, user, isAuthenticated: !!user, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
```

**Step 2: Update API client to include auth header**

Replace `web/frontend/src/api/client.ts` with:

```typescript
const BASE = '/api'

function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem('auth_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`)
  return res.json()
}

async function postJson<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`POST ${path} failed: ${res.status}`)
  return res.json()
}

async function putJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`PUT ${path} failed: ${res.status}`)
  return res.json()
}

export const api = {
  players: {
    list: () => fetchJson<import('./types').Player[]>('/players'),
    get: (name: string) => fetchJson<import('./types').PlayerDetail>(`/players/${name}`),
    rankings: (name: string, weeks = 4) => fetchJson<import('./types').Ranking[]>(`/players/${name}/rankings?weeks=${weeks}`),
    gear: (name: string) => fetchJson<import('./types').GearCheck>(`/players/${name}/gear`),
    attendance: (name: string, weeks = 4) => fetchJson<import('./types').AttendanceWeek[]>(`/players/${name}/attendance?weeks=${weeks}`),
  },
  leaderboard: (weeks = 4) => fetchJson<import('./types').LeaderboardEntry[]>(`/leaderboard?weeks=${weeks}`),
  reports: {
    list: () => fetchJson<import('./types').ReportSummary[]>('/reports'),
    get: (code: string) => fetchJson<import('./types').ReportDetail>(`/reports/${code}`),
  },
  attendance: (weeks = 4) => fetchJson<import('./types').PlayerAttendance[]>(`/attendance?weeks=${weeks}`),
  config: {
    specs: () => fetchJson<Record<string, any>>('/config/specs'),
    consumables: () => fetchJson<any[]>('/config/consumables'),
    attendance: () => fetchJson<any[]>('/config/attendance'),
    gear: () => fetchJson<Record<string, any>>('/config/gear'),
    updateTarget: (specKey: string, metric: string, target: number) =>
      putJson(`/config/specs/${specKey}/contributions/${metric}`, { target }),
    updateWeights: (specKey: string, weights: { parse_weight: number; utility_weight: number; consumables_weight: number }) =>
      putJson(`/config/specs/${specKey}/weights`, weights),
    updateAttendance: (zoneId: number, required: number) =>
      putJson(`/config/attendance/${zoneId}`, { required_per_week: required }),
  },
  sync: {
    status: () => fetchJson<import('./types').SyncStatusEntry[]>('/sync/status'),
    trigger: (force: boolean) => postJson('/sync/trigger?force=' + force),
  },
}
```

**Step 3: Create Login page**

Create `web/frontend/src/pages/Login.tsx`:

```tsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(username, password)
      navigate('/')
    } catch (err: any) {
      setError(err.message || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-bg-base">
      <div className="w-full max-w-sm p-8 bg-bg-surface border border-border-default rounded-xl">
        <div className="flex items-center justify-center gap-3 mb-8">
          <img src="/favicon.jpg" alt="CRANK" className="w-10 h-10 rounded" />
          <h1 className="text-2xl font-bold text-text-primary">CRANK</h1>
        </div>
        <h2 className="text-lg font-semibold text-text-primary mb-6 text-center">Officer Login</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm text-text-secondary mb-1">Username</label>
            <input
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              className="w-full px-3 py-2 bg-bg-base border border-border-default rounded-lg text-text-primary focus:outline-none focus:border-accent-gold transition-colors"
              required
            />
          </div>
          <div>
            <label className="block text-sm text-text-secondary mb-1">Password</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              className="w-full px-3 py-2 bg-bg-base border border-border-default rounded-lg text-text-primary focus:outline-none focus:border-accent-gold transition-colors"
              required
            />
          </div>
          {error && <p className="text-sm text-danger">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-2 bg-accent-gold text-bg-base font-semibold rounded-lg hover:bg-accent-gold-light disabled:opacity-50 transition-colors cursor-pointer disabled:cursor-not-allowed"
          >
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>
      </div>
    </div>
  )
}
```

**Step 4: Update App.tsx with AuthProvider and Login route**

Replace `web/frontend/src/App.tsx` with:

```tsx
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from './contexts/AuthContext'
import Home from './pages/Home'
import PlayerProfile from './pages/PlayerProfile'
import RaidHistory from './pages/RaidHistory'
import RaidDetail from './pages/RaidDetail'
import Attendance from './pages/Attendance'
import Config from './pages/Config'
import Login from './pages/Login'

const queryClient = new QueryClient()

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/" element={<Home />} />
            <Route path="/player/:name" element={<PlayerProfile />} />
            <Route path="/raids" element={<RaidHistory />} />
            <Route path="/raids/:code" element={<RaidDetail />} />
            <Route path="/attendance" element={<Attendance />} />
            <Route path="/config" element={<Config />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  )
}
```

**Step 5: Build and verify**

Run: `cd web/frontend && npm run build`
Expected: Build succeeds

**Step 6: Commit**

```bash
git add web/frontend/src/contexts/AuthContext.tsx web/frontend/src/pages/Login.tsx web/frontend/src/api/client.ts web/frontend/src/App.tsx
git commit -m "feat: add auth context, login page, and protected API calls"
```

---

## Phase 4: Layout Overhaul

### Task 8: Sidebar Navigation and Layout Component

**Files:**
- Create: `web/frontend/src/components/Sidebar.tsx`
- Rewrite: `web/frontend/src/components/Layout.tsx`

**Step 1: Create Sidebar component**

Create `web/frontend/src/components/Sidebar.tsx`:

```tsx
import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

const NAV_ITEMS = [
  { path: '/', label: 'Leaderboard', icon: 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M12 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75' },
  { path: '/raids', label: 'Raids', icon: 'M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2zM14 2v6h6M16 13H8M16 17H8M10 9H8' },
  { path: '/attendance', label: 'Attendance', icon: 'M8 2v4M16 2v4M3 10h18M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z' },
  { path: '/config', label: 'Config', icon: 'M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2zM12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z' },
]

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const location = useLocation()
  const { isAuthenticated, user, logout } = useAuth()

  const isActive = (path: string) => {
    if (path === '/') return location.pathname === '/'
    return location.pathname.startsWith(path)
  }

  const sidebarContent = (
    <>
      {/* Logo */}
      <div className="p-4 border-b border-border-default">
        <Link to="/" className="flex items-center gap-3 no-underline">
          <img src="/favicon.jpg" alt="CRANK" className="w-8 h-8 rounded flex-shrink-0" />
          {!collapsed && <span className="text-lg font-bold text-accent-gold">CRANK</span>}
        </Link>
      </div>

      {/* Nav items */}
      <nav className="flex-1 py-4 px-2 space-y-1">
        {NAV_ITEMS.map(item => (
          <Link
            key={item.path}
            to={item.path}
            onClick={() => setMobileOpen(false)}
            className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium no-underline transition-all duration-200 group ${
              isActive(item.path)
                ? 'bg-accent-gold/10 text-accent-gold border-l-2 border-accent-gold'
                : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary border-l-2 border-transparent'
            }`}
          >
            <svg className="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d={item.icon} />
            </svg>
            {!collapsed && <span>{item.label}</span>}
          </Link>
        ))}
      </nav>

      {/* Footer - Auth */}
      <div className="p-4 border-t border-border-default">
        {isAuthenticated ? (
          <div className={`${collapsed ? 'text-center' : ''}`}>
            {!collapsed && (
              <div className="text-xs text-text-muted mb-2">Signed in as</div>
            )}
            {!collapsed && (
              <div className="text-sm font-medium text-accent-gold mb-3">{user?.username}</div>
            )}
            <button
              onClick={logout}
              className={`text-sm text-text-secondary hover:text-danger transition-colors cursor-pointer bg-transparent border-none ${collapsed ? 'p-0' : 'w-full text-left'}`}
            >
              {collapsed ? (
                <svg className="w-5 h-5 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0 0 13.5 3h-6a2.25 2.25 0 0 0-2.25 2.25v13.5A2.25 2.25 0 0 0 7.5 21h6a2.25 2.25 0 0 0 2.25-2.25V15m3 0 3-3m0 0-3-3m3 3H9" />
                </svg>
              ) : 'Sign Out'}
            </button>
          </div>
        ) : (
          <Link
            to="/login"
            className={`flex items-center gap-2 text-sm text-text-secondary hover:text-accent-gold no-underline transition-colors ${collapsed ? 'justify-center' : ''}`}
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0" />
            </svg>
            {!collapsed && <span>Officer Login</span>}
          </Link>
        )}
      </div>

      {/* Collapse toggle (desktop only) */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="hidden lg:flex items-center justify-center p-3 border-t border-border-default text-text-muted hover:text-text-primary transition-colors cursor-pointer bg-transparent w-full"
      >
        <svg className={`w-4 h-4 transition-transform ${collapsed ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5 8.25 12l7.5-7.5" />
        </svg>
      </button>
    </>
  )

  return (
    <>
      {/* Mobile hamburger */}
      <button
        onClick={() => setMobileOpen(!mobileOpen)}
        className="lg:hidden fixed top-4 left-4 z-50 p-2 bg-bg-surface border border-border-default rounded-lg text-text-primary cursor-pointer"
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d={mobileOpen ? 'M6 18 18 6M6 6l12 12' : 'M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5'} />
        </svg>
      </button>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="lg:hidden fixed inset-0 bg-black/60 z-40"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed top-0 left-0 h-full bg-bg-surface border-r border-border-default z-40 flex flex-col transition-all duration-300
          ${mobileOpen ? 'translate-x-0' : '-translate-x-full'}
          lg:translate-x-0
          ${collapsed ? 'lg:w-(--width-sidebar-collapsed)' : 'lg:w-(--width-sidebar)'}
          w-(--width-sidebar)
        `}
      >
        {sidebarContent}
      </aside>
    </>
  )
}
```

**Step 2: Rewrite Layout component**

Replace `web/frontend/src/components/Layout.tsx` with:

```tsx
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { useAuth } from '../contexts/AuthContext'
import Sidebar from './Sidebar'

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return 'never'
  const now = Date.now()
  const then = new Date(dateStr + 'Z').getTime()
  const seconds = Math.floor((now - then) / 1000)
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

export default function Layout({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient()
  const { isAuthenticated } = useAuth()

  const { data: syncStatus } = useQuery({
    queryKey: ['sync-status'],
    queryFn: api.sync.status,
    refetchInterval: 15000,
  })

  const syncMutation = useMutation({
    mutationFn: () => api.sync.trigger(false),
    onSuccess: () => {
      setTimeout(() => queryClient.invalidateQueries({ queryKey: ['sync-status'] }), 2000)
    },
  })

  const fullResyncMutation = useMutation({
    mutationFn: () => api.sync.trigger(true),
    onSuccess: () => {
      setTimeout(() => queryClient.invalidateQueries({ queryKey: ['sync-status'] }), 2000)
    },
  })

  const isSyncing = syncMutation.isPending || fullResyncMutation.isPending
  const reportsSync = syncStatus?.find(s => s.sync_type === 'reports')
  const lastSynced = reportsSync?.last_run_at

  return (
    <div className="min-h-screen bg-bg-base">
      <Sidebar />

      {/* Main content */}
      <main className="lg:ml-(--width-sidebar) min-h-screen">
        {/* Top bar */}
        <div className="sticky top-0 z-30 bg-bg-base/80 backdrop-blur-md border-b border-border-default px-6 py-3 flex items-center justify-between">
          <div />
          <div className="flex items-center gap-4 text-sm">
            <span className="text-text-muted">
              Synced {timeAgo(lastSynced ?? null)}
            </span>
            {isAuthenticated && (
              <>
                <button
                  onClick={() => syncMutation.mutate()}
                  disabled={isSyncing}
                  className="px-3 py-1.5 bg-success/20 text-success border border-success/30 rounded-lg text-xs font-medium hover:bg-success/30 disabled:opacity-50 transition-colors cursor-pointer disabled:cursor-not-allowed"
                >
                  {isSyncing ? 'Syncing...' : 'Sync Now'}
                </button>
                <button
                  onClick={() => { if (confirm('This will re-fetch and re-process all reports. Continue?')) fullResyncMutation.mutate() }}
                  disabled={isSyncing}
                  className="px-3 py-1.5 bg-danger/20 text-danger border border-danger/30 rounded-lg text-xs font-medium hover:bg-danger/30 disabled:opacity-50 transition-colors cursor-pointer disabled:cursor-not-allowed"
                >
                  Full Resync
                </button>
              </>
            )}
          </div>
        </div>

        {/* Page content */}
        <div className="p-6">
          {children}
        </div>
      </main>
    </div>
  )
}
```

**Step 3: Build and verify**

Run: `cd web/frontend && npm run build`
Expected: Build succeeds

**Step 4: Commit**

```bash
git add web/frontend/src/components/Sidebar.tsx web/frontend/src/components/Layout.tsx
git commit -m "feat: add collapsible sidebar and redesign layout with Tailwind"
```

---

## Phase 5: Component Redesign

### Task 9: Utility Components (ClassIcon, ParseBar, ScoreCard, Skeleton, Toast)

**Files:**
- Rewrite: `web/frontend/src/components/ClassIcon.tsx`
- Rewrite: `web/frontend/src/components/ParseBar.tsx`
- Rewrite: `web/frontend/src/components/ScoreCard.tsx`
- Create: `web/frontend/src/components/Skeleton.tsx`
- Create: `web/frontend/src/components/Toast.tsx`

**Step 1: Rewrite ClassIcon with Tailwind**

Replace `web/frontend/src/components/ClassIcon.tsx` with:

```tsx
const CLASS_COLORS: Record<string, string> = {
  warrior: 'text-class-warrior',
  paladin: 'text-class-paladin',
  hunter: 'text-class-hunter',
  rogue: 'text-class-rogue',
  priest: 'text-class-priest',
  shaman: 'text-class-shaman',
  mage: 'text-class-mage',
  warlock: 'text-class-warlock',
  druid: 'text-class-druid',
}

const CLASS_ICONS: Record<string, string> = {
  warrior: 'classicon_warrior',
  paladin: 'classicon_paladin',
  hunter: 'classicon_hunter',
  rogue: 'classicon_rogue',
  priest: 'classicon_priest',
  shaman: 'classicon_shaman',
  mage: 'classicon_mage',
  warlock: 'classicon_warlock',
  druid: 'classicon_druid',
}

export default function ClassIcon({ className, name, size = 20 }: { className: string; name: string; size?: number }) {
  const cls = className.toLowerCase()
  const colorClass = CLASS_COLORS[cls] || 'text-text-secondary'
  const icon = CLASS_ICONS[cls]

  return (
    <span className="inline-flex items-center gap-1.5">
      {icon && (
        <img
          src={`https://wow.zamimg.com/images/wow/icons/medium/${icon}.jpg`}
          alt={className}
          width={size}
          height={size}
          className="rounded-sm align-middle"
        />
      )}
      <span className={`font-bold ${colorClass}`}>{name}</span>
    </span>
  )
}
```

**Step 2: Rewrite ParseBar with gradient fills**

Replace `web/frontend/src/components/ParseBar.tsx` with:

```tsx
function getParseColor(percent: number): string {
  if (percent >= 95) return 'bg-parse-legendary'
  if (percent >= 75) return 'bg-parse-epic'
  if (percent >= 50) return 'bg-parse-rare'
  if (percent >= 25) return 'bg-parse-uncommon'
  return 'bg-parse-common'
}

function getParseTextColor(percent: number): string {
  if (percent >= 95) return 'text-parse-legendary'
  if (percent >= 75) return 'text-parse-epic'
  if (percent >= 50) return 'text-parse-rare'
  if (percent >= 25) return 'text-parse-uncommon'
  return 'text-parse-common'
}

export default function ParseBar({ percent }: { percent: number }) {
  const rounded = Math.round(percent * 10) / 10

  return (
    <div className="flex items-center gap-2">
      <div className="w-24 h-2.5 bg-bg-base rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${getParseColor(percent)}`}
          style={{ width: `${Math.min(percent, 100)}%` }}
        />
      </div>
      <span className={`text-sm font-semibold tabular-nums ${getParseTextColor(percent)}`}>
        {rounded}
      </span>
    </div>
  )
}
```

**Step 3: Rewrite ScoreCard**

Replace `web/frontend/src/components/ScoreCard.tsx` with:

```tsx
export default function ScoreCard({ label, value }: { label: string; value: number | null }) {
  if (value === null) return null

  return (
    <div className="flex-1 bg-bg-surface border border-border-default rounded-xl p-4 text-center hover:border-border-hover transition-colors">
      <div className="text-xs text-text-muted uppercase tracking-wider mb-1">{label}</div>
      <div className="text-3xl font-bold text-accent-gold tabular-nums">{value.toFixed(1)}</div>
    </div>
  )
}
```

**Step 4: Create Skeleton component**

Create `web/frontend/src/components/Skeleton.tsx`:

```tsx
export function SkeletonRow({ cols = 5 }: { cols?: number }) {
  return (
    <tr>
      {Array.from({ length: cols }).map((_, i) => (
        <td key={i} className="p-3">
          <div className="skeleton h-4 w-full rounded" />
        </td>
      ))}
    </tr>
  )
}

export function SkeletonTable({ rows = 5, cols = 5 }: { rows?: number; cols?: number }) {
  return (
    <>
      {Array.from({ length: rows }).map((_, i) => (
        <SkeletonRow key={i} cols={cols} />
      ))}
    </>
  )
}

export function SkeletonCard() {
  return (
    <div className="bg-bg-surface border border-border-default rounded-xl p-5">
      <div className="skeleton h-4 w-1/3 rounded mb-3" />
      <div className="skeleton h-6 w-2/3 rounded mb-2" />
      <div className="skeleton h-3 w-1/2 rounded" />
    </div>
  )
}
```

**Step 5: Create Toast component**

Create `web/frontend/src/components/Toast.tsx`:

```tsx
import { createContext, useContext, useState, useCallback } from 'react'
import type { ReactNode } from 'react'

interface Toast {
  id: number
  message: string
  type: 'success' | 'error' | 'info'
}

interface ToastContextType {
  addToast: (message: string, type?: Toast['type']) => void
}

const ToastContext = createContext<ToastContextType | null>(null)

let nextId = 0

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const addToast = useCallback((message: string, type: Toast['type'] = 'info') => {
    const id = nextId++
    setToasts(prev => [...prev, { id, message, type }])
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id))
    }, 3000)
  }, [])

  const typeStyles = {
    success: 'border-success/50 bg-success/10 text-success',
    error: 'border-danger/50 bg-danger/10 text-danger',
    info: 'border-info/50 bg-info/10 text-info',
  }

  return (
    <ToastContext.Provider value={{ addToast }}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
        {toasts.map(toast => (
          <div
            key={toast.id}
            className={`px-4 py-3 rounded-lg border text-sm font-medium shadow-lg animate-[slide-in_0.3s_ease-out] ${typeStyles[toast.type]}`}
          >
            {toast.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}
```

**Step 6: Update App.tsx to include ToastProvider**

Wrap the existing app content in `web/frontend/src/App.tsx` with `<ToastProvider>` (inside AuthProvider, outside BrowserRouter):

```tsx
import { ToastProvider } from './components/Toast'

// In the render:
<QueryClientProvider client={queryClient}>
  <AuthProvider>
    <ToastProvider>
      <BrowserRouter>
        ...
      </BrowserRouter>
    </ToastProvider>
  </AuthProvider>
</QueryClientProvider>
```

**Step 7: Build and verify**

Run: `cd web/frontend && npm run build`
Expected: Build succeeds

**Step 8: Commit**

```bash
git add web/frontend/src/components/ web/frontend/src/App.tsx
git commit -m "feat: redesign utility components with Tailwind, add skeleton and toast"
```

---

### Task 10: Leaderboard Page (Home) Redesign

**Files:**
- Rewrite: `web/frontend/src/pages/Home.tsx`

**Step 1: Rewrite Home page with search, class filter, sortable table**

Replace `web/frontend/src/pages/Home.tsx` with:

```tsx
import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import Layout from '../components/Layout'
import ClassIcon from '../components/ClassIcon'
import ParseBar from '../components/ParseBar'
import { SkeletonTable } from '../components/Skeleton'

const CLASSES = ['warrior', 'paladin', 'hunter', 'rogue', 'priest', 'shaman', 'mage', 'warlock', 'druid']
const CLASS_ICONS: Record<string, string> = {
  warrior: 'classicon_warrior', paladin: 'classicon_paladin', hunter: 'classicon_hunter',
  rogue: 'classicon_rogue', priest: 'classicon_priest', shaman: 'classicon_shaman',
  mage: 'classicon_mage', warlock: 'classicon_warlock', druid: 'classicon_druid',
}

type SortKey = 'rank' | 'avg_score' | 'avg_parse' | 'fight_count'

const MEDAL = ['', '\u{1F947}', '\u{1F948}', '\u{1F949}']

export default function Home() {
  const [search, setSearch] = useState('')
  const [weeks, setWeeks] = useState(4)
  const [classFilter, setClassFilter] = useState<string | null>(null)
  const [sortKey, setSortKey] = useState<SortKey>('rank')
  const [sortAsc, setSortAsc] = useState(true)

  const { data: leaderboard, isLoading } = useQuery({
    queryKey: ['leaderboard', weeks],
    queryFn: () => api.leaderboard(weeks),
  })

  const filtered = useMemo(() => {
    let result = leaderboard || []
    if (search) result = result.filter(p => p.name.toLowerCase().includes(search.toLowerCase()))
    if (classFilter) result = result.filter(p => p.class_name === classFilter)
    const sorted = [...result].sort((a, b) => {
      const av = a[sortKey], bv = b[sortKey]
      return sortAsc ? (av > bv ? 1 : -1) : (av < bv ? 1 : -1)
    })
    return sorted
  }, [leaderboard, search, classFilter, sortKey, sortAsc])

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc(!sortAsc)
    else { setSortKey(key); setSortAsc(key === 'rank') }
  }

  const SortHeader = ({ label, field }: { label: string; field: SortKey }) => (
    <th
      className="p-3 text-left text-xs font-semibold text-text-muted uppercase tracking-wider cursor-pointer hover:text-text-primary transition-colors select-none"
      onClick={() => toggleSort(field)}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        {sortKey === field && (
          <svg className={`w-3 h-3 ${sortAsc ? '' : 'rotate-180'}`} fill="currentColor" viewBox="0 0 20 20">
            <path d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" />
          </svg>
        )}
      </span>
    </th>
  )

  const WEEK_OPTIONS = [2, 4, 8]

  return (
    <Layout>
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <img src="/favicon.jpg" alt="CRANK" className="w-9 h-9 rounded" />
        <h1 className="text-2xl font-bold text-text-primary">Guild Leaderboard</h1>
      </div>

      {/* Search + Filters */}
      <div className="flex flex-col sm:flex-row gap-3 mb-4">
        <div className="relative flex-1">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" />
          </svg>
          <input
            type="text"
            placeholder="Search players..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 bg-bg-surface/50 border border-border-default rounded-lg text-text-primary placeholder-text-muted focus:outline-none focus:border-accent-gold backdrop-blur-sm transition-colors"
          />
        </div>
        <div className="flex rounded-lg border border-border-default overflow-hidden">
          {WEEK_OPTIONS.map(w => (
            <button
              key={w}
              onClick={() => setWeeks(w)}
              className={`px-4 py-2 text-sm font-medium transition-colors cursor-pointer border-none ${
                weeks === w
                  ? 'bg-accent-gold text-bg-base'
                  : 'bg-bg-surface text-text-secondary hover:text-text-primary'
              }`}
            >
              {w}w
            </button>
          ))}
        </div>
      </div>

      {/* Class filter */}
      <div className="flex gap-1.5 mb-5 flex-wrap">
        <button
          onClick={() => setClassFilter(null)}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all cursor-pointer border ${
            classFilter === null
              ? 'border-accent-gold bg-accent-gold/10 text-accent-gold'
              : 'border-border-default bg-bg-surface text-text-secondary hover:border-border-hover'
          }`}
        >
          All
        </button>
        {CLASSES.map(cls => (
          <button
            key={cls}
            onClick={() => setClassFilter(classFilter === cls ? null : cls)}
            className={`p-1.5 rounded-lg transition-all cursor-pointer border ${
              classFilter === cls
                ? 'border-accent-gold bg-accent-gold/10 ring-1 ring-accent-gold/30'
                : 'border-border-default bg-bg-surface hover:border-border-hover'
            }`}
            title={cls}
          >
            <img
              src={`https://wow.zamimg.com/images/wow/icons/medium/${CLASS_ICONS[cls]}.jpg`}
              alt={cls}
              className="w-6 h-6 rounded-sm"
            />
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="bg-bg-surface border border-border-default rounded-xl overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border-default">
              <SortHeader label="Rank" field="rank" />
              <th className="p-3 text-left text-xs font-semibold text-text-muted uppercase tracking-wider">Player</th>
              <th className="p-3 text-left text-xs font-semibold text-text-muted uppercase tracking-wider hidden sm:table-cell">Class</th>
              <SortHeader label="Score" field="avg_score" />
              <SortHeader label="Avg Parse" field="avg_parse" />
              <SortHeader label="Fights" field="fight_count" />
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <SkeletonTable rows={10} cols={6} />
            ) : (
              filtered?.map(entry => (
                <tr
                  key={entry.name}
                  className="border-b border-border-default/50 hover:bg-bg-hover transition-colors group cursor-pointer"
                >
                  <td className="p-3 text-sm font-medium text-text-secondary">
                    {entry.rank <= 3 ? MEDAL[entry.rank] : entry.rank}
                  </td>
                  <td className="p-3">
                    <Link to={`/player/${entry.name}`} className="no-underline">
                      <ClassIcon className={entry.class_name} name={entry.name} />
                    </Link>
                  </td>
                  <td className="p-3 text-sm text-text-secondary capitalize hidden sm:table-cell">{entry.class_name}</td>
                  <td className="p-3 text-sm font-semibold text-accent-gold tabular-nums">{entry.avg_score}</td>
                  <td className="p-3"><ParseBar percent={entry.avg_parse} /></td>
                  <td className="p-3 text-sm text-text-secondary tabular-nums">{entry.fight_count}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </Layout>
  )
}
```

**Step 2: Build and verify**

Run: `cd web/frontend && npm run build`
Expected: Build succeeds

**Step 3: Commit**

```bash
git add web/frontend/src/pages/Home.tsx
git commit -m "feat: redesign leaderboard with search, class filter, and sortable table"
```

---

### Task 11: Player Profile Redesign

**Files:**
- Rewrite: `web/frontend/src/pages/PlayerProfile.tsx`
- Rewrite: `web/frontend/src/components/GearGrid.tsx`

**Step 1: Rewrite PlayerProfile with hero header, styled tabs**

Replace `web/frontend/src/pages/PlayerProfile.tsx` with a Tailwind version that includes:
- Hero header with large class icon (48px), name in class color, class/server subtitle
- Score cards using the redesigned ScoreCard component
- Styled tab bar with gold underline on active tab
- Week selector as segmented control (matching Home page)
- Performance tab: same polished table style with ParseBar
- Gear tab: avg ilvl + GearGrid + issues
- Attendance tab: styled weekly cards

Key sections for the implementation:

```tsx
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import Layout from '../components/Layout'
import ClassIcon from '../components/ClassIcon'
import ScoreCard from '../components/ScoreCard'
import ParseBar from '../components/ParseBar'
import GearGrid from '../components/GearGrid'
import { SkeletonTable, SkeletonCard } from '../components/Skeleton'

type Tab = 'performance' | 'gear' | 'attendance'

export default function PlayerProfile() {
  const { name } = useParams<{ name: string }>()
  const [tab, setTab] = useState<Tab>('performance')
  const [weeks, setWeeks] = useState(4)

  const { data: player, isLoading } = useQuery({
    queryKey: ['player', name],
    queryFn: () => api.players.get(name!),
    enabled: !!name,
  })

  const { data: rankings } = useQuery({
    queryKey: ['rankings', name, weeks],
    queryFn: () => api.players.rankings(name!, weeks),
    enabled: !!name && tab === 'performance',
  })

  const { data: gear } = useQuery({
    queryKey: ['gear', name],
    queryFn: () => api.players.gear(name!),
    enabled: !!name && tab === 'gear',
  })

  const { data: attendance } = useQuery({
    queryKey: ['player-attendance', name, weeks],
    queryFn: () => api.players.attendance(name!, weeks),
    enabled: !!name && tab === 'attendance',
  })

  if (isLoading) return <Layout><div className="space-y-4"><SkeletonCard /><SkeletonCard /></div></Layout>
  if (!player) return <Layout><p className="text-text-secondary">Player not found</p></Layout>

  const avgScore = player.scores.length
    ? player.scores.reduce((sum, s) => sum + s.overall_score, 0) / player.scores.length
    : null
  const avgParse = player.scores.length
    ? player.scores.reduce((sum, s) => sum + s.parse_score, 0) / player.scores.length
    : null

  const TABS: { key: Tab; label: string }[] = [
    { key: 'performance', label: 'Performance' },
    { key: 'gear', label: 'Gear' },
    { key: 'attendance', label: 'Attendance' },
  ]

  const WEEK_OPTIONS = [2, 4, 8]

  return (
    <Layout>
      {/* Hero header */}
      <div className="mb-6">
        <div className="flex items-center gap-4 mb-3">
          <ClassIcon className={player.class_name} name={player.name} size={48} />
        </div>
        <p className="text-sm text-text-secondary capitalize">
          {player.class_name} — {player.server} ({player.region.toUpperCase()})
        </p>
      </div>

      {/* Score cards */}
      <div className="flex gap-4 mb-6">
        <ScoreCard label="Consistency" value={avgScore} />
        <ScoreCard label="Avg Parse" value={avgParse} />
      </div>

      {/* Tabs + week selector */}
      <div className="flex items-center justify-between mb-5 border-b border-border-default">
        <div className="flex">
          {TABS.map(t => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`px-4 py-3 text-sm font-medium transition-colors cursor-pointer bg-transparent border-none border-b-2 -mb-px ${
                tab === t.key
                  ? 'text-accent-gold border-accent-gold'
                  : 'text-text-secondary hover:text-text-primary border-transparent'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
        {(tab === 'performance' || tab === 'attendance') && (
          <div className="flex rounded-lg border border-border-default overflow-hidden mb-1">
            {WEEK_OPTIONS.map(w => (
              <button
                key={w}
                onClick={() => setWeeks(w)}
                className={`px-3 py-1.5 text-xs font-medium transition-colors cursor-pointer border-none ${
                  weeks === w
                    ? 'bg-accent-gold text-bg-base'
                    : 'bg-bg-surface text-text-secondary hover:text-text-primary'
                }`}
              >
                {w}w
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Performance tab */}
      {tab === 'performance' && (
        <div className="bg-bg-surface border border-border-default rounded-xl overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border-default">
                <th className="p-3 text-left text-xs font-semibold text-text-muted uppercase tracking-wider">Boss</th>
                <th className="p-3 text-left text-xs font-semibold text-text-muted uppercase tracking-wider">Spec</th>
                <th className="p-3 text-left text-xs font-semibold text-text-muted uppercase tracking-wider">Parse</th>
                <th className="p-3 text-left text-xs font-semibold text-text-muted uppercase tracking-wider hidden sm:table-cell">Report</th>
              </tr>
            </thead>
            <tbody>
              {!rankings ? (
                <SkeletonTable rows={6} cols={4} />
              ) : (
                rankings.map((r, i) => (
                  <tr key={i} className="border-b border-border-default/50 hover:bg-bg-hover transition-colors">
                    <td className="p-3 text-sm text-text-primary">{r.encounter_name}</td>
                    <td className="p-3 text-sm text-text-secondary">{r.spec}</td>
                    <td className="p-3"><ParseBar percent={r.rank_percent} /></td>
                    <td className="p-3 text-xs text-text-muted font-mono hidden sm:table-cell">{r.report_code}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Gear tab */}
      {tab === 'gear' && gear && (
        <div>
          <div className="flex items-center gap-4 mb-4">
            <span className="text-sm text-text-secondary">
              Avg iLvl: <strong className="text-text-primary">{gear.avg_ilvl.toFixed(1)}</strong>
              {gear.ilvl_ok ? ' \u2705' : ' \u26A0\uFE0F'}
            </span>
            {gear.issues.length > 0 && (
              <span className="text-sm text-danger">{gear.issues.length} issue(s)</span>
            )}
          </div>
          <GearGrid gear={gear.gear} issues={gear.issues} />
        </div>
      )}

      {/* Attendance tab */}
      {tab === 'attendance' && attendance && (
        <div className="space-y-3">
          {attendance.map((week, i) => (
            <div key={i} className="bg-bg-surface border border-border-default rounded-xl p-4">
              <div className="font-semibold text-sm text-text-primary mb-2">
                Week {week.week}, {week.year}
              </div>
              <div className="flex flex-wrap gap-3">
                {week.zones?.map((z, j) => (
                  <span
                    key={j}
                    className={`text-sm px-3 py-1 rounded-lg border ${
                      z.met
                        ? 'border-success/30 bg-success/10 text-success'
                        : 'border-danger/30 bg-danger/10 text-danger'
                    }`}
                  >
                    {z.met ? '\u2705' : '\u274C'} {z.zone_label} ({z.clear_count}/{z.required})
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </Layout>
  )
}
```

**Step 2: Rewrite GearGrid with Tailwind and hover expand**

Replace `web/frontend/src/components/GearGrid.tsx` with:

```tsx
import { useEffect } from 'react'
import type { GearItem } from '../api/types'

const SLOT_NAMES: Record<number, string> = {
  0: 'Head', 1: 'Neck', 2: 'Shoulder', 4: 'Chest', 5: 'Waist',
  6: 'Legs', 7: 'Feet', 8: 'Wrist', 9: 'Hands', 10: 'Ring 1',
  11: 'Ring 2', 12: 'Trinket 1', 13: 'Trinket 2', 14: 'Cloak',
  15: 'Main Hand', 16: 'Off Hand', 17: 'Ranged',
}

const QUALITY_BORDERS: Record<number, string> = {
  0: 'border-l-quality-poor', 1: 'border-l-quality-common', 2: 'border-l-quality-uncommon',
  3: 'border-l-quality-rare', 4: 'border-l-quality-epic', 5: 'border-l-quality-legendary',
}

declare global {
  interface Window {
    $WowheadPower?: { refreshLinks: () => void }
  }
}

function buildDataWowhead(item: GearItem): string | undefined {
  const parts: string[] = []
  if (item.permanent_enchant) parts.push(`ench=${item.permanent_enchant}`)
  const gemIds = item.gems?.filter(g => g.id > 0).map(g => g.id) || []
  if (gemIds.length > 0) parts.push(`gems=${gemIds.join(':')}`)
  return parts.length > 0 ? parts.join('&') : undefined
}

export default function GearGrid({ gear, issues }: { gear: GearItem[]; issues: { slot: string; problem: string }[] }) {
  const issueMap = new Map(issues.map(i => [i.slot, i.problem]))

  useEffect(() => {
    const timer = setTimeout(() => {
      window.$WowheadPower?.refreshLinks()
    }, 100)
    return () => clearTimeout(timer)
  }, [gear])

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
      {gear.map(item => {
        const slotName = SLOT_NAMES[item.slot] || `Slot ${item.slot}`
        const issue = issueMap.get(slotName)
        const activeGems = item.gems?.filter(g => g.id > 0) || []
        const dataWh = buildDataWowhead(item)
        const borderClass = QUALITY_BORDERS[item.quality] || 'border-l-text-muted'
        return (
          <div
            key={item.slot}
            className={`p-3 rounded-lg border-l-3 transition-all duration-200 hover:scale-[1.02] hover:shadow-lg hover:shadow-black/20 ${borderClass} ${
              issue ? 'bg-danger/10 border border-danger/20' : 'bg-bg-surface border border-border-default hover:border-border-hover'
            }`}
          >
            <div className="text-xs text-text-muted">{slotName}</div>
            <div className="text-sm mt-0.5">
              <a
                href={`https://tbc.wowhead.com/item=${item.item_id}`}
                target="_blank"
                rel="noopener noreferrer"
                {...(dataWh ? { 'data-wowhead': dataWh } : {})}
              >
                {slotName}
              </a>
              <span className="text-text-muted text-xs ml-1.5">ilvl {item.item_level}</span>
            </div>
            {item.permanent_enchant && (
              <div className="text-xs text-parse-uncommon mt-1">Enchanted</div>
            )}
            {activeGems.length > 0 && (
              <div className="text-xs mt-1 flex flex-wrap gap-1">
                {activeGems.map((gem, idx) => (
                  <a
                    key={idx}
                    href={`https://tbc.wowhead.com/item=${gem.id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs"
                  >
                    [Gem]
                  </a>
                ))}
              </div>
            )}
            {issue && <div className="text-xs text-danger mt-1">{issue}</div>}
          </div>
        )
      })}
    </div>
  )
}
```

**Step 3: Build and verify**

Run: `cd web/frontend && npm run build`
Expected: Build succeeds

**Step 4: Commit**

```bash
git add web/frontend/src/pages/PlayerProfile.tsx web/frontend/src/components/GearGrid.tsx
git commit -m "feat: redesign player profile and gear grid with Tailwind"
```

---

### Task 12: Raid History and Raid Detail Redesign

**Files:**
- Rewrite: `web/frontend/src/pages/RaidHistory.tsx`
- Rewrite: `web/frontend/src/pages/RaidDetail.tsx`

**Step 1: Rewrite RaidHistory with card grid and hover effects**

Replace `web/frontend/src/pages/RaidHistory.tsx` with:

```tsx
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import Layout from '../components/Layout'
import { SkeletonCard } from '../components/Skeleton'

export default function RaidHistory() {
  const { data: reports, isLoading } = useQuery({
    queryKey: ['reports'],
    queryFn: api.reports.list,
  })

  return (
    <Layout>
      <h1 className="text-2xl font-bold text-text-primary mb-6">Raid History</h1>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {isLoading
          ? Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)
          : reports?.map(r => (
              <Link
                key={r.code}
                to={`/raids/${r.code}`}
                className="no-underline group"
              >
                <div className="bg-bg-surface border border-border-default rounded-xl p-5 transition-all duration-200 group-hover:-translate-y-1 group-hover:shadow-xl group-hover:shadow-accent-gold/5 group-hover:border-accent-gold/30">
                  <div className="font-semibold text-text-primary group-hover:text-accent-gold transition-colors">
                    {r.zone_name}
                  </div>
                  <div className="text-sm text-text-secondary mt-1">
                    {new Date(r.start_time).toLocaleDateString()}
                  </div>
                  <div className="flex items-center gap-2 mt-3">
                    <span className="text-xs px-2 py-0.5 bg-bg-hover rounded-full text-text-muted">
                      {r.player_count} players
                    </span>
                    <span className="text-xs text-text-muted font-mono">{r.code}</span>
                  </div>
                </div>
              </Link>
            ))}
      </div>
    </Layout>
  )
}
```

**Step 2: Rewrite RaidDetail with polished table**

Replace `web/frontend/src/pages/RaidDetail.tsx` with:

```tsx
import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import Layout from '../components/Layout'
import ClassIcon from '../components/ClassIcon'
import ParseBar from '../components/ParseBar'
import { SkeletonTable } from '../components/Skeleton'

export default function RaidDetail() {
  const { code } = useParams<{ code: string }>()
  const { data: report, isLoading } = useQuery({
    queryKey: ['report', code],
    queryFn: () => api.reports.get(code!),
    enabled: !!code,
  })

  if (isLoading) return <Layout><div className="bg-bg-surface border border-border-default rounded-xl overflow-hidden"><table className="w-full"><tbody><SkeletonTable rows={8} cols={5} /></tbody></table></div></Layout>
  if (!report) return <Layout><p className="text-text-secondary">Report not found</p></Layout>

  const consumables = report.consumables?.filter(c => c.actual_value > 0) || []

  return (
    <Layout>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-text-primary">{report.zone_name}</h1>
        <div className="flex items-center gap-3 mt-1 text-sm text-text-secondary">
          <span>{new Date(report.start_time).toLocaleDateString()}</span>
          <span className="text-text-muted">|</span>
          <span>{report.player_count} players</span>
          <span className="text-text-muted">|</span>
          <span className="font-mono text-text-muted">{report.code}</span>
        </div>
      </div>

      {/* Scores */}
      <div className="bg-bg-surface border border-border-default rounded-xl overflow-hidden mb-6">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border-default">
              <th className="p-3 text-left text-xs font-semibold text-text-muted uppercase tracking-wider">Player</th>
              <th className="p-3 text-left text-xs font-semibold text-text-muted uppercase tracking-wider hidden sm:table-cell">Spec</th>
              <th className="p-3 text-left text-xs font-semibold text-text-muted uppercase tracking-wider">Score</th>
              <th className="p-3 text-left text-xs font-semibold text-text-muted uppercase tracking-wider">Parse</th>
            </tr>
          </thead>
          <tbody>
            {report.scores.map((s, i) => (
              <tr key={i} className="border-b border-border-default/50 hover:bg-bg-hover transition-colors">
                <td className="p-3">
                  <ClassIcon className={s.class_name} name={s.player_name} />
                </td>
                <td className="p-3 text-sm text-text-secondary hidden sm:table-cell">{s.spec}</td>
                <td className="p-3 text-sm font-semibold text-accent-gold tabular-nums">{s.overall_score.toFixed(1)}</td>
                <td className="p-3"><ParseBar percent={s.parse_score} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Consumables */}
      {consumables.length > 0 && (
        <details className="bg-bg-surface border border-border-default rounded-xl overflow-hidden">
          <summary className="p-4 cursor-pointer text-sm font-semibold text-text-primary hover:bg-bg-hover transition-colors select-none">
            Consumables ({consumables.length})
          </summary>
          <table className="w-full">
            <thead>
              <tr className="border-b border-border-default">
                <th className="p-3 text-left text-xs font-semibold text-text-muted uppercase tracking-wider">Player</th>
                <th className="p-3 text-left text-xs font-semibold text-text-muted uppercase tracking-wider">Metric</th>
                <th className="p-3 text-left text-xs font-semibold text-text-muted uppercase tracking-wider">Value</th>
                <th className="p-3 text-left text-xs font-semibold text-text-muted uppercase tracking-wider">Target</th>
              </tr>
            </thead>
            <tbody>
              {consumables.map((c, i) => (
                <tr key={i} className="border-b border-border-default/50">
                  <td className="p-3 text-sm text-text-primary">{c.player_name}</td>
                  <td className="p-3 text-sm text-text-secondary">
                    {c.label}
                    {c.optional && <span className="ml-1.5 text-xs text-text-muted">(optional)</span>}
                  </td>
                  <td className="p-3 text-sm tabular-nums text-text-primary">{c.actual_value}</td>
                  <td className="p-3 text-sm tabular-nums text-text-muted">{c.target_value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      )}
    </Layout>
  )
}
```

**Step 3: Build and verify**

Run: `cd web/frontend && npm run build`
Expected: Build succeeds

**Step 4: Commit**

```bash
git add web/frontend/src/pages/RaidHistory.tsx web/frontend/src/pages/RaidDetail.tsx
git commit -m "feat: redesign raid history cards and raid detail with Tailwind"
```

---

### Task 13: Attendance Page Redesign

**Files:**
- Rewrite: `web/frontend/src/pages/Attendance.tsx`

**Step 1: Rewrite Attendance with styled cards**

Replace `web/frontend/src/pages/Attendance.tsx` with:

```tsx
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import Layout from '../components/Layout'
import ClassIcon from '../components/ClassIcon'
import { SkeletonCard } from '../components/Skeleton'

export default function Attendance() {
  const [weeks, setWeeks] = useState(4)
  const { data: attendance, isLoading } = useQuery({
    queryKey: ['attendance', weeks],
    queryFn: () => api.attendance(weeks),
  })

  const WEEK_OPTIONS = [2, 4, 8]

  return (
    <Layout>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-text-primary">Guild Attendance</h1>
        <div className="flex rounded-lg border border-border-default overflow-hidden">
          {WEEK_OPTIONS.map(w => (
            <button
              key={w}
              onClick={() => setWeeks(w)}
              className={`px-4 py-2 text-sm font-medium transition-colors cursor-pointer border-none ${
                weeks === w
                  ? 'bg-accent-gold text-bg-base'
                  : 'bg-bg-surface text-text-secondary hover:text-text-primary'
              }`}
            >
              {w}w
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      ) : (
        <div className="space-y-3">
          {attendance?.map((player, i) => (
            <div key={i} className="bg-bg-surface border border-border-default rounded-xl p-4 hover:border-border-hover transition-colors">
              <div className="mb-3">
                <ClassIcon className={player.class_name} name={player.name} />
              </div>
              <div className="flex flex-wrap gap-2">
                {player.weeks.map((w, j) => (
                  <span
                    key={j}
                    className={`text-xs px-2.5 py-1 rounded-lg border ${
                      w.met
                        ? 'border-success/30 bg-success/10 text-success'
                        : 'border-danger/30 bg-danger/10 text-danger'
                    }`}
                  >
                    {w.met ? '\u2705' : '\u274C'} W{w.week} {w.zone_label}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </Layout>
  )
}
```

**Step 2: Build and verify**

Run: `cd web/frontend && npm run build`
Expected: Build succeeds

**Step 3: Commit**

```bash
git add web/frontend/src/pages/Attendance.tsx
git commit -m "feat: redesign attendance page with Tailwind"
```

---

### Task 14: Config Page Redesign with Auth Gating

**Files:**
- Rewrite: `web/frontend/src/pages/Config.tsx`

**Step 1: Rewrite Config with accordion, auth-gated editing, toast feedback**

Replace `web/frontend/src/pages/Config.tsx` with a Tailwind version that:
- Shows all config as read-only cards by default
- When authenticated (officer): shows edit buttons, inline editors with save/cancel
- Spec section: accordion pattern — click spec header to expand contributions
- Weight editor: three number inputs that validate sum = 100%
- Attendance: editable required counts per zone (officer only)
- Gear check: clean read-only display
- Uses toast notifications for save success/failure
- Uses `useAuth()` to check `isAuthenticated` before showing edit controls

Key structure:

```tsx
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import Layout from '../components/Layout'
import { useAuth } from '../contexts/AuthContext'
import { useToast } from '../components/Toast'
import { SkeletonCard } from '../components/Skeleton'

export default function Config() {
  const { isAuthenticated } = useAuth()
  const { addToast } = useToast()
  const queryClient = useQueryClient()

  const { data: specs, isLoading: specsLoading } = useQuery({
    queryKey: ['config-specs'],
    queryFn: api.config.specs,
  })
  const { data: consumables } = useQuery({
    queryKey: ['config-consumables'],
    queryFn: api.config.consumables,
  })
  const { data: attendanceConfig } = useQuery({
    queryKey: ['config-attendance'],
    queryFn: api.config.attendance,
  })
  const { data: gearConfig } = useQuery({
    queryKey: ['config-gear'],
    queryFn: api.config.gear,
  })

  const [expandedSpec, setExpandedSpec] = useState<string | null>(null)
  const [editingTarget, setEditingTarget] = useState<{ spec: string; metric: string } | null>(null)
  const [editValue, setEditValue] = useState('')
  const [editingWeights, setEditingWeights] = useState<string | null>(null)
  const [weights, setWeights] = useState({ parse: 0, utility: 0, consumables: 0 })
  const [editingAttendance, setEditingAttendance] = useState<number | null>(null)
  const [attendanceValue, setAttendanceValue] = useState(0)

  const targetMutation = useMutation({
    mutationFn: ({ spec, metric, target }: { spec: string; metric: string; target: number }) =>
      api.config.updateTarget(spec, metric, target),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['config-specs'] })
      addToast('Target updated', 'success')
      setEditingTarget(null)
    },
    onError: () => addToast('Failed to update target', 'error'),
  })

  const weightsMutation = useMutation({
    mutationFn: ({ spec, w }: { spec: string; w: { parse_weight: number; utility_weight: number; consumables_weight: number } }) =>
      api.config.updateWeights(spec, w),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['config-specs'] })
      addToast('Weights updated', 'success')
      setEditingWeights(null)
    },
    onError: () => addToast('Weights must sum to 100%', 'error'),
  })

  const attendanceMutation = useMutation({
    mutationFn: ({ zoneId, required }: { zoneId: number; required: number }) =>
      api.config.updateAttendance(zoneId, required),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['config-attendance'] })
      addToast('Attendance updated', 'success')
      setEditingAttendance(null)
    },
    onError: () => addToast('Failed to update attendance', 'error'),
  })

  if (specsLoading) return <Layout><div className="space-y-4">{Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)}</div></Layout>

  return (
    <Layout>
      <h1 className="text-2xl font-bold text-text-primary mb-6">Configuration</h1>
      {!isAuthenticated && (
        <div className="mb-6 p-4 bg-accent-gold/10 border border-accent-gold/20 rounded-xl text-sm text-accent-gold">
          Viewing as guest. Log in as an officer to edit configuration.
        </div>
      )}

      {/* Spec Profiles */}
      <h2 className="text-lg font-semibold text-text-primary mb-3">Spec Profiles</h2>
      <div className="space-y-2 mb-8">
        {specs && Object.entries(specs).map(([key, spec]: [string, any]) => (
          <div key={key} className="bg-bg-surface border border-border-default rounded-xl overflow-hidden">
            <button
              onClick={() => setExpandedSpec(expandedSpec === key ? null : key)}
              className="w-full flex items-center justify-between p-4 text-left bg-transparent border-none cursor-pointer hover:bg-bg-hover transition-colors"
            >
              <span className="text-sm font-semibold text-text-primary capitalize">{key.replace(':', ' — ')}</span>
              <div className="flex items-center gap-3 text-xs text-text-muted">
                <span>Parse {((spec.parse_weight || 0) * 100).toFixed(0)}%</span>
                <span>Utility {((spec.utility_weight || 0) * 100).toFixed(0)}%</span>
                <span>Consumes {((spec.consumables_weight || 0) * 100).toFixed(0)}%</span>
                <svg className={`w-4 h-4 transition-transform ${expandedSpec === key ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
                </svg>
              </div>
            </button>
            {expandedSpec === key && (
              <div className="border-t border-border-default p-4">
                {/* Weights editor */}
                {isAuthenticated && editingWeights === key ? (
                  <div className="flex items-center gap-2 mb-4 text-sm">
                    <label className="text-text-muted">Parse:</label>
                    <input type="number" value={weights.parse} onChange={e => setWeights({ ...weights, parse: +e.target.value })} className="w-16 px-2 py-1 bg-bg-base border border-border-default rounded text-text-primary text-center" />
                    <label className="text-text-muted">Utility:</label>
                    <input type="number" value={weights.utility} onChange={e => setWeights({ ...weights, utility: +e.target.value })} className="w-16 px-2 py-1 bg-bg-base border border-border-default rounded text-text-primary text-center" />
                    <label className="text-text-muted">Consumes:</label>
                    <input type="number" value={weights.consumables} onChange={e => setWeights({ ...weights, consumables: +e.target.value })} className="w-16 px-2 py-1 bg-bg-base border border-border-default rounded text-text-primary text-center" />
                    <button onClick={() => weightsMutation.mutate({ spec: key, w: { parse_weight: weights.parse / 100, utility_weight: weights.utility / 100, consumables_weight: weights.consumables / 100 } })} className="px-2 py-1 bg-success text-white rounded text-xs cursor-pointer border-none">Save</button>
                    <button onClick={() => setEditingWeights(null)} className="px-2 py-1 bg-bg-hover text-text-secondary rounded text-xs cursor-pointer border-none">Cancel</button>
                  </div>
                ) : isAuthenticated ? (
                  <button onClick={() => { setEditingWeights(key); setWeights({ parse: (spec.parse_weight || 0) * 100, utility: (spec.utility_weight || 0) * 100, consumables: (spec.consumables_weight || 0) * 100 }) }} className="text-xs text-info hover:underline cursor-pointer bg-transparent border-none mb-4 block">Edit weights</button>
                ) : null}

                {/* Contributions */}
                {spec.contributions?.length > 0 ? (
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-xs text-text-muted uppercase">
                        <th className="pb-2 text-left font-semibold">Metric</th>
                        <th className="pb-2 text-left font-semibold">Type</th>
                        <th className="pb-2 text-right font-semibold">Target</th>
                      </tr>
                    </thead>
                    <tbody>
                      {spec.contributions.map((c: any) => (
                        <tr key={c.metric} className="border-t border-border-default/50">
                          <td className="py-2 text-text-primary">{c.label}</td>
                          <td className="py-2 text-text-muted">{c.type}{c.subtype ? ` (${c.subtype})` : ''}</td>
                          <td className="py-2 text-right">
                            {isAuthenticated && editingTarget?.spec === key && editingTarget?.metric === c.metric ? (
                              <span className="inline-flex items-center gap-1">
                                <input type="number" value={editValue} onChange={e => setEditValue(e.target.value)} className="w-16 px-2 py-0.5 bg-bg-base border border-border-default rounded text-text-primary text-right" autoFocus />
                                <button onClick={() => targetMutation.mutate({ spec: key, metric: c.metric, target: +editValue })} className="px-1.5 py-0.5 bg-success text-white rounded text-xs cursor-pointer border-none">OK</button>
                                <button onClick={() => setEditingTarget(null)} className="px-1.5 py-0.5 bg-bg-hover text-text-secondary rounded text-xs cursor-pointer border-none">X</button>
                              </span>
                            ) : (
                              <span
                                className={`tabular-nums ${isAuthenticated ? 'cursor-pointer hover:text-accent-gold' : ''}`}
                                onClick={isAuthenticated ? () => { setEditingTarget({ spec: key, metric: c.metric }); setEditValue(String(c.target)) } : undefined}
                              >
                                {c.target}
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <p className="text-sm text-text-muted">No contributions configured (pure parse scoring)</p>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Consumables */}
      <h2 className="text-lg font-semibold text-text-primary mb-3">Consumables</h2>
      <div className="bg-bg-surface border border-border-default rounded-xl p-4 mb-8">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-text-muted uppercase">
              <th className="pb-2 text-left font-semibold">Label</th>
              <th className="pb-2 text-left font-semibold">Type</th>
              <th className="pb-2 text-right font-semibold">Target</th>
              <th className="pb-2 text-right font-semibold">Optional</th>
            </tr>
          </thead>
          <tbody>
            {consumables?.map((c: any, i: number) => (
              <tr key={i} className="border-t border-border-default/50">
                <td className="py-2 text-text-primary">{c.label}</td>
                <td className="py-2 text-text-muted">{c.type}</td>
                <td className="py-2 text-right tabular-nums">{c.target}</td>
                <td className="py-2 text-right">{c.optional ? '\u2705' : ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Attendance Requirements */}
      <h2 className="text-lg font-semibold text-text-primary mb-3">Attendance Requirements</h2>
      <div className="bg-bg-surface border border-border-default rounded-xl p-4 mb-8">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-text-muted uppercase">
              <th className="pb-2 text-left font-semibold">Zone</th>
              <th className="pb-2 text-right font-semibold">Required / Week</th>
            </tr>
          </thead>
          <tbody>
            {attendanceConfig?.map((z: any) => (
              <tr key={z.zone_id} className="border-t border-border-default/50">
                <td className="py-2 text-text-primary">{z.label}</td>
                <td className="py-2 text-right">
                  {isAuthenticated && editingAttendance === z.zone_id ? (
                    <span className="inline-flex items-center gap-1">
                      <input type="number" value={attendanceValue} onChange={e => setAttendanceValue(+e.target.value)} className="w-16 px-2 py-0.5 bg-bg-base border border-border-default rounded text-text-primary text-right" autoFocus />
                      <button onClick={() => attendanceMutation.mutate({ zoneId: z.zone_id, required: attendanceValue })} className="px-1.5 py-0.5 bg-success text-white rounded text-xs cursor-pointer border-none">OK</button>
                      <button onClick={() => setEditingAttendance(null)} className="px-1.5 py-0.5 bg-bg-hover text-text-secondary rounded text-xs cursor-pointer border-none">X</button>
                    </span>
                  ) : (
                    <span
                      className={`tabular-nums ${isAuthenticated ? 'cursor-pointer hover:text-accent-gold' : ''}`}
                      onClick={isAuthenticated ? () => { setEditingAttendance(z.zone_id); setAttendanceValue(z.required_per_week) } : undefined}
                    >
                      {z.required_per_week}
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Gear Check Config */}
      <h2 className="text-lg font-semibold text-text-primary mb-3">Gear Check</h2>
      <div className="bg-bg-surface border border-border-default rounded-xl p-4">
        {gearConfig && (
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div className="text-text-muted">Min Avg iLvl</div>
            <div className="text-text-primary font-medium">{gearConfig.min_avg_ilvl}</div>
            <div className="text-text-muted">Min Quality</div>
            <div className="text-text-primary font-medium">{gearConfig.min_quality}</div>
            <div className="text-text-muted">Check Enchants</div>
            <div className="text-text-primary">{gearConfig.check_enchants ? '\u2705' : '\u274C'}</div>
            <div className="text-text-muted">Check Gems</div>
            <div className="text-text-primary">{gearConfig.check_gems ? '\u2705' : '\u274C'}</div>
          </div>
        )}
      </div>
    </Layout>
  )
}
```

**Step 2: Build and verify**

Run: `cd web/frontend && npm run build`
Expected: Build succeeds

**Step 3: Run full test suite**

Run: `pytest tests/ -q`
Expected: All tests pass

**Step 4: Commit**

```bash
git add web/frontend/src/pages/Config.tsx
git commit -m "feat: redesign config page with accordion, auth-gated editing, and toasts"
```

---

### Task 15: Final Integration and Cleanup

**Files:**
- Modify: `web/frontend/src/main.tsx` (verify clean entry)
- Modify: `web/frontend/index.html` (verify Wowhead script still present)
- Modify: `Dockerfile.web` (verify no build issues)
- Modify: `.env.example` (add JWT_SECRET)

**Step 1: Update .env.example with JWT_SECRET**

Add to `.env.example`:
```
JWT_SECRET=your-secret-key-change-in-production
```

**Step 2: Full build verification**

Run:
```bash
cd web/frontend && npm run build
```
Expected: Build succeeds with no warnings

**Step 3: Run all tests**

Run:
```bash
pytest tests/ -q
```
Expected: All tests pass

**Step 4: Visual check (dev server)**

Run:
```bash
cd web/frontend && npm run dev
```

Open http://localhost:5173 in browser and verify:
- Sidebar navigation renders with icons
- Leaderboard loads with search, class filter, sortable table
- Player profiles show with tabs, score cards
- Raid history shows card grid with hover effects
- Login page accessible at /login
- Config page shows read-only for guests

**Step 5: Commit**

```bash
git add .env.example
git commit -m "docs: add JWT_SECRET to env example"
```

---

## Deployment Notes

After all tasks are complete:

1. **Create first officer account** on the server:
   ```bash
   docker exec -it <web-api-container> python -m web.api.create_user admin <password>
   ```

2. **Set JWT_SECRET** in AWS Secrets Manager (add to the existing `warcraftlogs-bot/credentials` secret)

3. **Update docker-compose.prod.yml** to pass `JWT_SECRET` env var to web-api and sync-worker services

4. **Push and deploy** via the existing GitHub Actions pipeline
