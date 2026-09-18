import SeverityBadge from "./SeverityBadge";

const SEVERITY_ORDER = { critical: 0, suspicious: 1, expected: 2 };

export default function DriftTable({ comparison, onRowClick }) {
  const drifts = [...comparison.drifts].sort(
    (a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity]
  );

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-700">
      <table className="min-w-full text-sm text-left text-gray-200">
        <thead className="bg-gray-800 text-gray-400 uppercase text-xs">
          <tr>
            <th className="px-4 py-3">Severity</th>
            <th className="px-4 py-3">Key</th>
            <th className="px-4 py-3">Staging</th>
            <th className="px-4 py-3">Production</th>
            <th className="px-4 py-3">Rule</th>
          </tr>
        </thead>
        <tbody>
          {drifts.map((d) => (
            <tr
              key={d.drift_id}
              onClick={() => onRowClick?.(d)}
              className="border-t border-gray-700 hover:bg-gray-800 cursor-pointer transition-colors"
            >
              <td className="px-4 py-3"><SeverityBadge severity={d.severity} /></td>
              <td className="px-4 py-3 font-mono text-xs">{d.key}</td>
              <td className="px-4 py-3 font-mono text-xs">{String(d.value_a)}</td>
              <td className="px-4 py-3 font-mono text-xs">{String(d.value_b)}</td>
              <td className="px-4 py-3 text-gray-400 text-xs">{d.rule_id}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}