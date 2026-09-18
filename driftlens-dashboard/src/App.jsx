import { useState } from "react";
import DriftTable from "./components/DriftTable";
import AttributionPanel from "./components/AttributionPanel";
import comparisonData from "./data/comparison_response_sample.json";

function App() {
  const [selectedDrift, setSelectedDrift] = useState(null);

  return (
    <div className="min-h-screen bg-gray-900 text-white p-8">
      <h1 className="text-2xl font-bold mb-1">DriftLens</h1>
      <p className="text-gray-400 mb-6">
        {comparisonData.data.pair} — {comparisonData.data.summary.critical} critical,{" "}
        {comparisonData.data.summary.suspicious} suspicious,{" "}
        {comparisonData.data.summary.expected} expected
      </p>

      <DriftTable comparison={comparisonData.data} onRowClick={setSelectedDrift} />

      {selectedDrift && (
        <div className="mt-6">
          <h2 className="text-lg font-semibold mb-2">
            {selectedDrift.key}
          </h2>
          <AttributionPanel attribution={selectedDrift.attribution} />
        </div>
      )}
    </div>
  );
}

export default App;