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
