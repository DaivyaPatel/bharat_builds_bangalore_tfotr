import { useState } from "react";
import DriftTable from "./components/DriftTable";
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
        <pre className="mt-6 p-4 bg-gray-800 rounded text-xs overflow-x-auto">
          {JSON.stringify(selectedDrift, null, 2)}
        </pre>
      )}
    </div>
  );
}

export default App;