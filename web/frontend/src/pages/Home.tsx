import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { api } from '../api/client'
import { CHART_COLORS, CHART_DEFAULTS } from '../components/ChartTheme'
import Layout from '../components/Layout'
import ClassIcon, { getSpecLabel } from '../components/ClassIcon'
import ParseBar from '../components/ParseBar'
import { SkeletonTable } from '../components/Skeleton'
import { useScoreAccess } from '../hooks/useScoreAccess'

const CLASSES = ['warrior', 'paladin', 'hunter', 'rogue', 'priest', 'shaman', 'mage', 'warlock', 'druid']
const CLASS_ICONS: Record<string, string> = {
  warrior: 'classicon_warrior', paladin: 'classicon_paladin', hunter: 'classicon_hunter',
  rogue: 'classicon_rogue', priest: 'classicon_priest', shaman: 'classicon_shaman',
  mage: 'classicon_mage', warlock: 'classicon_warlock', druid: 'classicon_druid',
}

type SortKey = 'rank' | 'avg_score' | 'avg_parse' | 'fight_count'
type RoleFilter = 'all' | 'tank' | 'healer' | 'caster' | 'physical'

const MEDAL = ['', '\u{1F947}', '\u{1F948}', '\u{1F949}']

const TANK_SPECS = ['warrior:protection', 'warrior:gladiator', 'paladin:protection', 'paladin:justicar', 'druid:feral', 'druid:guardian']
const HEALER_SPECS = ['paladin:holy', 'priest:holy', 'priest:discipline', 'shaman:restoration', 'druid:restoration']
const CASTER_SPECS = ['mage:arcane', 'mage:fire', 'mage:frost', 'warlock:affliction', 'warlock:destruction', 'warlock:demonology', 'priest:shadow', 'shaman:elemental', 'druid:balance']
const PHYSICAL_SPECS = ['warrior:fury', 'warrior:arms', 'rogue:combat', 'rogue:assassination', 'hunter:beastmastery', 'hunter:beast mastery', 'hunter:survival', 'hunter:marksmanship', 'shaman:enhancement', 'paladin:retribution']

function getRole(spec: string | undefined): RoleFilter {
  if (!spec) return 'physical'
  if (TANK_SPECS.includes(spec)) return 'tank'
  if (HEALER_SPECS.includes(spec)) return 'healer'
  if (CASTER_SPECS.includes(spec)) return 'caster'
  if (PHYSICAL_SPECS.includes(spec)) return 'physical'
  return 'physical'
}

const ROLE_FILTERS: { key: RoleFilter; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'tank', label: 'Tanks' },
  { key: 'healer', label: 'Healers' },
  { key: 'caster', label: 'Casters' },
  { key: 'physical', label: 'Physical DPS' },
]

export default function Home() {
  const [search, setSearch] = useState('')
  const [weeks, setWeeks] = useState(4)
  const [classFilter, setClassFilter] = useState<string | null>(null)
  const [roleFilter, setRoleFilter] = useState<RoleFilter>('all')
  const [sortKey, setSortKey] = useState<SortKey>('rank')
  const [sortAsc, setSortAsc] = useState(true)
  const { canViewScores } = useScoreAccess()
  const [leaderboardTab, setLeaderboardTab] = useState<'parse' | 'score'>('parse')

  const { data: leaderboard, isLoading } = useQuery({
    queryKey: ['leaderboard', weeks, leaderboardTab],
    queryFn: () => api.leaderboard(weeks, leaderboardTab),
  })

  const { data: mvp } = useQuery({
    queryKey: ['mvp'],
    queryFn: () => api.mvp(),
    enabled: canViewScores,
  })

  const { data: guildTrends } = useQuery({
    queryKey: ['guild-trends', weeks],
    queryFn: () => api.guildTrends(weeks),
  })

  const filtered = useMemo(() => {
    let result = leaderboard || []
    if (search) result = result.filter(p => p.name.toLowerCase().includes(search.toLowerCase()))
    if (classFilter) result = result.filter(p => p.class_name === classFilter)
    if (roleFilter !== 'all') result = result.filter(p => getRole(p.spec) === roleFilter)
    const sorted = [...result].sort((a, b) => {
      const av = a[sortKey], bv = b[sortKey]
      return sortAsc ? (av > bv ? 1 : -1) : (av < bv ? 1 : -1)
    })
    return sorted
  }, [leaderboard, search, classFilter, roleFilter, sortKey, sortAsc])

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

      {/* Leaderboard tabs */}
      {canViewScores && (
      <div className="flex gap-1 mb-5">
        <button
          onClick={() => setLeaderboardTab('parse')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-all cursor-pointer border ${
            leaderboardTab === 'parse'
              ? 'border-accent-gold bg-accent-gold/10 text-accent-gold'
              : 'border-border-default bg-bg-surface text-text-secondary hover:border-border-hover'
          }`}
        >
          Parses
        </button>
        <button
          onClick={() => setLeaderboardTab('score')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-all cursor-pointer border ${
            leaderboardTab === 'score'
              ? 'border-accent-gold bg-accent-gold/10 text-accent-gold'
              : 'border-border-default bg-bg-surface text-text-secondary hover:border-border-hover'
          }`}
        >
          Performance Score
        </button>
      </div>
      )}

      {/* MVP of the Week */}
      {canViewScores && leaderboardTab === 'score' && mvp && (
        <div className="mb-6 p-4 bg-gradient-to-r from-accent-gold/10 to-transparent border border-accent-gold/30 rounded-xl">
          <div className="flex items-center gap-1.5 mb-2">
            <svg className="w-5 h-5 text-accent-gold" fill="currentColor" viewBox="0 0 20 20">
              <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
            </svg>
            <span className="text-xs font-semibold text-accent-gold uppercase tracking-wider">MVP of the Week</span>
          </div>
          <div className="flex items-center gap-3">
            <ClassIcon className={mvp.class_name} name={mvp.name} size={28} />
            <div>
              <span className="text-sm text-text-secondary capitalize">{mvp.spec?.split(':').pop()}</span>
              <span className="text-sm text-text-muted ml-2">Score: <strong className="text-accent-gold">{mvp.overall_score}</strong></span>
              <span className="text-sm text-text-muted ml-2">Parse: <strong className="text-text-primary">{mvp.parse_score}</strong></span>
            </div>
          </div>
        </div>
      )}

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

      {/* Role filter */}
      <div className="flex gap-1.5 mb-3 flex-wrap">
        {ROLE_FILTERS.map(rf => (
          <button
            key={rf.key}
            onClick={() => setRoleFilter(rf.key)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all cursor-pointer border ${
              roleFilter === rf.key
                ? 'border-accent-gold bg-accent-gold/10 text-accent-gold'
                : 'border-border-default bg-bg-surface text-text-secondary hover:border-border-hover'
            }`}
          >
            {rf.label}
          </button>
        ))}
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

      {/* Guild Trend Chart */}
      {guildTrends && guildTrends.length > 1 && (
        <div className="bg-bg-surface border border-border-default rounded-xl p-4 mb-5">
          <h2 className="text-sm font-semibold text-text-primary mb-3">Guild Trends</h2>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={guildTrends.map(p => ({ ...p, date: new Date(p.date).toLocaleDateString() }))}>
              <CartesianGrid stroke={CHART_DEFAULTS.gridStroke} strokeDasharray="3 3" />
              <XAxis dataKey="date" tick={CHART_DEFAULTS.tick} axisLine={CHART_DEFAULTS.axisLine} />
              <YAxis tick={CHART_DEFAULTS.tick} axisLine={CHART_DEFAULTS.axisLine} domain={[0, 100]} />
              <Tooltip contentStyle={{ backgroundColor: CHART_COLORS.bg, border: `1px solid ${CHART_COLORS.grid}`, borderRadius: 8 }} />
              <Legend />
              <Line type="monotone" dataKey="avg_parse" name="Avg Parse" stroke={CHART_COLORS.info} strokeWidth={2} dot={{ r: 3 }} />
              {canViewScores && <Line type="monotone" dataKey="avg_score" name="Avg Score" stroke={CHART_COLORS.gold} strokeWidth={2} dot={{ r: 3 }} />}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Table */}
      <div className="bg-bg-surface border border-border-default rounded-xl overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border-default">
              <SortHeader label="Rank" field="rank" />
              <th className="p-3 text-left text-xs font-semibold text-text-muted uppercase tracking-wider">Player</th>
              <th className="p-3 text-left text-xs font-semibold text-text-muted uppercase tracking-wider hidden sm:table-cell">Spec</th>
              {canViewScores && leaderboardTab === 'score' && <SortHeader label="Score" field="avg_score" />}
              <SortHeader label="Avg Parse" field="avg_parse" />
              <SortHeader label="Fights" field="fight_count" />
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <SkeletonTable rows={10} cols={leaderboardTab === 'score' ? 6 : 5} />
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
                      <ClassIcon className={entry.class_name} name={entry.name} spec={entry.spec} />
                    </Link>
                  </td>
                  <td className="p-3 text-sm text-text-secondary capitalize hidden sm:table-cell">{entry.spec ? `${getSpecLabel(entry.spec)} ${entry.class_name}` : entry.class_name}</td>
                  {canViewScores && leaderboardTab === 'score' && (
                    <td className="p-3 text-sm font-semibold text-accent-gold tabular-nums">{entry.avg_score}</td>
                  )}
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
