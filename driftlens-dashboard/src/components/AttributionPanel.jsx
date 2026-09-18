const CONFIDENCE_STYLES = {
  high: "bg-emerald-500/20 text-emerald-400 border-emerald-500/40",
  medium: "bg-amber-500/20 text-amber-400 border-amber-500/40",
  none: "bg-gray-500/20 text-gray-400 border-gray-500/40",
};

function formatIST(isoTimestamp) {
  const date = new Date(isoTimestamp);
  return date.toLocaleString("en-IN", {
    timeZone: "Asia/Kolkata",
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
  }) + " IST";
}

export default function AttributionPanel({ attribution }) {
  if (!attribution) {
    return (
      <div className="p-4 bg-gray-800 rounded border border-gray-700">
        <span className={`inline-block px-2 py-1 rounded text-xs font-semibold uppercase border ${CONFIDENCE_STYLES.none}`}>
          none
        </span>
        <p className="mt-2 text-gray-400 text-sm">
          No attributable event found.
        </p>
      </div>
    );
  }

  const style = CONFIDENCE_STYLES[attribution.confidence] ?? CONFIDENCE_STYLES.none;

  return (
    <div className="p-4 bg-gray-800 rounded border border-gray-700 space-y-3">
      <span className={`inline-block px-2 py-1 rounded text-xs font-semibold uppercase border ${style}`}>
        {attribution.confidence} confidence
      </span>

      <p className="text-gray-100 text-sm leading-relaxed">
        {attribution.narrative}
      </p>

      <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs text-gray-400 pt-2 border-t border-gray-700">
        <div>
          <span className="text-gray-500">Principal</span>
          <p className="text-gray-200 font-mono break-all">{attribution.principal_arn}</p>
        </div>
        <div>
          <span className="text-gray-500">Event</span>
          <p className="text-gray-200 font-mono">{attribution.event_name}</p>
        </div>
        <div>
          <span className="text-gray-500">Time</span>
          <p className="text-gray-200 font-mono">{formatIST(attribution.event_time)}</p>
        </div>
        <div>
          <span className="text-gray-500">Source IP</span>
          <p className="text-gray-200 font-mono">{attribution.source_ip}</p>
        </div>
      </div>
    </div>
  );
}