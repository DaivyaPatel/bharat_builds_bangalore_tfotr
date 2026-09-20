import { useState } from "react";
import DriftTable from "./components/DriftTable";
import AttributionPanel from "./components/AttributionPanel";
import Timeline from "./components/Timeline";
import comparisonData from "./data/comparison_response_sample.json";
import snapshotsData from "./data/snapshots_sample.json";

function App() {
  const [selectedDrift, setSelectedDrift] = useState(null);
  const [viewMode, setViewMode] = useState("current"); // "current" | "time-travel"
  const [selectedSnapshot, setSelectedSnapshot] = useState(null);

  const handleCompareClick = (snapshot) => {
    setSelectedSnapshot(snapshot);
    setViewMode("time-travel");
    setSelectedDrift(null);
  };

  const handleBackToCurrent = () => {
    setViewMode("current");
    setSelectedSnapshot(null);
    setSelectedDrift(null);
  };

  return (
    <div className="min-h-screen bg-gray-900 text-white p-8">
      <h1 className="text-2xl font-bold mb-1">DriftLens</h1>
      <p className="text-gray-400 mb-6">
        {comparisonData.data.pair} — {comparisonData.data.summary.critical} critical,{" "}
        {comparisonData.data.summary.suspicious} suspicious,{" "}
        {comparisonData.data.summary.expected} expected
      </p>

      {viewMode === "time-travel" && (
        <div className="mb-4 p-3 bg-emerald-900/30 border border-emerald-700 rounded flex items-center justify-between">
          <span className="text-sm text-emerald-300">
            Time-travel: comparing production against {selectedSnapshot?.captured_at}
          </span>
          <button
            onClick={handleBackToCurrent}
            className="text-xs px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded"
          >
            ← Back to current
          </button>
        </div>
      )}

      <DriftTable comparison={comparisonData.data} onRowClick={setSelectedDrift} />

      {selectedDrift && (
        <div className="mt-6">
          <h2 className="text-lg font-semibold mb-2">{selectedDrift.key}</h2>
          <AttributionPanel attribution={selectedDrift.attribution} />
        </div>
      )}

      <Timeline snapshots={snapshotsData} onCompareClick={handleCompareClick} />
    </div>
  );
}

export default App;