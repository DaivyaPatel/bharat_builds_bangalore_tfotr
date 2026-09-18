const SEVERITY_STYLES = {
  critical: "bg-red-500/20 text-red-400 border-red-500/40",
  suspicious: "bg-amber-500/20 text-amber-400 border-amber-500/40",
  expected: "bg-emerald-500/20 text-emerald-400 border-emerald-500/40",
};

export default function SeverityBadge({ severity }) {
  const style = SEVERITY_STYLES[severity] ?? "bg-gray-500/20 text-gray-400 border-gray-500/40";
  return (
    <span className={`inline-block px-2 py-1 rounded text-xs font-semibold uppercase border ${style}`}>
      {severity}
    </span>
  );
}