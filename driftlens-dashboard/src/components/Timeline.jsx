export default function Timeline({ snapshots, onCompareClick }) {
  return (
    <div className="mt-8">
      <h2 className="text-lg font-semibold mb-3">Snapshot Timeline — production</h2>
      <div className="flex gap-3 overflow-x-auto pb-2">
        {snapshots.map((snap) => (
          <button
            key={snap.snapshot_id}
            onClick={() => onCompareClick(snap)}
            className="flex-shrink-0 px-4 py-3 bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded text-left transition-colors"
          >
            <p className="text-xs text-gray-500">Snapshot</p>
            <p className="text-sm font-mono text-gray-200">{snap.captured_at}</p>
            <p className="text-xs text-emerald-400 mt-1">Compare against now →</p>
          </button>
        ))}
      </div>
    </div>
  );
}